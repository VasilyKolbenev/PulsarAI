"""Tests for config validation."""

from pulsar_ai.validation import validate_config, _has_nested


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_valid_sft_config(self) -> None:
        config = {
            "task": "sft",
            "model": {"name": "test-model"},
            "dataset": {"path": "data.csv"},
            "training": {"epochs": 3, "learning_rate": 2e-4, "batch_size": 1},
        }
        errors = validate_config(config, task="sft")
        assert errors == []

    def test_missing_model_name(self) -> None:
        config = {
            "task": "sft",
            "model": {},
            "dataset": {"path": "data.csv"},
        }
        errors = validate_config(config, task="sft")
        assert any("model.name" in e for e in errors)

    def test_missing_dataset_path(self) -> None:
        config = {
            "task": "sft",
            "model": {"name": "test-model"},
            "dataset": {},
        }
        errors = validate_config(config, task="sft")
        assert any("dataset.path" in e for e in errors)

    def test_dpo_requires_adapter_path(self) -> None:
        config = {
            "task": "dpo",
            "model": {"name": "test-model"},
            "dpo": {"pairs_path": "pairs.jsonl"},
        }
        errors = validate_config(config, task="dpo")
        assert any("sft_adapter_path" in e or "base_model_path" in e for e in errors)

    def test_dpo_accepts_either_adapter_key(self) -> None:
        config = {
            "task": "dpo",
            "model": {"name": "test-model"},
            "sft_adapter_path": "./adapter",
            "dpo": {"pairs_path": "pairs.jsonl"},
        }
        errors = validate_config(config, task="dpo")
        assert errors == []

    def test_invalid_learning_rate_type(self) -> None:
        config = {
            "task": "sft",
            "model": {"name": "test-model"},
            "dataset": {"path": "data.csv"},
            "training": {"learning_rate": "fast"},
        }
        errors = validate_config(config, task="sft")
        assert any("learning_rate" in e for e in errors)

    def test_invalid_batch_size(self) -> None:
        config = {
            "task": "sft",
            "model": {"name": "test-model"},
            "dataset": {"path": "data.csv"},
            "training": {"batch_size": -1},
        }
        errors = validate_config(config, task="sft")
        assert any("batch_size" in e for e in errors)

    def test_auto_detects_task(self) -> None:
        config = {
            "task": "sft",
            "model": {"name": "test-model"},
            "dataset": {"path": "data.csv"},
        }
        errors = validate_config(config)
        assert errors == []


class TestHasNested:
    """Tests for _has_nested helper."""

    def test_simple_key(self) -> None:
        assert _has_nested({"a": 1}, "a") is True

    def test_nested_key(self) -> None:
        assert _has_nested({"a": {"b": 1}}, "a.b") is True

    def test_missing_key(self) -> None:
        assert _has_nested({"a": 1}, "b") is False

    def test_missing_nested_key(self) -> None:
        assert _has_nested({"a": {"b": 1}}, "a.c") is False

    def test_none_value(self) -> None:
        assert _has_nested({"a": None}, "a") is False
