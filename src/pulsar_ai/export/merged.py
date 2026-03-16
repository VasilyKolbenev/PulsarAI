"""Merge LoRA adapter into base model."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def export_merged(config: dict) -> dict:
    """Merge LoRA adapter with base model and save full model.

    Args:
        config: Config dict with model_path, export settings, model.name.

    Returns:
        Dict with output_path and model info.
    """
    model_path = config.get("model_path")
    export_config = config.get("export", {})
    output_path = export_config.get(
        "output_path",
        str(Path(model_path).parent / "merged"),
    )

    if not model_path:
        raise ValueError("model_path is required for export")

    strategy = config.get("_detected_strategy", config.get("strategy", "qlora"))
    use_unsloth = config.get("use_unsloth", strategy in ("qlora", "lora"))
    model_config = config.get("model", {})

    if use_unsloth:
        model, tokenizer = _merge_unsloth(config, model_path, model_config)
    else:
        model, tokenizer = _merge_peft(config, model_path, model_config)

    Path(output_path).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_path)
    tokenizer.save_pretrained(output_path)

    logger.info("Merged model saved to %s", output_path)
    return {
        "output_path": output_path,
        "base_model": model_config.get("name", "unknown"),
        "adapter_path": model_path,
    }


def _merge_unsloth(config: dict, adapter_path: str, model_config: dict) -> tuple[Any, Any]:
    """Merge adapter using Unsloth.

    Args:
        config: Full config dict.
        adapter_path: Path to LoRA adapter.
        model_config: Model config section.

    Returns:
        Tuple of (merged_model, tokenizer).
    """
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=adapter_path,
        max_seq_length=config.get("training", {}).get("max_seq_length", 1024),
        load_in_4bit=False,  # Full precision for merge
    )

    # Unsloth merge_and_unload
    if hasattr(model, "merge_and_unload"):
        model = model.merge_and_unload()
    else:
        from peft import PeftModel

        base_model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_config.get("name"),
            max_seq_length=config.get("training", {}).get("max_seq_length", 1024),
            load_in_4bit=False,
        )
        model = PeftModel.from_pretrained(base_model, adapter_path)
        model = model.merge_and_unload()

    return model, tokenizer


def _merge_peft(config: dict, adapter_path: str, model_config: dict) -> tuple[Any, Any]:
    """Merge adapter using PEFT.

    Args:
        config: Full config dict.
        adapter_path: Path to LoRA adapter.
        model_config: Model config section.

    Returns:
        Tuple of (merged_model, tokenizer).
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    base_name = model_config.get("name")
    if not base_name:
        import json

        adapter_config_path = Path(adapter_path) / "adapter_config.json"
        with open(adapter_config_path) as f:
            adapter_cfg = json.load(f)
        base_name = adapter_cfg.get("base_model_name_or_path")

    base_model = AutoModelForCausalLM.from_pretrained(
        base_name,
        torch_dtype=torch.float16,
        device_map="auto",
    )
    tokenizer = AutoTokenizer.from_pretrained(base_name)

    model = PeftModel.from_pretrained(base_model, adapter_path)
    model = model.merge_and_unload()

    return model, tokenizer
