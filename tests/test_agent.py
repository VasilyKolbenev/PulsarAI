"""Tests for BaseAgent ReAct loop."""

from unittest.mock import MagicMock, patch

import pytest

from pulsar_ai.agent.base import BaseAgent
from pulsar_ai.agent.client import ModelClient
from pulsar_ai.agent.guardrails import GuardrailsConfig
from pulsar_ai.agent.memory import ShortTermMemory
from pulsar_ai.agent.tool import Tool, ToolRegistry


def _make_registry_with_search() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="search",
            description="Search for items",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            func=lambda query: f"Found: {query}",
        )
    )
    return registry


def _mock_client_responses(*responses: dict) -> ModelClient:
    """Create a ModelClient that returns predefined responses."""
    client = MagicMock(spec=ModelClient)
    client.chat = MagicMock(side_effect=list(responses))
    return client


class TestBaseAgentReact:
    """Tests for ReAct text-based agent loop."""

    def test_direct_answer(self) -> None:
        client = _mock_client_responses(
            {"content": "Thought: I know the answer.\nFinal Answer: 42"}
        )
        agent = BaseAgent(
            client=client,
            tools=ToolRegistry(),
            use_native_tools=False,
        )
        result = agent.run("What is the answer?")
        assert result == "42"

    def test_tool_call_then_answer(self) -> None:
        client = _mock_client_responses(
            {
                "content": (
                    "Thought: I need to search.\n"
                    "Action: search\n"
                    'Action Input: {"query": "meaning of life"}'
                )
            },
            {
                "content": (
                    "Thought: I got the result.\n"
                    "Final Answer: The meaning of life is Found: meaning of life"
                )
            },
        )
        registry = _make_registry_with_search()
        agent = BaseAgent(
            client=client,
            tools=registry,
            use_native_tools=False,
        )
        result = agent.run("Search for meaning of life")
        assert "Found: meaning of life" in result

    def test_max_iterations_stops_agent(self) -> None:
        # Agent that never gives a final answer
        client = _mock_client_responses(
            {"content": "Thought: Hmm, let me think..."},
            {"content": "Thought: Still thinking..."},
            {"content": "Thought: Almost there..."},
            # Force final answer response
            {"content": "I cannot complete this task."},
        )
        guardrails = GuardrailsConfig(max_iterations=3)
        agent = BaseAgent(
            client=client,
            tools=ToolRegistry(),
            guardrails=guardrails,
            use_native_tools=False,
        )
        result = agent.run("Do something impossible")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_banned_tool_returns_error(self) -> None:
        client = _mock_client_responses(
            {
                "content": (
                    "Thought: Let me search.\n" "Action: search\n" 'Action Input: {"query": "test"}'
                )
            },
            {"content": "Final Answer: Could not search, tool is banned."},
        )
        registry = _make_registry_with_search()
        guardrails = GuardrailsConfig(banned_tools=["search"])
        agent = BaseAgent(
            client=client,
            tools=registry,
            guardrails=guardrails,
            use_native_tools=False,
        )
        result = agent.run("Search for test")
        assert isinstance(result, str)

    def test_unknown_tool_returns_error(self) -> None:
        client = _mock_client_responses(
            {
                "content": (
                    "Thought: Let me use a tool.\n"
                    "Action: nonexistent\n"
                    'Action Input: {"arg": "val"}'
                )
            },
            {"content": "Final Answer: Tool not available."},
        )
        agent = BaseAgent(
            client=client,
            tools=ToolRegistry(),
            use_native_tools=False,
        )
        result = agent.run("Use nonexistent tool")
        assert isinstance(result, str)

    def test_trace_records_steps(self) -> None:
        client = _mock_client_responses(
            {
                "content": (
                    "Thought: Search time.\n" "Action: search\n" 'Action Input: {"query": "hello"}'
                )
            },
            {"content": "Final Answer: Done."},
        )
        registry = _make_registry_with_search()
        agent = BaseAgent(
            client=client,
            tools=registry,
            use_native_tools=False,
        )
        agent.run("Search hello")

        trace = agent.trace
        assert len(trace) >= 3  # llm_response, tool_call, observation, ...
        tool_calls = [t for t in trace if t["type"] == "tool_call"]
        assert len(tool_calls) == 1
        assert tool_calls[0]["tool"] == "search"


class TestBaseAgentNative:
    """Tests for native tool calling mode."""

    def test_native_tool_call_then_answer(self) -> None:
        client = _mock_client_responses(
            {
                "content": "",
                "tool_calls": [{"name": "search", "arguments": {"query": "test"}}],
            },
            {"content": "Found the result: test"},
        )
        registry = _make_registry_with_search()
        agent = BaseAgent(
            client=client,
            tools=registry,
            use_native_tools=True,
        )
        result = agent.run("Search for test")
        assert result == "Found the result: test"

    def test_native_direct_answer(self) -> None:
        client = _mock_client_responses({"content": "Hello! I can help you."})
        agent = BaseAgent(
            client=client,
            tools=ToolRegistry(),
            use_native_tools=True,
        )
        result = agent.run("Hi")
        assert result == "Hello! I can help you."


class TestBaseAgentFromConfig:
    """Tests for BaseAgent.from_config."""

    def test_from_config_basic(self) -> None:
        config = {
            "model": {
                "base_url": "http://localhost:9000/v1",
                "name": "test-model",
                "timeout": 30,
            },
            "agent": {
                "system_prompt": "You are a test agent.",
            },
            "memory": {
                "max_tokens": 2048,
            },
            "guardrails": {
                "max_iterations": 10,
                "banned_tools": ["dangerous"],
            },
        }
        agent = BaseAgent.from_config(config)
        assert agent.client.base_url == "http://localhost:9000/v1"
        assert agent.client.model == "test-model"
        assert agent.memory.max_tokens == 2048
        assert agent.guardrails.max_iterations == 10
        assert "dangerous" in agent.guardrails.banned_tools

    def test_from_config_defaults(self) -> None:
        agent = BaseAgent.from_config({})
        assert agent.client.base_url == "http://localhost:8080/v1"
        assert agent.guardrails.max_iterations == 15
