"""Tests for agent CLI commands."""

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from pulsar_ai.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestAgentInit:
    """Tests for pulsar agent init command."""

    def test_creates_agent_config(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["agent", "init", "test-bot"])
            assert result.exit_code == 0

            config_path = Path("configs/agents/test-bot.yaml")
            assert config_path.exists()

            with open(config_path) as f:
                config = yaml.safe_load(f)

            assert config["agent"]["name"] == "test-bot"
            assert "agents/base" in config["inherit"]
            assert len(config["tools"]) == 3

    def test_custom_model_url(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                main,
                ["agent", "init", "my-agent", "--model-url", "http://localhost:11434/v1"],
            )
            assert result.exit_code == 0

            config_path = Path("configs/agents/my-agent.yaml")
            with open(config_path) as f:
                config = yaml.safe_load(f)

            assert config["model"]["base_url"] == "http://localhost:11434/v1"

    def test_custom_model_name(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                main,
                ["agent", "init", "my-agent", "--model-name", "llama3.2"],
            )
            assert result.exit_code == 0

            config_path = Path("configs/agents/my-agent.yaml")
            with open(config_path) as f:
                config = yaml.safe_load(f)

            assert config["model"]["name"] == "llama3.2"


class TestAgentHelp:
    """Tests for agent subcommand help."""

    def test_agent_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["agent", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "test" in result.output

    def test_agent_init_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["agent", "init", "--help"])
        assert result.exit_code == 0
        assert "NAME" in result.output or "name" in result.output.lower()

    def test_agent_test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["agent", "test", "--help"])
        assert result.exit_code == 0
        assert "CONFIG_PATH" in result.output or "config" in result.output.lower()
