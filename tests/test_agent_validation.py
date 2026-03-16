"""Tests for agent config validation."""

from pulsar_ai.validation import validate_agent_config


class TestValidateAgentConfig:
    """Tests for validate_agent_config."""

    def test_valid_config(self) -> None:
        config = {
            "agent": {"name": "test-bot"},
            "model": {"base_url": "http://localhost:8080/v1"},
        }
        errors = validate_agent_config(config)
        assert errors == []

    def test_missing_agent_name(self) -> None:
        config = {
            "agent": {},
            "model": {"base_url": "http://localhost:8080/v1"},
        }
        errors = validate_agent_config(config)
        assert any("agent.name" in e for e in errors)

    def test_missing_model_base_url(self) -> None:
        config = {
            "agent": {"name": "test"},
            "model": {},
        }
        errors = validate_agent_config(config)
        assert any("model.base_url" in e for e in errors)

    def test_invalid_max_iterations(self) -> None:
        config = {
            "agent": {"name": "test"},
            "model": {"base_url": "http://localhost:8080/v1"},
            "guardrails": {"max_iterations": -1},
        }
        errors = validate_agent_config(config)
        assert any("max_iterations" in e for e in errors)

    def test_invalid_max_tokens(self) -> None:
        config = {
            "agent": {"name": "test"},
            "model": {"base_url": "http://localhost:8080/v1"},
            "guardrails": {"max_tokens": "not_a_number"},
        }
        errors = validate_agent_config(config)
        assert any("max_tokens" in e for e in errors)

    def test_invalid_memory_tokens(self) -> None:
        config = {
            "agent": {"name": "test"},
            "model": {"base_url": "http://localhost:8080/v1"},
            "memory": {"max_tokens": 0},
        }
        errors = validate_agent_config(config)
        assert any("memory.max_tokens" in e for e in errors)

    def test_empty_config(self) -> None:
        errors = validate_agent_config({})
        assert len(errors) >= 2  # missing agent.name and model.base_url
