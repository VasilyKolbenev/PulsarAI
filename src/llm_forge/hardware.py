"""Hardware detection and training strategy selection."""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class HardwareInfo:
    """Detected hardware capabilities."""

    num_gpus: int
    vram_per_gpu_gb: float
    total_vram_gb: float
    compute_capability: tuple[int, int]
    bf16_supported: bool
    gpu_name: str
    strategy: str
    recommended_batch_size: int
    recommended_gradient_accumulation: int


def detect_hardware() -> HardwareInfo:
    """Detect available GPU hardware and recommend training strategy.

    Returns:
        HardwareInfo with detected capabilities and recommended strategy.
    """
    try:
        import torch
    except ImportError:
        logger.warning("PyTorch not available, assuming CPU-only")
        return HardwareInfo(
            num_gpus=0,
            vram_per_gpu_gb=0,
            total_vram_gb=0,
            compute_capability=(0, 0),
            bf16_supported=False,
            gpu_name="CPU",
            strategy="cpu",
            recommended_batch_size=1,
            recommended_gradient_accumulation=16,
        )

    if not torch.cuda.is_available():
        logger.info("No CUDA GPUs detected, using CPU strategy")
        return HardwareInfo(
            num_gpus=0,
            vram_per_gpu_gb=0,
            total_vram_gb=0,
            compute_capability=(0, 0),
            bf16_supported=False,
            gpu_name="CPU",
            strategy="cpu",
            recommended_batch_size=1,
            recommended_gradient_accumulation=16,
        )

    num_gpus = torch.cuda.device_count()
    props = torch.cuda.get_device_properties(0)
    vram_bytes = getattr(props, "total_memory", None) or getattr(props, "total_mem", 0)
    vram_gb = vram_bytes / (1024**3)
    total_vram = vram_gb * num_gpus
    cc = (props.major, props.minor)
    bf16_ok = cc >= (8, 0)
    gpu_name = props.name

    strategy, batch_size, grad_accum = _select_strategy(num_gpus, vram_gb)

    info = HardwareInfo(
        num_gpus=num_gpus,
        vram_per_gpu_gb=round(vram_gb, 1),
        total_vram_gb=round(total_vram, 1),
        compute_capability=cc,
        bf16_supported=bf16_ok,
        gpu_name=gpu_name,
        strategy=strategy,
        recommended_batch_size=batch_size,
        recommended_gradient_accumulation=grad_accum,
    )

    logger.info(
        "Detected: %d x %s (%.1f GB VRAM), strategy=%s",
        num_gpus,
        gpu_name,
        vram_gb,
        strategy,
    )
    return info


def _select_strategy(
    num_gpus: int, vram_per_gpu_gb: float
) -> tuple[str, int, int]:
    """Select training strategy based on hardware.

    Returns:
        Tuple of (strategy_name, batch_size, gradient_accumulation).
    """
    if num_gpus == 1:
        if vram_per_gpu_gb < 12:
            # RTX 3060/4060/5070 Laptop - tight VRAM
            return "qlora", 1, 16
        elif vram_per_gpu_gb < 24:
            # RTX 3090/4090 - comfortable LoRA
            return "lora", 2, 8
        elif vram_per_gpu_gb < 48:
            # A6000/L40 - full finetune possible for small models
            return "full", 4, 4
        else:
            # A100 80GB / H100
            return "full", 8, 2
    elif num_gpus <= 4:
        if vram_per_gpu_gb < 24:
            return "fsdp_qlora", 1, 8
        else:
            return "fsdp_lora", 2, 4
    else:
        # 8+ GPUs
        if vram_per_gpu_gb >= 40:
            return "fsdp_full", 4, 2
        else:
            return "deepspeed_zero3", 2, 4


def get_strategy_config(strategy: str) -> dict:
    """Return default config overrides for a given strategy.

    Args:
        strategy: One of cpu, qlora, lora, full, fsdp_qlora, fsdp_lora,
                  fsdp_full, deepspeed_zero3.

    Returns:
        Dict of config overrides to merge into base config.
    """
    configs = {
        "cpu": {
            "load_in_4bit": False,
            "use_lora": True,
            "lora_r": 8,
            "lora_alpha": 16,
            "lora_dropout": 0.0,
            "gradient_checkpointing": False,
        },
        "qlora": {
            "load_in_4bit": True,
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_compute_dtype": "bfloat16",
            "bnb_4bit_use_double_quant": True,
            "use_lora": True,
            "lora_r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.0,
            "gradient_checkpointing": True,
        },
        "lora": {
            "load_in_4bit": False,
            "use_lora": True,
            "lora_r": 64,
            "lora_alpha": 128,
            "lora_dropout": 0.05,
            "gradient_checkpointing": True,
        },
        "full": {
            "load_in_4bit": False,
            "use_lora": False,
            "gradient_checkpointing": True,
        },
        "fsdp_qlora": {
            "load_in_4bit": True,
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_compute_dtype": "bfloat16",
            "use_lora": True,
            "lora_r": 32,
            "lora_alpha": 64,
            "lora_dropout": 0.0,
            "gradient_checkpointing": True,
            "fsdp_enabled": True,
            "fsdp_sharding_strategy": "FULL_SHARD",
            "fsdp_cpu_offload": True,
        },
        "fsdp_lora": {
            "load_in_4bit": False,
            "use_lora": True,
            "lora_r": 64,
            "lora_alpha": 128,
            "lora_dropout": 0.05,
            "gradient_checkpointing": True,
            "fsdp_enabled": True,
            "fsdp_sharding_strategy": "FULL_SHARD",
        },
        "fsdp_full": {
            "load_in_4bit": False,
            "use_lora": False,
            "gradient_checkpointing": True,
            "fsdp_enabled": True,
            "fsdp_sharding_strategy": "FULL_SHARD",
        },
        "deepspeed_zero3": {
            "load_in_4bit": False,
            "use_lora": False,
            "gradient_checkpointing": True,
            "deepspeed_enabled": True,
            "deepspeed_stage": 3,
            "deepspeed_offload_optimizer": True,
            "deepspeed_offload_params": True,
        },
    }
    if strategy not in configs:
        raise ValueError(
            f"Unknown strategy '{strategy}'. "
            f"Available: {list(configs.keys())}"
        )
    return configs[strategy]
