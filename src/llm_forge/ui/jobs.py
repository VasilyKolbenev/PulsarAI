"""Background job manager for training jobs."""

import gc
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any

from llm_forge.ui.experiment_store import ExperimentStore
from llm_forge.ui.progress import ProgressCallback, cleanup_queue

logger = logging.getLogger(__name__)

# Single worker вЂ” training is GPU-bound, one job at a time
_executor = ThreadPoolExecutor(max_workers=1)
_jobs: dict[str, dict[str, Any]] = {}
_store = ExperimentStore()

_MAX_COMPLETED_JOBS = 50
_JOB_TTL_SECONDS = 3600  # 1 hour


def _cleanup_cuda() -> None:
    """Force-release GPU memory after training completes or fails."""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            allocated = torch.cuda.memory_allocated() / (1024**3)
            logger.info("CUDA cleanup done. Remaining allocated: %.2f GB", allocated)
    except ImportError:
        pass


def _check_vram_available(min_free_gb: float = 2.0) -> None:
    """Log warning if available VRAM is dangerously low."""
    try:
        import torch
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            free_gb = free / (1024**3)
            total_gb = total / (1024**3)
            logger.info("VRAM check: %.1f GB free / %.1f GB total", free_gb, total_gb)
            if free_gb < min_free_gb:
                logger.warning(
                    "Low VRAM: only %.1f GB free (need %.1f GB minimum). "
                    "Training may OOM.",
                    free_gb, min_free_gb,
                )
    except ImportError:
        pass


def _cleanup_old_jobs() -> None:
    """Remove completed/failed jobs older than TTL."""
    now = time.time()
    to_remove = []
    for job_id, job in _jobs.items():
        if job["status"] in ("completed", "failed", "cancelled"):
            age = now - job.get("finished_at", now)
            if age > _JOB_TTL_SECONDS:
                to_remove.append(job_id)

    completed = [
        (jid, j) for jid, j in _jobs.items()
        if j["status"] in ("completed", "failed", "cancelled")
    ]
    if len(completed) > _MAX_COMPLETED_JOBS:
        completed.sort(key=lambda x: x[1].get("finished_at", 0))
        to_remove.extend(
            jid for jid, _ in completed[:len(completed) - _MAX_COMPLETED_JOBS]
        )

    for jid in set(to_remove):
        del _jobs[jid]
        logger.debug("Cleaned up old job %s", jid)


def submit_training_job(
    experiment_id: str,
    config: dict,
    task: str = "sft",
) -> str:
    """Submit a training job to run in background.

    Args:
        experiment_id: Experiment ID in the store.
        config: Full resolved training config.
        task: Training task (sft or dpo).

    Returns:
        Job ID for tracking progress.
    """
    global _executor

    _cleanup_old_jobs()

    job_id = str(uuid.uuid4())[:8]
    progress = ProgressCallback(job_id, experiment_id)

    try:
        future = _executor.submit(
            _run_training, job_id, experiment_id, config, task, progress
        )
    except RuntimeError:
        logger.warning("Executor dead, recreating ThreadPoolExecutor")
        _executor = ThreadPoolExecutor(max_workers=1)
        future = _executor.submit(
            _run_training, job_id, experiment_id, config, task, progress
        )

    _jobs[job_id] = {
        "job_id": job_id,
        "experiment_id": experiment_id,
        "status": "running",
        "future": future,
    }

    _store.update_status(experiment_id, "running")
    logger.info("Submitted training job %s for experiment %s", job_id, experiment_id)
    return job_id


def _run_training(
    job_id: str,
    experiment_id: str,
    config: dict,
    task: str,
    progress: ProgressCallback,
) -> dict:
    """Execute training in background thread.

    Args:
        job_id: Job ID.
        experiment_id: Experiment ID.
        config: Training config.
        task: Training task.
        progress: Progress callback for SSE.

    Returns:
        Training results dict.
    """
    store = ExperimentStore()
    _check_vram_available()

    try:
        if task == "sft":
            from llm_forge.training.sft import train_sft
            results = train_sft(config, progress=progress)
        elif task == "dpo":
            from llm_forge.training.dpo import train_dpo
            results = train_dpo(config, progress=progress)
        else:
            raise ValueError(f"Unknown task: {task}")

        store.update_status(experiment_id, "completed")
        store.set_artifacts(experiment_id, {
            k: v for k, v in results.items()
            if isinstance(v, str)
        })
        if "training_loss" in results:
            store.add_metrics(experiment_id, {
                "loss": results["training_loss"],
                "step": results.get("global_steps", 0),
            })

        # Store eval results if auto-eval ran
        if "eval_results" in results:
            store.set_eval_results(experiment_id, results["eval_results"])

        progress.on_complete(results)
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["finished_at"] = time.time()

        logger.info("Training job %s completed", job_id)
        return results

    except Exception as e:
        logger.exception("Training job %s failed", job_id)
        store.update_status(experiment_id, "failed")
        progress.on_error(str(e))
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)
        _jobs[job_id]["finished_at"] = time.time()
        # DO NOT re-raise: keeps the ThreadPoolExecutor worker alive
        return {"error": str(e)}
    finally:
        _cleanup_cuda()
        cleanup_queue(job_id)


def get_job(job_id: str) -> dict | None:
    """Get job info by ID.

    Args:
        job_id: Job ID.

    Returns:
        Job info dict or None.
    """
    job = _jobs.get(job_id)
    if job:
        return {k: v for k, v in job.items() if k != "future"}
    return None


def list_jobs() -> list[dict]:
    """List all jobs.

    Returns:
        List of job info dicts.
    """
    return [
        {k: v for k, v in job.items() if k != "future"}
        for job in _jobs.values()
    ]


def shutdown_executor() -> None:
    """Gracefully shut down the training executor."""
    logger.info("Shutting down training executor...")
    _executor.shutdown(wait=False, cancel_futures=True)
    _cleanup_cuda()
    logger.info("Training executor shut down")


def cancel_job(job_id: str) -> bool:
    """Cancel a running job.

    Args:
        job_id: Job ID.

    Returns:
        True if cancelled, False otherwise.
    """
    job = _jobs.get(job_id)
    if job and isinstance(job.get("future"), Future):
        cancelled = job["future"].cancel()
        if cancelled:
            job["status"] = "cancelled"
            store = ExperimentStore()
            store.update_status(job["experiment_id"], "cancelled")
        return cancelled
    return False

