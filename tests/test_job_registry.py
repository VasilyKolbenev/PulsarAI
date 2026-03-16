"""Tests for JobRegistry durable job tracking."""

import pytest
from pulsar_ai.storage.database import Database
from pulsar_ai.storage.job_registry import JobRegistry


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def registry(db):
    return JobRegistry(db=db)


def test_create_job(registry):
    job = registry.create(job_type="sft", config={"lr": 2e-5})
    assert job["status"] == "queued"
    assert job["job_type"] == "sft"
    assert job["config"]["lr"] == 2e-5
    assert len(job["id"]) == 8


def test_create_with_experiment_id(registry):
    job = registry.create(job_type="eval", experiment_id="exp123")
    assert job["experiment_id"] == "exp123"


def test_get_job(registry):
    job = registry.create(job_type="sft")
    got = registry.get(job["id"])
    assert got is not None
    assert got["id"] == job["id"]


def test_get_nonexistent(registry):
    assert registry.get("nope") is None


def test_list_all(registry):
    registry.create(job_type="sft")
    registry.create(job_type="eval")
    jobs = registry.list_all()
    assert len(jobs) == 2


def test_list_by_status(registry):
    j1 = registry.create(job_type="sft")
    registry.create(job_type="eval")
    registry.update_status(j1["id"], "running")
    assert len(registry.list_all(status="running")) == 1
    assert len(registry.list_all(status="queued")) == 1


def test_update_status_running(registry):
    job = registry.create(job_type="sft")
    assert registry.update_status(job["id"], "running", pid=1234) is True
    updated = registry.get(job["id"])
    assert updated["status"] == "running"
    assert updated["pid"] == 1234


def test_update_status_completed(registry):
    job = registry.create(job_type="sft")
    registry.update_status(job["id"], "running")
    registry.update_status(job["id"], "completed")
    updated = registry.get(job["id"])
    assert updated["status"] == "completed"
    assert updated["completed_at"] is not None


def test_update_status_failed_with_error(registry):
    job = registry.create(job_type="sft")
    registry.update_status(job["id"], "failed", error_message="OOM on GPU 0")
    updated = registry.get(job["id"])
    assert updated["status"] == "failed"
    assert updated["error_message"] == "OOM on GPU 0"
    assert updated["completed_at"] is not None


def test_update_status_invalid(registry):
    job = registry.create(job_type="sft")
    with pytest.raises(ValueError, match="Invalid status"):
        registry.update_status(job["id"], "invalid_status")


def test_update_nonexistent(registry):
    assert registry.update_status("nope", "running") is False


def test_delete_job(registry):
    job = registry.create(job_type="sft")
    assert registry.delete(job["id"]) is True
    assert registry.get(job["id"]) is None


def test_delete_nonexistent(registry):
    assert registry.delete("nope") is False


def test_get_active_jobs(registry):
    j1 = registry.create(job_type="sft")
    j2 = registry.create(job_type="eval")
    j3 = registry.create(job_type="pipeline")
    registry.update_status(j2["id"], "completed")
    active = registry.get_active_jobs()
    active_ids = {j["id"] for j in active}
    assert j1["id"] in active_ids
    assert j3["id"] in active_ids
    assert j2["id"] not in active_ids
