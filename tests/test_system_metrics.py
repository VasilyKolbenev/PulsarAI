"""Tests for system metrics collection and SSE endpoints."""

import json
import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from pulsar_ai.ui.metrics import (
    collect_metrics,
    SystemMetrics,
    GPUMetrics,
    _collect_gpu_metrics,
)
from pulsar_ai.ui.app import create_app

# ──────────────────────────────────────────────────────────
# Metrics Collection
# ──────────────────────────────────────────────────────────


class TestCollectMetrics:
    """Test system metrics collection."""

    def test_returns_system_metrics(self):
        """Test collect_metrics returns SystemMetrics instance."""
        m = collect_metrics()
        assert isinstance(m, SystemMetrics)

    def test_cpu_percent_in_range(self):
        """Test CPU percent is between 0 and 100."""
        m = collect_metrics()
        assert 0 <= m.cpu_percent <= 100

    def test_cpu_count_positive(self):
        """Test CPU count is positive."""
        m = collect_metrics()
        assert m.cpu_count >= 1

    def test_ram_values_positive(self):
        """Test RAM values are positive."""
        m = collect_metrics()
        assert m.ram_total_gb > 0
        assert m.ram_used_gb > 0
        assert m.ram_used_gb <= m.ram_total_gb

    def test_ram_percent_in_range(self):
        """Test RAM percent is between 0 and 100."""
        m = collect_metrics()
        assert 0 <= m.ram_percent <= 100

    def test_disk_values_positive(self):
        """Test disk values are positive."""
        m = collect_metrics()
        assert m.disk_total_gb > 0
        assert m.disk_used_gb >= 0

    def test_timestamp_is_set(self):
        """Test timestamp is a valid float."""
        m = collect_metrics()
        assert m.timestamp > 0

    def test_gpus_is_list(self):
        """Test GPUs field is a list."""
        m = collect_metrics()
        assert isinstance(m.gpus, list)


class TestGPUMetrics:
    """Test GPU metrics collection."""

    def test_returns_list(self):
        """Test _collect_gpu_metrics returns a list."""
        result = _collect_gpu_metrics()
        assert isinstance(result, list)

    def test_gpu_metrics_dataclass(self):
        """Test GPUMetrics dataclass fields."""
        gpu = GPUMetrics(
            index=0,
            name="RTX 4090",
            utilization_percent=75.0,
            memory_used_gb=8.0,
            memory_total_gb=24.0,
            temperature_c=65,
            power_watts=250.0,
        )
        assert gpu.index == 0
        assert gpu.name == "RTX 4090"
        assert gpu.utilization_percent == 75.0

    def test_collect_with_mocked_gpus(self):
        """Test collect_metrics with mocked GPU data."""
        import pulsar_ai.ui.metrics as metrics_mod

        fake_gpus = [
            GPUMetrics(
                index=0,
                name="NVIDIA RTX 4090",
                utilization_percent=75.0,
                memory_used_gb=8.0,
                memory_total_gb=24.0,
                temperature_c=65,
                power_watts=250.0,
            ),
            GPUMetrics(
                index=1,
                name="NVIDIA RTX 4090",
                utilization_percent=50.0,
                memory_used_gb=4.0,
                memory_total_gb=24.0,
                temperature_c=55,
                power_watts=200.0,
            ),
        ]
        original = metrics_mod._collect_gpu_metrics
        metrics_mod._collect_gpu_metrics = lambda: fake_gpus
        try:
            m = collect_metrics()
            assert len(m.gpus) == 2
            assert m.gpus[0].name == "NVIDIA RTX 4090"
            assert m.gpus[0].utilization_percent == 75.0
            assert m.gpus[1].utilization_percent == 50.0
        finally:
            metrics_mod._collect_gpu_metrics = original


# ──────────────────────────────────────────────────────────
# API Endpoints
# ──────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """Create test client."""
    with (
        patch("pulsar_ai.ui.routes.training._store"),
        patch("pulsar_ai.ui.routes.experiments._store"),
        patch("pulsar_ai.ui.routes.evaluation._store"),
        patch("pulsar_ai.ui.routes.export_routes._store"),
    ):
        app = create_app()
        yield TestClient(app)


class TestMetricsAPI:
    """Test metrics API endpoints."""

    def test_snapshot_returns_200(self, client):
        """Test GET /api/v1/metrics/snapshot returns 200."""
        resp = client.get("/api/v1/metrics/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert "timestamp" in data
        assert "cpu_percent" in data
        assert "ram_used_gb" in data
        assert "ram_total_gb" in data
        assert "gpus" in data
        assert "cpu_count" in data

    def test_snapshot_has_valid_values(self, client):
        """Test snapshot returns valid metric values."""
        data = client.get("/api/v1/metrics/snapshot").json()
        assert data["ram_total_gb"] > 0
        assert 0 <= data["cpu_percent"] <= 100
        assert data["cpu_count"] >= 1

    def test_snapshot_has_disk(self, client):
        """Test snapshot includes disk metrics."""
        data = client.get("/api/v1/metrics/snapshot").json()
        assert "disk_total_gb" in data
        assert "disk_used_gb" in data
        assert data["disk_total_gb"] > 0

    def test_metrics_stream_function(self):
        """Test metrics_stream yields valid SSE events."""
        import asyncio
        from pulsar_ai.ui.metrics import metrics_stream

        async def read_first():
            async for event in metrics_stream(interval=0.1):
                return event

        result = asyncio.run(read_first())
        assert result.startswith("data: ")
        data = json.loads(result[6:])
        assert "timestamp" in data
        assert "cpu_percent" in data
        assert "gpus" in data

    def test_health_still_works(self, client):
        """Test that health endpoint still works after metrics added."""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
