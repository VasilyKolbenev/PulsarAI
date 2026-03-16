"""Tests for model registry."""

import pytest

from pulsar_ai.registry import ModelRegistry


@pytest.fixture
def registry(tmp_path):
    """Create registry with temp file."""
    return ModelRegistry(registry_path=tmp_path / "registry.json")


class TestModelRegistry:
    """Test ModelRegistry CRUD operations."""

    def test_register_model(self, registry):
        entry = registry.register(
            name="customer-intent",
            model_path="/outputs/sft/lora",
            task="sft",
            base_model="qwen2.5-3b",
            metrics={"accuracy": 0.95},
            tags=["production-ready"],
        )

        assert entry["id"] == "customer-intent-v1"
        assert entry["version"] == 1
        assert entry["status"] == "registered"
        assert entry["metrics"]["accuracy"] == 0.95

    def test_register_multiple_versions(self, registry):
        registry.register(name="model-a", model_path="/v1")
        entry2 = registry.register(name="model-a", model_path="/v2")

        assert entry2["id"] == "model-a-v2"
        assert entry2["version"] == 2

    def test_list_models(self, registry):
        registry.register(name="a", model_path="/a")
        registry.register(name="b", model_path="/b")
        registry.register(name="a", model_path="/a2")

        assert len(registry.list_models()) == 3
        assert len(registry.list_models(name="a")) == 2
        assert len(registry.list_models(name="b")) == 1

    def test_list_by_status(self, registry):
        registry.register(name="a", model_path="/a")
        registry.register(name="b", model_path="/b")
        registry.update_status("a-v1", "production")

        assert len(registry.list_models(status="registered")) == 1
        assert len(registry.list_models(status="production")) == 1

    def test_list_by_tag(self, registry):
        registry.register(name="a", model_path="/a", tags=["sft", "v1"])
        registry.register(name="b", model_path="/b", tags=["dpo"])

        assert len(registry.list_models(tag="sft")) == 1
        assert len(registry.list_models(tag="dpo")) == 1
        assert len(registry.list_models(tag="nonexistent")) == 0

    def test_get_model(self, registry):
        registry.register(name="test", model_path="/test")
        model = registry.get("test-v1")
        assert model is not None
        assert model["name"] == "test"

    def test_get_nonexistent(self, registry):
        assert registry.get("nonexistent") is None

    def test_get_latest(self, registry):
        registry.register(name="model", model_path="/v1")
        registry.register(name="model", model_path="/v2")
        registry.register(name="model", model_path="/v3")

        latest = registry.get_latest("model")
        assert latest["version"] == 3
        assert latest["model_path"] == "/v3"

    def test_get_latest_nonexistent(self, registry):
        assert registry.get_latest("nomodel") is None

    def test_update_status(self, registry):
        registry.register(name="m", model_path="/m")

        result = registry.update_status("m-v1", "staging")
        assert result["status"] == "staging"

        result = registry.update_status("m-v1", "production")
        assert result["status"] == "production"
        assert result["deployed_at"] is not None

    def test_update_status_nonexistent(self, registry):
        assert registry.update_status("nope", "production") is None

    def test_update_metrics(self, registry):
        registry.register(name="m", model_path="/m", metrics={"accuracy": 0.9})

        result = registry.update_metrics("m-v1", {"f1": 0.88, "accuracy": 0.95})
        assert result["metrics"]["accuracy"] == 0.95
        assert result["metrics"]["f1"] == 0.88

    def test_delete(self, registry):
        registry.register(name="del-test", model_path="/del")
        assert registry.delete("del-test-v1") is True
        assert registry.get("del-test-v1") is None

    def test_delete_nonexistent(self, registry):
        assert registry.delete("nope") is False

    def test_compare_models(self, registry):
        registry.register(
            name="a",
            model_path="/a",
            metrics={"accuracy": 0.9, "loss": 0.2},
        )
        registry.register(
            name="b",
            model_path="/b",
            metrics={"accuracy": 0.95, "loss": 0.15},
        )

        result = registry.compare(["a-v1", "b-v1"])
        assert len(result["models"]) == 2
        assert "accuracy" in result["metrics"]
        assert result["metrics"]["accuracy"] == [0.9, 0.95]

    def test_compare_insufficient(self, registry):
        registry.register(name="a", model_path="/a")
        result = registry.compare(["a-v1"])
        assert "error" in result

    def test_persistence(self, tmp_path):
        path = tmp_path / "reg.json"
        reg1 = ModelRegistry(registry_path=path)
        reg1.register(name="persist", model_path="/p")

        reg2 = ModelRegistry(registry_path=path)
        assert len(reg2.list_models()) == 1
        assert reg2.get("persist-v1") is not None
