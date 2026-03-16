"""FSDP and DeepSpeed distributed training launcher."""

import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def launch_distributed(
    config: dict,
    script_path: Optional[str] = None,
) -> dict:
    """Launch distributed training via accelerate.

    Generates accelerate config based on strategy and runs training.

    Args:
        config: Full resolved config dict.
        script_path: Path to training script. If None, uses internal launcher.

    Returns:
        Dict with training results.
    """
    strategy = config.get("_detected_strategy", config.get("strategy"))
    num_gpus = config.get("_hardware", {}).get("num_gpus", 1)

    if strategy in ("fsdp_qlora", "fsdp_full"):
        accel_config = _build_fsdp_config(config)
    elif strategy == "deepspeed":
        accel_config = _build_deepspeed_config(config)
    else:
        raise ValueError(
            f"Strategy '{strategy}' does not require distributed launcher. "
            "Use single-GPU training instead."
        )

    # Write accelerate config to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, prefix="accel_") as f:
        import yaml

        yaml.dump(accel_config, f)
        accel_config_path = f.name

    # Write training config to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, prefix="train_config_"
    ) as f:
        import yaml

        yaml.dump(config, f)
        train_config_path = f.name

    if script_path is None:
        script_path = str(Path(__file__).parent / "_distributed_entry.py")

    cmd = [
        sys.executable,
        "-m",
        "accelerate.commands.launch",
        "--config_file",
        accel_config_path,
        "--num_processes",
        str(num_gpus),
        script_path,
        "--config",
        train_config_path,
    ]

    logger.info(
        "Launching distributed training: %d GPUs, strategy=%s",
        num_gpus,
        strategy,
    )
    logger.debug("Command: %s", " ".join(cmd))

    subprocess.run(cmd, check=True)

    # Clean up temp files
    Path(accel_config_path).unlink(missing_ok=True)
    Path(train_config_path).unlink(missing_ok=True)

    return {"status": "completed", "strategy": strategy, "num_gpus": num_gpus}


def _build_fsdp_config(config: dict) -> dict:
    """Build accelerate FSDP config.

    Args:
        config: Full config dict with fsdp section.

    Returns:
        Accelerate config dict.
    """
    fsdp_config = config.get("fsdp", {})
    training_config = config.get("training", {})

    sharding = fsdp_config.get("sharding_strategy", "FULL_SHARD")
    cpu_offload = fsdp_config.get("cpu_offload", False)

    accel = {
        "compute_environment": "LOCAL_MACHINE",
        "distributed_type": "FSDP",
        "fsdp_config": {
            "fsdp_sharding_strategy": sharding,
            "fsdp_offload_params": cpu_offload,
            "fsdp_auto_wrap_policy": fsdp_config.get("auto_wrap_policy", "TRANSFORMER_BASED_WRAP"),
            "fsdp_backward_prefetch_policy": fsdp_config.get("backward_prefetch", "BACKWARD_PRE"),
            "fsdp_state_dict_type": "SHARDED_STATE_DICT",
            "fsdp_sync_module_states": fsdp_config.get("sync_module_states", True),
            "fsdp_use_orig_params": True,
        },
        "mixed_precision": ("bf16" if training_config.get("bf16", True) else "no"),
        "num_machines": 1,
        "num_processes": config.get("_hardware", {}).get("num_gpus", 2),
        "main_training_function": "main",
    }

    return accel


def _build_deepspeed_config(config: dict) -> dict:
    """Build accelerate DeepSpeed config.

    Args:
        config: Full config dict with deepspeed section.

    Returns:
        Accelerate config dict.
    """
    ds_config = config.get("deepspeed", {})
    training_config = config.get("training", {})
    stage = ds_config.get("stage", 2)

    zero_config = {
        "zero_optimization": {
            "stage": stage,
            "offload_optimizer": {
                "device": ("cpu" if ds_config.get("cpu_offload", False) else "none"),
            },
            "offload_param": {
                "device": ("cpu" if stage == 3 and ds_config.get("cpu_offload") else "none"),
            },
            "overlap_comm": True,
            "contiguous_gradients": True,
            "reduce_bucket_size": ds_config.get("reduce_bucket_size", 5e8),
            "stage3_prefetch_bucket_size": ds_config.get("prefetch_bucket_size", 5e8),
            "stage3_param_persistence_threshold": ds_config.get("param_persistence_threshold", 1e6),
        },
        "bf16": {"enabled": training_config.get("bf16", True)},
        "gradient_accumulation_steps": training_config.get("gradient_accumulation", 8),
        "train_batch_size": "auto",
        "train_micro_batch_size_per_gpu": training_config.get("batch_size", 1),
    }

    accel = {
        "compute_environment": "LOCAL_MACHINE",
        "distributed_type": "DEEPSPEED",
        "deepspeed_config": zero_config,
        "num_machines": 1,
        "num_processes": config.get("_hardware", {}).get("num_gpus", 2),
        "main_training_function": "main",
    }

    return accel


def generate_deepspeed_config(
    stage: int = 2,
    bf16: bool = True,
    cpu_offload: bool = False,
    batch_size: int = 1,
    gradient_accumulation: int = 8,
) -> dict:
    """Generate a standalone DeepSpeed JSON config.

    Useful for manual accelerate launch or torchrun.

    Args:
        stage: ZeRO stage (2 or 3).
        bf16: Use bf16 mixed precision.
        cpu_offload: Offload optimizer/params to CPU.
        batch_size: Per-device batch size.
        gradient_accumulation: Gradient accumulation steps.

    Returns:
        DeepSpeed config dict.
    """
    config = {
        "bf16": {"enabled": bf16},
        "zero_optimization": {
            "stage": stage,
            "offload_optimizer": {
                "device": "cpu" if cpu_offload else "none",
                "pin_memory": True,
            },
            "overlap_comm": True,
            "contiguous_gradients": True,
            "reduce_scatter": True,
            "reduce_bucket_size": 5e8,
            "allgather_bucket_size": 5e8,
        },
        "gradient_accumulation_steps": gradient_accumulation,
        "train_micro_batch_size_per_gpu": batch_size,
        "wall_clock_breakdown": False,
    }

    if stage == 3:
        config["zero_optimization"]["offload_param"] = {
            "device": "cpu" if cpu_offload else "none",
            "pin_memory": True,
        }
        config["zero_optimization"]["stage3_gather_16bit_weights_on_model_save"] = True

    return config
