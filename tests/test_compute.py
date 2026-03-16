"""Tests for compute target management and remote runner."""

import pytest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from pulsar_ai.compute.manager import ComputeManager, ComputeTarget, ConnectionTestResult
from pulsar_ai.compute.ssh import SSHConnection
from pulsar_ai.compute.remote_runner import RemoteJobRunner, RemoteJobStatus
from pulsar_ai.storage.database import Database
from pulsar_ai.ui.app import create_app

# ──────────────────────────────────────────────────────────
# ComputeManager
# ──────────────────────────────────────────────────────────


class TestComputeManager:
    """Test compute target CRUD operations."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create manager with temp store."""
        return ComputeManager(db=Database(tmp_path / "test.db"))

    def test_add_target(self, manager):
        """Test adding a compute target."""
        target = manager.add_target(
            name="gpu-box",
            host="192.168.1.100",
            user="ubuntu",
        )
        assert target.name == "gpu-box"
        assert target.host == "192.168.1.100"
        assert target.user == "ubuntu"
        assert target.port == 22
        assert len(target.id) == 8

    def test_list_targets(self, manager):
        """Test listing targets."""
        manager.add_target(name="box1", host="10.0.0.1", user="user1")
        manager.add_target(name="box2", host="10.0.0.2", user="user2")
        targets = manager.list_targets()
        assert len(targets) == 2
        assert targets[0].name == "box1"
        assert targets[1].name == "box2"

    def test_get_target(self, manager):
        """Test getting a specific target."""
        created = manager.add_target(name="test", host="1.2.3.4", user="u")
        found = manager.get_target(created.id)
        assert found is not None
        assert found.name == "test"
        assert found.host == "1.2.3.4"

    def test_get_target_not_found(self, manager):
        """Test getting nonexistent target."""
        assert manager.get_target("nonexistent") is None

    def test_remove_target(self, manager):
        """Test removing a target."""
        target = manager.add_target(name="temp", host="1.1.1.1", user="u")
        assert manager.remove_target(target.id) is True
        assert manager.list_targets() == []

    def test_remove_nonexistent(self, manager):
        """Test removing nonexistent target."""
        assert manager.remove_target("nope") is False

    def test_add_with_key_path(self, manager):
        """Test adding target with SSH key."""
        target = manager.add_target(
            name="keyed",
            host="10.0.0.1",
            user="ubuntu",
            port=2222,
            key_path="/home/user/.ssh/id_rsa",
        )
        assert target.port == 2222
        assert target.key_path == "/home/user/.ssh/id_rsa"

    def test_targets_persist(self, tmp_path):
        """Test targets persist across manager instances."""
        db = Database(tmp_path / "persist.db")
        m1 = ComputeManager(db=db)
        m1.add_target(name="persist", host="5.5.5.5", user="x")

        m2 = ComputeManager(db=db)
        targets = m2.list_targets()
        assert len(targets) == 1
        assert targets[0].name == "persist"


# ──────────────────────────────────────────────────────────
# SSHConnection
# ──────────────────────────────────────────────────────────


class TestSSHConnection:
    """Test SSH connection wrapper."""

    def test_init(self):
        """Test SSH connection initialization."""
        conn = SSHConnection(host="1.2.3.4", user="ubuntu", port=2222)
        assert conn.host == "1.2.3.4"
        assert conn.user == "ubuntu"
        assert conn.port == 2222
        assert conn.key_path is None

    def test_init_with_key(self):
        """Test SSH connection with key path."""
        conn = SSHConnection(host="10.0.0.1", user="root", key_path="/tmp/key")
        assert conn.key_path == "/tmp/key"

    def test_context_manager(self):
        """Test SSH connection as context manager."""
        with (
            patch.object(SSHConnection, "connect") as mock_connect,
            patch.object(SSHConnection, "close") as mock_close,
        ):
            with SSHConnection(host="x", user="y") as conn:
                mock_connect.assert_called_once()
            mock_close.assert_called_once()


# ──────────────────────────────────────────────────────────
# RemoteJobRunner
# ──────────────────────────────────────────────────────────


class TestRemoteJobRunner:
    """Test remote job runner."""

    def test_init(self):
        """Test runner initialization."""
        target = ComputeTarget(
            id="abc",
            name="test",
            host="1.2.3.4",
            user="ubuntu",
            gpu_count=2,
        )
        runner = RemoteJobRunner(target)
        assert runner.target.id == "abc"
        assert runner.target.gpu_count == 2

    def test_remote_job_status_dataclass(self):
        """Test RemoteJobStatus fields."""
        status = RemoteJobStatus(
            job_id="j1",
            target_id="t1",
            status="running",
            started_at="2025-01-01",
            log_tail=["training step 1", "loss: 0.5"],
        )
        assert status.job_id == "j1"
        assert status.status == "running"
        assert len(status.log_tail) == 2


# ──────────────────────────────────────────────────────────
# API Endpoints
# ──────────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path):
    """Create test client with patched stores."""
    with (
        patch("pulsar_ai.ui.routes.training._store"),
        patch("pulsar_ai.ui.routes.experiments._store"),
        patch("pulsar_ai.ui.routes.evaluation._store"),
        patch("pulsar_ai.ui.routes.export_routes._store"),
        patch("pulsar_ai.ui.routes.compute._manager") as mock_mgr,
    ):
        mock_mgr.list_targets.return_value = []
        mock_mgr.add_target.return_value = ComputeTarget(
            id="abc12345",
            name="test-gpu",
            host="10.0.0.1",
            user="ubuntu",
            added_at="2025-01-01",
        )
        mock_mgr.get_target.return_value = ComputeTarget(
            id="abc12345",
            name="test-gpu",
            host="10.0.0.1",
            user="ubuntu",
            added_at="2025-01-01",
        )
        mock_mgr.remove_target.return_value = True
        mock_mgr.test_connection.return_value = ConnectionTestResult(
            success=True, message="OK", latency_ms=50.0
        )
        mock_mgr.detect_remote_hardware.return_value = {
            "gpu_count": 2,
            "gpu_type": "RTX 4090",
            "vram_gb": 24.0,
        }
        app = create_app()
        yield TestClient(app)


class TestComputeAPI:
    """Test compute API endpoints."""

    def test_list_targets(self, client):
        """Test GET /api/v1/compute/targets."""
        resp = client.get("/api/v1/compute/targets")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_add_target(self, client):
        """Test POST /api/v1/compute/targets."""
        resp = client.post(
            "/api/v1/compute/targets",
            json={
                "name": "test-gpu",
                "host": "10.0.0.1",
                "user": "ubuntu",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-gpu"
        assert "id" in data

    def test_get_target(self, client):
        """Test GET /api/v1/compute/targets/{id}."""
        resp = client.get("/api/v1/compute/targets/abc12345")
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-gpu"

    def test_remove_target(self, client):
        """Test DELETE /api/v1/compute/targets/{id}."""
        resp = client.delete("/api/v1/compute/targets/abc12345")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_test_connection(self, client):
        """Test POST /api/v1/compute/targets/{id}/test."""
        resp = client.post("/api/v1/compute/targets/abc12345/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["latency_ms"] == 50.0

    def test_detect_hardware(self, client):
        """Test POST /api/v1/compute/targets/{id}/detect."""
        resp = client.post("/api/v1/compute/targets/abc12345/detect")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gpu_count"] == 2
        assert data["gpu_type"] == "RTX 4090"
