"""Real-time system metrics collection and SSE streaming."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, asdict
from typing import AsyncGenerator

import psutil
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@dataclass
class GPUMetrics:
    """Per-GPU metrics snapshot."""

    index: int
    name: str
    utilization_percent: float
    memory_used_gb: float
    memory_total_gb: float
    temperature_c: int
    power_watts: float


@dataclass
class SystemMetrics:
    """Full system metrics snapshot."""

    timestamp: float
    cpu_percent: float
    cpu_count: int
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float
    disk_used_gb: float
    disk_total_gb: float
    gpus: list[GPUMetrics]


def _collect_gpu_metrics() -> list[GPUMetrics]:
    """Collect metrics from all NVIDIA GPUs via pynvml."""
    try:
        import pynvml

        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        gpus = []
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except pynvml.NVMLError:
                temp = 0
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
            except pynvml.NVMLError:
                power = 0.0

            gpus.append(
                GPUMetrics(
                    index=i,
                    name=name,
                    utilization_percent=float(util.gpu),
                    memory_used_gb=round(mem.used / (1024**3), 2),
                    memory_total_gb=round(mem.total / (1024**3), 2),
                    temperature_c=temp,
                    power_watts=round(power, 1),
                )
            )
        pynvml.nvmlShutdown()
        return gpus
    except Exception:
        return []


def collect_metrics() -> SystemMetrics:
    """Collect a single snapshot of system metrics.

    Returns:
        SystemMetrics with CPU, RAM, disk, and GPU data.
    """
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return SystemMetrics(
        timestamp=time.time(),
        cpu_percent=cpu_percent,
        cpu_count=psutil.cpu_count(logical=True) or 1,
        ram_used_gb=round(mem.used / (1024**3), 2),
        ram_total_gb=round(mem.total / (1024**3), 2),
        ram_percent=mem.percent,
        disk_used_gb=round(disk.used / (1024**3), 2),
        disk_total_gb=round(disk.total / (1024**3), 2),
        gpus=_collect_gpu_metrics(),
    )


async def metrics_stream(interval: float = 2.0) -> AsyncGenerator[str, None]:
    """Yield SSE events with system metrics.

    Args:
        interval: Seconds between snapshots.

    Yields:
        SSE-formatted JSON strings.
    """
    # Prime psutil CPU measurement
    psutil.cpu_percent(interval=None)
    await asyncio.sleep(0.1)

    while True:
        metrics = collect_metrics()
        data = json.dumps(asdict(metrics))
        yield f"data: {data}\n\n"
        await asyncio.sleep(interval)


@router.get("/live")
async def metrics_live() -> StreamingResponse:
    """SSE stream of system metrics every 2 seconds."""
    return StreamingResponse(
        metrics_stream(interval=2.0),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/snapshot")
async def metrics_snapshot() -> dict:
    """Single snapshot of current system metrics."""
    return asdict(collect_metrics())
