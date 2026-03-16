"""SQLite-backed workflow storage for visual pipeline builder.

Replaces the legacy JSON load-mutate-save pattern with direct SQL
operations.  All public method signatures and return types are preserved
for backward compatibility with routes and assistant.
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pulsar_ai.storage.database import Database, get_database
from pulsar_ai.storage.migration import migrate_workflows

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2
DEFAULT_JSON_PATH = Path("./data/workflows.json")
_GOV_NODE_TYPES = {"agent", "a2a", "router", "gateway"}
_GOV_RISK_LEVELS = {"low", "medium", "high", "critical"}


class WorkflowStore:
    """CRUD operations for visual workflows backed by SQLite.

    Args:
        db: Database instance.  Uses the module singleton when *None*.
    """

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()
        if db is None:
            self._auto_migrate_json()

    def save(
        self,
        name: str,
        nodes: list[dict],
        edges: list[dict],
        workflow_id: str | None = None,
    ) -> dict:
        """Save or update a workflow.

        Args:
            name: Workflow display name.
            nodes: React Flow nodes array.
            edges: React Flow edges array.
            workflow_id: Existing ID to update, or None to create new.

        Returns:
            Saved workflow dict.
        """
        normalized_nodes = [self._normalize_node(node) for node in nodes]
        now_iso = datetime.now().isoformat()
        nodes_json = json.dumps(normalized_nodes, ensure_ascii=False)
        edges_json = json.dumps(edges, ensure_ascii=False)

        if workflow_id:
            cursor = self._db.execute(
                """
                UPDATE workflows
                SET name = ?, nodes = ?, edges = ?,
                    schema_version = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, nodes_json, edges_json, SCHEMA_VERSION, now_iso, workflow_id),
            )
            self._db.commit()
            if cursor.rowcount > 0:
                return self.get(workflow_id)  # type: ignore[return-value]

        new_id = workflow_id or str(uuid.uuid4())[:8]
        self._db.execute(
            """
            INSERT INTO workflows
                (id, name, nodes, edges, schema_version,
                 created_at, updated_at, last_run, run_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0)
            """,
            (new_id, name, nodes_json, edges_json, SCHEMA_VERSION, now_iso, now_iso),
        )
        self._db.commit()
        logger.info("Saved workflow %s: %s", new_id, name)
        return self.get(new_id)  # type: ignore[return-value]

    def get(self, workflow_id: str) -> dict | None:
        """Get a workflow by ID.

        Args:
            workflow_id: Workflow ID.

        Returns:
            Workflow dict or None.
        """
        row = self._db.fetch_one("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_all(self) -> list[dict]:
        """List all workflows (newest first).

        Returns:
            List of workflow dicts.
        """
        rows = self._db.fetch_all("SELECT * FROM workflows ORDER BY updated_at DESC")
        return [self._row_to_dict(r) for r in rows]

    def delete(self, workflow_id: str) -> bool:
        """Delete a workflow.

        Args:
            workflow_id: Workflow ID.

        Returns:
            True if deleted, False if not found.
        """
        cursor = self._db.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
        self._db.commit()
        return cursor.rowcount > 0

    def mark_run(self, workflow_id: str) -> None:
        """Mark a workflow as having been run.

        Args:
            workflow_id: Workflow ID.
        """
        now_iso = datetime.now().isoformat()
        self._db.execute(
            """
            UPDATE workflows
            SET last_run = ?, run_count = run_count + 1
            WHERE id = ?
            """,
            (now_iso, workflow_id),
        )
        self._db.commit()

    def to_pipeline_config(self, workflow_id: str) -> dict | None:
        """Convert a workflow to PipelineExecutor-compatible config.

        Args:
            workflow_id: Workflow ID.

        Returns:
            Pipeline config dict or None.
        """
        wf = self.get(workflow_id)
        if not wf:
            return None

        nodes = wf["nodes"]
        edges = wf["edges"]

        deps: dict[str, list[str]] = {}
        for edge in edges:
            deps.setdefault(edge["target"], []).append(edge["source"])

        node_names: dict[str, str] = {}
        for node in nodes:
            node_names[node["id"]] = (
                node.get("data", {}).get("label", node["id"]).lower().replace(" ", "_")
            )

        steps = []
        for node in nodes:
            node_type = node.get("type", "default")
            data = node.get("data", {})
            step_name = node_names[node["id"]]

            step: dict[str, Any] = {
                "name": step_name,
                "type": self._node_type_to_step_type(node_type),
                "config": data.get("config", {}),
            }

            node_deps = deps.get(node["id"], [])
            if node_deps:
                step["depends_on"] = [node_names[d] for d in node_deps]

            steps.append(step)

        return {
            "pipeline": {"name": wf["name"]},
            "steps": steps,
        }

    def migrate_from_json(self, json_path: Path | None = None) -> int:
        """One-time migration from a legacy JSON store file.

        Args:
            json_path: Path to ``workflows.json``.

        Returns:
            Number of migrated workflows.
        """
        path = json_path or DEFAULT_JSON_PATH
        return migrate_workflows(self._db, path)

    # ── Internals ─────────────────────────────────────────────────────

    @staticmethod
    def _node_type_to_step_type(node_type: str) -> str:
        """Map React Flow node type to pipeline step type."""
        mapping = {
            "dataSource": "data",
            "model": "model",
            "training": "training",
            "eval": "evaluation",
            "export": "export",
            "agent": "agent",
            "prompt": "prompt",
            "conditional": "conditional",
            "rag": "rag",
            "inference": "inference",
            "router": "router",
            "dataGen": "data_generation",
            "serve": "serve",
            "splitter": "splitter",
        }
        return mapping.get(node_type, node_type)

    def _row_to_dict(self, row: dict) -> dict:
        """Convert a SQLite row into the legacy dict format."""
        wf = {
            "id": row["id"],
            "name": row["name"],
            "nodes": json.loads(row["nodes"] or "[]"),
            "edges": json.loads(row["edges"] or "[]"),
            "schema_version": row.get("schema_version", 1),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_run": row.get("last_run"),
            "run_count": row.get("run_count", 0),
        }
        wf["nodes"] = [self._normalize_node(n) for n in wf["nodes"]]
        return wf

    def _normalize_node(self, node: dict[str, Any]) -> dict[str, Any]:
        normalized_node = dict(node)
        data = dict(normalized_node.get("data", {}))
        config = dict(data.get("config", {}))

        if normalized_node.get("type") in _GOV_NODE_TYPES:
            if "agent_role" not in config:
                config["agent_role"] = ""
            risk_level = str(config.get("risk_level", "medium")).lower()
            if risk_level not in _GOV_RISK_LEVELS:
                risk_level = "medium"
            config["risk_level"] = risk_level
            config["requires_approval"] = bool(config.get("requires_approval", False))

        data["config"] = config
        normalized_node["data"] = data
        return normalized_node

    def _auto_migrate_json(self) -> None:
        """Auto-migrate from JSON if the SQLite table is empty and JSON exists."""
        count_row = self._db.fetch_one("SELECT COUNT(*) as cnt FROM workflows")
        if count_row and count_row["cnt"] > 0:
            return

        if not DEFAULT_JSON_PATH.exists():
            return

        count = migrate_workflows(self._db, DEFAULT_JSON_PATH)
        if count > 0:
            logger.info("Auto-migrated %d workflows from %s", count, DEFAULT_JSON_PATH)
