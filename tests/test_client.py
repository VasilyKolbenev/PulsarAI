"""Tests for agent ModelClient."""

import json
from unittest.mock import MagicMock, patch

import pytest

from pulsar_ai.agent.client import ModelClient


def _make_chat_response(
    content: str = "Hello!",
    tool_calls: list | None = None,
) -> dict:
    """Build a mock OpenAI chat completion response."""
    message: dict = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "choices": [{"message": message}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


class TestModelClient:
    """Tests for ModelClient."""

    def test_init_defaults(self) -> None:
        client = ModelClient()
        assert client.base_url == "http://localhost:8080/v1"
        assert client.model == "default"
        assert client.timeout == 120

    def test_init_custom(self) -> None:
        client = ModelClient(
            base_url="http://my-server:9000/v1/",
            model="my-model",
            timeout=30,
        )
        assert client.base_url == "http://my-server:9000/v1"
        assert client.model == "my-model"

    @patch("pulsar_ai.agent.client.requests.Session.post")
    def test_chat_basic(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_chat_response("Hi there!")
        mock_post.return_value = mock_response

        client = ModelClient()
        result = client.chat([{"role": "user", "content": "Hello"}])

        assert result["content"] == "Hi there!"
        assert result["role"] == "assistant"
        assert "usage" in result

    @patch("pulsar_ai.agent.client.requests.Session.post")
    def test_chat_with_tool_calls(self, mock_post: MagicMock) -> None:
        tool_calls = [
            {
                "function": {
                    "name": "search",
                    "arguments": json.dumps({"query": "test"}),
                }
            }
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_chat_response(content="", tool_calls=tool_calls)
        mock_post.return_value = mock_response

        client = ModelClient()
        result = client.chat(
            [{"role": "user", "content": "Search for test"}],
            tools=[{"type": "function", "function": {"name": "search"}}],
        )

        assert "tool_calls" in result
        assert result["tool_calls"][0]["name"] == "search"
        assert result["tool_calls"][0]["arguments"] == {"query": "test"}

    @patch("pulsar_ai.agent.client.requests.Session.post")
    def test_chat_api_error(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        client = ModelClient()
        with pytest.raises(RuntimeError, match="API error 500"):
            client.chat([{"role": "user", "content": "Hello"}])

    @patch("pulsar_ai.agent.client.requests.Session.post")
    def test_chat_connection_error(self, mock_post: MagicMock) -> None:
        import requests

        mock_post.side_effect = requests.ConnectionError("refused")

        client = ModelClient()
        with pytest.raises(ConnectionError, match="Cannot connect"):
            client.chat([{"role": "user", "content": "Hello"}])

    @patch("pulsar_ai.agent.client.requests.Session.get")
    def test_health_check_healthy(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        client = ModelClient()
        assert client.health_check() is True

    @patch("pulsar_ai.agent.client.requests.Session.get")
    def test_health_check_unhealthy(self, mock_get: MagicMock) -> None:
        import requests

        mock_get.side_effect = requests.ConnectionError("refused")

        client = ModelClient()
        assert client.health_check() is False

    def test_repr(self) -> None:
        client = ModelClient(base_url="http://localhost:8080/v1", model="test")
        assert "localhost:8080" in repr(client)
        assert "test" in repr(client)
