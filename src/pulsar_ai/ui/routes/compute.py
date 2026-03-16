"""API routes for compute target management."""

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pulsar_ai.compute.manager import ComputeManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compute", tags=["compute"])

_manager = ComputeManager()


class AddTargetRequest(BaseModel):
    name: str
    host: str
    user: str
    port: int = 22
    key_path: str | None = None


class SubmitJobRequest(BaseModel):
    target_id: str
    config: dict
    task: str = "sft"


@router.get("/targets")
async def list_targets() -> list[dict]:
    """List all compute targets."""
    return [asdict(t) for t in _manager.list_targets()]


@router.post("/targets")
async def add_target(req: AddTargetRequest) -> dict:
    """Add a new compute target."""
    target = _manager.add_target(
        name=req.name,
        host=req.host,
        user=req.user,
        port=req.port,
        key_path=req.key_path,
    )
    return asdict(target)


@router.delete("/targets/{target_id}")
async def remove_target(target_id: str) -> dict:
    """Remove a compute target."""
    if _manager.remove_target(target_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Target not found")


@router.post("/targets/{target_id}/test")
async def test_connection(target_id: str) -> dict:
    """Test SSH connection to a target."""
    result = _manager.test_connection(target_id)
    return asdict(result)


@router.post("/targets/{target_id}/detect")
async def detect_hardware(target_id: str) -> dict:
    """Detect GPU hardware on a remote target."""
    return _manager.detect_remote_hardware(target_id)


@router.get("/targets/{target_id}")
async def get_target(target_id: str) -> dict:
    """Get a single compute target."""
    target = _manager.get_target(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return asdict(target)
