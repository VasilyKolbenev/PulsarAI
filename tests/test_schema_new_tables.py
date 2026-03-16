"""Verify new tables exist after bootstrap."""

import pytest

from pulsar_ai.storage.database import Database, reset_database


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    """Ensure the module singleton is reset between tests."""
    reset_database()
    yield
    reset_database()


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_api_keys_table_exists(db: Database) -> None:
    db.execute(
        "INSERT INTO api_keys (id, name, key_hash, created_at) "
        "VALUES ('k1', 'test', 'hash123', '2026-01-01')"
    )
    db.commit()
    row = db.fetch_one("SELECT * FROM api_keys WHERE id = 'k1'")
    assert row is not None
    assert row["name"] == "test"


def test_compute_targets_table_exists(db: Database) -> None:
    db.execute(
        "INSERT INTO compute_targets (id, name, host, user, created_at) "
        "VALUES ('c1', 'gpu1', '10.0.0.1', 'root', '2026-01-01')"
    )
    db.commit()
    row = db.fetch_one("SELECT * FROM compute_targets WHERE id = 'c1'")
    assert row is not None
    assert row["host"] == "10.0.0.1"


def test_jobs_table_exists(db: Database) -> None:
    db.execute(
        "INSERT INTO jobs (id, status, job_type, started_at) "
        "VALUES ('j1', 'running', 'sft', '2026-01-01')"
    )
    db.commit()
    row = db.fetch_one("SELECT * FROM jobs WHERE id = 'j1'")
    assert row is not None
    assert row["status"] == "running"


def test_assistant_sessions_table_exists(db: Database) -> None:
    db.execute(
        "INSERT INTO assistant_sessions (id, session_type, messages, created_at, updated_at) "
        "VALUES ('s1', 'assistant', '[]', '2026-01-01', '2026-01-01')"
    )
    db.commit()
    row = db.fetch_one("SELECT * FROM assistant_sessions WHERE id = 's1'")
    assert row is not None
    assert row["session_type"] == "assistant"


def test_api_key_events_table_exists(db: Database) -> None:
    db.execute(
        "INSERT INTO api_key_events (key_id, event_type, timestamp) "
        "VALUES ('k1', 'created', '2026-01-01')"
    )
    db.commit()
    rows = db.fetch_all("SELECT * FROM api_key_events WHERE key_id = 'k1'")
    assert len(rows) == 1


def test_jobs_default_values(db: Database) -> None:
    """Verify default column values for jobs table."""
    db.execute("INSERT INTO jobs (id, started_at) VALUES ('j2', '2026-01-01')")
    db.commit()
    row = db.fetch_one("SELECT * FROM jobs WHERE id = 'j2'")
    assert row is not None
    assert row["status"] == "queued"
    assert row["job_type"] == "sft"
    assert row["config"] == "{}"


def test_compute_targets_default_values(db: Database) -> None:
    """Verify default column values for compute_targets table."""
    db.execute(
        "INSERT INTO compute_targets (id, name, host, user, created_at) "
        "VALUES ('c2', 'gpu2', '10.0.0.2', 'admin', '2026-01-01')"
    )
    db.commit()
    row = db.fetch_one("SELECT * FROM compute_targets WHERE id = 'c2'")
    assert row is not None
    assert row["gpu_count"] == 0
    assert row["gpu_type"] == ""
    assert row["vram_gb"] == 0.0
    assert row["key_path"] == ""


def test_assistant_sessions_default_values(db: Database) -> None:
    """Verify default column values for assistant_sessions table."""
    db.execute(
        "INSERT INTO assistant_sessions (id, created_at, updated_at) "
        "VALUES ('s2', '2026-01-01', '2026-01-01')"
    )
    db.commit()
    row = db.fetch_one("SELECT * FROM assistant_sessions WHERE id = 's2'")
    assert row is not None
    assert row["session_type"] == "assistant"
    assert row["messages"] == "[]"
    assert row["ttl_hours"] == 24


def test_jobs_status_index(db: Database) -> None:
    """Verify the idx_jobs_status index was created."""
    rows = db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_jobs_status'"
    )
    assert len(rows) == 1


def test_new_tables_present_in_sqlite_master(db: Database) -> None:
    """Verify all 5 new tables appear in sqlite_master."""
    tables = {
        row["name"] for row in db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
    }
    expected_new = {"api_keys", "compute_targets", "jobs", "assistant_sessions", "api_key_events"}
    assert expected_new.issubset(tables)
