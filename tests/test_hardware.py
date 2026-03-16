"""Tests for hardware detection and strategy selection."""

import pytest

from pulsar_ai.hardware import (
    HardwareInfo,
    _select_strategy,
    get_strategy_config,
)


class TestSelectStrategy:
    """Tests for strategy selection based on hardware."""

    def test_single_gpu_low_vram_selects_qlora(self) -> None:
        strategy, _, _ = _select_strategy(1, 8.0)
        assert strategy == "qlora"

    def test_single_gpu_11gb_selects_qlora(self) -> None:
        strategy, _, _ = _select_strategy(1, 11.0)
        assert strategy == "qlora"

    def test_single_gpu_medium_vram_selects_lora(self) -> None:
        strategy, _, _ = _select_strategy(1, 20.0)
        assert strategy == "lora"

    def test_single_gpu_high_vram_selects_full(self) -> None:
        strategy, _, _ = _select_strategy(1, 48.0)
        assert strategy == "full"

    def test_multi_gpu_small_selects_fsdp_qlora(self) -> None:
        strategy, _, _ = _select_strategy(2, 16.0)
        assert strategy == "fsdp_qlora"

    def test_multi_gpu_large_selects_fsdp_full(self) -> None:
        strategy, _, _ = _select_strategy(8, 80.0)
        assert strategy == "fsdp_full"

    def test_returns_batch_size_and_grad_accum(self) -> None:
        strategy, batch_size, grad_accum = _select_strategy(1, 8.0)
        assert isinstance(batch_size, int)
        assert isinstance(grad_accum, int)
        assert batch_size > 0
        assert grad_accum > 0


class TestGetStrategyConfig:
    """Tests for strategy config generation."""

    def test_qlora_config(self) -> None:
        config = get_strategy_config("qlora")
        assert config.get("load_in_4bit") is True
        assert config.get("use_lora") is True

    def test_lora_config(self) -> None:
        config = get_strategy_config("lora")
        assert config.get("load_in_4bit") is False
        assert config.get("use_lora") is True

    def test_full_config(self) -> None:
        config = get_strategy_config("full")
        assert config.get("load_in_4bit") is False
        assert config.get("use_lora") is False

    def test_unknown_strategy_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown strategy"):
            get_strategy_config("unknown_strategy")


class TestHardwareInfo:
    """Tests for HardwareInfo dataclass."""

    def test_hardware_info_creation(self) -> None:
        hw = HardwareInfo(
            num_gpus=2,
            gpu_name="NVIDIA RTX 5090",
            vram_per_gpu_gb=32.0,
            total_vram_gb=64.0,
            compute_capability=(12, 0),
            bf16_supported=True,
            strategy="fsdp_qlora",
            recommended_batch_size=2,
            recommended_gradient_accumulation=8,
        )
        assert hw.num_gpus == 2
        assert hw.strategy == "fsdp_qlora"
        assert hw.total_vram_gb == 64.0
        assert hw.compute_capability == (12, 0)
