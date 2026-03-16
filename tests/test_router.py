"""Tests for multi-agent router."""

from unittest.mock import MagicMock


from pulsar_ai.agent.base import BaseAgent
from pulsar_ai.agent.client import ModelClient
from pulsar_ai.agent.router import AgentRoute, RouterAgent
from pulsar_ai.agent.tool import ToolRegistry


def _mock_agent(answer: str = "mock answer") -> BaseAgent:
    """Create a mock agent that returns a fixed answer."""
    client = MagicMock(spec=ModelClient)
    client.chat = MagicMock(return_value={"content": f"Final Answer: {answer}"})
    agent = BaseAgent(
        client=client,
        tools=ToolRegistry(),
        use_native_tools=False,
    )
    return agent


class TestAgentRoute:
    """Tests for AgentRoute matching."""

    def test_match_score_with_triggers(self) -> None:
        route = AgentRoute(
            name="code",
            agent=_mock_agent(),
            triggers=["code", "programming", "debug"],
        )
        score = route.match_score("Help me debug this code")
        assert score > 0.5  # matches 'debug' and 'code'

    def test_match_score_no_triggers(self) -> None:
        route = AgentRoute(name="general", agent=_mock_agent(), triggers=[])
        assert route.match_score("anything") == 0.0

    def test_match_score_no_match(self) -> None:
        route = AgentRoute(
            name="data",
            agent=_mock_agent(),
            triggers=["data", "csv", "analysis"],
        )
        assert route.match_score("Write a poem about cats") == 0.0

    def test_match_score_case_insensitive(self) -> None:
        route = AgentRoute(
            name="code",
            agent=_mock_agent(),
            triggers=["python"],
        )
        assert route.match_score("Write PYTHON code") > 0

    def test_match_score_word_boundary(self) -> None:
        route = AgentRoute(
            name="data",
            agent=_mock_agent(),
            triggers=["data"],
        )
        # "data" as a standalone word should match
        assert route.match_score("analyze the data") > 0
        # "database" should NOT match (different word)
        assert route.match_score("connect to database") == 0.0


class TestRouterAgent:
    """Tests for RouterAgent routing logic."""

    def test_routes_to_best_match(self) -> None:
        code_agent = _mock_agent("code answer")
        data_agent = _mock_agent("data answer")
        fallback = _mock_agent("fallback answer")

        router = RouterAgent(
            routes=[
                AgentRoute(
                    name="code",
                    agent=code_agent,
                    triggers=["code", "programming", "debug", "python"],
                ),
                AgentRoute(
                    name="data",
                    agent=data_agent,
                    triggers=["data", "csv", "analysis", "chart"],
                ),
            ],
            fallback=fallback,
            confidence_threshold=0.2,
        )

        route_name, agent = router.route("Help me debug this python code")
        assert route_name == "code"
        assert agent is code_agent

    def test_routes_to_fallback_when_no_match(self) -> None:
        code_agent = _mock_agent("code")
        fallback = _mock_agent("fallback")

        router = RouterAgent(
            routes=[
                AgentRoute(
                    name="code",
                    agent=code_agent,
                    triggers=["code", "programming"],
                ),
            ],
            fallback=fallback,
            confidence_threshold=0.3,
        )

        route_name, agent = router.route("Tell me a joke about cats")
        assert route_name == "fallback"
        assert agent is fallback

    def test_routes_to_fallback_below_threshold(self) -> None:
        code_agent = _mock_agent("code")
        fallback = _mock_agent("fallback")

        router = RouterAgent(
            routes=[
                AgentRoute(
                    name="code",
                    agent=code_agent,
                    triggers=["code", "programming", "debug", "python", "javascript"],
                ),
            ],
            fallback=fallback,
            confidence_threshold=0.5,  # Need at least 50% triggers to match
        )

        # Only matches "code" = 1/5 = 0.2 < 0.5 threshold
        route_name, _ = router.route("Show me the code")
        assert route_name == "fallback"

    def test_run_returns_result(self) -> None:
        agent = _mock_agent("test result")
        fallback = _mock_agent("fallback")

        router = RouterAgent(
            routes=[
                AgentRoute(
                    name="test",
                    agent=agent,
                    triggers=["test"],
                ),
            ],
            fallback=fallback,
        )

        result = router.run("run the test")
        assert "answer" in result
        assert result["route"] == "test"
        assert "trace" in result

    def test_last_route_tracking(self) -> None:
        agent = _mock_agent()
        fallback = _mock_agent()

        router = RouterAgent(
            routes=[
                AgentRoute(name="a", agent=agent, triggers=["alpha"]),
            ],
            fallback=fallback,
        )

        assert router.last_route is None
        router.route("alpha query")
        assert router.last_route == "a"
        router.route("unmatched query")
        assert router.last_route == "fallback"

    def test_empty_routes_uses_fallback(self) -> None:
        fallback = _mock_agent("fallback")
        router = RouterAgent(routes=[], fallback=fallback)

        route_name, agent = router.route("anything")
        assert route_name == "fallback"
        assert agent is fallback
