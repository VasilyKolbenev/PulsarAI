"""Serving metrics collector for model endpoints.

Tracks request latency, throughput, tokens/sec, and error rates.
Thread-safe for use with concurrent serving.
"""

import logging
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RequestMetric:
    """Single request measurement."""

    timestamp: float
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    status: str = "ok"
    error: str = ""


class ServingMetrics:
    """Thread-safe serving metrics collector.

    Maintains a sliding window of request metrics for computing
    latency percentiles, throughput, and token rates.

    Args:
        window_size: Maximum number of requests to keep in memory.
    """

    def __init__(self, window_size: int = 10000) -> None:
        self._lock = threading.Lock()
        self._requests: deque[RequestMetric] = deque(maxlen=window_size)
        self._total_requests: int = 0
        self._total_errors: int = 0
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._start_time: float = time.time()

    def record(
        self,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        status: str = "ok",
        error: str = "",
    ) -> None:
        """Record a request metric.

        Args:
            latency_ms: Request latency in milliseconds.
            input_tokens: Number of input tokens processed.
            output_tokens: Number of output tokens generated.
            status: Request status ("ok" or "error").
            error: Error message if status is "error".
        """
        metric = RequestMetric(
            timestamp=time.time(),
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status=status,
            error=error,
        )

        with self._lock:
            self._requests.append(metric)
            self._total_requests += 1
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens
            if status == "error":
                self._total_errors += 1

    def get_summary(self, window_seconds: int = 60) -> dict[str, Any]:
        """Get metrics summary for a time window.

        Args:
            window_seconds: Look-back window in seconds.

        Returns:
            Dict with latency percentiles, throughput, token rates.
        """
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            recent = [r for r in self._requests if r.timestamp >= cutoff]
            total = self._total_requests
            total_errors = self._total_errors
            uptime = now - self._start_time

        if not recent:
            return {
                "window_seconds": window_seconds,
                "total_requests": total,
                "total_errors": total_errors,
                "uptime_seconds": round(uptime, 1),
                "requests_in_window": 0,
                "rps": 0.0,
                "latency_p50_ms": 0.0,
                "latency_p95_ms": 0.0,
                "latency_p99_ms": 0.0,
                "latency_avg_ms": 0.0,
                "tokens_per_second": 0.0,
                "error_rate": 0.0,
            }

        latencies = [r.latency_ms for r in recent]
        latencies.sort()
        ok_count = sum(1 for r in recent if r.status == "ok")
        error_count = len(recent) - ok_count
        output_tokens = sum(r.output_tokens for r in recent)

        return {
            "window_seconds": window_seconds,
            "total_requests": total,
            "total_errors": total_errors,
            "uptime_seconds": round(uptime, 1),
            "requests_in_window": len(recent),
            "rps": round(len(recent) / window_seconds, 2),
            "latency_p50_ms": round(_percentile(latencies, 50), 2),
            "latency_p95_ms": round(_percentile(latencies, 95), 2),
            "latency_p99_ms": round(_percentile(latencies, 99), 2),
            "latency_avg_ms": round(statistics.mean(latencies), 2),
            "latency_min_ms": round(min(latencies), 2),
            "latency_max_ms": round(max(latencies), 2),
            "tokens_per_second": round(output_tokens / window_seconds, 2),
            "error_rate": round(error_count / len(recent), 4) if recent else 0.0,
        }

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._requests.clear()
            self._total_requests = 0
            self._total_errors = 0
            self._total_input_tokens = 0
            self._total_output_tokens = 0
            self._start_time = time.time()


def _percentile(sorted_data: list[float], pct: float) -> float:
    """Compute percentile from sorted data.

    Args:
        sorted_data: Pre-sorted list of values.
        pct: Percentile (0-100).

    Returns:
        Percentile value.
    """
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_data) - 1)
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


# Global singleton for app-wide metrics
_global_metrics = ServingMetrics()


def get_global_metrics() -> ServingMetrics:
    """Get the global serving metrics instance."""
    return _global_metrics
