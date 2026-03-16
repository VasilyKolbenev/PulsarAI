"""Experiment tracking integration: ClearML, W&B, and local JSON tracker.

Provides a unified interface for logging experiments across different backends.
The `@pulsar_track` decorator auto-captures config, metrics, and artifacts.
"""

import hashlib
import json
import logging
import platform
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)

RUNS_DIR = Path("./data/runs")


class RunTracker:
    """Unified experiment tracker with pluggable backends.

    Supports: local JSON, ClearML, Weights & Biases.

    Args:
        backend: Tracking backend ("local", "clearml", "wandb", "none").
        project: Project name for grouping experiments.
        run_name: Human-readable run name.
        config: Full experiment config dict.
        tags: Optional list of tags.
    """

    def __init__(
        self,
        backend: str = "local",
        project: str = "pulsar-ai",
        run_name: str = "",
        config: dict | None = None,
        tags: list[str] | None = None,
    ) -> None:
        self.backend = backend
        self.project = project
        self.run_name = run_name or f"run-{int(time.time())}"
        self.config = config or {}
        self.tags = tags or []
        self.metrics_history: list[dict] = []
        self.artifacts: dict[str, str] = {}
        self.start_time = time.time()
        self._run_id = hashlib.sha256(f"{self.run_name}-{self.start_time}".encode()).hexdigest()[
            :12
        ]
        self._external_task: Any = None

        self._init_backend()

    @property
    def run_id(self) -> str:
        """Unique run identifier."""
        return self._run_id

    def _init_backend(self) -> None:
        """Initialize the tracking backend."""
        if self.backend == "clearml":
            self._init_clearml()
        elif self.backend == "wandb":
            self._init_wandb()
        elif self.backend == "local":
            logger.info("Using local JSON tracker (run_id=%s)", self._run_id)
        elif self.backend == "none":
            logger.debug("Tracking disabled")

    def _init_clearml(self) -> None:
        """Initialize ClearML Task."""
        try:
            from clearml import Task

            self._external_task = Task.init(
                project_name=self.project,
                task_name=self.run_name,
                tags=self.tags,
                auto_connect_frameworks=True,
            )
            if self.config:
                self._external_task.connect(self.config, name="pulsar_config")
            logger.info("ClearML task initialized: %s", self.run_name)
        except ImportError:
            logger.warning("clearml not installed, falling back to local tracker")
            self.backend = "local"
        except Exception as e:
            logger.warning("ClearML init failed: %s, falling back to local", e)
            self.backend = "local"

    def _init_wandb(self) -> None:
        """Initialize Weights & Biases run."""
        try:
            import wandb

            self._external_task = wandb.init(
                project=self.project,
                name=self.run_name,
                config=self.config,
                tags=self.tags,
            )
            logger.info("W&B run initialized: %s", self.run_name)
        except ImportError:
            logger.warning("wandb not installed, falling back to local tracker")
            self.backend = "local"
        except Exception as e:
            logger.warning("W&B init failed: %s, falling back to local", e)
            self.backend = "local"

    def log_metrics(self, metrics: dict, step: int | None = None) -> None:
        """Log training metrics.

        Args:
            metrics: Dict of metric_name → value.
            step: Optional global step number.
        """
        entry = {**metrics, "_timestamp": time.time()}
        if step is not None:
            entry["_step"] = step
        self.metrics_history.append(entry)

        if self.backend == "clearml" and self._external_task:
            task_logger = self._external_task.get_logger()
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    task_logger.report_scalar(
                        title=key,
                        series=key,
                        value=value,
                        iteration=step or len(self.metrics_history),
                    )
        elif self.backend == "wandb" and self._external_task:
            import wandb

            wandb.log(metrics, step=step)

    def log_artifact(self, name: str, path: str) -> None:
        """Register an artifact (model, dataset, etc.).

        Args:
            name: Artifact name.
            path: Path to artifact file/directory.
        """
        self.artifacts[name] = path

        if self.backend == "clearml" and self._external_task:
            self._external_task.upload_artifact(name=name, artifact_object=path)
        elif self.backend == "wandb":
            try:
                import wandb

                artifact = wandb.Artifact(name, type="model")
                if Path(path).is_dir():
                    artifact.add_dir(path)
                else:
                    artifact.add_file(path)
                wandb.log_artifact(artifact)
            except Exception as e:
                logger.warning("W&B artifact upload failed: %s", e)

    def set_tags(self, tags: list[str]) -> None:
        """Update run tags.

        Args:
            tags: List of tag strings.
        """
        self.tags = tags
        if self.backend == "clearml" and self._external_task:
            self._external_task.set_tags(tags)

    def finish(self, status: str = "completed", results: dict | None = None) -> dict:
        """Finalize the run and save results.

        Args:
            status: Final status (completed, failed).
            results: Optional final results dict.

        Returns:
            Run summary dict.
        """
        elapsed = time.time() - self.start_time
        summary = {
            "run_id": self._run_id,
            "name": self.run_name,
            "project": self.project,
            "backend": self.backend,
            "status": status,
            "config": self.config,
            "tags": self.tags,
            "metrics_history": self.metrics_history,
            "artifacts": self.artifacts,
            "results": results or {},
            "started_at": datetime.fromtimestamp(self.start_time).isoformat(),
            "finished_at": datetime.now().isoformat(),
            "duration_s": round(elapsed, 1),
            "environment": capture_environment(),
        }

        if self.backend == "local":
            self._save_local(summary)
        elif self.backend == "clearml" and self._external_task:
            self._external_task.close()
        elif self.backend == "wandb":
            try:
                import wandb

                if results:
                    wandb.summary.update(results)
                wandb.finish()
            except Exception as e:
                logger.warning("W&B finish failed: %s", e)

        logger.info("Run '%s' finished (%s) in %.1fs", self.run_name, status, elapsed)
        return summary

    def _save_local(self, summary: dict) -> None:
        """Save run to local JSON file."""
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        run_path = RUNS_DIR / f"{self._run_id}.json"
        with open(run_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
        logger.info("Run saved to %s", run_path)


def capture_environment() -> dict:
    """Capture current execution environment.

    Returns:
        Dict with Python version, platform, packages, GPU info.
    """
    env: dict[str, Any] = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hostname": platform.node(),
    }

    # Installed packages
    try:
        import importlib.metadata

        packages = {
            dist.metadata["Name"]: dist.metadata["Version"]
            for dist in importlib.metadata.distributions()
            if dist.metadata["Name"] in _TRACKED_PACKAGES
        }
        env["packages"] = packages
    except Exception:
        env["packages"] = {}

    # GPU info
    try:
        import torch

        if torch.cuda.is_available():
            env["cuda_version"] = torch.version.cuda
            env["gpu_count"] = torch.cuda.device_count()
            env["gpu_name"] = torch.cuda.get_device_properties(0).name
            props = torch.cuda.get_device_properties(0)
            vram = getattr(props, "total_memory", None) or getattr(props, "total_mem", 0)
            env["gpu_vram_gb"] = round(vram / (1024**3), 1)
    except ImportError:
        pass

    return env


_TRACKED_PACKAGES = {
    "torch",
    "transformers",
    "peft",
    "trl",
    "datasets",
    "bitsandbytes",
    "accelerate",
    "unsloth",
    "vllm",
    "llama-cpp-python",
    "clearml",
    "wandb",
    "optuna",
    "pulsar-ai",
}


@contextmanager
def track_experiment(
    config: dict,
    task: str = "sft",
    backend: str | None = None,
) -> Generator[RunTracker, None, None]:
    """Context manager for experiment tracking.

    Auto-detects backend from config if not specified.

    Args:
        config: Full experiment config dict.
        task: Training task type (sft, dpo, eval).
        backend: Override backend (local, clearml, wandb, none).

    Yields:
        RunTracker instance.

    Example:
        with track_experiment(config, task="sft") as tracker:
            results = train_sft(config)
            tracker.log_metrics({"loss": results["training_loss"]})
            tracker.log_artifact("adapter", results["adapter_dir"])
    """
    if backend is None:
        backend = config.get("logging", {}).get("tracker", "local")

    model_name = config.get("model", {}).get("name", "unknown")
    run_name = f"{task}-{model_name}-{int(time.time())}"
    tags = [task, model_name]

    tracker = RunTracker(
        backend=backend,
        project=config.get("project", "pulsar-ai"),
        run_name=run_name,
        config=config,
        tags=tags,
    )

    try:
        yield tracker
    except Exception as e:
        tracker.finish(status="failed", results={"error": str(e)})
        raise
    else:
        tracker.finish(status="completed")


def fingerprint_dataset(path: str, algorithm: str = "sha256") -> str:
    """Compute hash fingerprint of a dataset file.

    Args:
        path: Path to dataset file.
        algorithm: Hash algorithm (sha256, md5).

    Returns:
        Hex digest string.
    """
    h = hashlib.new(algorithm)
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)

    digest = h.hexdigest()
    logger.info("Dataset fingerprint (%s): %s...%s", algorithm, digest[:8], digest[-8:])
    return digest


def list_runs(
    project: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List local tracked runs.

    Args:
        project: Filter by project name.
        status: Filter by status.
        limit: Maximum number of runs to return.

    Returns:
        List of run summary dicts (newest first).
    """
    if not RUNS_DIR.exists():
        return []

    runs = []
    for run_file in sorted(RUNS_DIR.glob("*.json"), reverse=True):
        try:
            with open(run_file, encoding="utf-8") as f:
                run = json.load(f)
            if project and run.get("project") != project:
                continue
            if status and run.get("status") != status:
                continue
            runs.append(run)
            if len(runs) >= limit:
                break
        except (json.JSONDecodeError, KeyError):
            continue

    return runs


def get_run(run_id: str) -> dict | None:
    """Get a single run by ID.

    Args:
        run_id: Run identifier.

    Returns:
        Run dict or None if not found.
    """
    run_path = RUNS_DIR / f"{run_id}.json"
    if not run_path.exists():
        return None
    with open(run_path, encoding="utf-8") as f:
        return json.load(f)


def compare_runs(run_ids: list[str]) -> dict:
    """Compare multiple runs side by side.

    Args:
        run_ids: List of run IDs to compare.

    Returns:
        Dict with config_diff, metrics_comparison, and summary.
    """
    runs = []
    for rid in run_ids:
        run = get_run(rid)
        if run:
            runs.append(run)

    if len(runs) < 2:
        return {"error": "Need at least 2 valid runs to compare"}

    # Config diff — find keys that differ
    all_config_keys = set()
    for run in runs:
        all_config_keys.update(_flatten_dict(run.get("config", {})).keys())

    config_diff: dict[str, list] = {}
    for key in sorted(all_config_keys):
        values = []
        for run in runs:
            flat = _flatten_dict(run.get("config", {}))
            values.append(flat.get(key))
        if len(set(str(v) for v in values)) > 1:
            config_diff[key] = values

    # Metrics comparison — final metrics
    metrics_comparison: dict[str, list] = {}
    for run in runs:
        results = run.get("results", {})
        for key, value in results.items():
            if isinstance(value, (int, float)):
                metrics_comparison.setdefault(key, []).append(value)

    return {
        "run_ids": [r["run_id"] for r in runs],
        "run_names": [r["name"] for r in runs],
        "config_diff": config_diff,
        "metrics_comparison": metrics_comparison,
        "durations": [r.get("duration_s") for r in runs],
        "statuses": [r.get("status") for r in runs],
    }


def _flatten_dict(d: dict, prefix: str = "") -> dict[str, Any]:
    """Flatten nested dict with dot notation keys.

    Args:
        d: Dict to flatten.
        prefix: Key prefix for recursion.

    Returns:
        Flat dict with dotted keys.
    """
    items: dict[str, Any] = {}
    for key, value in d.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            items.update(_flatten_dict(value, full_key))
        else:
            items[full_key] = value
    return items
