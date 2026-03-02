"""Model client for OpenAI-compatible local LLM servers."""

import json
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class ModelClient:
    """Client for OpenAI-compatible chat completion APIs.

    Works with llama.cpp server, vLLM, Ollama, and any OpenAI-compatible
    endpoint. Supports both native tool calling and plain text responses.

    Args:
        base_url: Base URL of the API (e.g. "http://localhost:8080/v1").
        model: Model name/identifier for the API.
        timeout: Request timeout in seconds.
        api_key: Optional API key (for OpenAI-compatible servers that require it).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080/v1",
        model: str = "default",
        timeout: int = 120,
        api_key: str = "not-needed",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        })

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.

        Returns:
            Dict with 'content' (str) and optionally 'tool_calls' (list).

        Raises:
            ConnectionError: If the server is unreachable.
            RuntimeError: If the API returns an error.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        url = f"{self.base_url}/chat/completions"

        try:
            response = self._session.post(
                url, json=payload, timeout=self.timeout
            )
        except requests.ConnectionError as e:
            raise ConnectionError(
                f"Cannot connect to model server at {self.base_url}. "
                f"Is the server running? Error: {e}"
            ) from e
        except requests.Timeout as e:
            raise RuntimeError(
                f"Request timed out after {self.timeout}s. "
                f"Consider increasing timeout for complex queries."
            ) from e

        if response.status_code != 200:
            raise RuntimeError(
                f"API error {response.status_code}: {response.text}"
            )

        data = response.json()
        choice = data["choices"][0]
        message = choice["message"]

        result: dict[str, Any] = {
            "content": message.get("content", ""),
            "role": message.get("role", "assistant"),
        }

        # Extract tool calls if present (native tool calling)
        if message.get("tool_calls"):
            result["tool_calls"] = [
                {
                    "id": tc.get("id", ""),
                    "name": tc["function"]["name"],
                    "arguments": json.loads(tc["function"]["arguments"]),
                }
                for tc in message["tool_calls"]
            ]

        # Track usage if available
        if "usage" in data:
            result["usage"] = data["usage"]

        return result

    def health_check(self) -> bool:
        """Check if the model server is reachable.

        Returns:
            True if server responds, False otherwise.
        """
        try:
            resp = self._session.get(
                f"{self.base_url}/models", timeout=5
            )
            return resp.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            return False

    def __repr__(self) -> str:
        return f"ModelClient(base_url='{self.base_url}', model='{self.model}')"
