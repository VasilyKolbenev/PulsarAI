"""JSON-based experiment tracker for Web UI."""

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = Path("./data/experiments.json")
try:
    DEFAULT_STALE_RUNNING_MINUTES = int(
        os.environ.get("FORGE_STALE_RUNNING_MINUTES", "90")
    )
except ValueError:
    DEFAULT_STALE_RUNNING_MINUTES = 90


class ExperimentStore:
    """CRUD operations on experiments stored in a JSON file.

    Args:
        store_path: Path to the JSON file.
    """

    def __init__(self, store_path: Path | None = None) -> None:
        self.store_path = store_path or DEFAULT_STORE_PATH
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self._save([])

    def create(self, name: str, config: dict, task: str = "sft") -> str:
        """Create a new experiment entry.

        Args:
            name: Experiment name.
            config: Full training config dict.
            task: Training task type.

        Returns:
            Experiment ID.
        """
        exp_id = str(uuid.uuid4())[:8]
        experiments = self._load()
        now_iso = datetime.now().isoformat()

        experiments.append(
            {
                "id": exp_id,
                "name": name,
                "status": "queued",
                "task": task,
                "model": config.get("model", {}).get("name", "unknown"),
                "dataset_id": config.get("_dataset_id", ""),
                "config": config,
                "created_at": now_iso,
                "last_update_at": now_iso,
                "completed_at": None,
                "final_loss": None,
                "training_history": [],
                "eval_results": None,
                "artifacts": {},
            }
        )

        self._save(experiments)
        logger.info("Created experiment %s: %s", exp_id, name)
        return exp_id

    def update_status(self, exp_id: str, status: str) -> None:
        """Update experiment status.

        Args:
            exp_id: Experiment ID.
            status: New status (queued/running/completed/failed).
        """
        experiments = self._load()
        now_iso = datetime.now().isoformat()
        for exp in experiments:
            if exp["id"] == exp_id:
                exp["status"] = status
                exp["last_update_at"] = now_iso
                if status in {"completed", "failed"}:
                    exp["completed_at"] = now_iso
                break
        self._save(experiments)

    def add_metrics(self, exp_id: str, metrics: dict) -> None:
        """Append training metrics to history.

        Args:
            exp_id: Experiment ID.
            metrics: Dict with step, loss, epoch, etc.
        """
        experiments = self._load()
        for exp in experiments:
            if exp["id"] == exp_id:
                exp.setdefault("training_history", []).append(metrics)
                if "loss" in metrics and metrics["loss"] is not None:
                    exp["final_loss"] = metrics["loss"]
                exp["last_update_at"] = (
                    metrics.get("time")
                    if isinstance(metrics.get("time"), str)
                    else datetime.now().isoformat()
                )
                break
        self._save(experiments)

    def set_artifacts(self, exp_id: str, artifacts: dict) -> None:
        """Store artifact paths for an experiment.

        Args:
            exp_id: Experiment ID.
            artifacts: Dict of artifact paths (adapter_dir, output_dir, etc.).
        """
        experiments = self._load()
        for exp in experiments:
            if exp["id"] == exp_id:
                exp["artifacts"] = artifacts
                exp["last_update_at"] = datetime.now().isoformat()
                break
        self._save(experiments)

    def set_eval_results(self, exp_id: str, results: dict) -> None:
        """Store evaluation results.

        Args:
            exp_id: Experiment ID.
            results: Eval results dict.
        """
        experiments = self._load()
        for exp in experiments:
            if exp["id"] == exp_id:
                exp["eval_results"] = results
                exp["last_update_at"] = datetime.now().isoformat()
                break
        self._save(experiments)

    def reconcile_stale_running(self, stale_after_minutes: int | None = None) -> int:
        """Mark stale running experiments as failed.

        A stale experiment is one with status=running and no updates for more than
        `stale_after_minutes` minutes.

        Args:
            stale_after_minutes: Override threshold; defaults to env setting.

        Returns:
            Number of reconciled experiments.
        """
        threshold_min = (
            DEFAULT_STALE_RUNNING_MINUTES
            if stale_after_minutes is None
            else stale_after_minutes
        )
        if threshold_min <= 0:
            return 0

        now = datetime.now()
        experiments = self._load()
        updated = 0

        for exp in experiments:
            if exp.get("status") != "running":
                continue

            last_seen = self._get_last_seen(exp)
            if last_seen is None:
                continue

            if now - last_seen <= timedelta(minutes=threshold_min):
                continue

            exp["status"] = "failed"
            exp["completed_at"] = now.isoformat()
            exp["last_update_at"] = now.isoformat()
            artifacts = exp.get("artifacts") or {}
            if "error" not in artifacts:
                artifacts["error"] = (
                    "Marked failed automatically: no progress updates "
                    f"for more than {threshold_min} minutes"
                )
            exp["artifacts"] = artifacts
            updated += 1

        if updated:
            self._save(experiments)
            logger.warning("Reconciled %d stale running experiments", updated)

        return updated

    def get(self, exp_id: str) -> dict | None:
        """Get a single experiment by ID.

        Args:
            exp_id: Experiment ID.

        Returns:
            Experiment dict or None.
        """
        for exp in self._load():
            if exp["id"] == exp_id:
                return exp
        return None

    def list_all(self, status: str | None = None) -> list[dict]:
        """List all experiments, optionally filtered by status.

        Args:
            status: Optional status filter.

        Returns:
            List of experiment dicts (newest first).
        """
        self.reconcile_stale_running()
        experiments = self._load()
        if status:
            experiments = [e for e in experiments if e["status"] == status]
        return sorted(experiments, key=lambda e: e["created_at"], reverse=True)

    def delete(self, exp_id: str) -> bool:
        """Delete an experiment.

        Args:
            exp_id: Experiment ID.

        Returns:
            True if deleted, False if not found.
        """
        experiments = self._load()
        original_len = len(experiments)
        experiments = [e for e in experiments if e["id"] != exp_id]
        if len(experiments) < original_len:
            self._save(experiments)
            return True
        return False

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    def _get_last_seen(self, exp: dict) -> datetime | None:
        candidates: list[Any] = [exp.get("last_update_at")]

        history = exp.get("training_history")
        if isinstance(history, list) and history:
            last = history[-1]
            if isinstance(last, dict):
                candidates.append(last.get("time"))

        candidates.append(exp.get("created_at"))

        for item in candidates:
            parsed = self._parse_dt(item)
            if parsed is not None:
                return parsed
        return None

    def _load(self) -> list[dict]:
        with open(self.store_path, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, experiments: list[dict]) -> None:
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(experiments, f, ensure_ascii=False, indent=2)
