"""SQLite-backed versioned prompt storage.

Replaces the legacy JSON load-mutate-save pattern with direct SQL
operations via the Database class. All public method signatures and
return types are preserved for backward compatibility.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from difflib import unified_diff
from pathlib import Path
from typing import Any

from pulsar_ai.storage.database import Database, get_database
from pulsar_ai.storage.migration import migrate_prompts

logger = logging.getLogger(__name__)

DEFAULT_JSON_PATH = Path("./data/prompts.json")


@dataclass
class PromptVersion:
    """A single version of a prompt."""

    version: int
    system_prompt: str
    variables: list[str]
    model: str
    parameters: dict[str, Any]
    created_at: str
    metrics: dict[str, Any] | None = None


@dataclass
class Prompt:
    """A prompt with version history."""

    id: str
    name: str
    description: str
    current_version: int
    versions: list[dict[str, Any]]
    tags: list[str]
    created_at: str
    updated_at: str


class PromptStore:
    """CRUD + versioning for prompts backed by SQLite.

    Args:
        db: Database instance.  Uses the module singleton when *None*.
    """

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()
        if db is None:
            self._auto_migrate_json()

    def create(
        self,
        name: str,
        system_prompt: str,
        *,
        description: str = "",
        model: str = "",
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Create a new prompt with version 1.

        Args:
            name: Prompt display name.
            system_prompt: The prompt text.
            description: Optional description.
            model: Target model ID.
            parameters: Generation parameters (temperature, etc.).
            tags: Optional tags for categorization.

        Returns:
            Created prompt dict.
        """
        prompt_id = str(uuid.uuid4())[:8]
        now_iso = datetime.now().isoformat()
        variables = self._extract_variables(system_prompt)

        self._db.execute(
            """
            INSERT INTO prompts
                (id, name, description, current_version, tags,
                 created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (
                prompt_id,
                name,
                description,
                json.dumps(tags or [], ensure_ascii=False),
                now_iso,
                now_iso,
            ),
        )

        self._db.execute(
            """
            INSERT INTO prompt_versions
                (prompt_id, version, system_prompt, variables,
                 model, parameters, metrics, created_at)
            VALUES (?, 1, ?, ?, ?, ?, NULL, ?)
            """,
            (
                prompt_id,
                system_prompt,
                json.dumps(variables, ensure_ascii=False),
                model,
                json.dumps(parameters or {}, ensure_ascii=False),
                now_iso,
            ),
        )
        self._db.commit()
        logger.info("Created prompt %s: %s", prompt_id, name)
        return self.get(prompt_id)  # type: ignore[return-value]

    def get(self, prompt_id: str) -> dict | None:
        """Get a prompt by ID with all versions.

        Args:
            prompt_id: Prompt ID.

        Returns:
            Prompt dict or None.
        """
        row = self._db.fetch_one("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_all(self, tag: str | None = None) -> list[dict]:
        """List all prompts, optionally filtered by tag.

        Args:
            tag: Optional tag to filter by.

        Returns:
            List of prompt dicts (newest first).
        """
        rows = self._db.fetch_all("SELECT * FROM prompts ORDER BY updated_at DESC")
        prompts = [self._row_to_dict(r) for r in rows]
        if tag:
            prompts = [p for p in prompts if tag in p.get("tags", [])]
        return prompts

    def update(
        self,
        prompt_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> dict | None:
        """Update prompt metadata (not content — use add_version for that).

        Args:
            prompt_id: Prompt ID.
            name: New name.
            description: New description.
            tags: New tags.

        Returns:
            Updated prompt dict or None.
        """
        existing = self._db.fetch_one("SELECT id FROM prompts WHERE id = ?", (prompt_id,))
        if existing is None:
            return None

        now_iso = datetime.now().isoformat()
        if name is not None:
            self._db.execute("UPDATE prompts SET name = ? WHERE id = ?", (name, prompt_id))
        if description is not None:
            self._db.execute(
                "UPDATE prompts SET description = ? WHERE id = ?",
                (description, prompt_id),
            )
        if tags is not None:
            self._db.execute(
                "UPDATE prompts SET tags = ? WHERE id = ?",
                (json.dumps(tags, ensure_ascii=False), prompt_id),
            )
        self._db.execute(
            "UPDATE prompts SET updated_at = ? WHERE id = ?",
            (now_iso, prompt_id),
        )
        self._db.commit()
        return self.get(prompt_id)

    def add_version(
        self,
        prompt_id: str,
        system_prompt: str,
        *,
        model: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict | None:
        """Add a new version to a prompt.

        Args:
            prompt_id: Prompt ID.
            system_prompt: New prompt text.
            model: Target model (inherits from previous if None).
            parameters: Generation parameters (inherits if None).

        Returns:
            New version dict or None if prompt not found.
        """
        prompt_row = self._db.fetch_one(
            "SELECT id, current_version FROM prompts WHERE id = ?",
            (prompt_id,),
        )
        if prompt_row is None:
            return None

        prev_version = self._db.fetch_one(
            """
            SELECT model, parameters FROM prompt_versions
            WHERE prompt_id = ? AND version = ?
            """,
            (prompt_id, prompt_row["current_version"]),
        )

        new_version_num = prompt_row["current_version"] + 1
        variables = self._extract_variables(system_prompt)
        now_iso = datetime.now().isoformat()

        resolved_model = (
            model if model is not None else (prev_version["model"] if prev_version else "")
        )
        resolved_params = (
            parameters
            if parameters is not None
            else (json.loads(prev_version["parameters"] or "{}") if prev_version else {})
        )

        self._db.execute(
            """
            INSERT INTO prompt_versions
                (prompt_id, version, system_prompt, variables,
                 model, parameters, metrics, created_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                prompt_id,
                new_version_num,
                system_prompt,
                json.dumps(variables, ensure_ascii=False),
                resolved_model,
                json.dumps(resolved_params, ensure_ascii=False),
                now_iso,
            ),
        )

        self._db.execute(
            """
            UPDATE prompts
            SET current_version = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_version_num, now_iso, prompt_id),
        )
        self._db.commit()
        logger.info("Added version %d to prompt %s", new_version_num, prompt_id)

        return self._version_row_to_dict(
            self._db.fetch_one(
                """
                SELECT * FROM prompt_versions
                WHERE prompt_id = ? AND version = ?
                """,
                (prompt_id, new_version_num),
            )
        )

    def get_version(self, prompt_id: str, version: int) -> dict | None:
        """Get a specific version of a prompt.

        Args:
            prompt_id: Prompt ID.
            version: Version number (1-based).

        Returns:
            Version dict or None.
        """
        row = self._db.fetch_one(
            """
            SELECT * FROM prompt_versions
            WHERE prompt_id = ? AND version = ?
            """,
            (prompt_id, version),
        )
        if row is None:
            return None
        return self._version_row_to_dict(row)

    def diff_versions(self, prompt_id: str, v1: int, v2: int) -> dict | None:
        """Generate a unified diff between two versions.

        Args:
            prompt_id: Prompt ID.
            v1: First version number.
            v2: Second version number.

        Returns:
            Dict with diff lines and metadata, or None.
        """
        ver1 = self.get_version(prompt_id, v1)
        ver2 = self.get_version(prompt_id, v2)
        if not ver1 or not ver2:
            return None

        diff_lines = list(
            unified_diff(
                ver1["system_prompt"].splitlines(keepends=True),
                ver2["system_prompt"].splitlines(keepends=True),
                fromfile=f"v{v1}",
                tofile=f"v{v2}",
            )
        )

        return {
            "prompt_id": prompt_id,
            "v1": v1,
            "v2": v2,
            "diff": "".join(diff_lines),
            "v1_variables": ver1["variables"],
            "v2_variables": ver2["variables"],
            "variables_added": [v for v in ver2["variables"] if v not in ver1["variables"]],
            "variables_removed": [v for v in ver1["variables"] if v not in ver2["variables"]],
        }

    def delete(self, prompt_id: str) -> bool:
        """Delete a prompt and all its versions (cascade).

        Args:
            prompt_id: Prompt ID.

        Returns:
            True if deleted, False if not found.
        """
        cursor = self._db.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
        self._db.commit()
        return cursor.rowcount > 0

    def migrate_from_json(self, json_path: Path | None = None) -> int:
        """One-time migration from a legacy JSON store file.

        Args:
            json_path: Path to ``prompts.json``.

        Returns:
            Number of migrated prompts.
        """
        path = json_path or DEFAULT_JSON_PATH
        return migrate_prompts(self._db, path)

    # ── Internals ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_variables(text: str) -> list[str]:
        """Extract {{variable}} placeholders from prompt text."""
        return sorted(set(re.findall(r"\{\{(\w+)\}\}", text)))

    def _row_to_dict(self, row: dict) -> dict:
        """Convert a prompts row + its versions into the legacy dict format."""
        version_rows = self._db.fetch_all(
            """
            SELECT * FROM prompt_versions
            WHERE prompt_id = ?
            ORDER BY version
            """,
            (row["id"],),
        )
        versions = [self._version_row_to_dict(v) for v in version_rows]

        return {
            "id": row["id"],
            "name": row["name"],
            "description": row.get("description", ""),
            "current_version": row["current_version"],
            "versions": versions,
            "tags": json.loads(row["tags"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _version_row_to_dict(row: dict | None) -> dict:
        """Convert a prompt_versions row into dict format."""
        if row is None:
            return {}
        return {
            "version": row["version"],
            "system_prompt": row["system_prompt"],
            "variables": json.loads(row["variables"] or "[]"),
            "model": row.get("model", ""),
            "parameters": json.loads(row["parameters"] or "{}"),
            "created_at": row["created_at"],
            "metrics": (json.loads(row["metrics"]) if row.get("metrics") else None),
        }

    def _auto_migrate_json(self) -> None:
        """Auto-migrate from JSON if the SQLite table is empty and JSON exists."""
        count_row = self._db.fetch_one("SELECT COUNT(*) as cnt FROM prompts")
        if count_row and count_row["cnt"] > 0:
            return

        if not DEFAULT_JSON_PATH.exists():
            return

        count = migrate_prompts(self._db, DEFAULT_JSON_PATH)
        if count > 0:
            logger.info("Auto-migrated %d prompts from %s", count, DEFAULT_JSON_PATH)
