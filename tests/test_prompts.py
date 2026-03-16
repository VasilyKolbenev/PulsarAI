"""Tests for versioned prompt store and API routes."""

from pathlib import Path

import pytest

from pulsar_ai.storage.database import Database
from pulsar_ai.prompts.store import PromptStore

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


@pytest.fixture
def store(db: Database) -> PromptStore:
    return PromptStore(db=db)


SAMPLE_PROMPT = "You are a {{role}}. Help the user with {{task}}."


# ── PromptStore Unit Tests ──────────────────────────────────────────────


class TestPromptStore:
    def test_init_creates_empty_store(self, db: Database) -> None:
        s = PromptStore(db=db)
        assert s.list_all() == []

    def test_create_prompt(self, store: PromptStore) -> None:
        p = store.create("Test Prompt", SAMPLE_PROMPT, description="A test")
        assert p["name"] == "Test Prompt"
        assert p["description"] == "A test"
        assert p["current_version"] == 1
        assert len(p["versions"]) == 1
        assert p["versions"][0]["system_prompt"] == SAMPLE_PROMPT
        assert p["versions"][0]["version"] == 1

    def test_extract_variables(self, store: PromptStore) -> None:
        p = store.create("Vars", SAMPLE_PROMPT)
        assert sorted(p["versions"][0]["variables"]) == ["role", "task"]

    def test_extract_no_variables(self, store: PromptStore) -> None:
        p = store.create("No Vars", "Plain prompt without variables")
        assert p["versions"][0]["variables"] == []

    def test_create_with_tags(self, store: PromptStore) -> None:
        p = store.create("Tagged", "Prompt", tags=["agent", "production"])
        assert p["tags"] == ["agent", "production"]

    def test_create_with_model_and_params(self, store: PromptStore) -> None:
        p = store.create("Config", "Prompt", model="gpt-4", parameters={"temperature": 0.7})
        v = p["versions"][0]
        assert v["model"] == "gpt-4"
        assert v["parameters"]["temperature"] == 0.7

    def test_get_prompt(self, store: PromptStore) -> None:
        p = store.create("Get Me", "Prompt")
        got = store.get(p["id"])
        assert got is not None
        assert got["name"] == "Get Me"

    def test_get_returns_none(self, store: PromptStore) -> None:
        assert store.get("nope") is None

    def test_list_all_empty(self, store: PromptStore) -> None:
        assert store.list_all() == []

    def test_list_all_sorted_newest_first(self, store: PromptStore) -> None:
        store.create("A", "first")
        store.create("B", "second")
        store.create("C", "third")
        names = [p["name"] for p in store.list_all()]
        assert names == ["C", "B", "A"]

    def test_list_by_tag(self, store: PromptStore) -> None:
        store.create("Agent", "p1", tags=["agent"])
        store.create("Training", "p2", tags=["training"])
        store.create("Both", "p3", tags=["agent", "training"])
        agent_prompts = store.list_all(tag="agent")
        names = [p["name"] for p in agent_prompts]
        assert "Agent" in names
        assert "Both" in names
        assert "Training" not in names

    def test_update_metadata(self, store: PromptStore) -> None:
        p = store.create("Original", "Prompt")
        updated = store.update(p["id"], name="Renamed", tags=["new"])
        assert updated is not None
        assert updated["name"] == "Renamed"
        assert updated["tags"] == ["new"]

    def test_update_nonexistent(self, store: PromptStore) -> None:
        assert store.update("nope", name="X") is None

    def test_delete(self, store: PromptStore) -> None:
        p = store.create("Delete Me", "Prompt")
        assert store.delete(p["id"]) is True
        assert store.get(p["id"]) is None

    def test_delete_nonexistent(self, store: PromptStore) -> None:
        assert store.delete("nope") is False


class TestPromptVersioning:
    def test_add_version(self, store: PromptStore) -> None:
        p = store.create("Versioned", "V1 prompt")
        v = store.add_version(p["id"], "V2 prompt with {{input}}")
        assert v is not None
        assert v["version"] == 2
        assert v["variables"] == ["input"]

        updated = store.get(p["id"])
        assert updated is not None
        assert updated["current_version"] == 2
        assert len(updated["versions"]) == 2

    def test_add_version_inherits_model(self, store: PromptStore) -> None:
        p = store.create("Inherit", "V1", model="llama-3")
        v = store.add_version(p["id"], "V2")
        assert v is not None
        assert v["model"] == "llama-3"

    def test_add_version_overrides_model(self, store: PromptStore) -> None:
        p = store.create("Override", "V1", model="llama-3")
        v = store.add_version(p["id"], "V2", model="gpt-4")
        assert v is not None
        assert v["model"] == "gpt-4"

    def test_add_version_nonexistent(self, store: PromptStore) -> None:
        assert store.add_version("nope", "text") is None

    def test_get_version(self, store: PromptStore) -> None:
        p = store.create("Multi", "V1")
        store.add_version(p["id"], "V2")
        store.add_version(p["id"], "V3")

        v1 = store.get_version(p["id"], 1)
        v3 = store.get_version(p["id"], 3)
        assert v1 is not None
        assert v1["system_prompt"] == "V1"
        assert v3 is not None
        assert v3["system_prompt"] == "V3"

    def test_get_version_not_found(self, store: PromptStore) -> None:
        p = store.create("One", "V1")
        assert store.get_version(p["id"], 99) is None
        assert store.get_version("nope", 1) is None

    def test_diff_versions(self, store: PromptStore) -> None:
        p = store.create("Diff", "Hello {{name}}")
        store.add_version(p["id"], "Hello {{name}}, welcome to {{place}}")
        d = store.diff_versions(p["id"], 1, 2)
        assert d is not None
        assert d["v1"] == 1
        assert d["v2"] == 2
        assert "diff" in d
        assert "-Hello {{name}}" in d["diff"] or "Hello" in d["diff"]
        assert d["variables_added"] == ["place"]
        assert d["variables_removed"] == []

    def test_diff_nonexistent_version(self, store: PromptStore) -> None:
        p = store.create("Diff Fail", "V1")
        assert store.diff_versions(p["id"], 1, 99) is None

    def test_version_sequence(self, store: PromptStore) -> None:
        p = store.create("Seq", "V1")
        for i in range(2, 6):
            v = store.add_version(p["id"], f"V{i}")
            assert v is not None
            assert v["version"] == i
        assert store.get(p["id"])["current_version"] == 5
        assert len(store.get(p["id"])["versions"]) == 5


# ── API Route Tests ────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path: Path):
    """Create test client with isolated prompt store."""
    from fastapi.testclient import TestClient

    from pulsar_ai.ui.routes import prompts as prompts_module

    original_store = prompts_module._store
    test_db = Database(tmp_path / "test_api.db")
    prompts_module._store = PromptStore(db=test_db)
    try:
        from pulsar_ai.ui.app import create_app

        app = create_app()
        yield TestClient(app)
    finally:
        prompts_module._store = original_store


class TestPromptAPI:
    def test_list_empty(self, client) -> None:
        resp = client.get("/api/v1/prompts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_and_get(self, client) -> None:
        resp = client.post(
            "/api/v1/prompts",
            json={
                "name": "API Prompt",
                "system_prompt": "You are {{role}}",
                "tags": ["test"],
            },
        )
        assert resp.status_code == 200
        p = resp.json()
        assert p["name"] == "API Prompt"
        assert p["versions"][0]["variables"] == ["role"]

        resp2 = client.get(f"/api/v1/prompts/{p['id']}")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "API Prompt"

    def test_get_nonexistent(self, client) -> None:
        assert client.get("/api/v1/prompts/nope").status_code == 404

    def test_update_metadata(self, client) -> None:
        resp = client.post("/api/v1/prompts", json={"name": "V1", "system_prompt": "text"})
        pid = resp.json()["id"]

        resp2 = client.put(
            f"/api/v1/prompts/{pid}", json={"name": "V1 Renamed", "tags": ["renamed"]}
        )
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "V1 Renamed"

    def test_delete(self, client) -> None:
        resp = client.post("/api/v1/prompts", json={"name": "Del", "system_prompt": "x"})
        pid = resp.json()["id"]

        assert client.delete(f"/api/v1/prompts/{pid}").status_code == 200
        assert client.get(f"/api/v1/prompts/{pid}").status_code == 404

    def test_delete_nonexistent(self, client) -> None:
        assert client.delete("/api/v1/prompts/nope").status_code == 404

    def test_add_version(self, client) -> None:
        resp = client.post("/api/v1/prompts", json={"name": "Ver", "system_prompt": "V1"})
        pid = resp.json()["id"]

        resp2 = client.post(
            f"/api/v1/prompts/{pid}/versions", json={"system_prompt": "V2 with {{var}}"}
        )
        assert resp2.status_code == 200
        assert resp2.json()["version"] == 2
        assert resp2.json()["variables"] == ["var"]

    def test_get_specific_version(self, client) -> None:
        resp = client.post("/api/v1/prompts", json={"name": "Ver", "system_prompt": "V1"})
        pid = resp.json()["id"]
        client.post(f"/api/v1/prompts/{pid}/versions", json={"system_prompt": "V2"})

        resp2 = client.get(f"/api/v1/prompts/{pid}/versions/1")
        assert resp2.status_code == 200
        assert resp2.json()["system_prompt"] == "V1"

    def test_diff_versions(self, client) -> None:
        resp = client.post(
            "/api/v1/prompts", json={"name": "Diff", "system_prompt": "Hello {{name}}"}
        )
        pid = resp.json()["id"]
        client.post(
            f"/api/v1/prompts/{pid}/versions",
            json={"system_prompt": "Hi {{name}}, welcome to {{place}}"},
        )

        resp2 = client.get(f"/api/v1/prompts/{pid}/diff?v1=1&v2=2")
        assert resp2.status_code == 200
        d = resp2.json()
        assert d["variables_added"] == ["place"]

    def test_test_prompt_renders(self, client) -> None:
        resp = client.post(
            "/api/v1/prompts",
            json={"name": "Test", "system_prompt": "Hello {{name}}, you are {{role}}"},
        )
        pid = resp.json()["id"]

        resp2 = client.post(
            f"/api/v1/prompts/{pid}/test", json={"variables": {"name": "Alice", "role": "admin"}}
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["rendered"] == "Hello Alice, you are admin"
        assert data["variables_missing"] == []

    def test_test_prompt_missing_vars(self, client) -> None:
        resp = client.post(
            "/api/v1/prompts", json={"name": "Test", "system_prompt": "{{a}} and {{b}}"}
        )
        pid = resp.json()["id"]

        resp2 = client.post(f"/api/v1/prompts/{pid}/test", json={"variables": {"a": "yes"}})
        assert resp2.status_code == 200
        assert resp2.json()["variables_missing"] == ["b"]

    def test_list_by_tag(self, client) -> None:
        client.post("/api/v1/prompts", json={"name": "A", "system_prompt": "x", "tags": ["agent"]})
        client.post(
            "/api/v1/prompts", json={"name": "B", "system_prompt": "y", "tags": ["training"]}
        )

        resp = client.get("/api/v1/prompts?tag=agent")
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "A"
