"""Tests for SQLite persistence layer: bootstrap, queries, migration."""

import json
import sqlite3
import threading
from pathlib import Path

import pytest

from pulsar_ai.storage.database import Database, get_database, reset_database
from pulsar_ai.storage.migration import (
    migrate_all,
    migrate_experiments,
    migrate_prompts,
    migrate_runs,
    migrate_workflows,
)
from pulsar_ai.storage.schema import SCHEMA_VERSION

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure the module singleton is reset between tests."""
    reset_database()
    yield
    reset_database()


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Return a fresh Database pointed at a temp directory."""
    return Database(db_path=tmp_path / "test.db")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temp data directory for JSON fixtures."""
    d = tmp_path / "data"
    d.mkdir()
    return d


# ── Schema Bootstrap ────────────────────────────────────────────────────


class TestBootstrap:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "new.db"
        assert not db_path.exists()
        Database(db_path=db_path)
        assert db_path.exists()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        db_path = tmp_path / "sub" / "dir" / "deep.db"
        Database(db_path=db_path)
        assert db_path.exists()

    def test_schema_version_stamped(self, db: Database) -> None:
        assert db.schema_version == SCHEMA_VERSION

    def test_tables_exist(self, db: Database) -> None:
        tables = {
            row["name"] for row in db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
        }
        expected = {
            "_schema_meta",
            "experiments",
            "experiment_metrics",
            "prompts",
            "prompt_versions",
            "workflows",
            "runs",
        }
        assert expected.issubset(tables)

    def test_wal_mode_enabled(self, db: Database) -> None:
        row = db.fetch_one("PRAGMA journal_mode")
        assert row is not None
        assert row["journal_mode"] == "wal"

    def test_foreign_keys_enabled(self, db: Database) -> None:
        row = db.fetch_one("PRAGMA foreign_keys")
        assert row is not None
        assert row["foreign_keys"] == 1

    def test_bootstrap_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "idem.db"
        db1 = Database(db_path=db_path)
        db1.execute("""INSERT INTO experiments
                (id, name, status, task, created_at, last_update_at)
            VALUES ('x1', 'exp', 'queued', 'sft', '2024-01-01', '2024-01-01')
            """)
        db1.commit()
        db1.close()

        # Re-bootstrap must not lose data.
        db2 = Database(db_path=db_path)
        row = db2.fetch_one("SELECT * FROM experiments WHERE id = 'x1'")
        assert row is not None
        assert row["name"] == "exp"
        db2.close()


# ── Query Helpers ────────────────────────────────────────────────────────


class TestQueryHelpers:
    def test_execute_and_fetch(self, db: Database) -> None:
        db.execute(
            """INSERT INTO experiments
                (id, name, status, task, created_at, last_update_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ("e1", "test", "queued", "sft", "2024-01-01", "2024-01-01"),
        )
        db.commit()

        row = db.fetch_one("SELECT * FROM experiments WHERE id = ?", ("e1",))
        assert row is not None
        assert row["name"] == "test"

    def test_fetch_all(self, db: Database) -> None:
        for i in range(3):
            db.execute(
                """INSERT INTO experiments
                    (id, name, status, task, created_at, last_update_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (f"e{i}", f"exp{i}", "queued", "sft", "2024-01-01", "2024-01-01"),
            )
        db.commit()

        rows = db.fetch_all("SELECT * FROM experiments")
        assert len(rows) == 3

    def test_fetch_one_returns_none(self, db: Database) -> None:
        assert db.fetch_one("SELECT * FROM experiments WHERE id = ?", ("nope",)) is None

    def test_transaction_commit(self, db: Database) -> None:
        with db.transaction():
            db.execute("""INSERT INTO experiments
                    (id, name, status, task, created_at, last_update_at)
                VALUES ('tx1', 'txn', 'queued', 'sft', '2024-01-01', '2024-01-01')""")

        assert db.fetch_one("SELECT * FROM experiments WHERE id = 'tx1'") is not None

    def test_transaction_rollback(self, db: Database) -> None:
        with pytest.raises(ValueError):
            with db.transaction():
                db.execute("""INSERT INTO experiments
                        (id, name, status, task, created_at, last_update_at)
                    VALUES ('tx2', 'fail', 'queued', 'sft', '2024-01-01', '2024-01-01')""")
                raise ValueError("rollback me")

        assert db.fetch_one("SELECT * FROM experiments WHERE id = 'tx2'") is None


# ── Concurrent Access ────────────────────────────────────────────────────


class TestConcurrency:
    def test_concurrent_inserts(self, tmp_path: Path) -> None:
        db_path = tmp_path / "concurrent.db"
        errors: list[Exception] = []

        def insert_row(thread_id: int) -> None:
            try:
                d = Database(db_path=db_path)
                d.execute(
                    """INSERT INTO experiments
                        (id, name, status, task, created_at, last_update_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        f"t{thread_id}",
                        f"thread-{thread_id}",
                        "queued",
                        "sft",
                        "2024-01-01",
                        "2024-01-01",
                    ),
                )
                d.commit()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=insert_row, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent insert errors: {errors}"

        db = Database(db_path=db_path)
        rows = db.fetch_all("SELECT * FROM experiments")
        assert len(rows) == 10


# ── Singleton ────────────────────────────────────────────────────────────


class TestSingleton:
    def test_get_database_returns_same_instance(self, tmp_path: Path) -> None:
        db1 = get_database(tmp_path / "single.db")
        db2 = get_database()
        assert db1 is db2


# ── Migration: Experiments ───────────────────────────────────────────────


class TestMigrateExperiments:
    def test_migrate_experiments(self, db: Database, data_dir: Path) -> None:
        experiments = [
            {
                "id": "abc12345",
                "name": "test-sft",
                "status": "completed",
                "task": "sft",
                "model": "qwen2.5-3b",
                "dataset_id": "ds1",
                "config": {"model": {"name": "qwen2.5-3b"}},
                "created_at": "2024-06-01T10:00:00",
                "last_update_at": "2024-06-01T12:00:00",
                "completed_at": "2024-06-01T12:00:00",
                "final_loss": 0.25,
                "training_history": [
                    {"step": 10, "loss": 0.5, "time": "2024-06-01T10:30:00"},
                    {"step": 20, "loss": 0.25, "time": "2024-06-01T11:00:00"},
                ],
                "eval_results": {"accuracy": 0.92},
                "artifacts": {"adapter_dir": "/output/lora"},
            },
            {
                "id": "def67890",
                "name": "test-dpo",
                "status": "running",
                "task": "dpo",
                "model": "qwen2.5-2b",
                "dataset_id": "",
                "config": {},
                "created_at": "2024-06-02T08:00:00",
                "last_update_at": "2024-06-02T08:30:00",
                "completed_at": None,
                "final_loss": None,
                "training_history": [],
                "eval_results": None,
                "artifacts": {},
            },
        ]
        (data_dir / "experiments.json").write_text(
            json.dumps(experiments, ensure_ascii=False), encoding="utf-8"
        )

        count = migrate_experiments(db, data_dir / "experiments.json")
        assert count == 2

        rows = db.fetch_all("SELECT * FROM experiments ORDER BY id")
        assert len(rows) == 2
        assert rows[0]["id"] == "abc12345"
        assert rows[0]["status"] == "completed"
        assert rows[0]["final_loss"] == 0.25
        assert json.loads(rows[0]["eval_results"]) == {"accuracy": 0.92}

        # Metrics should be in separate table.
        metrics = db.fetch_all(
            "SELECT * FROM experiment_metrics WHERE experiment_id = ?",
            ("abc12345",),
        )
        assert len(metrics) == 2
        first = json.loads(metrics[0]["data"])
        assert first["step"] == 10

    def test_migrate_missing_file(self, db: Database, data_dir: Path) -> None:
        count = migrate_experiments(db, data_dir / "nope.json")
        assert count == 0

    def test_migrate_idempotent(self, db: Database, data_dir: Path) -> None:
        experiments = [
            {
                "id": "idem1",
                "name": "re-import",
                "status": "queued",
                "task": "sft",
                "model": "",
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
        path = data_dir / "experiments.json"
        path.write_text(json.dumps(experiments), encoding="utf-8")

        migrate_experiments(db, path)
        migrate_experiments(db, path)  # Second call should not duplicate.

        rows = db.fetch_all("SELECT * FROM experiments")
        assert len(rows) == 1


# ── Migration: Prompts ───────────────────────────────────────────────────


class TestMigratePrompts:
    def test_migrate_prompts_with_versions(self, db: Database, data_dir: Path) -> None:
        prompts = [
            {
                "id": "p1",
                "name": "Intent Prompt",
                "description": "Classify intent",
                "current_version": 2,
                "versions": [
                    {
                        "version": 1,
                        "system_prompt": "Classify: {{text}}",
                        "variables": ["text"],
                        "model": "gpt-4",
                        "parameters": {"temperature": 0.0},
                        "created_at": "2024-05-01",
                        "metrics": None,
                    },
                    {
                        "version": 2,
                        "system_prompt": "Classify intent of: {{text}}",
                        "variables": ["text"],
                        "model": "gpt-4",
                        "parameters": {"temperature": 0.1},
                        "created_at": "2024-05-15",
                        "metrics": {"accuracy": 0.95},
                    },
                ],
                "tags": ["production", "intent"],
                "created_at": "2024-05-01",
                "updated_at": "2024-05-15",
            }
        ]
        (data_dir / "prompts.json").write_text(json.dumps(prompts), encoding="utf-8")

        count = migrate_prompts(db, data_dir / "prompts.json")
        assert count == 1

        row = db.fetch_one("SELECT * FROM prompts WHERE id = 'p1'")
        assert row is not None
        assert row["current_version"] == 2
        assert json.loads(row["tags"]) == ["production", "intent"]

        versions = db.fetch_all(
            "SELECT * FROM prompt_versions WHERE prompt_id = 'p1' ORDER BY version"
        )
        assert len(versions) == 2
        assert versions[0]["system_prompt"] == "Classify: {{text}}"
        assert versions[1]["model"] == "gpt-4"
        assert json.loads(versions[1]["metrics"]) == {"accuracy": 0.95}


# ── Migration: Workflows ────────────────────────────────────────────────


class TestMigrateWorkflows:
    def test_migrate_workflows(self, db: Database, data_dir: Path) -> None:
        workflows = [
            {
                "id": "wf1",
                "name": "Training Pipeline",
                "nodes": [{"id": "n1", "type": "training"}],
                "edges": [{"source": "n1", "target": "n2"}],
                "schema_version": 2,
                "created_at": "2024-04-01",
                "updated_at": "2024-04-01",
                "last_run": None,
                "run_count": 0,
            }
        ]
        (data_dir / "workflows.json").write_text(json.dumps(workflows), encoding="utf-8")

        count = migrate_workflows(db, data_dir / "workflows.json")
        assert count == 1

        row = db.fetch_one("SELECT * FROM workflows WHERE id = 'wf1'")
        assert row is not None
        assert json.loads(row["nodes"])[0]["type"] == "training"


# ── Migration: Runs ──────────────────────────────────────────────────────


class TestMigrateRuns:
    def test_migrate_run_files(self, db: Database, data_dir: Path) -> None:
        runs_dir = data_dir / "runs"
        runs_dir.mkdir()
        run = {
            "run_id": "r1abc",
            "name": "sft-run",
            "project": "pulsar-ai",
            "backend": "local",
            "status": "completed",
            "config": {"lr": 1e-4},
            "tags": ["sft"],
            "metrics_history": [{"loss": 0.3, "_step": 1}],
            "artifacts": {"model": "/out/model"},
            "results": {"training_loss": 0.1},
            "started_at": "2024-03-01",
            "finished_at": "2024-03-01T01:00:00",
            "duration_s": 3600.0,
            "environment": {"python_version": "3.11"},
        }
        (runs_dir / "r1abc.json").write_text(json.dumps(run), encoding="utf-8")

        count = migrate_runs(db, runs_dir)
        assert count == 1

        row = db.fetch_one("SELECT * FROM runs WHERE run_id = 'r1abc'")
        assert row is not None
        assert row["status"] == "completed"
        assert row["duration_s"] == 3600.0


# ── Full Migration ───────────────────────────────────────────────────────


class TestMigrateAll:
    def test_migrate_all_from_data_dir(self, db: Database, data_dir: Path) -> None:
        # Create minimal JSON fixtures.
        (data_dir / "experiments.json").write_text(
            json.dumps(
                [
                    {
                        "id": "e1",
                        "name": "exp",
                        "status": "queued",
                        "task": "sft",
                        "model": "",
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
        (data_dir / "prompts.json").write_text("[]", encoding="utf-8")
        (data_dir / "workflows.json").write_text("[]", encoding="utf-8")

        report = migrate_all(db, data_dir=data_dir)
        assert report["experiments"] == 1
        assert report["prompts"] == 0
        assert report["workflows"] == 0
        assert report["runs"] == 0

    def test_migrate_all_missing_files(self, db: Database, data_dir: Path) -> None:
        report = migrate_all(db, data_dir=data_dir)
        assert all(v == 0 for v in report.values())
