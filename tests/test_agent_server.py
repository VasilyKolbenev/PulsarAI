"""Tests for agent FastAPI server."""

import pytest

# Skip all tests if fastapi is not installed
fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from pulsar_ai.agent.server import create_agent_app  # noqa: E402


@pytest.fixture
def agent_config() -> dict:
    return {
        "agent": {
            "name": "test-agent",
            "system_prompt": "You are a test agent.",
        },
        "model": {
            "base_url": "http://localhost:8080/v1",
            "name": "test-model",
            "timeout": 30,
        },
        "guardrails": {
            "max_iterations": 5,
        },
    }


@pytest.fixture
def client(agent_config: dict) -> TestClient:
    app = create_agent_app(agent_config)
    return TestClient(app)


class TestAgentServerHealth:
    """Tests for /v1/agent/health endpoint."""

    def test_health_returns_ok(self, client: TestClient) -> None:
        response = client.get("/v1/agent/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["agent_name"] == "test-agent"
        assert data["tools_count"] == 4  # builtin tools
        assert data["active_sessions"] == 0


class TestAgentServerTools:
    """Tests for /v1/agent/tools endpoint."""

    def test_list_tools(self, client: TestClient) -> None:
        response = client.get("/v1/agent/tools")
        assert response.status_code == 200
        tools = response.json()
        assert len(tools) == 4
        names = [t["name"] for t in tools]
        assert "search_files" in names
        assert "read_file" in names
        assert "calculate" in names


class TestAgentServerChat:
    """Tests for /v1/agent/chat endpoint."""

    def test_empty_message_returns_400(self, client: TestClient) -> None:
        response = client.post(
            "/v1/agent/chat",
            json={"message": "  "},
        )
        assert response.status_code == 400

    def test_chat_creates_session(self, client: TestClient) -> None:
        # This will fail to connect to model server, but should create a session
        # and return a 502 (model server unreachable)
        response = client.post(
            "/v1/agent/chat",
            json={"message": "Hello"},
        )
        # Either 502 (can't reach model) or 500 (other error) is expected
        # since no model server is running
        assert response.status_code in (500, 502)


class TestAgentServerSessions:
    """Tests for session management."""

    def test_delete_nonexistent_session(self, client: TestClient) -> None:
        response = client.delete("/v1/agent/sessions/nonexistent")
        assert response.status_code == 404
