"""Tests for Web UI API routes."""

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from pulsar_ai.ui.app import create_app


@pytest.fixture
def client(tmp_path):
    """Create a test client with temp experiment store."""
    with (
        patch("pulsar_ai.ui.routes.training._store") as mock_store,
        patch("pulsar_ai.ui.routes.experiments._store") as mock_exp_store,
        patch("pulsar_ai.ui.routes.evaluation._store") as mock_eval_store,
        patch("pulsar_ai.ui.routes.export_routes._store") as mock_export_store,
    ):

        mock_store.create.return_value = "exp123"
        mock_exp_store.list_all.return_value = []
        mock_exp_store.get.return_value = None
        mock_eval_store.get.return_value = None
        mock_export_store.get.return_value = None

        app = create_app()
        yield TestClient(app)


class TestHealthEndpoint:
    """Test health check."""

    def test_health(self, client):
        """Test GET /api/v1/health returns ok."""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestTrainingRoutes:
    """Test training endpoints."""

    @patch("pulsar_ai.ui.routes.training.submit_training_job")
    def test_start_training(self, mock_submit, client):
        """Test POST /api/v1/training/start."""
        mock_submit.return_value = "job123"

        resp = client.post(
            "/api/v1/training/start",
            json={
                "name": "test-experiment",
                "config": {"model": {"name": "test"}},
                "task": "sft",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "job123"
        assert data["experiment_id"] == "exp123"
        assert data["status"] == "running"

    @patch("pulsar_ai.ui.routes.training.list_jobs")
    def test_list_jobs(self, mock_list, client):
        """Test GET /api/v1/training/jobs."""
        mock_list.return_value = [
            {"job_id": "j1", "status": "running", "experiment_id": "e1"},
        ]
        resp = client.get("/api/v1/training/jobs")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @patch("pulsar_ai.ui.routes.training.get_job")
    def test_get_job_not_found(self, mock_get, client):
        """Test GET /api/v1/training/jobs/{id} returns 404."""
        mock_get.return_value = None
        resp = client.get("/api/v1/training/jobs/unknown")
        assert resp.status_code == 404

    @patch("pulsar_ai.ui.routes.training.cancel_job")
    def test_cancel_job(self, mock_cancel, client):
        """Test DELETE /api/v1/training/jobs/{id}."""
        mock_cancel.return_value = True
        resp = client.delete("/api/v1/training/jobs/j1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    @patch("pulsar_ai.ui.routes.training.cancel_job")
    def test_cancel_job_fails(self, mock_cancel, client):
        """Test cancel returns 400 when job can't be cancelled."""
        mock_cancel.return_value = False
        resp = client.delete("/api/v1/training/jobs/j1")
        assert resp.status_code == 400


class TestExperimentRoutes:
    """Test experiment endpoints."""

    def test_list_experiments(self, client):
        """Test GET /api/v1/experiments."""
        resp = client.get("/api/v1/experiments")
        assert resp.status_code == 200

    def test_get_experiment_not_found(self, client):
        """Test GET /api/v1/experiments/{id} returns 404."""
        resp = client.get("/api/v1/experiments/nonexistent")
        assert resp.status_code == 404


class TestDatasetRoutes:
    """Test dataset endpoints."""

    def test_upload_csv(self, client, tmp_path):
        """Test POST /api/v1/datasets/upload with CSV."""
        csv_content = b"text,label\nhello,positive\nbye,negative\n"

        with patch("pulsar_ai.ui.routes.datasets.DATA_DIR", tmp_path):
            resp = client.post(
                "/api/v1/datasets/upload",
                files={"file": ("test.csv", csv_content, "text/csv")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test.csv"
        assert data["format"] == "csv"
        assert data["num_rows"] == 2
        assert "text" in data["columns"]
        assert "label" in data["columns"]

    def test_upload_unsupported_format(self, client):
        """Test upload rejects unsupported formats."""
        resp = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400

    def test_list_datasets(self, client, tmp_path):
        """Test GET /api/v1/datasets."""
        # Create a test CSV
        csv_path = tmp_path / "abc123.csv"
        csv_path.write_text("a,b\n1,2\n")

        with patch("pulsar_ai.ui.routes.datasets.DATA_DIR", tmp_path):
            resp = client.get("/api/v1/datasets")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "abc123"

    def test_preview_dataset(self, client, tmp_path):
        """Test GET /api/v1/datasets/{id}/preview."""
        csv_path = tmp_path / "ds1.csv"
        csv_path.write_text("col1,col2\nval1,val2\nval3,val4\n")

        with patch("pulsar_ai.ui.routes.datasets.DATA_DIR", tmp_path):
            resp = client.get("/api/v1/datasets/ds1/preview")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 2
        assert len(data["rows"]) == 2
        assert "col1" in data["columns"]

    def test_preview_not_found(self, client, tmp_path):
        """Test preview returns 404 for missing dataset."""
        with patch("pulsar_ai.ui.routes.datasets.DATA_DIR", tmp_path):
            resp = client.get("/api/v1/datasets/missing/preview")
        assert resp.status_code == 404

    def test_delete_dataset(self, client, tmp_path):
        """Test DELETE /api/v1/datasets/{id}."""
        csv_path = tmp_path / "del1.csv"
        csv_path.write_text("a\n1\n")

        with patch("pulsar_ai.ui.routes.datasets.DATA_DIR", tmp_path):
            resp = client.delete("/api/v1/datasets/del1")

        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        assert not csv_path.exists()

    def test_delete_not_found(self, client, tmp_path):
        """Test delete returns 404 for missing dataset."""
        with patch("pulsar_ai.ui.routes.datasets.DATA_DIR", tmp_path):
            resp = client.delete("/api/v1/datasets/missing")
        assert resp.status_code == 404


class TestHardwareRoute:
    """Test hardware endpoint."""

    @patch("pulsar_ai.hardware.detect_hardware")
    def test_get_hardware(self, mock_detect, client):
        """Test GET /api/v1/hardware."""
        from pulsar_ai.hardware import HardwareInfo

        mock_detect.return_value = HardwareInfo(
            num_gpus=1,
            vram_per_gpu_gb=24.0,
            total_vram_gb=24.0,
            compute_capability=(8, 9),
            bf16_supported=True,
            gpu_name="RTX 4090",
            strategy="qlora",
            recommended_batch_size=4,
            recommended_gradient_accumulation=4,
        )

        resp = client.get("/api/v1/hardware")
        assert resp.status_code == 200
        data = resp.json()
        assert data["num_gpus"] == 1
        assert data["gpu_name"] == "RTX 4090"
        assert data["strategy"] == "qlora"


class TestEvalRoute:
    """Test evaluation endpoint."""

    def test_eval_experiment_not_found(self, client):
        """Test eval returns 404 when experiment not found."""
        resp = client.post(
            "/api/v1/evaluation/run",
            json={
                "experiment_id": "missing",
                "test_data_path": "data/test.csv",
            },
        )
        assert resp.status_code == 404


class TestExportRoute:
    """Test export endpoint."""

    def test_export_experiment_not_found(self, client):
        """Test export returns 404 when experiment not found."""
        resp = client.post(
            "/api/v1/export",
            json={
                "experiment_id": "missing",
            },
        )
        assert resp.status_code == 404
