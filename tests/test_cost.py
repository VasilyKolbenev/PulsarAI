"""Tests for llm_forge.cost module.

Tests CostTracker.record(), estimate_cost(), budget management,
get_summary() breakdowns, add_pricing(), and reset().
"""

import pytest

from llm_forge.cost import CostTracker, MODEL_PRICING


class TestEstimateCost:
    """Tests for cost estimation with known and unknown models."""

    def test_estimate_cost_gpt4o(self) -> None:
        """Estimate cost for gpt-4o uses correct pricing."""
        tracker = CostTracker()
        cost = tracker.estimate_cost("gpt-4o", input_tokens=1000, output_tokens=1000)
        expected = (1000 / 1000) * 0.0025 + (1000 / 1000) * 0.01
        assert cost == pytest.approx(expected, abs=1e-6)

    def test_estimate_cost_claude_sonnet(self) -> None:
        """Estimate cost for claude-sonnet-4-6 uses correct pricing."""
        tracker = CostTracker()
        cost = tracker.estimate_cost("claude-sonnet-4-6", 2000, 500)
        expected = (2000 / 1000) * 0.003 + (500 / 1000) * 0.015
        assert cost == pytest.approx(expected, abs=1e-6)

    def test_local_model_costs_zero(self) -> None:
        """Local models have zero cost."""
        tracker = CostTracker()
        for model in ("llama-3-8b", "llama-3-70b", "mistral-7b", "local"):
            cost = tracker.estimate_cost(model, input_tokens=10000, output_tokens=5000)
            assert cost == 0.0, f"{model} should have zero cost"

    def test_unknown_model_falls_back_to_local(self) -> None:
        """Unknown model falls back to 'local' pricing (zero)."""
        tracker = CostTracker()
        cost = tracker.estimate_cost("unknown-model-xyz", 5000, 5000)
        assert cost == 0.0


class TestCostTrackerRecord:
    """Tests for CostTracker.record()."""

    def test_record_creates_entry(self) -> None:
        """record() creates a CostEntry and appends it."""
        tracker = CostTracker()
        entry = tracker.record("gpt-4o", 100, 50, operation="inference")
        assert entry.model == "gpt-4o"
        assert entry.input_tokens == 100
        assert entry.output_tokens == 50
        assert entry.operation == "inference"
        assert entry.estimated_cost > 0

    def test_record_with_experiment_id(self) -> None:
        """record() stores experiment_id."""
        tracker = CostTracker()
        entry = tracker.record("gpt-4o", 100, 50, experiment_id="exp-001")
        assert entry.experiment_id == "exp-001"

    def test_record_with_metadata(self) -> None:
        """record() stores extra metadata kwargs."""
        tracker = CostTracker()
        entry = tracker.record("gpt-4o", 100, 50, run_id="r1")
        assert entry.metadata["run_id"] == "r1"

    def test_record_sets_timestamp(self) -> None:
        """record() entry has a positive timestamp."""
        tracker = CostTracker()
        entry = tracker.record("gpt-4o", 100, 50)
        assert entry.timestamp > 0


class TestTotalCostAndTokens:
    """Tests for total_cost and total_tokens properties."""

    def test_total_cost_accumulates(self) -> None:
        """total_cost sums across multiple records."""
        tracker = CostTracker()
        tracker.record("gpt-4o", 1000, 1000)
        tracker.record("gpt-4o", 1000, 1000)
        single_cost = tracker.estimate_cost("gpt-4o", 1000, 1000)
        assert tracker.total_cost == pytest.approx(single_cost * 2, abs=1e-6)

    def test_total_tokens_accumulates(self) -> None:
        """total_tokens sums input + output across records."""
        tracker = CostTracker()
        tracker.record("gpt-4o", 100, 50)
        tracker.record("gpt-4o", 200, 100)
        assert tracker.total_tokens == 450

    def test_empty_tracker_zero(self) -> None:
        """Empty tracker has zero cost and tokens."""
        tracker = CostTracker()
        assert tracker.total_cost == 0.0
        assert tracker.total_tokens == 0


class TestBudgetManagement:
    """Tests for budget limit tracking."""

    def test_is_over_budget_false_when_no_limit(self) -> None:
        """No budget limit means never over budget."""
        tracker = CostTracker(budget_limit=0.0)
        tracker.record("gpt-4o", 100000, 100000)
        assert tracker.is_over_budget is False

    def test_is_over_budget_false_within_limit(self) -> None:
        """Under budget returns False."""
        tracker = CostTracker(budget_limit=100.0)
        tracker.record("gpt-4o", 100, 50)
        assert tracker.is_over_budget is False

    def test_is_over_budget_true_when_exceeded(self) -> None:
        """Over budget returns True."""
        tracker = CostTracker(budget_limit=0.001)
        tracker.record("gpt-4o", 10000, 10000)
        assert tracker.is_over_budget is True

    def test_budget_remaining_with_limit(self) -> None:
        """budget_remaining decreases as costs accumulate."""
        tracker = CostTracker(budget_limit=1.0)
        cost = tracker.record("gpt-4o", 1000, 1000).estimated_cost
        remaining = tracker.budget_remaining
        assert remaining is not None
        assert remaining == pytest.approx(1.0 - cost, abs=1e-6)

    def test_budget_remaining_no_limit(self) -> None:
        """budget_remaining is None when no budget limit."""
        tracker = CostTracker(budget_limit=0.0)
        assert tracker.budget_remaining is None

    def test_budget_remaining_never_negative(self) -> None:
        """budget_remaining floors at 0.0."""
        tracker = CostTracker(budget_limit=0.0001)
        tracker.record("gpt-4o", 100000, 100000)
        remaining = tracker.budget_remaining
        assert remaining is not None
        assert remaining == 0.0


class TestGetSummary:
    """Tests for get_summary() with model/operation breakdowns and filters."""

    def test_summary_by_model(self) -> None:
        """Summary includes per-model breakdown."""
        tracker = CostTracker()
        tracker.record("gpt-4o", 1000, 500, operation="inference")
        tracker.record("claude-sonnet-4-6", 2000, 1000, operation="eval")
        summary = tracker.get_summary()
        assert "gpt-4o" in summary["by_model"]
        assert "claude-sonnet-4-6" in summary["by_model"]
        assert summary["by_model"]["gpt-4o"]["calls"] == 1
        assert summary["by_model"]["claude-sonnet-4-6"]["calls"] == 1

    def test_summary_by_operation(self) -> None:
        """Summary includes per-operation cost breakdown."""
        tracker = CostTracker()
        tracker.record("gpt-4o", 1000, 500, operation="inference")
        tracker.record("gpt-4o", 2000, 1000, operation="eval")
        summary = tracker.get_summary()
        assert "inference" in summary["by_operation"]
        assert "eval" in summary["by_operation"]

    def test_summary_total_calls(self) -> None:
        """Summary total_calls matches number of records."""
        tracker = CostTracker()
        for _ in range(5):
            tracker.record("gpt-4o", 100, 50)
        summary = tracker.get_summary()
        assert summary["total_calls"] == 5

    def test_summary_filter_by_experiment_id(self) -> None:
        """Summary filtered by experiment_id only includes matching entries."""
        tracker = CostTracker()
        tracker.record("gpt-4o", 1000, 500, experiment_id="exp-A")
        tracker.record("gpt-4o", 2000, 1000, experiment_id="exp-B")
        tracker.record("gpt-4o", 3000, 1500, experiment_id="exp-A")

        summary_a = tracker.get_summary(experiment_id="exp-A")
        assert summary_a["total_calls"] == 2
        assert summary_a["total_tokens"] == 1000 + 500 + 3000 + 1500

    def test_summary_includes_budget_info(self) -> None:
        """Summary includes budget_limit and budget_remaining."""
        tracker = CostTracker(budget_limit=10.0)
        tracker.record("gpt-4o", 1000, 500)
        summary = tracker.get_summary()
        assert summary["budget_limit"] == 10.0
        assert summary["budget_remaining"] is not None
        assert "is_over_budget" in summary


class TestAddPricing:
    """Tests for add_pricing() custom model pricing."""

    def test_add_pricing_new_model(self) -> None:
        """add_pricing registers pricing for a new model."""
        tracker = CostTracker()
        tracker.add_pricing("my-custom-model", input_per_1k=0.005, output_per_1k=0.02)
        cost = tracker.estimate_cost("my-custom-model", 1000, 1000)
        assert cost == pytest.approx(0.005 + 0.02, abs=1e-6)

    def test_add_pricing_override_existing(self) -> None:
        """add_pricing overrides existing model pricing."""
        tracker = CostTracker()
        tracker.add_pricing("gpt-4o", input_per_1k=0.1, output_per_1k=0.2)
        cost = tracker.estimate_cost("gpt-4o", 1000, 1000)
        assert cost == pytest.approx(0.3, abs=1e-6)


class TestReset:
    """Tests for reset() clearing all entries."""

    def test_reset_clears_entries(self) -> None:
        """reset() removes all recorded entries."""
        tracker = CostTracker()
        tracker.record("gpt-4o", 1000, 500)
        tracker.record("gpt-4o", 2000, 1000)
        assert tracker.total_tokens > 0
        tracker.reset()
        assert tracker.total_cost == 0.0
        assert tracker.total_tokens == 0
        assert tracker.get_summary()["total_calls"] == 0
