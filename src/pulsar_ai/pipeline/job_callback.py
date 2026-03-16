"""Pipeline callback that tracks execution via JobRegistry."""

import logging
from typing import Any

from pulsar_ai.storage.job_registry import JobRegistry

logger = logging.getLogger(__name__)


class JobRegistryCallback:
    """Bridges PipelineExecutor events to the durable JobRegistry.

    Creates a job on pipeline start and updates its status as steps
    progress. This gives the UI live visibility into pipeline execution.

    Args:
        registry: JobRegistry instance.
        experiment_id: Optional linked experiment.
    """

    def __init__(
        self,
        registry: JobRegistry,
        experiment_id: str | None = None,
    ) -> None:
        self._registry = registry
        self._experiment_id = experiment_id
        self._job_id: str | None = None

    @property
    def job_id(self) -> str | None:
        """The ID of the tracked job (set after on_pipeline_start)."""
        return self._job_id

    def on_pipeline_start(self, pipeline_name: str, step_names: list[str]) -> None:
        """Create a job and mark it running."""
        job = self._registry.create(
            job_type="pipeline",
            config={"pipeline_name": pipeline_name, "steps": step_names},
            experiment_id=self._experiment_id,
        )
        self._job_id = job["id"]
        self._registry.update_status(self._job_id, "running")
        logger.info("Pipeline job %s started for '%s'", self._job_id, pipeline_name)

    def on_step_start(self, step_name: str, step_type: str) -> None:
        """Log step start (no job-level change needed)."""
        pass

    def on_step_complete(self, step_name: str, result: dict[str, Any], duration_s: float) -> None:
        """Log step completion."""
        pass

    def on_step_skip(self, step_name: str) -> None:
        """Log step skip."""
        pass

    def on_step_fail(self, step_name: str, error: str) -> None:
        """Log step failure (pipeline_fail handles the job status)."""
        pass

    def on_pipeline_complete(self, outputs: dict[str, Any]) -> None:
        """Mark job as completed."""
        if self._job_id:
            self._registry.update_status(self._job_id, "completed")

    def on_pipeline_fail(self, step_name: str, error: str) -> None:
        """Mark job as failed with error details."""
        if self._job_id:
            self._registry.update_status(
                self._job_id,
                "failed",
                error_message=f"Step '{step_name}' failed: {error}",
            )
