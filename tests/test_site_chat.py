"""Tests for landing page chat proxy endpoint."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from pulsar_ai.storage.database import Database
from pulsar_ai.storage.session_store import SessionStore
from pulsar_ai.ui.routes import site_chat


@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path):
    """Swap site_chat's session store with a temp DB for test isolation."""
    db = Database(tmp_path / "site_chat_test.db")
    original = site_chat._session_store
    site_chat._session_store = SessionStore(db=db)
    site_chat._rate_limits.clear()
    yield db
    site_chat._session_store = original
    site_chat._rate_limits.clear()


@pytest.fixture()
def client():
    """Create test client with site_chat router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(site_chat.router, prefix="/api/v1")
    return TestClient(app)


class TestSiteChatEndpoint:
    """Tests for POST /api/v1/site/chat."""

    def test_chat_empty_message_rejected(self, client: TestClient):
        """Empty message should return 400."""
        resp = client.post("/api/v1/site/chat", json={"message": ""})
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_chat_whitespace_only_rejected(self, client: TestClient):
        """Whitespace-only message should return 400."""
        resp = client.post("/api/v1/site/chat", json={"message": "   "})
        assert resp.status_code == 400

    def test_chat_no_api_key_fallback(self, client: TestClient):
        """Without OPENAI_API_KEY, should return fallback message."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            resp = client.post(
                "/api/v1/site/chat",
                json={"message": "What is Pulsar AI?"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "consultation form" in data["reply"].lower() or "api key" in data["reply"].lower()

    def test_chat_generates_session_id(self, client: TestClient):
        """Should generate session_id if not provided."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            resp = client.post(
                "/api/v1/site/chat",
                json={"message": "Hello"},
            )
        data = resp.json()
        assert data["session_id"]
        assert len(data["session_id"]) > 10  # UUID format

    def test_chat_reuses_session_id(self, client: TestClient):
        """Should reuse provided session_id."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            resp = client.post(
                "/api/v1/site/chat",
                json={"message": "Hello", "session_id": "my-session-123"},
            )
        assert resp.json()["session_id"] == "my-session-123"

    def test_chat_session_persistence(self, client: TestClient):
        """Messages should accumulate in session history via SQLite."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            resp1 = client.post(
                "/api/v1/site/chat",
                json={"message": "First message"},
            )
            sid = resp1.json()["session_id"]
            client.post(
                "/api/v1/site/chat",
                json={"message": "Second message", "session_id": sid},
            )
        # Should have 4 messages (2 user + 2 assistant fallbacks)
        msgs = site_chat._session_store.get_messages(sid)
        assert len(msgs) == 4

    @patch("pulsar_ai.ui.routes.site_chat._call_openai", new_callable=AsyncMock)
    def test_chat_returns_reply(self, mock_openai: AsyncMock, client: TestClient):
        """With API key, should call OpenAI and return reply."""
        mock_openai.return_value = "Pulsar AI is an amazing platform!"
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test123"}, clear=False):
            resp = client.post(
                "/api/v1/site/chat",
                json={"message": "Tell me about Pulsar AI"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] == "Pulsar AI is an amazing platform!"
        mock_openai.assert_called_once()

    @patch("pulsar_ai.ui.routes.site_chat._call_openai", new_callable=AsyncMock)
    def test_chat_sends_history_to_openai(self, mock_openai: AsyncMock, client: TestClient):
        """Should include conversation history when calling OpenAI."""
        mock_openai.return_value = "Reply"
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
            resp1 = client.post(
                "/api/v1/site/chat",
                json={"message": "First"},
            )
            sid = resp1.json()["session_id"]
            client.post(
                "/api/v1/site/chat",
                json={"message": "Second", "session_id": sid},
            )
        # Second call should include system + first user + first assistant + second user
        call_args = mock_openai.call_args_list[1]
        messages = call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "First"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "Second"


class TestSessionManagement:
    """Tests for session history management."""

    def test_max_history_trim(self, client: TestClient, _use_temp_db):
        """Session history should be trimmed to MAX_HISTORY."""
        sid = "trim-test"
        # Pre-fill with many messages via store
        store = site_chat._session_store
        store.get_or_create(sid, session_type="site_chat")
        msgs = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg-{i}"}
            for i in range(30)
        ]
        store.set_messages(sid, msgs)

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            client.post(
                "/api/v1/site/chat",
                json={"message": "New message", "session_id": sid},
            )
        # After trim + new user + assistant reply, should be <= MAX_HISTORY
        final_msgs = store.get_messages(sid)
        # Each append_message call trims to MAX_HISTORY (20)
        assert len(final_msgs) <= site_chat.MAX_HISTORY + 2


class TestRateLimiting:
    """Tests for chat rate limiting."""

    def test_rate_limit_allows_normal_usage(self, client: TestClient):
        """Normal usage should not trigger rate limit."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            for _ in range(5):
                resp = client.post(
                    "/api/v1/site/chat",
                    json={"message": "Hello", "session_id": "rate-test"},
                )
                assert resp.status_code == 200

    def test_rate_limit_blocks_excessive_requests(self, client: TestClient):
        """Exceeding rate limit should return 429."""
        sid = "rate-block-test"
        # Pre-fill rate limit timestamps
        now = time.time()
        site_chat._rate_limits[sid] = [now - i for i in range(site_chat.RATE_LIMIT)]

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            resp = client.post(
                "/api/v1/site/chat",
                json={"message": "Hello", "session_id": sid},
            )
        assert resp.status_code == 429
        assert "too many" in resp.json()["detail"].lower()

    def test_rate_limit_window_expires(self, client: TestClient):
        """Old rate limit entries should expire."""
        sid = "rate-expire-test"
        # Pre-fill with old timestamps (older than window)
        old_time = time.time() - site_chat.RATE_WINDOW - 10
        site_chat._rate_limits[sid] = [old_time] * site_chat.RATE_LIMIT

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            resp = client.post(
                "/api/v1/site/chat",
                json={"message": "Hello", "session_id": sid},
            )
        assert resp.status_code == 200


class TestChatStatus:
    """Tests for GET /api/v1/site/chat/status."""

    def test_status_without_key(self, client: TestClient):
        """Should report unavailable without API key."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            resp = client.get("/api/v1/site/chat/status")
        data = resp.json()
        assert data["available"] is False
        assert data["model"] is None

    def test_status_with_key(self, client: TestClient):
        """Should report available with API key."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
            resp = client.get("/api/v1/site/chat/status")
        data = resp.json()
        assert data["available"] is True
        assert data["model"] == "gpt-4o-mini"

    def test_status_tracks_sessions(self, client: TestClient):
        """Should count active site_chat sessions."""
        store = site_chat._session_store
        store.get_or_create("a", session_type="site_chat")
        store.get_or_create("b", session_type="site_chat")
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            resp = client.get("/api/v1/site/chat/status")
        assert resp.json()["active_sessions"] == 2


class TestSystemPrompt:
    """Tests for system prompt content."""

    def test_system_prompt_contains_product_info(self):
        """System prompt should contain key product information."""
        prompt = site_chat.SYSTEM_PROMPT
        assert "Pulsar AI" in prompt
        assert "26" in prompt  # node types
        assert "MCP" in prompt
        assert "A2A" in prompt
        assert "Guardrails" in prompt
        assert "fine-tune" in prompt.lower() or "fine-tuning" in prompt.lower()

    def test_system_prompt_contains_pricing(self):
        """System prompt should contain pricing/deployment information."""
        prompt = site_chat.SYSTEM_PROMPT
        assert "$49" in prompt
        assert "Cloud" in prompt or "SaaS" in prompt
        assert "Self-Hosted" in prompt

    def test_system_prompt_multilingual_instruction(self):
        """System prompt should instruct to respond in user's language."""
        prompt = site_chat.SYSTEM_PROMPT
        assert "same language" in prompt.lower()


class TestOpenAICall:
    """Tests for OpenAI API call function."""

    @pytest.mark.anyio
    async def test_call_openai_no_key(self):
        """Should raise 503 without API key."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await site_chat._call_openai([{"role": "user", "content": "test"}])
            assert exc_info.value.status_code == 503

    @pytest.mark.anyio
    async def test_call_openai_success(self):
        """Should return reply from OpenAI API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test reply"}}]}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with (
            patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await site_chat._call_openai([{"role": "user", "content": "test"}])
        assert result == "Test reply"
