"""Tests for CLI commands."""

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from pulsar_ai.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestForgeInit:
    """Tests for forge init command."""

    def test_init_creates_config_file(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init", "test-exp"])
            assert result.exit_code == 0

            config_path = Path("configs/experiments/test-exp.yaml")
            assert config_path.exists()

            with open(config_path) as f:
                config = yaml.safe_load(f)

            assert config["task"] == "sft"
            assert "base" in config["inherit"]
            assert config["dataset"]["path"] == "data/test-exp.csv"

    def test_init_dpo_task(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init", "test-dpo", "--task", "dpo"])
            assert result.exit_code == 0

            config_path = Path("configs/experiments/test-dpo.yaml")
            with open(config_path) as f:
                config = yaml.safe_load(f)

            assert config["task"] == "dpo"
            assert "sft_adapter_path" in config
            assert "dpo" in config

    def test_init_custom_model(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init", "test-llama", "--model", "llama3.2-1b"])
            assert result.exit_code == 0

            config_path = Path("configs/experiments/test-llama.yaml")
            with open(config_path) as f:
                config = yaml.safe_load(f)

            assert "models/llama3.2-1b" in config["inherit"]


class TestForgeHelp:
    """Tests for forge --help."""

    def test_help_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "pulsar-ai" in result.output.lower() or "universal" in result.output.lower()

    def test_train_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["train", "--help"])
        assert result.exit_code == 0
        assert "config_path" in result.output.lower() or "CONFIG_PATH" in result.output

    def test_init_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["init", "--help"])
        assert result.exit_code == 0
        assert "experiment" in result.output.lower() or "NAME" in result.output
