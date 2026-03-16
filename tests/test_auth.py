"""Tests for API key authentication."""

import pytest
from pathlib import Path

from pulsar_ai.storage.database import Database
from pulsar_ai.ui.auth import ApiKeyStore


class TestApiKeyStore:
    """Tests for ApiKeyStore."""

    @pytest.fixture
    def db(self, tmp_path: Path) -> Database:
        return Database(tmp_path / "test.db")

    @pytest.fixture
    def store(self, db: Database) -> ApiKeyStore:
        return ApiKeyStore(db=db)

    def test_generate_key_returns_pulsar_prefix(self, store: ApiKeyStore):
        key = store.generate_key("test")
        assert key.startswith("pulsar_")
        assert len(key) > 20

    def test_verify_valid_key(self, store: ApiKeyStore):
        key = store.generate_key("test")
        assert store.verify(key) is True

    def test_verify_invalid_key(self, store: ApiKeyStore):
        store.generate_key("test")
        assert store.verify("forge_invalid_key") is False

    def test_verify_empty_store(self, store: ApiKeyStore):
        assert store.verify("forge_anything") is False

    def test_list_keys_shows_names(self, store: ApiKeyStore):
        store.generate_key("alpha")
        store.generate_key("beta")
        names = [k["name"] for k in store.list_keys()]
        assert "alpha" in names
        assert "beta" in names

    def test_revoke_key(self, store: ApiKeyStore):
        key = store.generate_key("deleteme")
        assert store.verify(key) is True
        assert store.revoke("deleteme") is True
        assert store.verify(key) is False

    def test_revoke_nonexistent_returns_false(self, store: ApiKeyStore):
        assert store.revoke("ghost") is False

    def test_multiple_keys_independent(self, store: ApiKeyStore):
        key1 = store.generate_key("first")
        key2 = store.generate_key("second")
        store.revoke("first")
        assert store.verify(key1) is False
        assert store.verify(key2) is True


class TestApiKeyMiddleware:
    """Tests for auth middleware via FastAPI TestClient."""

    @pytest.fixture
    def auth_app(self, tmp_path: Path):
        from fastapi import FastAPI
        from pulsar_ai.ui.auth import ApiKeyMiddleware, ApiKeyStore

        key_store = ApiKeyStore(db=Database(tmp_path / "auth.db"))
        app = FastAPI()
        app.add_middleware(ApiKeyMiddleware, key_store=key_store, enabled=True)

        @app.get("/api/v1/health")
        async def health():
            return {"status": "ok"}

        @app.get("/api/v1/data")
        async def data():
            return {"data": "secret"}

        return app, key_store

    @pytest.fixture
    def client(self, auth_app):
        from fastapi.testclient import TestClient

        app, _ = auth_app
        return TestClient(app)

    def test_health_endpoint_public(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_protected_endpoint_no_key_returns_401(self, client):
        resp = client.get("/api/v1/data")
        assert resp.status_code == 401

    def test_protected_endpoint_invalid_key_returns_403(self, client):
        resp = client.get(
            "/api/v1/data",
            headers={"Authorization": "Bearer forge_bad_key"},
        )
        assert resp.status_code == 403

    def test_protected_endpoint_valid_key(self, auth_app):
        from fastapi.testclient import TestClient

        app, key_store = auth_app
        key = key_store.generate_key("test")
        client = TestClient(app)
        resp = client.get(
            "/api/v1/data",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == "secret"

    def test_disabled_middleware_allows_all(self, tmp_path: Path):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from pulsar_ai.ui.auth import ApiKeyMiddleware, ApiKeyStore

        key_store = ApiKeyStore(db=Database(tmp_path / "disabled.db"))
        app = FastAPI()
        app.add_middleware(ApiKeyMiddleware, key_store=key_store, enabled=False)

        @app.get("/api/v1/data")
        async def data():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/api/v1/data")
        assert resp.status_code == 200
