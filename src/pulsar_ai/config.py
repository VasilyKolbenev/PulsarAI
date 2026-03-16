"""YAML config loader with inheritance, merge, and hardware-aware overrides."""

import copy
import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from pulsar_ai.hardware import detect_hardware, get_strategy_config

logger = logging.getLogger(__name__)

CONFIGS_DIR = Path(__file__).parent.parent.parent / "configs"


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override dict into base dict.

    Args:
        base: Base configuration dict.
        override: Override values (takes priority).

    Returns:
        Merged dict (new copy, originals unchanged).
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_yaml(path: Path) -> dict:
    """Load a single YAML file.

    Args:
        path: Path to YAML file.

    Returns:
        Parsed dict.

    Raises:
        FileNotFoundError: If file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return data or {}


def resolve_config_path(name: str, config_dir: Optional[Path] = None) -> Path:
    """Resolve a config name to a full path.

    Supports:
        - Full path: /absolute/path/to/config.yaml
        - Relative path: ./my_config.yaml
        - Short name: base -> configs/base.yaml
        - Nested name: models/qwen2.5-3b -> configs/models/qwen2.5-3b.yaml

    Args:
        name: Config name or path.
        config_dir: Base directory for config resolution.

    Returns:
        Resolved Path.
    """
    config_dir = config_dir or CONFIGS_DIR

    path = Path(name)
    if path.is_absolute() and path.exists():
        return path
    if path.exists():
        return path

    # Try with .yaml extension
    yaml_path = config_dir / f"{name}.yaml"
    if yaml_path.exists():
        return yaml_path

    # Try without extension (already has .yaml)
    direct_path = config_dir / name
    if direct_path.exists():
        return direct_path

    raise FileNotFoundError(
        f"Config '{name}' not found in {config_dir}. " f"Tried: {path}, {yaml_path}, {direct_path}"
    )


def load_config(
    config_path: str,
    cli_overrides: Optional[dict[str, Any]] = None,
    auto_hardware: bool = True,
) -> dict:
    """Load and fully resolve a config with inheritance and hardware detection.

    Pipeline:
        1. Load experiment config
        2. Resolve `inherit:` list (base -> model -> strategy -> task)
        3. Merge inherited configs (left to right, experiment wins)
        4. If strategy=auto, detect hardware and apply strategy overrides
        5. Apply CLI overrides (highest priority)

    Args:
        config_path: Path to experiment YAML config.
        cli_overrides: Key-value overrides from CLI (e.g., learning_rate=1e-4).
        auto_hardware: Whether to auto-detect hardware for strategy=auto.

    Returns:
        Fully resolved config dict.
    """
    experiment = load_yaml(config_path)
    config_dir = Path(config_path).parent

    # Resolve inheritance chain
    inherit_list = experiment.pop("inherit", [])
    merged = {}
    for inherit_name in inherit_list:
        try:
            inherit_path = resolve_config_path(inherit_name, CONFIGS_DIR)
            inherited = load_yaml(inherit_path)
            merged = deep_merge(merged, inherited)
            logger.debug("Inherited: %s", inherit_path)
        except FileNotFoundError:
            logger.warning("Inherited config not found: %s", inherit_name)

    # Merge experiment on top
    merged = deep_merge(merged, experiment)

    # Hardware auto-detection
    strategy = merged.get("strategy", merged.get("training", {}).get("strategy"))
    if auto_hardware and strategy == "auto":
        hw = detect_hardware()
        strategy_overrides = get_strategy_config(hw.strategy)
        merged = deep_merge(merged, strategy_overrides)
        merged["_detected_strategy"] = hw.strategy
        merged["_hardware"] = {
            "num_gpus": hw.num_gpus,
            "gpu_name": hw.gpu_name,
            "vram_per_gpu_gb": hw.vram_per_gpu_gb,
            "bf16_supported": hw.bf16_supported,
        }
        # Apply recommended batch size if not explicitly set
        training = merged.get("training", {})
        if "batch_size" not in training:
            training["batch_size"] = hw.recommended_batch_size
        if "gradient_accumulation" not in training:
            training["gradient_accumulation"] = hw.recommended_gradient_accumulation
        merged["training"] = training
        logger.info(
            "Auto-detected strategy: %s (%d x %s, %.1f GB)",
            hw.strategy,
            hw.num_gpus,
            hw.gpu_name,
            hw.vram_per_gpu_gb,
        )

    # CLI overrides (highest priority)
    if cli_overrides:
        for key, value in cli_overrides.items():
            _set_nested(merged, key, value)
            logger.debug("CLI override: %s = %s", key, value)

    return merged


def _set_nested(d: dict, key: str, value: Any) -> None:
    """Set a value in a nested dict using dot notation.

    Example:
        _set_nested(d, "training.learning_rate", 1e-4)
        -> d["training"]["learning_rate"] = 1e-4

    Args:
        d: Target dict.
        key: Dot-separated key path.
        value: Value to set.
    """
    parts = key.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = _parse_value(value)


def _parse_value(value: Any) -> Any:
    """Parse CLI string values into Python types.

    Args:
        value: Raw string value from CLI.

    Returns:
        Parsed value (int, float, bool, or str).
    """
    if not isinstance(value, str):
        return value
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
