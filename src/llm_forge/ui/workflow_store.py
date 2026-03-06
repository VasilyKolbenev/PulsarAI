"""JSON-based workflow storage for visual pipeline builder."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = Path("./data/workflows.json")
SCHEMA_VERSION = 2
_GOV_NODE_TYPES = {"agent", "a2a", "router", "gateway"}
_GOV_RISK_LEVELS = {"low", "medium", "high", "critical"}


class WorkflowStore:
    """CRUD operations for visual workflows stored as JSON.

    Args:
        store_path: Path to the JSON file.
    """

    def __init__(self, store_path: Path | None = None) -> None:
        self.store_path = store_path or DEFAULT_STORE_PATH
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self._save([])

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
        workflows = self._load()
        normalized_nodes = [self._normalize_node(node) for node in nodes]

        if workflow_id:
            for wf in workflows:
                if wf["id"] == workflow_id:
                    wf["name"] = name
                    wf["nodes"] = normalized_nodes
                    wf["edges"] = edges
                    wf["schema_version"] = SCHEMA_VERSION
                    wf["updated_at"] = datetime.now().isoformat()
                    self._save(workflows)
                    return wf
            # Not found, create new with this id
            workflow_id = None

        workflow = {
            "id": workflow_id or str(uuid.uuid4())[:8],
            "name": name,
            "nodes": normalized_nodes,
            "edges": edges,
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "last_run": None,
            "run_count": 0,
        }
        workflows.append(workflow)
        self._save(workflows)
        logger.info("Saved workflow %s: %s", workflow["id"], name)
        return workflow

    def get(self, workflow_id: str) -> dict | None:
        """Get a workflow by ID.

        Args:
            workflow_id: Workflow ID.

        Returns:
            Workflow dict or None.
        """
        for wf in self._load():
            if wf["id"] == workflow_id:
                return self._normalize_workflow(wf)
        return None

    def list_all(self) -> list[dict]:
        """List all workflows (newest first).

        Returns:
            List of workflow summary dicts.
        """
        workflows = [self._normalize_workflow(w) for w in self._load()]
        return sorted(
            workflows, key=lambda w: w.get("updated_at", ""), reverse=True
        )

    def delete(self, workflow_id: str) -> bool:
        """Delete a workflow.

        Args:
            workflow_id: Workflow ID.

        Returns:
            True if deleted, False if not found.
        """
        workflows = self._load()
        original = len(workflows)
        workflows = [w for w in workflows if w["id"] != workflow_id]
        if len(workflows) < original:
            self._save(workflows)
            return True
        return False

    def mark_run(self, workflow_id: str) -> None:
        """Mark a workflow as having been run.

        Args:
            workflow_id: Workflow ID.
        """
        workflows = self._load()
        for wf in workflows:
            if wf["id"] == workflow_id:
                wf["last_run"] = datetime.now().isoformat()
                wf["run_count"] = wf.get("run_count", 0) + 1
                break
        self._save(workflows)

    def to_pipeline_config(self, workflow_id: str) -> dict | None:
        """Convert a workflow to PipelineExecutor-compatible config.

        Transforms React Flow nodes/edges into pipeline YAML format
        with steps and depends_on.

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

        # Build dependency map: target_node_id -> [source_node_ids]
        deps: dict[str, list[str]] = {}
        for edge in edges:
            target = edge["target"]
            source = edge["source"]
            deps.setdefault(target, []).append(source)

        # Node ID -> step name mapping
        node_names: dict[str, str] = {}
        for node in nodes:
            node_names[node["id"]] = node.get("data", {}).get(
                "label", node["id"]
            ).lower().replace(" ", "_")

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

            # Add depends_on from edges
            node_deps = deps.get(node["id"], [])
            if node_deps:
                step["depends_on"] = [node_names[d] for d in node_deps]

            steps.append(step)

        return {
            "pipeline": {"name": wf["name"]},
            "steps": steps,
        }

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

    def _normalize_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(workflow)
        normalized["schema_version"] = normalized.get("schema_version", 1)
        nodes = normalized.get("nodes", [])
        normalized["nodes"] = [self._normalize_node(node) for node in nodes]
        return normalized

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

    def _load(self) -> list[dict]:
        with open(self.store_path, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, workflows: list[dict]) -> None:
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(workflows, f, ensure_ascii=False, indent=2)
