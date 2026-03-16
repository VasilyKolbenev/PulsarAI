"""Tests for LoRA parameter resolution."""

from pulsar_ai.training.sft import _get_lora_params


class TestGetLoraParams:
    """Tests for _get_lora_params resolution logic."""

    def test_defaults_when_empty_config(self) -> None:
        config: dict = {}
        params = _get_lora_params(config)
        assert params["r"] == 16
        assert params["lora_alpha"] == 32
        assert params["lora_dropout"] == 0
        assert params["bias"] == "none"
        assert "q_proj" in params["target_modules"]

    def test_reads_from_lora_section(self) -> None:
        config = {
            "lora": {
                "r": 64,
                "lora_alpha": 128,
                "lora_dropout": 0.05,
                "target_modules": ["q_proj", "v_proj"],
                "bias": "lora_only",
            }
        }
        params = _get_lora_params(config)
        assert params["r"] == 64
        assert params["lora_alpha"] == 128
        assert params["lora_dropout"] == 0.05
        assert params["target_modules"] == ["q_proj", "v_proj"]
        assert params["bias"] == "lora_only"

    def test_falls_back_to_top_level_keys(self) -> None:
        config = {
            "lora_r": 32,
            "lora_alpha": 64,
            "lora_dropout": 0.1,
        }
        params = _get_lora_params(config)
        assert params["r"] == 32
        assert params["lora_alpha"] == 64
        assert params["lora_dropout"] == 0.1

    def test_lora_section_takes_priority_over_top_level(self) -> None:
        config = {
            "lora": {"r": 64},
            "lora_r": 16,
        }
        params = _get_lora_params(config)
        assert params["r"] == 64

    def test_model_config_target_modules_fallback(self) -> None:
        config = {
            "model": {
                "lora_target_modules": ["q_proj", "k_proj"],
            }
        }
        params = _get_lora_params(config)
        assert params["target_modules"] == ["q_proj", "k_proj"]

    def test_lora_target_modules_over_model_config(self) -> None:
        config = {
            "lora": {"target_modules": ["gate_proj"]},
            "model": {"lora_target_modules": ["q_proj"]},
        }
        params = _get_lora_params(config)
        assert params["target_modules"] == ["gate_proj"]
