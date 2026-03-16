"""Tests for workflow store and API routes."""

from pathlib import Path

import pytest

from pulsar_ai.storage.database import Database
from pulsar_ai.ui.workflow_store import WorkflowStore

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


@pytest.fixture
def store(db: Database) -> WorkflowStore:
    return WorkflowStore(db=db)


SAMPLE_NODES = [
    {
        "id": "n1",
        "type": "dataSource",
        "data": {"label": "My Dataset", "config": {"path": "/data/train.jsonl"}},
    },
    {
        "id": "n2",
        "type": "model",
        "data": {"label": "Base Model", "config": {"model_id": "meta-llama/Llama-3-8B"}},
    },
    {
        "id": "n3",
        "type": "training",
        "data": {"label": "SFT Train", "config": {"task": "sft", "lr": 2e-5}},
    },
]

SAMPLE_EDGES = [
    {"id": "e1", "source": "n1", "target": "n3"},
    {"id": "e2", "source": "n2", "target": "n3"},
]


# ── WorkflowStore Unit Tests ───────────────────────────────────────────


class TestWorkflowStore:
    def test_init_creates_empty_store(self, db: Database) -> None:
        s = WorkflowStore(db=db)
        assert s.list_all() == []

    def test_save_creates_workflow(self, store: WorkflowStore) -> None:
        wf = store.save("Test WF", SAMPLE_NODES, SAMPLE_EDGES)
        assert wf["name"] == "Test WF"
        assert wf["edges"] == SAMPLE_EDGES
        assert "id" in wf
        assert "created_at" in wf
        assert wf["run_count"] == 0
        assert wf["last_run"] is None

    def test_workflow_schema_version_saved(self, store: WorkflowStore) -> None:
        wf = store.save("Schema WF", SAMPLE_NODES, SAMPLE_EDGES)
        assert wf["schema_version"] == 2

    def test_governance_defaults_added_for_agent_nodes(self, store: WorkflowStore) -> None:
        nodes = [
            {
                "id": "agent_1",
                "type": "agent",
                "data": {"label": "Agent", "config": {"framework": "forge-react"}},
            },
        ]
        wf = store.save("Gov Defaults", nodes, [])
        saved_cfg = wf["nodes"][0]["data"]["config"]
        assert saved_cfg["agent_role"] == ""
        assert saved_cfg["risk_level"] == "medium"
        assert saved_cfg["requires_approval"] is False

    def test_governance_risk_level_normalized(self, store: WorkflowStore) -> None:
        nodes = [
            {
                "id": "agent_1",
                "type": "agent",
                "data": {
                    "label": "Agent",
                    "config": {"risk_level": "SEVERE", "requires_approval": 1},
                },
            },
        ]
        wf = store.save("Gov Normalize", nodes, [])
        saved_cfg = wf["nodes"][0]["data"]["config"]
        assert saved_cfg["risk_level"] == "medium"
        assert saved_cfg["requires_approval"] is True

    def test_save_generates_unique_ids(self, store: WorkflowStore) -> None:
        wf1 = store.save("WF1", [], [])
        wf2 = store.save("WF2", [], [])
        assert wf1["id"] != wf2["id"]

    def test_save_update_existing(self, store: WorkflowStore) -> None:
        wf = store.save("Original", SAMPLE_NODES, SAMPLE_EDGES)
        updated = store.save("Updated", [], [], workflow_id=wf["id"])
        assert updated["id"] == wf["id"]
        assert updated["name"] == "Updated"
        assert updated["nodes"] == []
        assert store.list_all() == [updated]

    def test_save_update_nonexistent_creates_new(self, store: WorkflowStore) -> None:
        wf = store.save("New", SAMPLE_NODES, SAMPLE_EDGES, workflow_id="missing")
        assert wf["name"] == "New"
        assert len(store.list_all()) == 1

    def test_get_returns_workflow(self, store: WorkflowStore) -> None:
        wf = store.save("Test", SAMPLE_NODES, SAMPLE_EDGES)
        got = store.get(wf["id"])
        assert got is not None
        assert got["name"] == "Test"

    def test_get_returns_none_for_missing(self, store: WorkflowStore) -> None:
        assert store.get("nonexistent") is None

    def test_list_all_empty(self, store: WorkflowStore) -> None:
        assert store.list_all() == []

    def test_list_all_sorted_by_updated_at(self, store: WorkflowStore) -> None:
        store.save("First", [], [])
        store.save("Second", [], [])
        store.save("Third", [], [])
        names = [w["name"] for w in store.list_all()]
        assert names == ["Third", "Second", "First"]

    def test_delete_existing(self, store: WorkflowStore) -> None:
        wf = store.save("Doomed", [], [])
        assert store.delete(wf["id"]) is True
        assert store.get(wf["id"]) is None

    def test_delete_nonexistent(self, store: WorkflowStore) -> None:
        assert store.delete("nope") is False

    def test_mark_run(self, store: WorkflowStore) -> None:
        wf = store.save("Runnable", SAMPLE_NODES, SAMPLE_EDGES)
        assert wf["run_count"] == 0
        store.mark_run(wf["id"])
        updated = store.get(wf["id"])
        assert updated is not None
        assert updated["run_count"] == 1
        assert updated["last_run"] is not None

    def test_mark_run_increments(self, store: WorkflowStore) -> None:
        wf = store.save("Multi-run", [], [])
        store.mark_run(wf["id"])
        store.mark_run(wf["id"])
        store.mark_run(wf["id"])
        assert store.get(wf["id"])["run_count"] == 3


class TestWorkflowToPipelineConfig:
    def test_simple_pipeline(self, store: WorkflowStore) -> None:
        wf = store.save("Pipeline Test", SAMPLE_NODES, SAMPLE_EDGES)
        config = store.to_pipeline_config(wf["id"])
        assert config is not None
        assert config["pipeline"]["name"] == "Pipeline Test"
        assert len(config["steps"]) == 3

        # Check step types
        step_types = {s["name"]: s["type"] for s in config["steps"]}
        assert step_types["my_dataset"] == "data"
        assert step_types["base_model"] == "model"
        assert step_types["sft_train"] == "training"

    def test_dependencies_from_edges(self, store: WorkflowStore) -> None:
        wf = store.save("Dep Test", SAMPLE_NODES, SAMPLE_EDGES)
        config = store.to_pipeline_config(wf["id"])
        assert config is not None
        training_step = next(s for s in config["steps"] if s["name"] == "sft_train")
        assert "depends_on" in training_step
        assert set(training_step["depends_on"]) == {"my_dataset", "base_model"}

    def test_no_deps_for_source_nodes(self, store: WorkflowStore) -> None:
        wf = store.save("No Deps", SAMPLE_NODES, SAMPLE_EDGES)
        config = store.to_pipeline_config(wf["id"])
        assert config is not None
        dataset_step = next(s for s in config["steps"] if s["name"] == "my_dataset")
        assert "depends_on" not in dataset_step

    def test_config_forwarded(self, store: WorkflowStore) -> None:
        wf = store.save("Config Test", SAMPLE_NODES, SAMPLE_EDGES)
        config = store.to_pipeline_config(wf["id"])
        assert config is not None
        training_step = next(s for s in config["steps"] if s["name"] == "sft_train")
        assert training_step["config"]["task"] == "sft"
        assert training_step["config"]["lr"] == 2e-5

    def test_nonexistent_returns_none(self, store: WorkflowStore) -> None:
        assert store.to_pipeline_config("nope") is None

    def test_node_type_mapping(self, store: WorkflowStore) -> None:
        nodes = [
            {"id": "a", "type": "eval", "data": {"label": "Eval Step", "config": {}}},
            {"id": "b", "type": "export", "data": {"label": "Export Step", "config": {}}},
            {"id": "c", "type": "agent", "data": {"label": "Agent Step", "config": {}}},
            {"id": "d", "type": "prompt", "data": {"label": "Prompt Step", "config": {}}},
            {"id": "e", "type": "conditional", "data": {"label": "Check Step", "config": {}}},
        ]
        wf = store.save("Type Map", nodes, [])
        config = store.to_pipeline_config(wf["id"])
        assert config is not None
        types = {s["name"]: s["type"] for s in config["steps"]}
        assert types["eval_step"] == "evaluation"
        assert types["export_step"] == "export"
        assert types["agent_step"] == "agent"
        assert types["prompt_step"] == "prompt"
        assert types["check_step"] == "conditional"


# ── API Route Tests ────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path: Path):
    """Create test client with isolated workflow store."""
    from fastapi.testclient import TestClient

    from pulsar_ai.ui.routes import workflows as wf_module

    original_store = wf_module._store
    test_db = Database(tmp_path / "test_api.db")
    wf_module._store = WorkflowStore(db=test_db)
    try:
        from pulsar_ai.ui.app import create_app

        app = create_app()
        yield TestClient(app)
    finally:
        wf_module._store = original_store


class TestWorkflowAPI:
    def test_list_templates(self, client) -> None:
        resp = client.get("/api/v1/workflows/templates")
        assert resp.status_code == 200
        templates = resp.json()
        assert isinstance(templates, list)
        assert any(t["id"] == "banking_agentoffice" for t in templates)

    def test_create_from_template(self, client) -> None:
        resp = client.post(
            "/api/v1/workflows/templates/banking_agentoffice/create",
            json={"name": "Banking Template Instance"},
        )
        assert resp.status_code == 200
        wf = resp.json()
        assert wf["name"] == "Banking Template Instance"
        assert len(wf["nodes"]) > 0
        assert len(wf["edges"]) > 0

    def test_create_from_unknown_template(self, client) -> None:
        resp = client.post(
            "/api/v1/workflows/templates/unknown/create",
            json={"name": "Nope"},
        )
        assert resp.status_code == 404

    def test_list_empty(self, client) -> None:
        resp = client.get("/api/v1/workflows")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_save_and_get(self, client) -> None:
        resp = client.post(
            "/api/v1/workflows",
            json={
                "name": "API Test",
                "nodes": SAMPLE_NODES,
                "edges": SAMPLE_EDGES,
            },
        )
        assert resp.status_code == 200
        wf = resp.json()
        assert wf["name"] == "API Test"

        resp2 = client.get(f"/api/v1/workflows/{wf['id']}")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "API Test"

    def test_get_nonexistent(self, client) -> None:
        resp = client.get("/api/v1/workflows/nope")
        assert resp.status_code == 404

    def test_update_workflow(self, client) -> None:
        resp = client.post(
            "/api/v1/workflows",
            json={
                "name": "V1",
                "nodes": [],
                "edges": [],
            },
        )
        wf_id = resp.json()["id"]

        resp2 = client.post(
            "/api/v1/workflows",
            json={
                "name": "V2",
                "nodes": SAMPLE_NODES,
                "edges": SAMPLE_EDGES,
                "workflow_id": wf_id,
            },
        )
        assert resp2.json()["name"] == "V2"
        assert resp2.json()["id"] == wf_id

    def test_delete_workflow(self, client) -> None:
        resp = client.post(
            "/api/v1/workflows",
            json={
                "name": "Delete Me",
                "nodes": [],
                "edges": [],
            },
        )
        wf_id = resp.json()["id"]

        resp2 = client.delete(f"/api/v1/workflows/{wf_id}")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "deleted"

        resp3 = client.get(f"/api/v1/workflows/{wf_id}")
        assert resp3.status_code == 404

    def test_delete_nonexistent(self, client) -> None:
        resp = client.delete("/api/v1/workflows/nope")
        assert resp.status_code == 404

    def test_run_workflow(self, client) -> None:
        resp = client.post(
            "/api/v1/workflows",
            json={
                "name": "Run Me",
                "nodes": SAMPLE_NODES,
                "edges": SAMPLE_EDGES,
            },
        )
        wf_id = resp.json()["id"]

        resp2 = client.post(f"/api/v1/workflows/{wf_id}/run")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["status"] == "started"
        assert "pipeline_config" in data
        assert data["pipeline_config"]["pipeline"]["name"] == "Run Me"

    def test_run_workflow_blocked_by_governance(self, client) -> None:
        risky_nodes = [
            {
                "id": "agent_1",
                "type": "agent",
                "data": {
                    "label": "Risky Decision Agent",
                    "config": {
                        "agent_role": "decision",
                        "risk_level": "critical",
                        "requires_approval": False,
                    },
                },
            }
        ]
        resp = client.post(
            "/api/v1/workflows",
            json={
                "name": "Risky",
                "nodes": risky_nodes,
                "edges": [],
            },
        )
        wf_id = resp.json()["id"]

        resp2 = client.post(f"/api/v1/workflows/{wf_id}/run")
        assert resp2.status_code == 400
        assert "requires_approval=true" in resp2.json()["detail"]

    def test_pipeline_sync_blocked_by_governance(self, client) -> None:
        resp = client.post(
            "/api/v1/pipeline/run/sync",
            json={
                "pipeline_config": {
                    "pipeline": {"name": "Risk Sync"},
                    "steps": [
                        {
                            "name": "decision_agent",
                            "type": "agent",
                            "config": {
                                "risk_level": "high",
                                "requires_approval": False,
                            },
                        }
                    ],
                }
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "blocked"
        assert "requires_approval=true" in body["error"]

    def test_run_nonexistent(self, client) -> None:
        resp = client.post("/api/v1/workflows/nope/run")
        assert resp.status_code == 404

    def test_get_config(self, client) -> None:
        resp = client.post(
            "/api/v1/workflows",
            json={
                "name": "Config Me",
                "nodes": SAMPLE_NODES,
                "edges": SAMPLE_EDGES,
            },
        )
        wf_id = resp.json()["id"]

        resp2 = client.get(f"/api/v1/workflows/{wf_id}/config")
        assert resp2.status_code == 200
        assert resp2.json()["pipeline"]["name"] == "Config Me"

    def test_list_returns_newest_first(self, client) -> None:
        client.post("/api/v1/workflows", json={"name": "A", "nodes": [], "edges": []})
        client.post("/api/v1/workflows", json={"name": "B", "nodes": [], "edges": []})
        client.post("/api/v1/workflows", json={"name": "C", "nodes": [], "edges": []})
        resp = client.get("/api/v1/workflows")
        names = [w["name"] for w in resp.json()]
        assert names == ["C", "B", "A"]
