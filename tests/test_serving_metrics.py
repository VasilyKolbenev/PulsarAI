"""Tests for serving metrics collector."""

import time
import threading
import pytest

from pulsar_ai.serving.metrics import ServingMetrics, _percentile


class TestServingMetrics:
    """Test ServingMetrics collector."""

    def test_record_and_summary(self):
        m = ServingMetrics()
        m.record(latency_ms=100, input_tokens=10, output_tokens=50)
        m.record(latency_ms=200, input_tokens=20, output_tokens=100)
        m.record(latency_ms=150, input_tokens=15, output_tokens=75)

        summary = m.get_summary(window_seconds=60)
        assert summary["requests_in_window"] == 3
        assert summary["total_requests"] == 3
        assert summary["latency_avg_ms"] == pytest.approx(150.0)
        assert summary["latency_min_ms"] == 100.0
        assert summary["latency_max_ms"] == 200.0
        assert summary["total_errors"] == 0

    def test_error_tracking(self):
        m = ServingMetrics()
        m.record(latency_ms=100, status="ok")
        m.record(latency_ms=0, status="error", error="timeout")
        m.record(latency_ms=100, status="ok")

        summary = m.get_summary()
        assert summary["total_errors"] == 1
        assert summary["error_rate"] == pytest.approx(1 / 3, abs=0.01)

    def test_empty_summary(self):
        m = ServingMetrics()
        summary = m.get_summary()
        assert summary["requests_in_window"] == 0
        assert summary["rps"] == 0.0
        assert summary["latency_p50_ms"] == 0.0

    def test_reset(self):
        m = ServingMetrics()
        m.record(latency_ms=100)
        m.record(latency_ms=200)
        assert m.get_summary()["total_requests"] == 2

        m.reset()
        assert m.get_summary()["total_requests"] == 0

    def test_window_filtering(self):
        m = ServingMetrics()
        # Add an old request by manually setting timestamp
        from pulsar_ai.serving.metrics import RequestMetric

        old = RequestMetric(
            timestamp=time.time() - 120,  # 2 minutes ago
            latency_ms=500,
        )
        m._requests.append(old)
        m._total_requests = 1

        m.record(latency_ms=100)

        summary = m.get_summary(window_seconds=60)
        assert summary["requests_in_window"] == 1  # Only recent one
        assert summary["total_requests"] == 2  # Both counted in total

    def test_thread_safety(self):
        m = ServingMetrics()
        errors = []

        def record_many():
            try:
                for i in range(100):
                    m.record(latency_ms=float(i), output_tokens=10)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert m.get_summary()["total_requests"] == 400

    def test_percentile_percentiles(self):
        m = ServingMetrics()
        for i in range(100):
            m.record(latency_ms=float(i + 1))

        summary = m.get_summary()
        assert summary["latency_p50_ms"] == pytest.approx(50.5, abs=1)
        assert summary["latency_p95_ms"] == pytest.approx(95.5, abs=1)
        assert summary["latency_p99_ms"] == pytest.approx(99.5, abs=1)

    def test_tokens_per_second(self):
        m = ServingMetrics()
        for _ in range(10):
            m.record(latency_ms=100, output_tokens=100)

        summary = m.get_summary(window_seconds=60)
        assert summary["tokens_per_second"] == pytest.approx(1000 / 60, abs=1)


class TestPercentile:
    """Test _percentile utility."""

    def test_single_value(self):
        assert _percentile([5.0], 50) == 5.0

    def test_two_values(self):
        assert _percentile([1.0, 2.0], 50) == 1.5

    def test_empty(self):
        assert _percentile([], 50) == 0.0

    def test_100th_percentile(self):
        assert _percentile([1.0, 2.0, 3.0], 100) == 3.0

    def test_0th_percentile(self):
        assert _percentile([1.0, 2.0, 3.0], 0) == 1.0
