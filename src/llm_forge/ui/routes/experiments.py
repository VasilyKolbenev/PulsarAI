"""Experiment management routes: list, detail, compare, delete."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from llm_forge.ui.experiment_store import ExperimentStore

logger = logging.getLogger(__name__)
router = APIRouter(tags=["experiments"])

_store = ExperimentStore()


class CompareRequest(BaseModel):
    """Request to compare multiple experiments."""

    experiment_ids: list[str]


@router.get("/experiments")
async def list_experiments(status: str | None = None) -> list[dict]:
    """List all experiments, optionally filtered by status."""
    return _store.list_all(status=status)


@router.get("/experiments/{exp_id}")
async def get_experiment(exp_id: str) -> dict:
    """Get a single experiment with full details."""
    _store.reconcile_stale_running()
    exp = _store.get(exp_id)
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment {exp_id} not found")
    return exp


@router.post("/experiments/compare")
async def compare_experiments(req: CompareRequest) -> dict:
    """Compare training metrics across multiple experiments.

    Returns aligned metric histories for chart overlay.
    """
    _store.reconcile_stale_running()
    results = {}
    for exp_id in req.experiment_ids:
        exp = _store.get(exp_id)
        if not exp:
            raise HTTPException(
                status_code=404,
                detail=f"Experiment {exp_id} not found",
            )
        results[exp_id] = {
            "name": exp["name"],
            "task": exp.get("task", "sft"),
            "status": exp["status"],
            "final_loss": exp.get("final_loss"),
            "training_history": exp.get("training_history", []),
            "config": {
                "model": exp.get("model", ""),
                "learning_rate": exp.get("config", {}).get(
                    "training", {}
                ).get("learning_rate"),
                "epochs": exp.get("config", {}).get("training", {}).get("epochs"),
            },
        }
    return {"experiments": results}


@router.delete("/experiments/{exp_id}")
async def delete_experiment(exp_id: str) -> dict:
    """Delete an experiment record."""
    deleted = _store.delete(exp_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Experiment {exp_id} not found")
    return {"id": exp_id, "deleted": True}
