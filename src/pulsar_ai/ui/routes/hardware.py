"""Hardware detection route."""

import logging
from dataclasses import asdict

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["hardware"])


@router.get("/hardware")
async def get_hardware() -> dict:
    """Detect and return hardware capabilities.

    Returns GPU count, name, VRAM, recommended strategy and batch size.
    """
    from pulsar_ai.hardware import detect_hardware

    hw = detect_hardware()
    return asdict(hw)
