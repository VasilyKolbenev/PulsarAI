"""Tests for pipeline callback and JobRegistry integration."""

import pytest
from unittest.mock import MagicMock, patch

from pulsar_ai.pipeline.executor import PipelineExecutor, NullCallback
from pulsar_ai.pipeline.job_callback import JobRegistryCallback
from pulsar_ai.storage.database import Database
from pulsar_ai.storage.job_registry import JobRegistry


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def registry(db):
    return JobRegistry(db=db)


SIMPLE_CONFIG = {
    "pipeline": {"name": "test-pipe"},
    "steps": [
        {"name": "step_a", "type": "data", "config": {}},
        {"name": "step_b", "type": "model", "config": {}, "depends_on": ["step_a"]},
    ],
}


class TestNullCallback:
    def test_all_methods_are_noop(self):
        cb = NullCallback()
        cb.on_pipeline_start("test", ["a", "b"])
        cb.on_step_start("a", "data")
        cb.on_step_complete("a", {"ok": True}, 1.0)
        cb.on_step_skip("a")
        cb.on_step_fail("a", "boom")
        cb.on_pipeline_complete({"a": {}})
        cb.on_pipeline_fail("a", "boom")


class TestJobRegistryCallback:
    def test_pipeline_lifecycle_creates_job(self, registry):
        cb = JobRegistryCallback(registry)

        cb.on_pipeline_start("my-pipe", ["a", "b"])
        assert cb.job_id is not None

        job = registry.get(cb.job_id)
        assert job["status"] == "running"
        assert job["job_type"] == "pipeline"
        assert job["config"]["pipeline_name"] == "my-pipe"

    def test_pipeline_complete_marks_job(self, registry):
        cb = JobRegistryCallback(registry)
        cb.on_pipeline_start("pipe", ["a"])
        cb.on_pipeline_complete({"a": {"result": "ok"}})

        job = registry.get(cb.job_id)
        assert job["status"] == "completed"

    def test_pipeline_fail_marks_job(self, registry):
        cb = JobRegistryCallback(registry)
        cb.on_pipeline_start("pipe", ["a"])
        cb.on_pipeline_fail("step_a", "OOM error")

        job = registry.get(cb.job_id)
        assert job["status"] == "failed"
        assert "OOM error" in job["error_message"]

    def test_callback_with_experiment_id(self, registry):
        cb = JobRegistryCallback(registry, experiment_id="exp42")
        cb.on_pipeline_start("pipe", ["a"])

        job = registry.get(cb.job_id)
        assert job["experiment_id"] == "exp42"


class TestExecutorWithCallback:
    @patch("pulsar_ai.pipeline.executor.dispatch_step")
    def test_callback_receives_events(self, mock_dispatch):
        mock_dispatch.return_value = {"output": "ok"}
        cb = MagicMock()

        executor = PipelineExecutor(SIMPLE_CONFIG, callback=cb)
        executor.run()

        cb.on_pipeline_start.assert_called_once_with("test-pipe", ["step_a", "step_b"])
        assert cb.on_step_start.call_count == 2
        assert cb.on_step_complete.call_count == 2
        cb.on_pipeline_complete.assert_called_once()
        cb.on_pipeline_fail.assert_not_called()

    @patch("pulsar_ai.pipeline.executor.dispatch_step")
    def test_callback_on_failure(self, mock_dispatch):
        mock_dispatch.side_effect = RuntimeError("GPU OOM")
        cb = MagicMock()

        executor = PipelineExecutor(SIMPLE_CONFIG, callback=cb)
        with pytest.raises(RuntimeError):
            executor.run()

        cb.on_step_fail.assert_called_once()
        cb.on_pipeline_fail.assert_called_once()
        cb.on_pipeline_complete.assert_not_called()

    @patch("pulsar_ai.pipeline.executor.dispatch_step")
    def test_executor_works_without_callback(self, mock_dispatch):
        mock_dispatch.return_value = {"ok": True}
        executor = PipelineExecutor(SIMPLE_CONFIG)
        result = executor.run()
        assert "step_a" in result
        assert "step_b" in result
