"""Abstract database backend interface for Pulsar AI.

Allows swapping SQLite for PostgreSQL (or other backends) via
the ``PULSAR_DB_URL`` environment variable.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Generator


class DatabaseBackend(ABC):
    """Abstract base for database backends.

    All storage code interacts through this interface so the
    concrete database engine can be changed via configuration.
    """

    @abstractmethod
    def execute(self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> Any:
        """Execute a single SQL statement."""

    @abstractmethod
    def executemany(
        self, sql: str, seq_of_params: list[tuple[Any, ...]] | list[dict[str, Any]]
    ) -> Any:
        """Execute a statement against multiple parameter sets."""

    @abstractmethod
    def fetch_one(
        self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> dict[str, Any] | None:
        """Execute a query and return the first row as a dict."""

    @abstractmethod
    def fetch_all(
        self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> list[dict[str, Any]]:
        """Execute a query and return all rows as dicts."""

    @abstractmethod
    def commit(self) -> None:
        """Commit the current transaction."""

    @abstractmethod
    def close(self) -> None:
        """Close database connections."""

    @contextmanager
    def transaction(self) -> Generator[Any, None, None]:
        """Context manager for transaction scope. Override in subclasses."""
        yield self
        self.commit()
