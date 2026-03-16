"""Training progress tracking via HF TrainerCallback + SSE streaming."""

import logging
import queue
from typing import Any

logger = logging.getLogger(__name__)

# Global registry: job_id -> Queue
_progress_queues: dict[str, queue.Queue] = {}


class ProgressCallback:
    """Pushes training metrics to SSE queue and ExperimentStore.

    Used by the SSE endpoint to stream real-time training progress.

    Args:
        job_id: Unique job identifier.
        experiment_id: Experiment ID for the store.
    """

    def __init__(self, job_id: str, experiment_id: str = "") -> None:
        self.job_id = job_id
        self.experiment_id = experiment_id
        self._queue: queue.Queue = queue.Queue()
        _progress_queues[job_id] = self._queue

    def on_log(self, step: int, epoch: float, logs: dict[str, Any]) -> None:
        """Called when trainer logs metrics.

        Args:
            step: Current global step.
            epoch: Current epoch (fractional).
            logs: Dict with loss, learning_rate, etc.
        """
        gpu_mem = _get_gpu_memory()

        metrics = {
            "step": step,
            "epoch": round(epoch, 2),
            "loss": logs.get("loss"),
            "learning_rate": logs.get("learning_rate"),
            "gpu_mem_gb": gpu_mem,
        }

        # Persist to ExperimentStore for UI history
        if self.experiment_id:
            try:
                from pulsar_ai.ui.experiment_store import ExperimentStore

                store = ExperimentStore()
                store.add_metrics(self.experiment_id, metrics)
            except Exception:
                logger.debug("Failed to persist metrics to store", exc_info=True)

        self._queue.put({"event": "metrics", "data": metrics})

    def on_complete(self, results: dict[str, Any]) -> None:
        """Called when training completes successfully.

        Args:
            results: Training results dict.
        """
        self._queue.put(
            {
                "event": "completed",
                "data": results,
            }
        )

    def on_error(self, error: str) -> None:
        """Called when training fails.

        Args:
            error: Error message.
        """
        self._queue.put(
            {
                "event": "error",
                "data": {"error": error},
            }
        )


def make_hf_callback(progress: ProgressCallback) -> Any:
    """Create a HuggingFace TrainerCallback that bridges to ProgressCallback.

    Args:
        progress: ProgressCallback instance for SSE streaming.

    Returns:
        A TrainerCallback instance compatible with HF Trainer.
    """
    from transformers import TrainerCallback, TrainerState, TrainerControl, TrainingArguments

    class _HFBridge(TrainerCallback):
        """Bridges HF Trainer logging events to ProgressCallback."""

        def on_log(
            self,
            args: TrainingArguments,
            state: TrainerState,
            control: TrainerControl,
            logs: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> None:
            if logs and "loss" in logs:
                progress.on_log(
                    step=state.global_step,
                    epoch=state.epoch or 0.0,
                    logs=logs,
                )

    return _HFBridge()


def get_progress_queue(job_id: str) -> queue.Queue | None:
    """Get the progress queue for a job.

    Args:
        job_id: Job identifier.

    Returns:
        Queue instance or None if not found.
    """
    return _progress_queues.get(job_id)


def cleanup_queue(job_id: str) -> None:
    """Remove a job's progress queue.

    Args:
        job_id: Job identifier.
    """
    _progress_queues.pop(job_id, None)


def _get_gpu_memory() -> float | None:
    """Get current GPU memory usage in GB.

    Returns:
        GPU memory in GB or None if no GPU.
    """
    try:
        import torch

        if torch.cuda.is_available():
            return round(torch.cuda.memory_allocated() / (1024**3), 2)
    except ImportError:
        pass
    return None
