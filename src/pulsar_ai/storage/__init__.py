"""SQLite-based persistence layer for Pulsar AI.

Replaces the load-mutate-save JSON stores with a transactional backend.
"""

from pulsar_ai.storage.database import Database, get_database

__all__ = ["Database", "get_database"]
