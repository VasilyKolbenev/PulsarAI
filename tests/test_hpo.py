"""Tests for HPO sweep module."""

import pytest
import yaml
from unittest.mock import patch, MagicMock

from pulsar_ai.hpo.sweep import SweepRunner, load_sweep_config


@pytest.fixture
def sweep_yaml(tmp_path):
    """Create a sweep config YAML."""
    config = {
        "hpo": {
            "method": "optuna",
            "metric": "training_loss",
            "direction": "minimize",
            "n_trials": 3,
            "search_space": {
                "training.learning_rate": [1e-5, 5e-4, "log"],
                "lora.r": [8, 64, "int"],
                "training.epochs": [1, 3, "int"],
            },
        }
    }
    path = tmp_path / "sweep.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)
    return str(path)


@pytest.fixture
def base_config_yaml(tmp_path):
    """Create a base training config YAML."""
    config = {
        "task": "sft",
        "model": {"name": "test-model"},
        "training": {"learning_rate": 2e-4, "epochs": 3},
        "dataset": {"path": "data/train.csv"},
        "output": {"dir": str(tmp_path / "outputs")},
    }
    path = tmp_path / "base.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)
    return str(path)


class TestLoadSweepConfig:
    """Test sweep config loading and validation."""

    def test_load_valid(self, sweep_yaml):
        config = load_sweep_config(sweep_yaml)
        assert "hpo" in config
        assert "search_space" in config["hpo"]
        assert len(config["hpo"]["search_space"]) == 3

    def test_load_empty_search_space(self, tmp_path):
        config = {"hpo": {"search_space": {}}}
        path = tmp_path / "bad.yaml"
        with open(path, "w") as f:
            yaml.dump(config, f)

        with pytest.raises(ValueError, match="search_space"):
            load_sweep_config(str(path))


class TestSweepRunner:
    """Test SweepRunner."""

    def test_init(self, base_config_yaml, sweep_yaml):
        runner = SweepRunner(
            base_config_path=base_config_yaml,
            sweep_config=sweep_yaml,
            study_name="test-study",
        )
        assert runner.study_name == "test-study"
        assert runner.sweep is not None

    def test_sample_params_log_float(self, base_config_yaml):
        runner = SweepRunner(
            base_config_path=base_config_yaml,
            sweep_config={
                "hpo": {
                    "search_space": {
                        "training.learning_rate": [1e-5, 1e-3, "log"],
                    }
                }
            },
        )

        # Mock optuna trial
        trial = MagicMock()
        trial.suggest_float.return_value = 1e-4

        params = runner._sample_params(trial, {"training.learning_rate": [1e-5, 1e-3, "log"]})
        assert "training.learning_rate" in params
        trial.suggest_float.assert_called_once()

    def test_sample_params_int(self, base_config_yaml):
        runner = SweepRunner(
            base_config_path=base_config_yaml,
            sweep_config={"hpo": {"search_space": {"lora.r": [8, 64, "int"]}}},
        )

        trial = MagicMock()
        trial.suggest_int.return_value = 32

        params = runner._sample_params(trial, {"lora.r": [8, 64, "int"]})
        assert params["lora.r"] == 32

    def test_sample_params_categorical(self, base_config_yaml):
        runner = SweepRunner(
            base_config_path=base_config_yaml,
            sweep_config={
                "hpo": {
                    "search_space": {
                        "training.optimizer": ["adamw_8bit", "adamw", "sgd"],
                    }
                }
            },
        )

        trial = MagicMock()
        trial.suggest_categorical.return_value = "adamw"

        params = runner._sample_params(
            trial,
            {"training.optimizer": ["adamw_8bit", "adamw", "sgd"]},
        )
        assert params["training.optimizer"] == "adamw"

    def test_sample_params_two_element_list(self, base_config_yaml):
        runner = SweepRunner(
            base_config_path=base_config_yaml,
            sweep_config={"hpo": {"search_space": {"x": [0.1, 0.9]}}},
        )

        trial = MagicMock()
        trial.suggest_float.return_value = 0.5

        params = runner._sample_params(trial, {"x": [0.1, 0.9]})
        assert params["x"] == 0.5

    @patch("pulsar_ai.hpo.sweep.SweepRunner._run_trial")
    def test_build_trial_config(self, mock_run, base_config_yaml, tmp_path):
        runner = SweepRunner(
            base_config_path=base_config_yaml,
            sweep_config={"hpo": {"search_space": {"training.lr": [1e-5, 1e-3, "log"]}}},
        )

        config = runner._build_trial_config({"training.lr": 1e-4}, trial_num=0)
        assert config["training"]["lr"] == 1e-4
        assert "trial_0" in config["output"]["dir"]

    @patch("pulsar_ai.hpo.sweep.SWEEP_RESULTS_DIR")
    def test_save_results(self, mock_dir, tmp_path, base_config_yaml):
        mock_dir.__truediv__ = lambda self, x: tmp_path / x
        mock_dir.mkdir = MagicMock()

        runner = SweepRunner(
            base_config_path=base_config_yaml,
            sweep_config={"hpo": {"search_space": {}}},
            study_name="save-test",
        )
        runner._save_results({"study_name": "save-test", "results": []})

        saved_files = list(tmp_path.glob("*.json"))
        assert len(saved_files) == 1
