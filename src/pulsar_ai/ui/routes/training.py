"""Training API routes: start jobs, stream progress, list/cancel jobs."""

import json
import logging
import queue
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pulsar_ai.ui.jobs import submit_training_job, get_job, list_jobs, cancel_job
from pulsar_ai.ui.progress import get_progress_queue
from pulsar_ai.ui.experiment_store import ExperimentStore

logger = logging.getLogger(__name__)
router = APIRouter(tags=["training"])

_store = ExperimentStore()


class TrainingRequest(BaseModel):
    """Request body for starting a training job."""

    name: str
    config: dict
    task: str = "sft"


class TrainingResponse(BaseModel):
    """Response after starting a training job."""

    job_id: str
    experiment_id: str
    status: str


@router.post("/training/start", response_model=TrainingResponse)
async def start_training(req: TrainingRequest) -> TrainingResponse:
    """Start a new training job.

    Creates an experiment record and submits background training.
    """
    experiment_id = _store.create(
        name=req.name,
        config=req.config,
        task=req.task,
    )

    job_id = submit_training_job(
        experiment_id=experiment_id,
        config=req.config,
        task=req.task,
    )

    return TrainingResponse(
        job_id=job_id,
        experiment_id=experiment_id,
        status="running",
    )


@router.get("/training/progress/{job_id}")
async def stream_progress(job_id: str) -> StreamingResponse:
    """SSE endpoint streaming real-time training progress.

    Sends metrics events with step, loss, epoch, gpu_mem_gb.
    """
    progress_queue = get_progress_queue(job_id)
    if not progress_queue:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    async def generate() -> AsyncGenerator[str, None]:
        while True:
            try:
                event = progress_queue.get(timeout=1.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("event") in ("completed", "error"):
                    break
            except queue.Empty:
                yield ": keepalive\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/training/jobs")
async def get_jobs() -> list[dict]:
    """List all training jobs."""
    return list_jobs()


@router.get("/training/jobs/{job_id}")
async def get_job_detail(job_id: str) -> dict:
    """Get a single job by ID."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.delete("/training/jobs/{job_id}")
async def delete_job(job_id: str) -> dict:
    """Cancel a running training job."""
    cancelled = cancel_job(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} cannot be cancelled",
        )
    return {"job_id": job_id, "status": "cancelled"}
