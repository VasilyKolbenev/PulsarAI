"""Canary and A/B deployment strategies.

Supports gradual rollout with traffic splitting between
model versions, with automatic rollback on error thresholds.
"""

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModelEndpoint:
    """A deployed model endpoint."""

    name: str
    model_id: str
    weight: float = 1.0
    status: str = "active"
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class CanaryConfig:
    """Configuration for canary deployment."""

    primary: ModelEndpoint | None = None
    canary: ModelEndpoint | None = None
    canary_weight: float = 0.1
    error_threshold: float = 0.05
    min_requests: int = 100
    auto_rollback: bool = True
    auto_promote: bool = False
    promote_after: int = 1000

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CanaryConfig":
        """Create from dict."""
        primary_data = data.get("primary", {})
        canary_data = data.get("canary", {})
        return cls(
            primary=ModelEndpoint(**primary_data) if primary_data else None,
            canary=ModelEndpoint(**canary_data) if canary_data else None,
            canary_weight=data.get("canary_weight", 0.1),
            error_threshold=data.get("error_threshold", 0.05),
            min_requests=data.get("min_requests", 100),
            auto_rollback=data.get("auto_rollback", True),
            auto_promote=data.get("auto_promote", False),
            promote_after=data.get("promote_after", 1000),
        )


@dataclass
class ABTestConfig:
    """Configuration for A/B model testing."""

    variants: list[ModelEndpoint] = field(default_factory=list)
    metric_name: str = "latency_ms"
    min_samples: int = 100
    confidence_level: float = 0.95

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ABTestConfig":
        """Create from dict."""
        variants = [
            ModelEndpoint(**v) if isinstance(v, dict) else v
            for v in data.get("variants", [])
        ]
        return cls(
            variants=variants,
            metric_name=data.get("metric_name", "latency_ms"),
            min_samples=data.get("min_samples", 100),
            confidence_level=data.get("confidence_level", 0.95),
        )


class CanaryDeployer:
    """Manages canary deployments with traffic splitting.

    Routes requests between primary and canary models based on
    configured weights, with automatic rollback on errors.

    Args:
        config: CanaryConfig with deployment settings.
    """

    def __init__(self, config: CanaryConfig) -> None:
        self.config = config
        self._primary_requests = 0
        self._primary_errors = 0
        self._canary_requests = 0
        self._canary_errors = 0

    def route(self) -> str:
        """Decide which endpoint to route a request to.

        Returns:
            "primary" or "canary".
        """
        if not self.config.canary or self.config.canary.status != "active":
            return "primary"

        if self._should_rollback():
            self.rollback()
            return "primary"

        if self._should_promote():
            self.promote()
            return "primary"

        if random.random() < self.config.canary_weight:
            return "canary"
        return "primary"

    def record_result(self, target: str, success: bool) -> None:
        """Record the result of a routed request.

        Args:
            target: "primary" or "canary".
            success: Whether the request succeeded.
        """
        if target == "canary":
            self._canary_requests += 1
            if not success:
                self._canary_errors += 1
        else:
            self._primary_requests += 1
            if not success:
                self._primary_errors += 1

    def _should_rollback(self) -> bool:
        """Check if canary should be rolled back."""
        if not self.config.auto_rollback:
            return False
        if self._canary_requests < self.config.min_requests:
            return False
        error_rate = self._canary_errors / self._canary_requests
        return error_rate > self.config.error_threshold

    def _should_promote(self) -> bool:
        """Check if canary should be promoted to primary."""
        if not self.config.auto_promote:
            return False
        return self._canary_requests >= self.config.promote_after

    def rollback(self) -> None:
        """Roll back canary — route all traffic to primary."""
        if self.config.canary:
            self.config.canary.status = "rolled_back"
            logger.info(
                "Canary rolled back: %s (error rate: %.2f%%)",
                self.config.canary.name,
                (self._canary_errors / max(1, self._canary_requests)) * 100,
            )

    def promote(self) -> None:
        """Promote canary to primary."""
        if self.config.canary:
            self.config.canary.status = "promoted"
            logger.info("Canary promoted: %s", self.config.canary.name)

    def get_status(self) -> dict[str, Any]:
        """Get current deployment status."""
        canary_error_rate = (
            self._canary_errors / self._canary_requests
            if self._canary_requests > 0 else 0.0
        )
        primary_error_rate = (
            self._primary_errors / self._primary_requests
            if self._primary_requests > 0 else 0.0
        )

        return {
            "primary": {
                "name": self.config.primary.name if self.config.primary else None,
                "requests": self._primary_requests,
                "error_rate": round(primary_error_rate, 4),
            },
            "canary": {
                "name": self.config.canary.name if self.config.canary else None,
                "status": self.config.canary.status if self.config.canary else None,
                "weight": self.config.canary_weight,
                "requests": self._canary_requests,
                "error_rate": round(canary_error_rate, 4),
            },
            "auto_rollback": self.config.auto_rollback,
            "error_threshold": self.config.error_threshold,
        }


class ABTester:
    """A/B testing between model variants.

    Distributes traffic by variant weights and collects metrics
    for statistical comparison.

    Args:
        config: ABTestConfig with variant definitions.
    """

    def __init__(self, config: ABTestConfig) -> None:
        self.config = config
        self._results: dict[str, list[float]] = {
            v.name: [] for v in config.variants
        }

    def route(self) -> str:
        """Select a variant weighted by config.

        Returns:
            Variant name.
        """
        if not self.config.variants:
            return ""
        total = sum(v.weight for v in self.config.variants)
        r = random.random() * total
        cumulative = 0.0
        for v in self.config.variants:
            cumulative += v.weight
            if r <= cumulative:
                return v.name
        return self.config.variants[-1].name

    def record_metric(self, variant_name: str, value: float) -> None:
        """Record a metric value for a variant.

        Args:
            variant_name: Variant name.
            value: Metric value.
        """
        if variant_name in self._results:
            self._results[variant_name].append(value)

    def get_results(self) -> dict[str, Any]:
        """Get A/B test results with basic statistics.

        Returns:
            Dict with per-variant stats.
        """
        results: dict[str, Any] = {}

        for name, values in self._results.items():
            if not values:
                results[name] = {"samples": 0, "mean": 0, "min": 0, "max": 0}
                continue

            results[name] = {
                "samples": len(values),
                "mean": round(sum(values) / len(values), 4),
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                "p50": round(sorted(values)[len(values) // 2], 4),
            }

        winner = None
        if all(r.get("samples", 0) >= self.config.min_samples for r in results.values()):
            means = {k: v["mean"] for k, v in results.items() if v["samples"] > 0}
            if means:
                winner = min(means, key=means.get)  # Lower is better for latency

        return {
            "metric": self.config.metric_name,
            "variants": results,
            "winner": winner,
            "sufficient_samples": all(
                r.get("samples", 0) >= self.config.min_samples for r in results.values()
            ),
        }
