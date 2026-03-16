"""Export routes: export trained models to production formats."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pulsar_ai.ui.experiment_store import ExperimentStore

logger = logging.getLogger(__name__)
router = APIRouter(tags=["export"])

_store = ExperimentStore()


class ExportRequest(BaseModel):
    """Request body for model export."""

    experiment_id: str
    format: str = "gguf"
    quantization: str = "q4_k_m"
    output_path: str | None = None


@router.post("/export")
async def export_model(req: ExportRequest) -> dict:
    """Export a trained model to production format (GGUF, merged, hub)."""
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
    config.setdefault("export", {}).update(
        {
            "format": req.format,
            "quantization": req.quantization,
        }
    )
    if req.output_path:
        config["export"]["output_path"] = req.output_path

    try:
        if req.format == "gguf":
            from pulsar_ai.export.gguf import export_gguf

            result = export_gguf(config)
        elif req.format == "merged":
            from pulsar_ai.export.merged import export_merged

            result = export_merged(config)
        elif req.format == "hub":
            from pulsar_ai.export.hub import push_to_hub

            result = push_to_hub(config)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown export format: {req.format}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Export failed for experiment %s", req.experiment_id)
        raise HTTPException(status_code=500, detail=str(e))

    return result
