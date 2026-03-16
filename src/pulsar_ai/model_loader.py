"""Unified model loading for training, evaluation, and export."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_model(
    config: dict,
    model_path: str,
    trainable: bool = False,
) -> tuple[Any, Any]:
    """Load a model (base or with adapter) based on config.

    Handles Unsloth and HuggingFace backends, adapter detection,
    quantization config, and pad_token setup.

    Args:
        config: Full resolved config dict.
        model_path: Path to model directory or adapter.
        trainable: Whether adapter should be trainable (for DPO).

    Returns:
        Tuple of (model, tokenizer).
    """
    strategy = config.get("_detected_strategy", config.get("strategy", "qlora"))
    use_unsloth = config.get("use_unsloth", strategy in ("qlora", "lora"))
    model_config = config.get("model", {})

    adapter_config_path = Path(model_path) / "adapter_config.json"
    is_adapter = adapter_config_path.exists()

    base_name = model_config.get("name")
    if is_adapter and not base_name:
        with open(adapter_config_path) as f:
            adapter_cfg = json.load(f)
        base_name = adapter_cfg.get("base_model_name_or_path")

    if is_adapter and use_unsloth:
        model, tokenizer = _load_unsloth_with_adapter(config, base_name, model_path, trainable)
    elif is_adapter:
        model, tokenizer = _load_hf_with_adapter(config, base_name, model_path, trainable)
    elif use_unsloth:
        model, tokenizer = _load_unsloth_base(config, base_name or model_path)
    else:
        model, tokenizer = _load_hf_base(config, base_name or model_path)

    # Ensure pad_token is set
    _ensure_pad_token(tokenizer)

    if not trainable:
        model.eval()

    logger.info(
        "Loaded model from %s (adapter=%s, trainable=%s, backend=%s)",
        model_path,
        is_adapter,
        trainable,
        "unsloth" if use_unsloth else "hf",
    )
    return model, tokenizer


def _resolve_model_class(model_name: str) -> Any:
    """Resolve the correct model class, handling multimodal architectures.

    Qwen 3.5 models use Qwen3_5ForConditionalGeneration with a nested
    language_model prefix. AutoModelForCausalLM resolves to Qwen3_5ForCausalLM
    which expects different weight names and produces random outputs.

    Args:
        model_name: HuggingFace model name or path.

    Returns:
        Model class to use for from_pretrained().
    """
    from transformers import AutoConfig, AutoModelForCausalLM

    try:
        hf_config = AutoConfig.from_pretrained(model_name, trust_remote_code=True)
        architectures = getattr(hf_config, "architectures", []) or []
        if any("ConditionalGeneration" in a for a in architectures):
            import transformers

            arch_name = architectures[0]
            cls = getattr(transformers, arch_name, None)
            if cls is not None:
                logger.info(
                    "Detected multimodal architecture %s, using %s",
                    arch_name,
                    cls.__name__,
                )
                return cls
    except Exception:
        logger.debug("Could not resolve architecture for %s", model_name, exc_info=True)

    return AutoModelForCausalLM


def _ensure_pad_token(tokenizer: Any) -> None:
    """Set pad_token to eos_token if not already set.

    Args:
        tokenizer: HuggingFace tokenizer.
    """
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
        logger.debug("Set pad_token to eos_token: %s", tokenizer.pad_token)


def _load_unsloth_with_adapter(
    config: dict,
    base_name: str,
    adapter_path: str,
    trainable: bool,
) -> tuple[Any, Any]:
    """Load Unsloth base model + PEFT adapter.

    Args:
        config: Full config dict.
        base_name: Base model name/path.
        adapter_path: Path to LoRA adapter.
        trainable: Whether adapter should be trainable.

    Returns:
        Tuple of (model, tokenizer).
    """
    from unsloth import FastLanguageModel
    from peft import PeftModel

    base_model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_name,
        max_seq_length=config.get("training", {}).get("max_seq_length", 1024),
        load_in_4bit=config.get("load_in_4bit", True),
    )
    model = PeftModel.from_pretrained(base_model, adapter_path, is_trainable=trainable)
    return model, tokenizer


def _load_hf_with_adapter(
    config: dict,
    base_name: str,
    adapter_path: str,
    trainable: bool,
) -> tuple[Any, Any]:
    """Load HF base model + PEFT adapter.

    Args:
        config: Full config dict.
        base_name: Base model name/path.
        adapter_path: Path to LoRA adapter.
        trainable: Whether adapter should be trainable.

    Returns:
        Tuple of (model, tokenizer).
    """
    import torch
    from transformers import AutoTokenizer
    from peft import PeftModel

    bnb_config = _get_bnb_config(config)
    model_cls = _resolve_model_class(base_name)

    base_model = model_cls.from_pretrained(
        base_name,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(base_name)
    model = PeftModel.from_pretrained(base_model, adapter_path, is_trainable=trainable)
    return model, tokenizer


def _load_unsloth_base(config: dict, model_name: str) -> tuple[Any, Any]:
    """Load base model via Unsloth (no adapter).

    Args:
        config: Full config dict.
        model_name: Model name or path.

    Returns:
        Tuple of (model, tokenizer).
    """
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=config.get("training", {}).get("max_seq_length", 1024),
        dtype=None,
        load_in_4bit=config.get("load_in_4bit", True),
    )
    return model, tokenizer


def _load_hf_base(config: dict, model_name: str) -> tuple[Any, Any]:
    """Load base model via HuggingFace Transformers (no adapter).

    Args:
        config: Full config dict.
        model_name: Model name or path.

    Returns:
        Tuple of (model, tokenizer).
    """
    import torch
    from transformers import AutoTokenizer

    bnb_config = _get_bnb_config(config)
    model_cls = _resolve_model_class(model_name)

    model = model_cls.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto" if not config.get("fsdp_enabled") else None,
        torch_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    return model, tokenizer


def _get_bnb_config(config: dict) -> Any:
    """Build BitsAndBytesConfig if load_in_4bit is enabled.

    Args:
        config: Full config dict.

    Returns:
        BitsAndBytesConfig or None.
    """
    if not config.get("load_in_4bit"):
        return None

    import torch
    from transformers import BitsAndBytesConfig

    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=config.get("bnb_4bit_quant_type", "nf4"),
        bnb_4bit_compute_dtype=getattr(torch, config.get("bnb_4bit_compute_dtype", "bfloat16")),
        bnb_4bit_use_double_quant=config.get("bnb_4bit_use_double_quant", True),
    )
