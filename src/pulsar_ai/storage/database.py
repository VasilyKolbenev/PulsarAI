"""Core SQLite database management for Pulsar AI.

Provides connection pooling (via thread-local connections), schema
bootstrap, and a simple ``execute`` / ``executemany`` interface that
the repository layer can build on.

Usage::

    from pulsar_ai.storage import get_database

    db = get_database()          # singleton, bootstraps schema on first call
    db.execute("INSERT INTO experiments ...", params)
    rows = db.fetch_all("SELECT * FROM experiments WHERE status = ?", ("running",))
"""

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from pulsar_ai.storage.schema import BOOTSTRAP_SQL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("./data/pulsar.db")

# Module-level singleton.
_instance: "Database | None" = None
_instance_lock = threading.Lock()


class Database:
    """Thread-safe SQLite database wrapper.

    Args:
        db_path: Path to the SQLite file.  Created automatically.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._bootstrap()

    # ── Connection management ────────────────────────────────────────

    def _get_connection(self) -> sqlite3.Connection:
        """Return a thread-local connection (created on first access)."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=10,
                check_same_thread=False,
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that wraps a block in BEGIN / COMMIT / ROLLBACK.

        Yields:
            The thread-local ``sqlite3.Connection``.
        """
        conn = self._get_connection()
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

    # ── Query helpers ────────────────────────────────────────────────

    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] | dict[str, Any] = (),
    ) -> sqlite3.Cursor:
        """Execute a single SQL statement.

        Args:
            sql: SQL string with ``?`` or ``:name`` placeholders.
            params: Positional or named parameters.

        Returns:
            ``sqlite3.Cursor`` for the executed statement.
        """
        conn = self._get_connection()
        return conn.execute(sql, params)

    def executemany(
        self,
        sql: str,
        seq_of_params: list[tuple[Any, ...]] | list[dict[str, Any]],
    ) -> sqlite3.Cursor:
        """Execute a statement against multiple parameter sets.

        Args:
            sql: SQL string.
            seq_of_params: List of parameter tuples/dicts.

        Returns:
            ``sqlite3.Cursor``.
        """
        conn = self._get_connection()
        return conn.executemany(sql, seq_of_params)

    def fetch_one(
        self,
        sql: str,
        params: tuple[Any, ...] | dict[str, Any] = (),
    ) -> dict[str, Any] | None:
        """Execute a query and return the first row as a dict.

        Args:
            sql: SQL SELECT string.
            params: Query parameters.

        Returns:
            Row as ``dict`` or ``None``.
        """
        row = self.execute(sql, params).fetchone()
        if row is None:
            return None
        return dict(row)

    def fetch_all(
        self,
        sql: str,
        params: tuple[Any, ...] | dict[str, Any] = (),
    ) -> list[dict[str, Any]]:
        """Execute a query and return all rows as dicts.

        Args:
            sql: SQL SELECT string.
            params: Query parameters.

        Returns:
            List of row dicts.
        """
        return [dict(r) for r in self.execute(sql, params).fetchall()]

    def commit(self) -> None:
        """Explicit commit on the current thread's connection."""
        self._get_connection().commit()

    def close(self) -> None:
        """Close the thread-local connection (if open)."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # ── Schema bootstrap ─────────────────────────────────────────────

    def _bootstrap(self) -> None:
        """Create tables if they don't exist and stamp the schema version."""
        conn = self._get_connection()
        conn.executescript(BOOTSTRAP_SQL)

        # Stamp schema version (idempotent).
        conn.execute(
            "INSERT OR REPLACE INTO _schema_meta(key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        conn.commit()
        logger.info(
            "Database bootstrapped at %s (schema v%d)",
            self.db_path,
            SCHEMA_VERSION,
        )

    @property
    def schema_version(self) -> int:
        """Return the current schema version stored in the database."""
        row = self.fetch_one(
            "SELECT value FROM _schema_meta WHERE key = ?",
            ("schema_version",),
        )
        if row is None:
            return 0
        return int(row["value"])


def get_database(db_path: Path | None = None) -> Database:
    """Return the module-level ``Database`` singleton.

    Thread-safe.  The first call creates the instance and bootstraps the
    schema; subsequent calls return the same object.

    Args:
        db_path: Override path (only effective on the first call).

    Returns:
        ``Database`` instance.
    """
    global _instance
    if _instance is not None:
        return _instance
    with _instance_lock:
        if _instance is None:
            _instance = Database(db_path)
    return _instance


def reset_database() -> None:
    """Reset the module-level singleton (useful for tests)."""
    global _instance
    with _instance_lock:
        if _instance is not None:
            _instance.close()
            _instance = None
