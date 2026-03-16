"""Tests for ExperimentStore CRUD operations (SQLite backend)."""

import json
import threading
from pathlib import Path

import pytest

from pulsar_ai.storage.database import Database, reset_database
from pulsar_ai.ui.experiment_store import ExperimentStore


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure the module-level DB singleton is reset between tests."""
    reset_database()
    yield
    reset_database()


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a fresh Database in a temp directory."""
    return Database(db_path=tmp_path / "test.db")


@pytest.fixture
def store(db: Database) -> ExperimentStore:
    """Create a fresh ExperimentStore backed by temp SQLite."""
    return ExperimentStore(db=db)


# ── Basic CRUD ───────────────────────────────────────────────────────────


def test_create_experiment(store: ExperimentStore) -> None:
    """Test creating a new experiment."""
    exp_id = store.create("test-exp", {"model": {"name": "test"}}, task="sft")
    assert len(exp_id) == 8
    exp = store.get(exp_id)
    assert exp is not None
    assert exp["name"] == "test-exp"
    assert exp["status"] == "queued"
    assert exp["task"] == "sft"
    assert exp["model"] == "test"


def test_create_experiment_empty_config(store: ExperimentStore) -> None:
    """Test creating with empty config doesn't crash."""
    exp_id = store.create("empty", {})
    exp = store.get(exp_id)
    assert exp is not None
    assert exp["config"] == {}


def test_update_status(store: ExperimentStore) -> None:
    """Test updating experiment status."""
    exp_id = store.create("test", {})
    store.update_status(exp_id, "running")
    assert store.get(exp_id)["status"] == "running"

    store.update_status(exp_id, "completed")
    exp = store.get(exp_id)
    assert exp["status"] == "completed"
    assert exp["completed_at"] is not None


def test_update_status_running_no_completed_at(store: ExperimentStore) -> None:
    """Transition to 'running' must not set completed_at."""
    exp_id = store.create("test", {})
    store.update_status(exp_id, "running")
    exp = store.get(exp_id)
    assert exp["completed_at"] is None


def test_add_metrics(store: ExperimentStore) -> None:
    """Test appending training metrics."""
    exp_id = store.create("test", {})
    store.add_metrics(exp_id, {"step": 10, "loss": 0.5})
    store.add_metrics(exp_id, {"step": 20, "loss": 0.3})

    exp = store.get(exp_id)
    assert len(exp["training_history"]) == 2
    assert exp["final_loss"] == 0.3


def test_add_metrics_no_loss(store: ExperimentStore) -> None:
    """Metrics without 'loss' key must not reset final_loss."""
    exp_id = store.create("test", {})
    store.add_metrics(exp_id, {"step": 1, "loss": 0.5})
    store.add_metrics(exp_id, {"step": 2, "accuracy": 0.9})

    exp = store.get(exp_id)
    assert exp["final_loss"] == 0.5
    assert len(exp["training_history"]) == 2


def test_set_artifacts(store: ExperimentStore) -> None:
    """Test storing artifact paths."""
    exp_id = store.create("test", {})
    store.set_artifacts(exp_id, {"adapter_dir": "/path/to/lora"})
    assert store.get(exp_id)["artifacts"]["adapter_dir"] == "/path/to/lora"


def test_set_eval_results(store: ExperimentStore) -> None:
    """Test storing eval results."""
    exp_id = store.create("test", {})
    store.set_eval_results(exp_id, {"accuracy": 0.95})
    assert store.get(exp_id)["eval_results"]["accuracy"] == 0.95


# ── Listing ──────────────────────────────────────────────────────────────


def test_list_all(store: ExperimentStore) -> None:
    """Test listing all experiments."""
    store.create("exp1", {})
    store.create("exp2", {})
    store.create("exp3", {})

    all_exps = store.list_all()
    assert len(all_exps) == 3


def test_list_all_filtered(store: ExperimentStore) -> None:
    """Test filtering experiments by status."""
    id1 = store.create("exp1", {})
    store.create("exp2", {})
    store.update_status(id1, "completed")

    completed = store.list_all(status="completed")
    assert len(completed) == 1
    assert completed[0]["id"] == id1


def test_list_empty(store: ExperimentStore) -> None:
    """Test listing returns empty list when no experiments."""
    assert store.list_all() == []


def test_list_all_ordered_newest_first(store: ExperimentStore) -> None:
    """Experiments should be returned newest-first."""
    id1 = store.create("first", {})
    id2 = store.create("second", {})
    id3 = store.create("third", {})

    ids = [e["id"] for e in store.list_all()]
    assert ids == [id3, id2, id1]


# ── Delete ───────────────────────────────────────────────────────────────


def test_delete_experiment(store: ExperimentStore) -> None:
    """Test deleting an experiment."""
    exp_id = store.create("test", {})
    assert store.delete(exp_id) is True
    assert store.get(exp_id) is None
    assert store.delete(exp_id) is False


def test_delete_cascades_metrics(store: ExperimentStore) -> None:
    """Deleting an experiment must also remove its metrics rows."""
    exp_id = store.create("test", {})
    store.add_metrics(exp_id, {"step": 1, "loss": 0.5})
    store.add_metrics(exp_id, {"step": 2, "loss": 0.3})

    store.delete(exp_id)

    # Verify metrics are gone.
    rows = store._db.fetch_all(
        "SELECT * FROM experiment_metrics WHERE experiment_id = ?",
        (exp_id,),
    )
    assert len(rows) == 0


# ── Get ──────────────────────────────────────────────────────────────────


def test_get_nonexistent(store: ExperimentStore) -> None:
    """Test getting a nonexistent experiment returns None."""
    assert store.get("nonexistent") is None


# ── Persistence ──────────────────────────────────────────────────────────


def test_persistence(tmp_path: Path) -> None:
    """Test that data persists across store instances."""
    db = Database(db_path=tmp_path / "persist.db")
    store1 = ExperimentStore(db=db)
    exp_id = store1.create("persistent", {"key": "value"})

    store2 = ExperimentStore(db=db)
    exp = store2.get(exp_id)
    assert exp is not None
    assert exp["name"] == "persistent"


# ── Reconcile Stale ─────────────────────────────────────────────────────


def test_reconcile_stale_running(store: ExperimentStore) -> None:
    """Stale running experiments should be marked failed."""
    exp_id = store.create("stale", {})
    store.update_status(exp_id, "running")

    # Backdate last_update_at to simulate staleness.
    store._db.execute(
        "UPDATE experiments SET last_update_at = '2020-01-01T00:00:00' WHERE id = ?",
        (exp_id,),
    )
    store._db.commit()

    reconciled = store.reconcile_stale_running(stale_after_minutes=1)
    assert reconciled == 1

    exp = store.get(exp_id)
    assert exp["status"] == "failed"
    assert "error" in exp["artifacts"]


def test_reconcile_preserves_existing_error(store: ExperimentStore) -> None:
    """If artifacts already has an error key, reconcile should keep it."""
    exp_id = store.create("stale", {})
    store.update_status(exp_id, "running")
    store.set_artifacts(exp_id, {"error": "OOM"})

    store._db.execute(
        "UPDATE experiments SET last_update_at = '2020-01-01T00:00:00' WHERE id = ?",
        (exp_id,),
    )
    store._db.commit()

    store.reconcile_stale_running(stale_after_minutes=1)
    exp = store.get(exp_id)
    assert exp["artifacts"]["error"] == "OOM"


def test_reconcile_threshold_zero(store: ExperimentStore) -> None:
    """Threshold <= 0 should be a no-op."""
    assert store.reconcile_stale_running(stale_after_minutes=0) == 0
    assert store.reconcile_stale_running(stale_after_minutes=-5) == 0


# ── JSON Migration ──────────────────────────────────────────────────────


def test_migrate_from_json(tmp_path: Path) -> None:
    """Test one-time JSON → SQLite migration."""
    json_path = tmp_path / "experiments.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "id": "migr1234",
                    "name": "migrated",
                    "status": "completed",
                    "task": "sft",
                    "model": "qwen",
                    "dataset_id": "",
                    "config": {"lr": 1e-4},
                    "created_at": "2024-06-01T10:00:00",
                    "last_update_at": "2024-06-01T12:00:00",
                    "completed_at": "2024-06-01T12:00:00",
                    "final_loss": 0.15,
                    "training_history": [
                        {"step": 1, "loss": 0.5, "time": "2024-06-01T10:30:00"},
                        {"step": 2, "loss": 0.15, "time": "2024-06-01T11:00:00"},
                    ],
                    "eval_results": {"accuracy": 0.95},
                    "artifacts": {"adapter_dir": "/out/lora"},
                }
            ]
        ),
        encoding="utf-8",
    )

    db = Database(db_path=tmp_path / "migr.db")
    store = ExperimentStore(db=db)
    count = store.migrate_from_json(json_path)
    assert count == 1

    exp = store.get("migr1234")
    assert exp is not None
    assert exp["name"] == "migrated"
    assert exp["final_loss"] == 0.15
    assert len(exp["training_history"]) == 2
    assert exp["eval_results"]["accuracy"] == 0.95


def test_auto_migrate_from_json(tmp_path: Path) -> None:
    """Auto-migration triggers when using the default singleton and JSON exists."""

    # Write a JSON file at the default path.
    json_path = tmp_path / "data" / "experiments.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(
            [
                {
                    "id": "auto1234",
                    "name": "auto-migrated",
                    "status": "queued",
                    "task": "dpo",
                    "model": "test",
                    "dataset_id": "",
                    "config": {},
                    "created_at": "2024-01-01",
                    "last_update_at": "2024-01-01",
                    "completed_at": None,
                    "final_loss": None,
                    "training_history": [],
                    "eval_results": None,
                    "artifacts": {},
                }
            ]
        ),
        encoding="utf-8",
    )

    # Test explicit migrate_from_json (the public API).
    db = Database(db_path=tmp_path / "auto.db")
    store = ExperimentStore(db=db)
    count = store.migrate_from_json(json_path)
    assert count == 1

    exp = store.get("auto1234")
    assert exp is not None
    assert exp["name"] == "auto-migrated"
    assert exp["task"] == "dpo"

    # Second call is idempotent.
    count2 = store.migrate_from_json(json_path)
    assert count2 == 1  # Re-import counted but rows deduplicated
    assert len(store.list_all()) == 1


# ── Concurrency ─────────────────────────────────────────────────────────


def test_concurrent_add_metrics(tmp_path: Path) -> None:
    """Multiple threads can add metrics without data loss."""
    db = Database(db_path=tmp_path / "concurrent.db")
    store = ExperimentStore(db=db)
    exp_id = store.create("concurrent", {})
    store.update_status(exp_id, "running")

    errors: list[Exception] = []

    def add_metric(step: int) -> None:
        try:
            # Each thread creates its own store with a fresh Database
            # (thread-local connections in same Database instance).
            s = ExperimentStore(db=db)
            s.add_metrics(exp_id, {"step": step, "loss": 1.0 / (step + 1)})
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=add_metric, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent errors: {errors}"

    exp = store.get(exp_id)
    assert len(exp["training_history"]) == 20


def test_concurrent_create(tmp_path: Path) -> None:
    """Multiple threads can create experiments concurrently."""
    db = Database(db_path=tmp_path / "create_conc.db")
    errors: list[Exception] = []
    ids: list[str] = []
    lock = threading.Lock()

    def create_exp(idx: int) -> None:
        try:
            s = ExperimentStore(db=db)
            eid = s.create(f"exp-{idx}", {"idx": idx})
            with lock:
                ids.append(eid)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=create_exp, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent errors: {errors}"
    assert len(ids) == 10
    assert len(set(ids)) == 10  # All unique.

    store = ExperimentStore(db=db)
    assert len(store.list_all()) == 10
