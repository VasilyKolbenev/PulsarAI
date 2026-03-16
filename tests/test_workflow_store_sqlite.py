"""Tests for SQLite-backed WorkflowStore."""

import pytest
from pulsar_ai.storage.database import Database
from pulsar_ai.ui.workflow_store import WorkflowStore


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def store(db):
    return WorkflowStore(db=db)


def test_create_and_get_workflow(store):
    result = store.save(name="test-wf", nodes=[{"id": "n1"}], edges=[])
    wf_id = result["id"]
    wf = store.get(wf_id)
    assert wf is not None
    assert wf["name"] == "test-wf"
    assert len(wf["nodes"]) == 1


def test_list_workflows(store):
    store.save(name="wf1", nodes=[], edges=[])
    store.save(name="wf2", nodes=[], edges=[])
    workflows = store.list_all()
    assert len(workflows) == 2


def test_delete_workflow(store):
    result = store.save(name="to-delete", nodes=[], edges=[])
    wf_id = result["id"]
    assert store.delete(wf_id) is True
    assert store.get(wf_id) is None


def test_update_workflow(store):
    result = store.save(name="original", nodes=[], edges=[])
    wf_id = result["id"]
    store.save(name="updated", nodes=[{"id": "n1"}], edges=[], workflow_id=wf_id)
    wf = store.get(wf_id)
    assert wf["name"] == "updated"
    assert len(wf["nodes"]) == 1


def test_mark_run(store):
    result = store.save(name="runnable", nodes=[], edges=[])
    wf_id = result["id"]
    store.mark_run(wf_id)
    wf = store.get(wf_id)
    assert wf["run_count"] == 1
    assert wf["last_run"] is not None


def test_to_pipeline_config(store):
    nodes = [
        {"id": "src", "type": "dataSource", "data": {"label": "My Data", "config": {}}},
        {"id": "mdl", "type": "model", "data": {"label": "Model", "config": {}}},
    ]
    edges = [{"id": "e1", "source": "src", "target": "mdl"}]
    result = store.save(name="pipe-wf", nodes=nodes, edges=edges)
    wf_id = result["id"]
    config = store.to_pipeline_config(wf_id)
    assert config is not None
    assert config["pipeline"]["name"] == "pipe-wf"
    assert len(config["steps"]) == 2
    assert config["steps"][1]["depends_on"] == ["my_data"]


def test_delete_nonexistent(store):
    assert store.delete("nonexistent") is False


def test_get_nonexistent(store):
    assert store.get("nonexistent") is None


def test_governance_normalization(store):
    nodes = [
        {
            "id": "a1",
            "type": "agent",
            "data": {"label": "Agent", "config": {}},
        }
    ]
    result = store.save(name="gov-wf", nodes=nodes, edges=[])
    wf = store.get(result["id"])
    agent_config = wf["nodes"][0]["data"]["config"]
    assert agent_config["agent_role"] == ""
    assert agent_config["risk_level"] == "medium"
    assert agent_config["requires_approval"] is False
