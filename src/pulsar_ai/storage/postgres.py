"""PostgreSQL database backend for Pulsar AI.

Uses psycopg2 with a threaded connection pool for production deployments.
Activated when ``PULSAR_DB_URL`` starts with ``postgresql://``.

Requires: ``pip install pulsar-ai[postgres]``
"""

import logging
import re
import threading
from contextlib import contextmanager
from typing import Any, Generator

from pulsar_ai.storage.backend import DatabaseBackend
from pulsar_ai.storage.schema import BOOTSTRAP_SQL, SCHEMA_VERSION

logger = logging.getLogger(__name__)


def _sqlite_to_pg_sql(sql: str) -> str:
    """Convert SQLite-flavored DDL to PostgreSQL syntax.

    Args:
        sql: SQLite DDL string.

    Returns:
        PostgreSQL-compatible DDL.
    """
    result = sql
    # AUTOINCREMENT → GENERATED ALWAYS AS IDENTITY
    result = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY",
        result,
        flags=re.IGNORECASE,
    )
    return result


class PostgresDatabase(DatabaseBackend):
    """PostgreSQL backend using psycopg2 connection pool.

    Args:
        dsn: PostgreSQL connection string
            (e.g. ``postgresql://user:pass@localhost:5432/pulsar``).
        min_conn: Minimum connections in the pool.
        max_conn: Maximum connections in the pool.
    """

    def __init__(
        self,
        dsn: str,
        min_conn: int = 2,
        max_conn: int = 10,
    ) -> None:
        try:
            import psycopg2
            import psycopg2.extras
            import psycopg2.pool
        except ImportError as exc:
            raise ImportError(
                "psycopg2 is required for PostgreSQL support. "
                "Install with: pip install pulsar-ai[postgres]"
            ) from exc

        self._dsn = dsn
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            min_conn, max_conn, dsn
        )
        self._local = threading.local()
        self._bootstrap()
        logger.info("PostgreSQL connected: %s", dsn.split("@")[-1] if "@" in dsn else dsn)

    def _get_conn(self) -> Any:
        """Get or create a thread-local connection from the pool."""
        conn = getattr(self._local, "conn", None)
        if conn is None or conn.closed:
            conn = self._pool.getconn()
            conn.autocommit = False
            self._local.conn = conn
        return conn

    def _put_conn(self) -> None:
        """Return the thread-local connection to the pool."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            self._pool.putconn(conn)
            self._local.conn = None

    def execute(self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> Any:
        """Execute a single SQL statement."""
        import psycopg2.extras

        conn = self._get_conn()
        # Convert ? placeholders to %s for psycopg2
        pg_sql = sql.replace("?", "%s")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(pg_sql, params)
        return cursor

    def executemany(
        self, sql: str, seq_of_params: list[tuple[Any, ...]] | list[dict[str, Any]]
    ) -> Any:
        """Execute a statement against multiple parameter sets."""
        import psycopg2.extras

        conn = self._get_conn()
        pg_sql = sql.replace("?", "%s")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.executemany(pg_sql, seq_of_params)
        return cursor

    def fetch_one(
        self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> dict[str, Any] | None:
        """Execute a query and return the first row as a dict."""
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetch_all(
        self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> list[dict[str, Any]]:
        """Execute a query and return all rows as dicts."""
        cursor = self.execute(sql, params)
        return [dict(r) for r in cursor.fetchall()]

    def commit(self) -> None:
        """Commit the current transaction."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.commit()

    def close(self) -> None:
        """Close all pool connections."""
        self._put_conn()
        self._pool.closeall()

    @contextmanager
    def transaction(self) -> Generator[Any, None, None]:
        """Context manager wrapping BEGIN/COMMIT/ROLLBACK."""
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

    def _bootstrap(self) -> None:
        """Create tables if they don't exist."""
        pg_sql = _sqlite_to_pg_sql(BOOTSTRAP_SQL)
        conn = self._get_conn()
        cursor = conn.cursor()
        # Split and execute statements one by one (PG doesn't support executescript)
        for statement in pg_sql.split(";"):
            stmt = statement.strip()
            if stmt:
                cursor.execute(stmt)
        # Stamp schema version
        cursor.execute(
            "INSERT INTO _schema_meta(key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        conn.commit()
        logger.info("PostgreSQL schema bootstrapped (v%d)", SCHEMA_VERSION)
