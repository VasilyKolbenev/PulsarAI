"""Prometheus metrics endpoint for Pulsar AI.

Exposes ``/metrics`` in standard Prometheus exposition format.
Reuses existing psutil/pynvml collection from the metrics module.
"""

import logging

from fastapi import APIRouter, Response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["prometheus"])

# ── Counters (in-memory, reset on restart) ────────────────────────
_counters: dict[str, float] = {
    "pulsar_requests_total": 0,
    "pulsar_training_jobs_total": 0,
    "pulsar_errors_total": 0,
}


def inc_counter(name: str, amount: float = 1.0) -> None:
    """Increment a Prometheus counter.

    Args:
        name: Counter metric name.
        amount: Increment amount.
    """
    _counters[name] = _counters.get(name, 0) + amount


def _collect_system_gauges() -> dict[str, float]:
    """Collect current system metrics as Prometheus gauges."""
    import psutil

    gauges: dict[str, float] = {
        "pulsar_cpu_percent": psutil.cpu_percent(interval=0),
        "pulsar_memory_percent": psutil.virtual_memory().percent,
        "pulsar_memory_used_bytes": psutil.virtual_memory().used,
        "pulsar_disk_percent": psutil.disk_usage("/").percent,
    }

    # GPU metrics (optional)
    try:
        import pynvml

        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gauges[f"pulsar_gpu{i}_utilization_percent"] = util.gpu
            gauges[f"pulsar_gpu{i}_memory_used_bytes"] = mem.used
            gauges[f"pulsar_gpu{i}_memory_total_bytes"] = mem.total
        pynvml.nvmlShutdown()
    except Exception:
        pass  # No GPU or pynvml not available

    return gauges


def _format_prometheus(
    counters: dict[str, float],
    gauges: dict[str, float],
) -> str:
    """Format metrics in Prometheus exposition format.

    Args:
        counters: Counter metrics.
        gauges: Gauge metrics.

    Returns:
        Prometheus-formatted text.
    """
    lines: list[str] = []

    for name, value in sorted(counters.items()):
        lines.append(f"# TYPE {name} counter")
        lines.append(f"{name} {value}")

    for name, value in sorted(gauges.items()):
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {value}")

    lines.append("")  # trailing newline
    return "\n".join(lines)


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns system and application metrics in exposition format.
    """
    gauges = _collect_system_gauges()
    body = _format_prometheus(_counters, gauges)
    return Response(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
