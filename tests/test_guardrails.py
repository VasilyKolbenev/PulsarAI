"""Tests for agent GuardrailsConfig."""

from pulsar_ai.agent.guardrails import GuardrailsConfig


class TestGuardrailsConfig:
    """Tests for GuardrailsConfig."""

    def test_defaults(self) -> None:
        g = GuardrailsConfig()
        assert g.max_iterations == 15
        assert g.max_tokens == 8192
        assert g.banned_tools == []
        assert g.require_confirmation == []
        assert g.max_tool_retries == 2

    def test_check_iteration_within_limit(self) -> None:
        g = GuardrailsConfig(max_iterations=10)
        assert g.check_iteration(0) is True
        assert g.check_iteration(9) is True

    def test_check_iteration_exceeded(self) -> None:
        g = GuardrailsConfig(max_iterations=10)
        assert g.check_iteration(10) is False
        assert g.check_iteration(15) is False

    def test_check_tool_allowed(self) -> None:
        g = GuardrailsConfig(banned_tools=["delete", "exec"])
        assert g.check_tool_allowed("search") is True
        assert g.check_tool_allowed("delete") is False
        assert g.check_tool_allowed("exec") is False

    def test_needs_confirmation(self) -> None:
        g = GuardrailsConfig(require_confirmation=["web_search", "send_email"])
        assert g.needs_confirmation("web_search") is True
        assert g.needs_confirmation("send_email") is True
        assert g.needs_confirmation("read_file") is False

    def test_from_config_full(self) -> None:
        config = {
            "guardrails": {
                "max_iterations": 20,
                "max_tokens": 16384,
                "banned_tools": ["rm"],
                "require_confirmation": ["deploy"],
                "max_tool_retries": 3,
            }
        }
        g = GuardrailsConfig.from_config(config)
        assert g.max_iterations == 20
        assert g.max_tokens == 16384
        assert g.banned_tools == ["rm"]
        assert g.require_confirmation == ["deploy"]
        assert g.max_tool_retries == 3

    def test_from_config_empty(self) -> None:
        g = GuardrailsConfig.from_config({})
        assert g.max_iterations == 15
        assert g.max_tokens == 8192

    def test_from_config_partial(self) -> None:
        config = {"guardrails": {"max_iterations": 5}}
        g = GuardrailsConfig.from_config(config)
        assert g.max_iterations == 5
        assert g.max_tokens == 8192  # default
