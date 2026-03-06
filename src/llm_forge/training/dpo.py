"""DPO (Direct Preference Optimization) trainer."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def train_dpo(config: dict, progress: Any = None) -> dict:
    """Run DPO training on top of an SFT model.

    Automatically tracks experiment if logging.tracker is set.

    Args:
        config: Fully resolved config dict with DPO settings.
        progress: Optional ProgressCallback for real-time metrics.

    Returns:
        Dict with training results.
    """
    from llm_forge.tracking import track_experiment, fingerprint_dataset

    # Fingerprint DPO pairs if path available
    pairs_path = config.get("dpo", {}).get("pairs_path")
    if pairs_path:
        try:
            config["_dataset_fingerprint"] = fingerprint_dataset(pairs_path)
        except FileNotFoundError:
            logger.warning("DPO pairs not found for fingerprinting: %s", pairs_path)

    import torch
    from trl import DPOTrainer, DPOConfig
    from datasets import Dataset

    dpo_config = config.get("dpo", {})
    training_config = config.get("training", {})
    output_dir = config.get("output", {}).get("dir", "./outputs/dpo")
    sft_adapter = config.get("base_model_path", config.get("sft_adapter_path"))

    if not sft_adapter:
        raise ValueError(
            "DPO requires base_model_path or sft_adapter_path in config"
        )

    hf_callbacks = []
    if progress is not None:
        from llm_forge.ui.progress import make_hf_callback
        hf_callbacks.append(make_hf_callback(progress))

    with track_experiment(config, task="dpo") as tracker:
        # Load model with SFT adapter
        from llm_forge.model_loader import load_model

        model, tokenizer = load_model(config, sft_adapter, trainable=True)

        # Load DPO dataset
        dpo_dataset = _load_dpo_dataset(config, tokenizer)

        trainer = DPOTrainer(
            model=model,
            ref_model=None,
            train_dataset=dpo_dataset,
            processing_class=tokenizer,
            callbacks=hf_callbacks,
            args=DPOConfig(
                per_device_train_batch_size=training_config.get("batch_size", 1),
                gradient_accumulation_steps=training_config.get(
                    "gradient_accumulation", 8
                ),
                warmup_steps=training_config.get("warmup_steps", 10),
                num_train_epochs=training_config.get("epochs", 2),
                learning_rate=float(training_config.get("learning_rate", 5e-5)),
                bf16=config.get("_hardware", {}).get("bf16_supported", True),
                logging_steps=training_config.get("logging_steps", 20),
                optim=training_config.get("optimizer", "adamw_8bit"),
                output_dir=output_dir,
                beta=dpo_config.get("beta", 0.1),
                max_length=dpo_config.get("max_length", 512),
                seed=training_config.get("seed", 42),
                report_to=config.get("logging", {}).get("report_to", "none"),
            ),
        )

        logger.info("Starting DPO training...")
        stats = trainer.train()

        adapter_dir = str(Path(output_dir) / "lora")
        model.save_pretrained(adapter_dir)
        tokenizer.save_pretrained(adapter_dir)
        logger.info("DPO adapter saved to %s", adapter_dir)

        vram_peak = torch.cuda.max_memory_allocated() / (1024**3)
        results = {
            "training_loss": stats.training_loss,
            "global_steps": stats.global_step,
            "vram_peak_gb": round(vram_peak, 2),
            "output_dir": output_dir,
            "adapter_dir": adapter_dir,
        }

        tracker.log_metrics({
            "training_loss": results["training_loss"],
            "global_steps": results["global_steps"],
            "vram_peak_gb": results["vram_peak_gb"],
        })
        tracker.log_artifact("adapter", adapter_dir)
        tracker.finish(status="completed", results=results)

    return results


def _load_dpo_dataset(config: dict, tokenizer: Any) -> Any:
    """Load and format DPO preference dataset.

    Args:
        config: Full config dict.
        tokenizer: Tokenizer for prompt formatting.

    Returns:
        HuggingFace Dataset with prompt, chosen, rejected fields.
    """
    from datasets import Dataset
    import json

    dpo_config = config.get("dpo", {})
    pairs_path = dpo_config.get("pairs_path")

    if pairs_path:
        import pandas as pd

        df = pd.read_json(pairs_path, lines=True)
        pairs = df.to_dict("records")
    else:
        raise ValueError("dpo.pairs_path is required for DPO training")

    ds_config = config.get("dataset", {})
    system_prompt = ds_config.get("system_prompt", "")
    if ds_config.get("system_prompt_file"):
        from llm_forge.data.formatter import load_system_prompt

        system_prompt = load_system_prompt(ds_config["system_prompt_file"])

    def format_pair(example: dict) -> dict:
        prompt_msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": example["prompt"]},
        ]
        prompt_text = tokenizer.apply_chat_template(
            prompt_msgs, tokenize=False, add_generation_prompt=True
        )
        return {
            "prompt": prompt_text,
            "chosen": example["chosen"],
            "rejected": example["rejected"],
        }

    ds = Dataset.from_list(pairs).map(format_pair)
    logger.info("Loaded %d DPO pairs", len(ds))
    return ds
