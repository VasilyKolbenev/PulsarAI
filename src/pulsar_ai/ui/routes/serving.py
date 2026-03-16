"""API routes for serving metrics."""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/serving", tags=["serving"])


@router.get("/metrics")
async def get_serving_metrics(window: int = 60) -> dict:
    """Get serving metrics summary for a time window.

    Args:
        window: Look-back window in seconds (default: 60).
    """
    from pulsar_ai.serving.metrics import get_global_metrics

    return get_global_metrics().get_summary(window_seconds=window)


@router.post("/metrics/reset")
async def reset_serving_metrics() -> dict:
    """Reset all serving metrics."""
    from pulsar_ai.serving.metrics import get_global_metrics

    get_global_metrics().reset()
    return {"status": "reset"}
