"""Config validation for Pulsar AI."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Required keys per task
_REQUIRED_KEYS: dict[str, list[str]] = {
    "sft": ["model.name", "dataset.path"],
    "dpo": ["model.name", "sft_adapter_path|base_model_path", "dpo.pairs_path"],
    "eval": ["model_path", "test_data_path"],
}

# Known top-level keys (warnings for typos)
_KNOWN_KEYS = {
    "model",
    "training",
    "dataset",
    "output",
    "logging",
    "strategy",
    "task",
    "inherit",
    "load_in_4bit",
    "use_lora",
    "use_unsloth",
    "gradient_checkpointing",
    "lora",
    "fsdp",
    "deepspeed",
    "dpo",
    "bnb_4bit_quant_type",
    "bnb_4bit_compute_dtype",
    "bnb_4bit_use_double_quant",
    "fsdp_enabled",
    "fsdp_sharding_strategy",
    "fsdp_cpu_offload",
    "deepspeed_enabled",
    "deepspeed_stage",
    "deepspeed_offload_optimizer",
    "deepspeed_offload_params",
    "lora_r",
    "lora_alpha",
    "lora_dropout",
    "sft_adapter_path",
    "base_model_path",
    "model_path",
    "test_data_path",
    "evaluation",
    "export",
    # Internal keys set by hardware detection
    "_detected_strategy",
    "_hardware",
    # Agent keys
    "agent",
    "tools",
    "memory",
    "guardrails",
    "resume_from_checkpoint",
}


def validate_agent_config(config: dict) -> list[str]:
    """Validate an agent config dict.

    Args:
        config: Resolved agent config dict.

    Returns:
        List of error messages (empty = valid).
    """
    errors: list[str] = []

    agent = config.get("agent", {})
    if not agent.get("name"):
        errors.append("agent.name is required")

    model = config.get("model", {})
    if not model.get("base_url"):
        errors.append("model.base_url is required")

    guardrails = config.get("guardrails", {})
    max_iter = guardrails.get("max_iterations")
    if max_iter is not None and (not isinstance(max_iter, int) or max_iter < 1):
        errors.append(f"guardrails.max_iterations must be a positive integer, got: {max_iter}")

    max_tokens = guardrails.get("max_tokens")
    if max_tokens is not None and (not isinstance(max_tokens, int) or max_tokens < 1):
        errors.append(f"guardrails.max_tokens must be a positive integer, got: {max_tokens}")

    memory = config.get("memory", {})
    mem_tokens = memory.get("max_tokens")
    if mem_tokens is not None and (not isinstance(mem_tokens, int) or mem_tokens < 1):
        errors.append(f"memory.max_tokens must be a positive integer, got: {mem_tokens}")

    return errors


def validate_config(config: dict, task: Optional[str] = None) -> list[str]:
    """Validate a resolved config dict.

    Checks required keys, warns about unknown top-level keys.

    Args:
        config: Fully resolved config dict.
        task: Task name (sft, dpo, eval). Auto-detected if None.

    Returns:
        List of error messages (empty = valid).
    """
    errors: list[str] = []

    if task is None:
        task = config.get("task", "sft")

    # Check required keys
    required = _REQUIRED_KEYS.get(task, [])
    for key_spec in required:
        if "|" in key_spec:
            # Any one of these must exist
            alternatives = key_spec.split("|")
            if not any(_has_nested(config, k) for k in alternatives):
                errors.append(f"Missing required key (one of): {', '.join(alternatives)}")
        else:
            if not _has_nested(config, key_spec):
                errors.append(f"Missing required key: {key_spec}")

    # Warn about unknown top-level keys
    for key in config:
        if key not in _KNOWN_KEYS:
            logger.warning("Unknown config key: '%s' (possible typo?)", key)

    # Type checks
    training = config.get("training", {})
    if isinstance(training, dict):
        lr = training.get("learning_rate")
        if lr is not None and not isinstance(lr, (int, float)):
            errors.append(f"training.learning_rate must be a number, got: {type(lr).__name__}")
        epochs = training.get("epochs")
        if epochs is not None and not isinstance(epochs, int):
            errors.append(f"training.epochs must be an integer, got: {type(epochs).__name__}")
        batch_size = training.get("batch_size")
        if batch_size is not None and (not isinstance(batch_size, int) or batch_size < 1):
            errors.append(f"training.batch_size must be a positive integer, got: {batch_size}")

    return errors


def _has_nested(d: dict, key: str) -> bool:
    """Check if a nested key exists in a dict.

    Args:
        d: Dict to check.
        key: Dot-separated key path.

    Returns:
        True if key exists and is not None.
    """
    parts = key.split(".")
    current: Any = d
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return current is not None
