"""Cost tracking for LLM operations.

Tracks token usage and estimates costs across models,
experiments, and pipeline runs.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Pricing table (per 1K tokens) ─────────────────────────────────

MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "claude-opus-4-6": {"input": 0.015, "output": 0.075},
    "claude-haiku-4-5": {"input": 0.001, "output": 0.005},
    "llama-3-8b": {"input": 0.0, "output": 0.0},
    "llama-3-70b": {"input": 0.0, "output": 0.0},
    "mistral-7b": {"input": 0.0, "output": 0.0},
    "local": {"input": 0.0, "output": 0.0},
}


@dataclass
class CostEntry:
    """A single cost entry for a tracked operation."""

    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    timestamp: float = 0.0
    operation: str = ""
    experiment_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost": self.estimated_cost,
            "timestamp": self.timestamp,
            "operation": self.operation,
            "experiment_id": self.experiment_id,
        }


class CostTracker:
    """Tracks token usage and costs across operations.

    Args:
        budget_limit: Optional budget limit in USD. 0 = no limit.
        custom_pricing: Override default model pricing.
    """

    def __init__(
        self,
        budget_limit: float = 0.0,
        custom_pricing: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self.budget_limit = budget_limit
        self._pricing = {**MODEL_PRICING, **(custom_pricing or {})}
        self._entries: list[CostEntry] = []

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        operation: str = "",
        experiment_id: str = "",
        **metadata: Any,
    ) -> CostEntry:
        """Record a token usage event.

        Args:
            model: Model name.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            operation: Operation type (inference, eval, agent, etc.).
            experiment_id: Associated experiment ID.
            **metadata: Extra metadata.

        Returns:
            The recorded CostEntry.
        """
        cost = self.estimate_cost(model, input_tokens, output_tokens)
        entry = CostEntry(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=cost,
            operation=operation,
            experiment_id=experiment_id,
            metadata=dict(metadata),
        )
        self._entries.append(entry)
        return entry

    def estimate_cost(
        self, model: str, input_tokens: int, output_tokens: int,
    ) -> float:
        """Estimate cost for a given model and token count.

        Args:
            model: Model name.
            input_tokens: Input token count.
            output_tokens: Output token count.

        Returns:
            Estimated cost in USD.
        """
        pricing = self._pricing.get(model, self._pricing.get("local", {}))
        cost = (
            (input_tokens / 1000) * pricing.get("input", 0.0)
            + (output_tokens / 1000) * pricing.get("output", 0.0)
        )
        return round(cost, 6)

    @property
    def total_cost(self) -> float:
        """Total cost across all entries."""
        return round(sum(e.estimated_cost for e in self._entries), 6)

    @property
    def total_tokens(self) -> int:
        """Total tokens across all entries."""
        return sum(e.input_tokens + e.output_tokens for e in self._entries)

    @property
    def is_over_budget(self) -> bool:
        """Check if total cost exceeds budget limit."""
        if self.budget_limit <= 0:
            return False
        return self.total_cost > self.budget_limit

    @property
    def budget_remaining(self) -> float | None:
        """Remaining budget, or None if no limit."""
        if self.budget_limit <= 0:
            return None
        return max(0.0, self.budget_limit - self.total_cost)

    def get_summary(
        self, experiment_id: str = "", window_seconds: float = 0,
    ) -> dict[str, Any]:
        """Get cost summary with breakdowns.

        Args:
            experiment_id: Filter by experiment.
            window_seconds: Only include entries within this time window. 0 = all.

        Returns:
            Cost summary dict.
        """
        entries = self._entries
        if experiment_id:
            entries = [e for e in entries if e.experiment_id == experiment_id]
        if window_seconds > 0:
            cutoff = time.time() - window_seconds
            entries = [e for e in entries if e.timestamp >= cutoff]

        by_model: dict[str, dict[str, Any]] = {}
        by_operation: dict[str, float] = {}

        for entry in entries:
            if entry.model not in by_model:
                by_model[entry.model] = {
                    "input_tokens": 0, "output_tokens": 0, "cost": 0.0, "calls": 0,
                }
            by_model[entry.model]["input_tokens"] += entry.input_tokens
            by_model[entry.model]["output_tokens"] += entry.output_tokens
            by_model[entry.model]["cost"] += entry.estimated_cost
            by_model[entry.model]["calls"] += 1

            op = entry.operation or "unknown"
            by_operation[op] = by_operation.get(op, 0.0) + entry.estimated_cost

        total_cost = sum(e.estimated_cost for e in entries)
        total_tokens = sum(e.input_tokens + e.output_tokens for e in entries)

        return {
            "total_cost": round(total_cost, 6),
            "total_tokens": total_tokens,
            "total_calls": len(entries),
            "by_model": by_model,
            "by_operation": {k: round(v, 6) for k, v in by_operation.items()},
            "budget_limit": self.budget_limit,
            "budget_remaining": self.budget_remaining,
            "is_over_budget": self.is_over_budget,
        }

    def add_pricing(self, model: str, input_per_1k: float, output_per_1k: float) -> None:
        """Add or update pricing for a model.

        Args:
            model: Model name.
            input_per_1k: Cost per 1K input tokens.
            output_per_1k: Cost per 1K output tokens.
        """
        self._pricing[model] = {"input": input_per_1k, "output": output_per_1k}

    def reset(self) -> None:
        """Clear all entries."""
        self._entries.clear()
