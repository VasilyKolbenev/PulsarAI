"""SFT (Supervised Fine-Tuning) trainer.

Supports two backends:
- Unsloth: 2-5x faster on single GPU (recommended for ≤24GB VRAM)
- HuggingFace SFTTrainer: multi-GPU via Accelerate
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _get_lora_params(config: dict) -> dict:
    """Resolve LoRA parameters from config.

    Reads from 'lora' section first, falls back to top-level keys.

    Args:
        config: Full config dict.

    Returns:
        Dict with r, lora_alpha, lora_dropout, target_modules, bias.
    """
    lora = config.get("lora", {})
    model_config = config.get("model", {})
    default_modules = [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ]
    return {
        "r": lora.get("r", config.get("lora_r", 16)),
        "lora_alpha": lora.get("lora_alpha", config.get("lora_alpha", 32)),
        "lora_dropout": lora.get("lora_dropout", config.get("lora_dropout", 0)),
        "target_modules": lora.get(
            "target_modules",
            model_config.get("lora_target_modules", default_modules),
        ),
        "bias": lora.get("bias", "none"),
    }


def train_sft(config: dict, progress: Any = None) -> dict:
    """Run SFT training based on config.

    Auto-selects backend (Unsloth vs HF) based on strategy.
    Automatically tracks experiment if logging.tracker is set.

    Args:
        config: Fully resolved config dict.
        progress: Optional ProgressCallback for real-time metrics.

    Returns:
        Dict with training results (loss, steps, output_dir).
    """
    from pulsar_ai.tracking import track_experiment, fingerprint_dataset

    # Fingerprint dataset if path available
    ds_path = config.get("dataset", {}).get("path")
    if ds_path:
        try:
            config["_dataset_fingerprint"] = fingerprint_dataset(ds_path)
        except FileNotFoundError:
            logger.warning("Dataset not found for fingerprinting: %s", ds_path)

    strategy = config.get("_detected_strategy", config.get("strategy", "qlora"))
    use_unsloth = config.get("use_unsloth", strategy in ("qlora", "lora"))
    fsdp = config.get("fsdp_enabled", False)

    # Build HF TrainerCallback list for real-time metrics
    hf_callbacks = []
    if progress is not None:
        from pulsar_ai.ui.progress import make_hf_callback

        hf_callbacks.append(make_hf_callback(progress))

    with track_experiment(config, task="sft") as tracker:
        if use_unsloth and not fsdp:
            results = _train_sft_unsloth(config, callbacks=hf_callbacks)
        else:
            results = _train_sft_hf(config, callbacks=hf_callbacks)

        tracker.log_metrics(
            {
                "training_loss": results.get("training_loss", 0),
                "global_steps": results.get("global_steps", 0),
                "vram_peak_gb": results.get("vram_peak_gb", 0),
            }
        )

        if results.get("adapter_dir"):
            tracker.log_artifact("adapter", results["adapter_dir"])

        tracker.finish(status="completed", results=results)

    return results


def _train_sft_unsloth(config: dict, callbacks: list | None = None) -> dict:
    """SFT training with Unsloth backend (single GPU).

    Args:
        config: Resolved config dict.
        callbacks: Optional list of HF TrainerCallbacks.

    Returns:
        Training results dict.
    """
    import torch
    from unsloth import FastLanguageModel
    from trl import SFTTrainer
    from transformers import TrainingArguments

    model_config = config.get("model", {})
    training_config = config.get("training", {})
    output_dir = config.get("output", {}).get("dir", "./outputs/sft")

    logger.info("Loading model via Unsloth: %s", model_config.get("name"))
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_config.get("name"),
        max_seq_length=training_config.get("max_seq_length", 1024),
        dtype=None,
        load_in_4bit=config.get("load_in_4bit", True),
    )

    # Apply LoRA if configured
    if config.get("use_lora", True):
        lora_params = _get_lora_params(config)
        model = FastLanguageModel.get_peft_model(
            model,
            r=lora_params["r"],
            target_modules=lora_params["target_modules"],
            lora_alpha=lora_params["lora_alpha"],
            lora_dropout=lora_params["lora_dropout"],
            bias=lora_params["bias"],
            use_gradient_checkpointing=(
                "unsloth" if config.get("gradient_checkpointing") else False
            ),
            random_state=training_config.get("seed", 42),
        )

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    logger.info(
        "Trainable: %s / %s (%.2f%%)", f"{trainable:,}", f"{total:,}", trainable / total * 100
    )

    # Load dataset
    train_dataset = _load_train_dataset(config, tokenizer)

    # Training arguments
    args = TrainingArguments(
        per_device_train_batch_size=training_config.get("batch_size", 1),
        gradient_accumulation_steps=training_config.get("gradient_accumulation", 16),
        warmup_steps=training_config.get("warmup_steps", 20),
        num_train_epochs=training_config.get("epochs", 3),
        learning_rate=training_config.get("learning_rate", 2e-4),
        bf16=config.get("_hardware", {}).get("bf16_supported", True),
        logging_steps=training_config.get("logging_steps", 20),
        save_steps=training_config.get("save_steps", 200),
        save_total_limit=training_config.get("save_total_limit", 2),
        optim=training_config.get("optimizer", "adamw_8bit"),
        output_dir=output_dir,
        seed=training_config.get("seed", 42),
        report_to=config.get("logging", {}).get("report_to", "none"),
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        max_seq_length=training_config.get("max_seq_length", 512),
        packing=training_config.get("packing", True),
        args=args,
        callbacks=callbacks or None,
    )

    resume_checkpoint = config.get("resume_from_checkpoint")
    if resume_checkpoint:
        logger.info("Resuming from checkpoint: %s", resume_checkpoint)

    logger.info("Starting SFT training...")
    stats = trainer.train(resume_from_checkpoint=resume_checkpoint)

    # Save adapter
    adapter_dir = str(Path(output_dir) / "lora")
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    logger.info("LoRA adapter saved to %s", adapter_dir)

    vram_peak = torch.cuda.max_memory_allocated() / (1024**3)
    results = {
        "training_loss": stats.training_loss,
        "global_steps": stats.global_step,
        "vram_peak_gb": round(vram_peak, 2),
        "output_dir": output_dir,
        "adapter_dir": adapter_dir,
    }

    # Auto-eval on test split
    eval_results = _auto_eval(model, tokenizer, config)
    if eval_results:
        results["eval_results"] = eval_results

    return results


def _train_sft_hf(config: dict, callbacks: list | None = None) -> dict:
    """SFT training with HuggingFace SFTTrainer (multi-GPU ready).

    Args:
        config: Resolved config dict.
        callbacks: Optional list of HF TrainerCallbacks.

    Returns:
        Training results dict.
    """
    import torch
    from transformers import (
        AutoConfig,
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )
    from peft import LoraConfig, get_peft_model
    from trl import SFTTrainer

    model_config = config.get("model", {})
    training_config = config.get("training", {})
    output_dir = config.get("output", {}).get("dir", "./outputs/sft")

    model_name = model_config.get("name")
    logger.info("Loading model via HF Transformers: %s", model_name)

    # Quantization config
    bnb_config = None
    if config.get("load_in_4bit"):
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=config.get("bnb_4bit_quant_type", "nf4"),
            bnb_4bit_compute_dtype=getattr(torch, config.get("bnb_4bit_compute_dtype", "bfloat16")),
            bnb_4bit_use_double_quant=config.get("bnb_4bit_use_double_quant", True),
        )

    # Detect multimodal models (e.g. Qwen 3.5) and use correct model class
    model_cls = AutoModelForCausalLM
    hf_config = AutoConfig.from_pretrained(model_name, trust_remote_code=True)
    architectures = getattr(hf_config, "architectures", []) or []
    if any("ConditionalGeneration" in a for a in architectures):
        import transformers

        arch_name = architectures[0]
        model_cls = getattr(transformers, arch_name, AutoModelForCausalLM)
        logger.info("Multimodal model detected, using %s", arch_name)

    model = model_cls.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto" if not config.get("fsdp_enabled") else None,
        dtype=torch.bfloat16,
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
    )

    # Apply LoRA
    if config.get("use_lora", True):
        lora_params = _get_lora_params(config)
        lora_config = LoraConfig(
            r=lora_params["r"],
            lora_alpha=lora_params["lora_alpha"],
            lora_dropout=lora_params["lora_dropout"],
            target_modules=lora_params["target_modules"],
            bias=lora_params["bias"],
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()

    train_dataset = _load_train_dataset(config, tokenizer)

    from trl import SFTConfig

    lr = training_config.get("learning_rate", 2e-4)
    if isinstance(lr, str):
        lr = float(lr)
    args = SFTConfig(
        per_device_train_batch_size=training_config.get("batch_size", 2),
        gradient_accumulation_steps=training_config.get("gradient_accumulation", 8),
        warmup_steps=training_config.get("warmup_steps", 20),
        num_train_epochs=training_config.get("epochs", 3),
        learning_rate=lr,
        bf16=config.get("_hardware", {}).get("bf16_supported", True),
        logging_steps=training_config.get("logging_steps", 20),
        save_steps=training_config.get("save_steps", 200),
        save_total_limit=2,
        optim=training_config.get("optimizer", "adamw_8bit"),
        output_dir=output_dir,
        seed=training_config.get("seed", 42),
        report_to=config.get("logging", {}).get("report_to", "none"),
        gradient_checkpointing=config.get("gradient_checkpointing", True),
        dataset_text_field="text",
        max_length=training_config.get("max_seq_length", 512),
        packing=training_config.get("packing", True),
        # FSDP settings
        fsdp=config.get("fsdp_sharding_strategy") if config.get("fsdp_enabled") else "",
        fsdp_config=(
            {
                "fsdp_auto_wrap_policy": "TRANSFORMER_BASED_WRAP",
                "fsdp_cpu_offload": config.get("fsdp_cpu_offload", False),
            }
            if config.get("fsdp_enabled")
            else None
        ),
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        args=args,
        callbacks=callbacks or None,
    )

    resume_checkpoint = config.get("resume_from_checkpoint")
    if resume_checkpoint:
        logger.info("Resuming from checkpoint: %s", resume_checkpoint)

    logger.info("Starting SFT training (HF backend)...")
    stats = trainer.train(resume_from_checkpoint=resume_checkpoint)

    adapter_dir = str(Path(output_dir) / "lora")
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    logger.info("Model saved to %s", adapter_dir)

    results = {
        "training_loss": stats.training_loss,
        "global_steps": stats.global_step,
        "output_dir": output_dir,
        "adapter_dir": adapter_dir,
    }

    # Auto-eval on test split
    eval_results = _auto_eval(model, tokenizer, config)
    if eval_results:
        results["eval_results"] = eval_results

    return results


def _load_train_dataset(config: dict, tokenizer: Any) -> Any:
    """Load and format training dataset from config.

    Stores test_df in config["_test_df"] for post-training eval.

    Args:
        config: Full config dict.
        tokenizer: Tokenizer for chat template.

    Returns:
        HuggingFace Dataset with "text" field.
    """
    from pulsar_ai.data.loader import load_dataset_from_config
    from pulsar_ai.data.formatter import (
        build_chat_examples,
        apply_chat_template,
        load_system_prompt,
    )
    from pulsar_ai.data.splitter import split_dataset

    df = load_dataset_from_config(config)
    ds_config = config.get("dataset", {})

    # Split
    splits = split_dataset(
        df,
        test_size=ds_config.get("test_size", 0.15),
        stratify_column=ds_config.get("stratify_column"),
        seed=config.get("training", {}).get("seed", 42),
    )
    train_df = splits["train"]

    # Store test split for auto-eval after training
    if "test" in splits and len(splits["test"]) > 0:
        config["_test_df"] = splits["test"]

    # System prompt
    system_prompt = ""
    prompt_file = ds_config.get("system_prompt_file")
    if prompt_file:
        system_prompt = load_system_prompt(prompt_file)
    elif ds_config.get("system_prompt"):
        system_prompt = ds_config["system_prompt"]

    # Build chat examples
    examples = build_chat_examples(
        train_df,
        system_prompt=system_prompt,
        text_column=ds_config.get("text_column", "phrase"),
        label_columns=ds_config.get("label_columns", ["label"]),
        output_format=ds_config.get("output_format", "json"),
    )

    return apply_chat_template(examples, tokenizer)


def _auto_eval(
    model: Any,
    tokenizer: Any,
    config: dict,
) -> dict | None:
    """Run evaluation on test split after training.

    Args:
        model: Trained model (with LoRA adapter applied).
        tokenizer: Tokenizer.
        config: Config dict (must have _test_df from _load_train_dataset).

    Returns:
        Eval results dict or None if no test data.
    """
    test_df = config.get("_test_df")
    if test_df is None or len(test_df) == 0:
        logger.info("No test split available, skipping auto-eval")
        return None

    ds_config = config.get("dataset", {})
    label_columns = ds_config.get("label_columns", ["label"])
    text_column = ds_config.get("text_column", "phrase")

    # Get system prompt
    from pulsar_ai.data.formatter import load_system_prompt

    system_prompt = ""
    if ds_config.get("system_prompt_file"):
        system_prompt = load_system_prompt(ds_config["system_prompt_file"])
    elif ds_config.get("system_prompt"):
        system_prompt = ds_config["system_prompt"]

    logger.info("Running auto-eval on %d test samples...", len(test_df))

    from pulsar_ai.evaluation.runner import _batch_inference
    from pulsar_ai.evaluation.metrics import compute_metrics, compute_f1

    predictions = _batch_inference(
        model=model,
        tokenizer=tokenizer,
        test_df=test_df,
        system_prompt=system_prompt,
        text_column=text_column,
        max_new_tokens=128,
    )

    true_labels = []
    for _, row in test_df.iterrows():
        true_labels.append({col: row[col] for col in label_columns if col in row})

    results = compute_metrics(
        predictions=predictions,
        true_labels=true_labels,
        label_columns=label_columns,
    )

    # Add F1 for primary column
    if label_columns:
        f1_results = compute_f1(
            predictions=predictions,
            true_labels=true_labels,
            column=label_columns[0],
            average="weighted",
        )
        results["f1_weighted"] = f1_results

    logger.info(
        "Auto-eval: accuracy=%.1f%%, parse_rate=%.1f%%",
        results.get("overall_accuracy", 0) * 100,
        results.get("json_parse_rate", 0) * 100,
    )
    return results
