"""Evaluation routes: run model evaluation."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pulsar_ai.ui.experiment_store import ExperimentStore

logger = logging.getLogger(__name__)
router = APIRouter(tags=["evaluation"])

_store = ExperimentStore()


class EvalRequest(BaseModel):
    """Request body for running evaluation."""

    experiment_id: str
    test_data_path: str
    batch_size: int = 8


@router.post("/evaluation/run")
async def run_eval(req: EvalRequest) -> dict:
    """Run evaluation on a trained model.

    Looks up experiment artifacts to find the adapter directory,
    then runs batch inference on the provided test data.
    """
    exp = _store.get(req.experiment_id)
    if not exp:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment {req.experiment_id} not found",
        )

    artifacts = exp.get("artifacts", {})
    model_path = artifacts.get("adapter_dir") or artifacts.get("output_dir")
    if not model_path:
        raise HTTPException(
            status_code=400,
            detail="No trained model found for this experiment",
        )

    config = exp.get("config", {}).copy()
    config["model_path"] = model_path
    config["test_data_path"] = req.test_data_path
    config.setdefault("evaluation", {})["batch_size"] = req.batch_size

    try:
        from pulsar_ai.evaluation.runner import run_evaluation

        results = run_evaluation(config)
    except Exception as e:
        logger.exception("Evaluation failed for experiment %s", req.experiment_id)
        raise HTTPException(status_code=500, detail=str(e))

    _store.set_eval_results(req.experiment_id, results)
    return results
