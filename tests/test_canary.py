"""Tests for llm_forge.deployment.canary module.

Tests CanaryDeployer routing, rollback, promote, traffic splitting,
CanaryConfig.from_dict, ABTester routing/metrics/winner detection.
"""

import random
from collections import Counter

import pytest

from llm_forge.deployment.canary import (
    ABTestConfig,
    ABTester,
    CanaryConfig,
    CanaryDeployer,
    ModelEndpoint,
)


@pytest.fixture
def primary_endpoint() -> ModelEndpoint:
    """Create a primary model endpoint."""
    return ModelEndpoint(name="primary-v1", model_id="gpt-4o", weight=1.0)


@pytest.fixture
def canary_endpoint() -> ModelEndpoint:
    """Create a canary model endpoint."""
    return ModelEndpoint(name="canary-v2", model_id="gpt-4o-new", weight=0.1)


@pytest.fixture
def canary_config(
    primary_endpoint: ModelEndpoint, canary_endpoint: ModelEndpoint,
) -> CanaryConfig:
    """Create a canary deployment config."""
    return CanaryConfig(
        primary=primary_endpoint,
        canary=canary_endpoint,
        canary_weight=0.2,
        error_threshold=0.05,
        min_requests=10,
        auto_rollback=True,
    )


class TestCanaryConfigFromDict:
    """Tests for CanaryConfig.from_dict()."""

    def test_from_dict_full(self) -> None:
        """from_dict with all fields creates correct config."""
        data = {
            "primary": {"name": "p", "model_id": "m1"},
            "canary": {"name": "c", "model_id": "m2"},
            "canary_weight": 0.3,
            "error_threshold": 0.1,
            "min_requests": 50,
            "auto_rollback": False,
            "auto_promote": True,
            "promote_after": 500,
        }
        config = CanaryConfig.from_dict(data)
        assert config.primary is not None
        assert config.primary.name == "p"
        assert config.canary is not None
        assert config.canary.name == "c"
        assert config.canary_weight == 0.3
        assert config.error_threshold == 0.1
        assert config.min_requests == 50
        assert config.auto_rollback is False
        assert config.auto_promote is True
        assert config.promote_after == 500

    def test_from_dict_defaults(self) -> None:
        """from_dict with empty dict uses defaults."""
        config = CanaryConfig.from_dict({})
        assert config.primary is None
        assert config.canary is None
        assert config.canary_weight == 0.1
        assert config.error_threshold == 0.05
        assert config.auto_rollback is True

    def test_from_dict_partial(self) -> None:
        """from_dict with partial data fills defaults."""
        config = CanaryConfig.from_dict({"canary_weight": 0.5})
        assert config.canary_weight == 0.5
        assert config.min_requests == 100


class TestCanaryDeployerRouting:
    """Tests for CanaryDeployer.route()."""

    def test_route_returns_primary_when_no_canary(
        self, primary_endpoint: ModelEndpoint,
    ) -> None:
        """Route returns 'primary' when no canary is configured."""
        config = CanaryConfig(primary=primary_endpoint, canary=None)
        deployer = CanaryDeployer(config)
        assert deployer.route() == "primary"

    def test_route_returns_primary_when_canary_inactive(
        self, primary_endpoint: ModelEndpoint, canary_endpoint: ModelEndpoint,
    ) -> None:
        """Route returns 'primary' when canary status is not 'active'."""
        canary_endpoint.status = "rolled_back"
        config = CanaryConfig(primary=primary_endpoint, canary=canary_endpoint)
        deployer = CanaryDeployer(config)
        assert deployer.route() == "primary"

    def test_traffic_split_respects_canary_weight(
        self, canary_config: CanaryConfig,
    ) -> None:
        """Traffic split roughly matches canary_weight over many requests."""
        deployer = CanaryDeployer(canary_config)
        random.seed(42)
        results = Counter(deployer.route() for _ in range(1000))
        canary_ratio = results["canary"] / 1000
        # canary_weight is 0.2, check within reasonable range
        assert 0.10 <= canary_ratio <= 0.35

    def test_route_all_primary_when_weight_zero(
        self, primary_endpoint: ModelEndpoint, canary_endpoint: ModelEndpoint,
    ) -> None:
        """Zero canary weight routes everything to primary."""
        config = CanaryConfig(
            primary=primary_endpoint, canary=canary_endpoint, canary_weight=0.0,
        )
        deployer = CanaryDeployer(config)
        results = [deployer.route() for _ in range(100)]
        assert all(r == "primary" for r in results)


class TestCanaryAutoRollback:
    """Tests for automatic rollback on error threshold."""

    def test_auto_rollback_on_error_threshold(
        self, canary_config: CanaryConfig,
    ) -> None:
        """Canary is rolled back when error rate exceeds threshold."""
        canary_config.canary_weight = 1.0  # force all traffic to canary
        deployer = CanaryDeployer(canary_config)

        # Record min_requests worth of errors (100% error rate)
        for _ in range(canary_config.min_requests):
            deployer.record_result("canary", success=False)

        # Next route should trigger rollback
        result = deployer.route()
        assert result == "primary"
        assert canary_config.canary is not None
        assert canary_config.canary.status == "rolled_back"

    def test_no_rollback_below_min_requests(
        self, canary_config: CanaryConfig,
    ) -> None:
        """No rollback if canary has fewer than min_requests."""
        deployer = CanaryDeployer(canary_config)
        # Record errors below min_requests threshold
        for _ in range(canary_config.min_requests - 1):
            deployer.record_result("canary", success=False)
        # Canary should still be active
        assert canary_config.canary is not None
        assert canary_config.canary.status == "active"

    def test_no_rollback_when_disabled(
        self, primary_endpoint: ModelEndpoint, canary_endpoint: ModelEndpoint,
    ) -> None:
        """No auto-rollback when auto_rollback=False."""
        config = CanaryConfig(
            primary=primary_endpoint, canary=canary_endpoint,
            auto_rollback=False, min_requests=5,
        )
        deployer = CanaryDeployer(config)
        for _ in range(10):
            deployer.record_result("canary", success=False)
        assert canary_endpoint.status == "active"


class TestCanaryPromote:
    """Tests for manual and auto promotion."""

    def test_manual_promote(self, canary_config: CanaryConfig) -> None:
        """promote() sets canary status to 'promoted'."""
        deployer = CanaryDeployer(canary_config)
        deployer.promote()
        assert canary_config.canary is not None
        assert canary_config.canary.status == "promoted"

    def test_auto_promote_after_threshold(
        self, primary_endpoint: ModelEndpoint, canary_endpoint: ModelEndpoint,
    ) -> None:
        """Auto-promote when canary reaches promote_after requests."""
        config = CanaryConfig(
            primary=primary_endpoint, canary=canary_endpoint,
            canary_weight=1.0, auto_promote=True, promote_after=10,
            auto_rollback=False,
        )
        deployer = CanaryDeployer(config)
        for _ in range(10):
            deployer.record_result("canary", success=True)
        deployer.route()  # triggers promote check
        assert canary_endpoint.status == "promoted"


class TestCanaryGetStatus:
    """Tests for CanaryDeployer.get_status()."""

    def test_get_status_structure(self, canary_config: CanaryConfig) -> None:
        """get_status returns dict with expected keys."""
        deployer = CanaryDeployer(canary_config)
        deployer.record_result("primary", success=True)
        deployer.record_result("canary", success=True)
        deployer.record_result("canary", success=False)

        status = deployer.get_status()
        assert "primary" in status
        assert "canary" in status
        assert status["primary"]["requests"] == 1
        assert status["canary"]["requests"] == 2
        assert status["canary"]["error_rate"] == pytest.approx(0.5)
        assert status["auto_rollback"] is True

    def test_get_status_no_canary(self, primary_endpoint: ModelEndpoint) -> None:
        """get_status handles missing canary gracefully."""
        config = CanaryConfig(primary=primary_endpoint, canary=None)
        deployer = CanaryDeployer(config)
        status = deployer.get_status()
        assert status["canary"]["name"] is None
        assert status["canary"]["status"] is None


class TestABTesterRouting:
    """Tests for ABTester.route()."""

    def test_route_respects_weights(self) -> None:
        """Routing distribution matches variant weights."""
        config = ABTestConfig(
            variants=[
                ModelEndpoint(name="A", model_id="m1", weight=3.0),
                ModelEndpoint(name="B", model_id="m2", weight=1.0),
            ],
        )
        tester = ABTester(config)
        random.seed(42)
        results = Counter(tester.route() for _ in range(1000))
        ratio_a = results["A"] / 1000
        # weight A is 3/(3+1) = 0.75
        assert 0.60 <= ratio_a <= 0.90

    def test_route_empty_variants(self) -> None:
        """Route returns empty string when no variants."""
        config = ABTestConfig(variants=[])
        tester = ABTester(config)
        assert tester.route() == ""

    def test_route_single_variant(self) -> None:
        """Single variant always selected."""
        config = ABTestConfig(
            variants=[ModelEndpoint(name="only", model_id="m1")],
        )
        tester = ABTester(config)
        results = [tester.route() for _ in range(50)]
        assert all(r == "only" for r in results)


class TestABTesterMetrics:
    """Tests for ABTester.record_metric() and get_results()."""

    def test_record_metric_and_get_results(self) -> None:
        """Recorded metrics appear in get_results()."""
        config = ABTestConfig(
            variants=[
                ModelEndpoint(name="A", model_id="m1"),
                ModelEndpoint(name="B", model_id="m2"),
            ],
            min_samples=3,
        )
        tester = ABTester(config)

        for val in [100.0, 200.0, 300.0]:
            tester.record_metric("A", val)
        for val in [150.0, 250.0, 350.0]:
            tester.record_metric("B", val)

        results = tester.get_results()
        assert results["variants"]["A"]["samples"] == 3
        assert results["variants"]["A"]["mean"] == pytest.approx(200.0)
        assert results["variants"]["B"]["samples"] == 3
        assert results["variants"]["B"]["mean"] == pytest.approx(250.0)

    def test_record_metric_unknown_variant_ignored(self) -> None:
        """Recording metric for unknown variant is silently ignored."""
        config = ABTestConfig(
            variants=[ModelEndpoint(name="A", model_id="m1")],
        )
        tester = ABTester(config)
        tester.record_metric("nonexistent", 100.0)
        results = tester.get_results()
        assert "nonexistent" not in results["variants"]

    def test_no_samples_returns_zero(self) -> None:
        """Variant with no samples returns zero stats."""
        config = ABTestConfig(
            variants=[ModelEndpoint(name="A", model_id="m1")],
        )
        tester = ABTester(config)
        results = tester.get_results()
        assert results["variants"]["A"]["samples"] == 0
        assert results["variants"]["A"]["mean"] == 0


class TestABTesterWinnerDetection:
    """Tests for A/B test winner detection."""

    def test_winner_detected_when_sufficient_samples(self) -> None:
        """Winner is detected when all variants have >= min_samples."""
        config = ABTestConfig(
            variants=[
                ModelEndpoint(name="fast", model_id="m1"),
                ModelEndpoint(name="slow", model_id="m2"),
            ],
            min_samples=5,
        )
        tester = ABTester(config)

        for _ in range(5):
            tester.record_metric("fast", 50.0)
            tester.record_metric("slow", 150.0)

        results = tester.get_results()
        assert results["sufficient_samples"] is True
        assert results["winner"] == "fast"  # lower is better

    def test_no_winner_insufficient_samples(self) -> None:
        """No winner when min_samples not reached."""
        config = ABTestConfig(
            variants=[
                ModelEndpoint(name="A", model_id="m1"),
                ModelEndpoint(name="B", model_id="m2"),
            ],
            min_samples=100,
        )
        tester = ABTester(config)
        tester.record_metric("A", 50.0)
        tester.record_metric("B", 150.0)

        results = tester.get_results()
        assert results["sufficient_samples"] is False
        assert results["winner"] is None

    def test_winner_lower_is_better(self) -> None:
        """Winner is the variant with the lowest mean (latency)."""
        config = ABTestConfig(
            variants=[
                ModelEndpoint(name="A", model_id="m1"),
                ModelEndpoint(name="B", model_id="m2"),
            ],
            min_samples=2,
        )
        tester = ABTester(config)
        tester.record_metric("A", 300.0)
        tester.record_metric("A", 400.0)
        tester.record_metric("B", 100.0)
        tester.record_metric("B", 200.0)

        results = tester.get_results()
        assert results["winner"] == "B"
