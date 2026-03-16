"""API routes for model registry."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pulsar_ai.registry import ModelRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/registry", tags=["registry"])

_registry = ModelRegistry()


class RegisterModelRequest(BaseModel):
    name: str
    model_path: str
    task: str = "sft"
    base_model: str = ""
    metrics: dict | None = None
    dataset_fingerprint: str = ""
    tags: list[str] | None = None
    serving_format: str = ""


class UpdateStatusRequest(BaseModel):
    status: str


class UpdateMetricsRequest(BaseModel):
    metrics: dict


@router.get("")
async def list_models(
    name: str | None = None,
    status: str | None = None,
    tag: str | None = None,
) -> list[dict]:
    """List registered models."""
    return _registry.list_models(name=name, status=status, tag=tag)


@router.post("")
async def register_model(req: RegisterModelRequest) -> dict:
    """Register a new model."""
    return _registry.register(
        name=req.name,
        model_path=req.model_path,
        task=req.task,
        base_model=req.base_model,
        metrics=req.metrics,
        dataset_fingerprint=req.dataset_fingerprint,
        tags=req.tags,
        serving_format=req.serving_format,
    )


@router.get("/{model_id}")
async def get_model(model_id: str) -> dict:
    """Get a model by ID."""
    model = _registry.get(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.put("/{model_id}/status")
async def update_model_status(model_id: str, req: UpdateStatusRequest) -> dict:
    """Update model deployment status."""
    model = _registry.update_status(model_id, req.status)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.put("/{model_id}/metrics")
async def update_model_metrics(model_id: str, req: UpdateMetricsRequest) -> dict:
    """Update model metrics."""
    model = _registry.update_metrics(model_id, req.metrics)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.delete("/{model_id}")
async def delete_model(model_id: str) -> dict:
    """Delete a model from registry."""
    if _registry.delete(model_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Model not found")


@router.post("/compare")
async def compare_models(model_ids: list[str]) -> dict:
    """Compare multiple models side by side."""
    if len(model_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 model IDs")
    return _registry.compare(model_ids)
