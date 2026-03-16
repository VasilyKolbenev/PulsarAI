"""Shared test fixtures for Pulsar AI test suite."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pulsar_ai.storage.database import Database, reset_database


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Database:
    """Create an isolated in-memory-like Database backed by a temp file.

    Yields a fully bootstrapped Database and resets the singleton after the test
    so no state leaks between tests.
    """
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    yield db
    reset_database()


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> Path:
    """Return a temporary path suitable for creating a new Database."""
    return tmp_path / "test.db"
