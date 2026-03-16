"""Tests for experiment tracking, fingerprinting, and run comparison."""

import json
import pytest
from unittest.mock import patch

from pulsar_ai.tracking import (
    RunTracker,
    capture_environment,
    fingerprint_dataset,
    list_runs,
    get_run,
    compare_runs,
    track_experiment,
    _flatten_dict,
)


@pytest.fixture
def runs_dir(tmp_path):
    """Override RUNS_DIR to temp directory."""
    with patch("pulsar_ai.tracking.RUNS_DIR", tmp_path):
        yield tmp_path


@pytest.fixture
def sample_config():
    return {
        "model": {"name": "qwen2.5-3b"},
        "training": {"learning_rate": 2e-4, "epochs": 3},
        "dataset": {"path": "data/train.csv"},
    }


class TestRunTracker:
    """Test RunTracker local backend."""

    def test_create_tracker(self, sample_config, runs_dir):
        tracker = RunTracker(
            backend="local",
            project="test",
            run_name="test-run",
            config=sample_config,
        )
        assert tracker.run_id
        assert tracker.backend == "local"

    def test_log_metrics(self, runs_dir):
        tracker = RunTracker(backend="local", run_name="m-test")
        tracker.log_metrics({"loss": 0.5, "accuracy": 0.8}, step=1)
        tracker.log_metrics({"loss": 0.3, "accuracy": 0.9}, step=2)
        assert len(tracker.metrics_history) == 2
        assert tracker.metrics_history[0]["loss"] == 0.5

    def test_log_artifact(self, runs_dir):
        tracker = RunTracker(backend="local", run_name="a-test")
        tracker.log_artifact("model", "/path/to/model")
        assert tracker.artifacts["model"] == "/path/to/model"

    def test_finish_saves_json(self, sample_config, runs_dir):
        tracker = RunTracker(
            backend="local",
            project="test",
            run_name="save-test",
            config=sample_config,
        )
        tracker.log_metrics({"loss": 0.1})
        summary = tracker.finish(status="completed", results={"training_loss": 0.1})

        assert summary["status"] == "completed"
        assert summary["results"]["training_loss"] == 0.1

        # Check file was saved
        files = list(runs_dir.glob("*.json"))
        assert len(files) == 1

        with open(files[0]) as f:
            saved = json.load(f)
        assert saved["name"] == "save-test"
        assert saved["status"] == "completed"

    def test_finish_failed_status(self, runs_dir):
        tracker = RunTracker(backend="local", run_name="fail-test")
        summary = tracker.finish(status="failed", results={"error": "OOM"})
        assert summary["status"] == "failed"

    def test_none_backend(self, runs_dir):
        tracker = RunTracker(backend="none", run_name="none-test")
        tracker.log_metrics({"loss": 0.5})
        tracker.finish()
        # Should not save anything for 'none' backend
        files = list(runs_dir.glob("*.json"))
        assert len(files) == 0

    def test_clearml_fallback_on_import_error(self, runs_dir):
        """ClearML backend falls back to local when not installed."""
        with patch.dict("sys.modules", {"clearml": None}):
            tracker = RunTracker(backend="clearml", run_name="cm-test")
            assert tracker.backend == "local"

    def test_wandb_fallback_on_import_error(self, runs_dir):
        """W&B backend falls back to local when not installed."""
        with patch.dict("sys.modules", {"wandb": None}):
            tracker = RunTracker(backend="wandb", run_name="wb-test")
            assert tracker.backend == "local"

    def test_set_tags(self, runs_dir):
        tracker = RunTracker(backend="local", run_name="tag-test")
        tracker.set_tags(["sft", "production"])
        assert tracker.tags == ["sft", "production"]

    def test_environment_in_summary(self, runs_dir):
        tracker = RunTracker(backend="local", run_name="env-test")
        summary = tracker.finish()
        assert "environment" in summary
        assert "python_version" in summary["environment"]
        assert "platform" in summary["environment"]


class TestFingerprint:
    """Test dataset fingerprinting."""

    def test_fingerprint_file(self, tmp_path):
        data_file = tmp_path / "data.csv"
        data_file.write_text("text,label\nhello,pos\nworld,neg\n")

        fp = fingerprint_dataset(str(data_file))
        assert isinstance(fp, str)
        assert len(fp) == 64  # SHA256 hex length

    def test_fingerprint_same_content(self, tmp_path):
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        content = "text,label\nhello,pos\n"
        f1.write_text(content)
        f2.write_text(content)

        assert fingerprint_dataset(str(f1)) == fingerprint_dataset(str(f2))

    def test_fingerprint_different_content(self, tmp_path):
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        f1.write_text("text\nhello\n")
        f2.write_text("text\nworld\n")

        assert fingerprint_dataset(str(f1)) != fingerprint_dataset(str(f2))

    def test_fingerprint_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            fingerprint_dataset("/nonexistent/file.csv")

    def test_fingerprint_md5(self, tmp_path):
        data_file = tmp_path / "data.csv"
        data_file.write_text("test data")

        fp = fingerprint_dataset(str(data_file), algorithm="md5")
        assert len(fp) == 32  # MD5 hex length


class TestListAndGetRuns:
    """Test run listing and retrieval."""

    def test_list_empty(self, runs_dir):
        assert list_runs() == []

    def test_list_and_get(self, runs_dir):
        tracker = RunTracker(backend="local", project="proj1", run_name="r1")
        tracker.finish(status="completed", results={"loss": 0.1})

        tracker2 = RunTracker(backend="local", project="proj1", run_name="r2")
        tracker2.finish(status="failed", results={"error": "OOM"})

        all_runs = list_runs()
        assert len(all_runs) == 2

        completed = list_runs(status="completed")
        assert len(completed) == 1

        run = get_run(all_runs[0]["run_id"])
        assert run is not None

    def test_get_nonexistent(self, runs_dir):
        assert get_run("nonexistent") is None

    def test_list_with_project_filter(self, runs_dir):
        t1 = RunTracker(backend="local", project="proj-a", run_name="r1")
        t1.finish()
        t2 = RunTracker(backend="local", project="proj-b", run_name="r2")
        t2.finish()

        assert len(list_runs(project="proj-a")) == 1
        assert len(list_runs(project="proj-b")) == 1


class TestCompareRuns:
    """Test run comparison."""

    def test_compare_two_runs(self, runs_dir):
        t1 = RunTracker(
            backend="local",
            run_name="r1",
            config={"training": {"learning_rate": 1e-4, "epochs": 3}},
        )
        t1.finish(status="completed", results={"training_loss": 0.2})

        t2 = RunTracker(
            backend="local",
            run_name="r2",
            config={"training": {"learning_rate": 5e-5, "epochs": 5}},
        )
        t2.finish(status="completed", results={"training_loss": 0.15})

        runs = list_runs()
        result = compare_runs([r["run_id"] for r in runs])

        assert "config_diff" in result
        assert "metrics_comparison" in result
        assert len(result["run_ids"]) == 2

    def test_compare_insufficient_runs(self, runs_dir):
        t = RunTracker(backend="local", run_name="only-one")
        t.finish()

        runs = list_runs()
        result = compare_runs([runs[0]["run_id"]])
        assert "error" in result


class TestTrackExperiment:
    """Test track_experiment context manager."""

    def test_context_manager_success(self, sample_config, runs_dir):
        with track_experiment(sample_config, task="sft") as tracker:
            tracker.log_metrics({"loss": 0.1})

        runs = list_runs()
        assert len(runs) == 1
        assert runs[0]["status"] == "completed"

    def test_context_manager_failure(self, sample_config, runs_dir):
        with pytest.raises(ValueError):
            with track_experiment(sample_config, task="sft") as _tracker:
                raise ValueError("Training error")

        runs = list_runs()
        assert len(runs) == 1
        assert runs[0]["status"] == "failed"


class TestCaptureEnvironment:
    """Test environment capture."""

    def test_basic_capture(self):
        env = capture_environment()
        assert "python_version" in env
        assert "platform" in env
        assert "machine" in env
        assert "packages" in env


class TestFlattenDict:
    """Test _flatten_dict utility."""

    def test_simple(self):
        assert _flatten_dict({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_nested(self):
        result = _flatten_dict({"a": {"b": 1, "c": {"d": 2}}})
        assert result == {"a.b": 1, "a.c.d": 2}

    def test_empty(self):
        assert _flatten_dict({}) == {}
