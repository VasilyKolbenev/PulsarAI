"""Tests for pipeline executor and tracker."""

import pytest
from unittest.mock import patch

from pulsar_ai.pipeline.executor import PipelineExecutor
from pulsar_ai.pipeline.tracker import PipelineTracker


@pytest.fixture
def tracker(tmp_path):
    """Create a tracker with temp runs dir."""
    return PipelineTracker("test-pipeline", runs_dir=tmp_path)


@pytest.fixture
def simple_pipeline():
    """Single-step pipeline config."""
    return {
        "pipeline": {"name": "simple"},
        "steps": [
            {
                "name": "step1",
                "type": "training",
                "config": {"task": "sft", "model": {"name": "test"}},
            }
        ],
    }


@pytest.fixture
def multi_step_pipeline():
    """Multi-step pipeline with dependencies."""
    return {
        "pipeline": {"name": "multi"},
        "steps": [
            {
                "name": "train",
                "type": "training",
                "config": {"task": "sft"},
            },
            {
                "name": "eval",
                "type": "evaluation",
                "depends_on": ["train"],
                "config": {
                    "model_path": "${train.adapter_dir}",
                    "test_data_path": "data/test.csv",
                },
            },
            {
                "name": "export",
                "type": "export",
                "depends_on": ["train"],
                "config": {
                    "model_path": "${train.adapter_dir}",
                    "export": {"format": "gguf"},
                },
            },
        ],
    }


class TestPipelineExecutor:
    """Test PipelineExecutor."""

    def test_resolve_order_simple(self, simple_pipeline, tracker):
        """Test topological sort with no dependencies."""
        executor = PipelineExecutor(simple_pipeline, tracker=tracker)
        order = executor._resolve_order()
        assert order == ["step1"]

    def test_resolve_order_multi(self, multi_step_pipeline, tracker):
        """Test topological sort respects dependencies."""
        executor = PipelineExecutor(multi_step_pipeline, tracker=tracker)
        order = executor._resolve_order()
        assert order[0] == "train"
        assert set(order[1:]) == {"eval", "export"}

    def test_resolve_order_circular_raises(self, tracker):
        """Test circular dependency detection."""
        config = {
            "pipeline": {"name": "circular"},
            "steps": [
                {"name": "a", "type": "training", "depends_on": ["b"], "config": {}},
                {"name": "b", "type": "training", "depends_on": ["a"], "config": {}},
            ],
        }
        executor = PipelineExecutor(config, tracker=tracker)
        with pytest.raises(ValueError, match="Circular"):
            executor._resolve_order()

    def test_resolve_order_missing_dep_raises(self, tracker):
        """Test missing dependency detection."""
        config = {
            "pipeline": {"name": "bad"},
            "steps": [
                {"name": "a", "type": "training", "depends_on": ["x"], "config": {}},
            ],
        }
        executor = PipelineExecutor(config, tracker=tracker)
        with pytest.raises(ValueError, match="unknown step"):
            executor._resolve_order()

    def test_variable_substitution(self, tracker):
        """Test ${step.key} substitution."""
        config = {
            "pipeline": {"name": "vars"},
            "steps": [
                {"name": "step1", "type": "training", "config": {}},
            ],
        }
        executor = PipelineExecutor(config, tracker=tracker)
        executor._outputs["step1"] = {"adapter_dir": "/path/to/adapter"}

        resolved = executor._resolve_vars({"model_path": "${step1.adapter_dir}"})
        assert resolved["model_path"] == "/path/to/adapter"

    def test_nested_variable_substitution(self, tracker):
        """Test variable substitution in nested config."""
        config = {
            "pipeline": {"name": "nested"},
            "steps": [{"name": "s1", "type": "training", "config": {}}],
        }
        executor = PipelineExecutor(config, tracker=tracker)
        executor._outputs["s1"] = {"dir": "/out"}

        resolved = executor._resolve_vars(
            {
                "a": {"b": "${s1.dir}/model"},
                "c": ["${s1.dir}/data"],
            }
        )
        assert resolved["a"]["b"] == "/out/model"
        assert resolved["c"][0] == "/out/data"

    @patch("pulsar_ai.pipeline.executor.dispatch_step")
    def test_run_success(self, mock_dispatch, simple_pipeline, tracker):
        """Test successful pipeline run."""
        mock_dispatch.return_value = {"adapter_dir": "/path", "training_loss": 0.1}

        executor = PipelineExecutor(simple_pipeline, tracker=tracker)
        outputs = executor.run()

        assert "step1" in outputs
        assert outputs["step1"]["adapter_dir"] == "/path"
        mock_dispatch.assert_called_once()

    @patch("pulsar_ai.pipeline.executor.dispatch_step")
    def test_run_failure(self, mock_dispatch, simple_pipeline, tracker):
        """Test pipeline failure propagation."""
        mock_dispatch.side_effect = RuntimeError("GPU OOM")

        executor = PipelineExecutor(simple_pipeline, tracker=tracker)
        with pytest.raises(RuntimeError, match="GPU OOM"):
            executor.run()

    @patch("pulsar_ai.pipeline.executor.dispatch_step")
    def test_run_multi_step_with_vars(self, mock_dispatch, multi_step_pipeline, tracker):
        """Test multi-step pipeline with variable resolution."""
        mock_dispatch.side_effect = [
            {"adapter_dir": "/out/lora", "training_loss": 0.2},
            {"accuracy": 0.95},
            {"output_path": "/out/model.gguf"},
        ]

        executor = PipelineExecutor(multi_step_pipeline, tracker=tracker)
        outputs = executor.run()

        assert len(outputs) == 3
        # Verify variable was resolved in the eval step
        calls = mock_dispatch.call_args_list
        eval_config = calls[1][1]["config"]
        assert eval_config["model_path"] == "/out/lora"


class TestPipelineTracker:
    """Test PipelineTracker."""

    def test_start_run(self, tracker):
        """Test starting a pipeline run."""
        run_id = tracker.start_run(["step1", "step2"])
        assert run_id is not None
        manifest = tracker.get_manifest()
        assert manifest["status"] == "running"
        assert "step1" in manifest["steps"]
        assert "step2" in manifest["steps"]

    def test_update_step(self, tracker):
        """Test updating step status."""
        tracker.start_run(["step1"])
        tracker.update_step("step1", "running")
        assert tracker.get_manifest()["steps"]["step1"]["status"] == "running"

        tracker.update_step("step1", "completed", result={"loss": 0.1}, duration_s=5.0)
        step = tracker.get_manifest()["steps"]["step1"]
        assert step["status"] == "completed"
        assert step["duration_s"] == 5.0

    def test_finish_run(self, tracker):
        """Test finishing a pipeline run."""
        tracker.start_run(["s1"])
        tracker.finish_run()
        manifest = tracker.get_manifest()
        assert manifest["status"] == "completed"
        assert manifest["completed_at"] is not None

    def test_fail_run(self, tracker):
        """Test failing a pipeline run."""
        tracker.start_run(["s1"])
        tracker.fail_run("something broke")
        manifest = tracker.get_manifest()
        assert manifest["status"] == "failed"
        assert manifest["error"] == "something broke"

    def test_list_runs(self, tmp_path):
        """Test listing all pipeline runs."""
        t1 = PipelineTracker("pipe1", runs_dir=tmp_path)
        t1.start_run(["s1"])
        t1.finish_run()

        t2 = PipelineTracker("pipe2", runs_dir=tmp_path)
        t2.start_run(["s2"])
        t2.finish_run()

        all_runs = PipelineTracker.list_runs(runs_dir=tmp_path)
        assert len(all_runs) == 2

        pipe1_runs = PipelineTracker.list_runs(pipeline_name="pipe1", runs_dir=tmp_path)
        assert len(pipe1_runs) == 1

    def test_persistence(self, tmp_path):
        """Test manifest persists to disk."""
        tracker = PipelineTracker("persist", runs_dir=tmp_path)
        tracker.start_run(["step1"])
        tracker.update_step("step1", "completed")
        tracker.finish_run()

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
