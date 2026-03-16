"""Pipeline run tracker — persists execution state to JSON manifest."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_RUNS_DIR = Path("./data/pipeline_runs")


class PipelineTracker:
    """Track pipeline execution state in a JSON manifest.

    Args:
        pipeline_name: Name of the pipeline.
        runs_dir: Directory to store run manifests.
    """

    def __init__(
        self,
        pipeline_name: str,
        runs_dir: Path | None = None,
    ) -> None:
        self.pipeline_name = pipeline_name
        self.runs_dir = runs_dir or DEFAULT_RUNS_DIR
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._manifest: dict[str, Any] = {}
        self._manifest_path: Path | None = None

    def start_run(self, step_names: list[str]) -> str:
        """Initialize a new pipeline run.

        Args:
            step_names: Ordered list of step names.

        Returns:
            Run ID (timestamp-based).
        """
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._manifest_path = self.runs_dir / f"{self.pipeline_name}_{run_id}.json"

        self._manifest = {
            "run_id": run_id,
            "pipeline": self.pipeline_name,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "steps": {
                name: {"status": "pending", "result": None, "error": None, "duration_s": None}
                for name in step_names
            },
        }
        self._save()
        logger.info("Pipeline run %s started", run_id)
        return run_id

    def update_step(
        self,
        step_name: str,
        status: str,
        result: dict | None = None,
        error: str | None = None,
        duration_s: float | None = None,
    ) -> None:
        """Update a step's status.

        Args:
            step_name: Name of the step.
            status: New status (running, completed, failed).
            result: Step output dict.
            error: Error message if failed.
            duration_s: Step duration in seconds.
        """
        if step_name in self._manifest.get("steps", {}):
            step = self._manifest["steps"][step_name]
            step["status"] = status
            if result is not None:
                # Only store string/number values to keep manifest clean
                step["result"] = {
                    k: v for k, v in result.items() if isinstance(v, (str, int, float, bool))
                }
            if error is not None:
                step["error"] = error
            if duration_s is not None:
                step["duration_s"] = duration_s
            self._save()

    def finish_run(self) -> None:
        """Mark the pipeline run as completed."""
        self._manifest["status"] = "completed"
        self._manifest["completed_at"] = datetime.now().isoformat()
        self._save()
        logger.info("Pipeline run %s completed", self._manifest.get("run_id"))

    def fail_run(self, error: str) -> None:
        """Mark the pipeline run as failed.

        Args:
            error: Error message.
        """
        self._manifest["status"] = "failed"
        self._manifest["completed_at"] = datetime.now().isoformat()
        self._manifest["error"] = error
        self._save()

    def get_manifest(self) -> dict:
        """Get the current run manifest."""
        return self._manifest.copy()

    def _save(self) -> None:
        """Persist manifest to disk."""
        if self._manifest_path:
            with open(self._manifest_path, "w", encoding="utf-8") as f:
                json.dump(self._manifest, f, ensure_ascii=False, indent=2)

    @classmethod
    def list_runs(
        cls,
        pipeline_name: str | None = None,
        runs_dir: Path | None = None,
    ) -> list[dict]:
        """List all pipeline runs.

        Args:
            pipeline_name: Filter by pipeline name.
            runs_dir: Directory containing run manifests.

        Returns:
            List of run manifests (newest first).
        """
        rd = runs_dir or DEFAULT_RUNS_DIR
        if not rd.exists():
            return []

        runs = []
        for path in rd.glob("*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    manifest = json.load(f)
                if pipeline_name and manifest.get("pipeline") != pipeline_name:
                    continue
                runs.append(manifest)
            except Exception:
                logger.warning("Failed to read manifest: %s", path)

        return sorted(runs, key=lambda r: r.get("started_at", ""), reverse=True)
