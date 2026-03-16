"""HPO sweep runner using Optuna for LLM fine-tuning.

Supports YAML-based sweep configs with search spaces for
learning_rate, lora_r, lora_alpha, epochs, batch_size, etc.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

SWEEP_RESULTS_DIR = Path("./data/sweeps")


class SweepRunner:
    """HPO sweep runner backed by Optuna.

    Args:
        base_config_path: Path to base training config YAML.
        sweep_config: Sweep configuration dict or path to sweep YAML.
        study_name: Optional name for the Optuna study.
    """

    def __init__(
        self,
        base_config_path: str,
        sweep_config: dict | str,
        study_name: str | None = None,
    ) -> None:
        self.base_config_path = base_config_path
        self.sweep = (
            self._load_sweep(sweep_config) if isinstance(sweep_config, str) else sweep_config
        )
        self.study_name = study_name or f"sweep-{int(time.time())}"
        self.results: list[dict] = []

    @staticmethod
    def _load_sweep(path: str) -> dict:
        """Load sweep config from YAML file.

        Args:
            path: Path to sweep YAML.

        Returns:
            Parsed sweep config dict.
        """
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def run(self, n_trials: int | None = None) -> dict:
        """Run the HPO sweep.

        Args:
            n_trials: Override number of trials.

        Returns:
            Dict with best_params, best_value, all_trials, study_name.
        """
        try:
            import optuna
        except ImportError:
            raise ImportError(
                "optuna is required for HPO sweeps. " "Install with: pip install optuna"
            )

        sweep_conf = self.sweep.get("hpo", self.sweep)
        n_trials = n_trials or sweep_conf.get("n_trials", 10)
        direction = sweep_conf.get("direction", "minimize")
        metric = sweep_conf.get("metric", "training_loss")
        search_space = sweep_conf.get("search_space", {})

        if not search_space:
            raise ValueError("hpo.search_space is empty in sweep config")

        # Suppress Optuna logs unless verbose
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        study = optuna.create_study(
            study_name=self.study_name,
            direction=direction,
        )

        def objective(trial: optuna.Trial) -> float:
            params = self._sample_params(trial, search_space)
            logger.info(
                "Trial %d: %s",
                trial.number,
                {k: round(v, 6) if isinstance(v, float) else v for k, v in params.items()},
            )

            config = self._build_trial_config(params, trial.number)
            result = self._run_trial(config)

            value = result.get(metric, float("inf") if direction == "minimize" else 0)
            self.results.append(
                {
                    "trial": trial.number,
                    "params": params,
                    "result": result,
                    "value": value,
                }
            )

            return value

        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

        summary = {
            "study_name": self.study_name,
            "metric": metric,
            "direction": direction,
            "n_trials": n_trials,
            "best_trial": study.best_trial.number,
            "best_value": study.best_value,
            "best_params": study.best_params,
            "all_trials": self.results,
            "completed_at": datetime.now().isoformat(),
        }

        self._save_results(summary)
        return summary

    def _sample_params(self, trial: Any, search_space: dict) -> dict:
        """Sample hyperparameters from search space.

        Args:
            trial: Optuna trial object.
            search_space: Dict of param_name → [min, max, scale] or [choices].

        Returns:
            Dict of sampled parameter values.
        """
        _SCALE_INDICATORS = {"log", "int", "linear"}

        params = {}
        for param_key, spec in search_space.items():
            name = param_key.replace(".", "_")

            if isinstance(spec, list) and len(spec) == 3 and spec[2] in _SCALE_INDICATORS:
                # Numeric range: [min, max, scale]
                low, high, scale = spec
                if scale == "log":
                    params[param_key] = trial.suggest_float(name, low, high, log=True)
                elif scale == "int":
                    params[param_key] = trial.suggest_int(name, int(low), int(high))
                else:
                    params[param_key] = trial.suggest_float(name, low, high)

            elif (
                isinstance(spec, list)
                and len(spec) == 2
                and all(isinstance(v, (int, float)) for v in spec)
            ):
                # Numeric range: [min, max]
                low, high = spec
                if isinstance(low, int) and isinstance(high, int):
                    params[param_key] = trial.suggest_int(name, low, high)
                else:
                    params[param_key] = trial.suggest_float(name, float(low), float(high))

            elif isinstance(spec, list):
                # Categorical choices (any number of elements)
                params[param_key] = trial.suggest_categorical(name, spec)

            else:
                logger.warning("Unknown search space format for %s: %s", param_key, spec)

        return params

    def _build_trial_config(self, params: dict, trial_num: int) -> dict:
        """Build a trial-specific config with sampled params.

        Args:
            params: Sampled hyperparameters.
            trial_num: Trial number for output directory.

        Returns:
            Modified config dict.
        """
        from pulsar_ai.config import load_config, _set_nested

        config = load_config(self.base_config_path)

        for key, value in params.items():
            _set_nested(config, key, value)

        # Unique output dir per trial
        base_output = config.get("output", {}).get("dir", "./outputs/sweep")
        config.setdefault("output", {})["dir"] = f"{base_output}/trial_{trial_num}"

        # Disable external trackers during sweep (use local only)
        config.setdefault("logging", {})["tracker"] = "local"

        return config

    def _run_trial(self, config: dict) -> dict:
        """Run a single training trial.

        Args:
            config: Trial-specific config.

        Returns:
            Training results dict.
        """
        task = config.get("task", "sft")

        try:
            if task == "sft":
                from pulsar_ai.training.sft import train_sft

                return train_sft(config)
            elif task == "dpo":
                from pulsar_ai.training.dpo import train_dpo

                return train_dpo(config)
            else:
                raise ValueError(f"Unknown task for HPO: {task}")
        except Exception as e:
            logger.error("Trial failed: %s", e)
            return {"training_loss": float("inf"), "error": str(e)}

    def _save_results(self, summary: dict) -> None:
        """Save sweep results to JSON.

        Args:
            summary: Sweep summary dict.
        """
        SWEEP_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        path = SWEEP_RESULTS_DIR / f"{self.study_name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
        logger.info("Sweep results saved to %s", path)


def load_sweep_config(path: str) -> dict:
    """Load and validate sweep config YAML.

    Expected format:
        hpo:
          method: optuna
          metric: training_loss
          direction: minimize
          n_trials: 20
          search_space:
            training.learning_rate: [1e-5, 5e-4, log]
            lora.r: [8, 64, int]
            lora.lora_alpha: [16, 128, int]
            training.epochs: [1, 5, int]

    Args:
        path: Path to sweep YAML file.

    Returns:
        Validated sweep config dict.
    """
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    hpo = config.get("hpo", config)
    if not hpo.get("search_space"):
        raise ValueError("sweep config must have hpo.search_space")

    return config
