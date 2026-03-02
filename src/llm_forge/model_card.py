"""Auto-generated model cards.

Creates standardized model documentation from training configs,
metrics, and registry metadata.
"""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def generate_model_card(
    name: str,
    base_model: str = "",
    task: str = "sft",
    config: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    dataset_info: dict[str, Any] | None = None,
    environment: dict[str, Any] | None = None,
    intended_use: str = "",
    limitations: str = "",
    extra_sections: dict[str, str] | None = None,
) -> str:
    """Generate a model card in Markdown format.

    Args:
        name: Model name.
        base_model: Base model ID.
        task: Training task (sft, dpo, etc.).
        config: Training configuration dict.
        metrics: Evaluation metrics dict.
        dataset_info: Dataset information dict.
        environment: Training environment info.
        intended_use: Description of intended use.
        limitations: Known limitations.
        extra_sections: Additional custom sections {title: content}.

    Returns:
        Model card as Markdown string.
    """
    config = config or {}
    metrics = metrics or {}
    dataset_info = dataset_info or {}
    environment = environment or {}

    sections: list[str] = []

    # Header
    sections.append(f"# Model Card: {name}\n")
    sections.append(f"*Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n")

    # Overview
    sections.append("## Overview\n")
    sections.append(f"| Field | Value |")
    sections.append(f"|-------|-------|")
    sections.append(f"| **Model Name** | {name} |")
    if base_model:
        sections.append(f"| **Base Model** | {base_model} |")
    sections.append(f"| **Task** | {task.upper()} |")
    if config.get("lora_r"):
        sections.append(f"| **LoRA Rank** | {config['lora_r']} |")
    if config.get("quantization"):
        sections.append(f"| **Quantization** | {config['quantization']} |")
    sections.append("")

    # Training Configuration
    if config:
        sections.append("## Training Configuration\n")
        sections.append("| Parameter | Value |")
        sections.append("|-----------|-------|")
        display_keys = [
            "lr", "epochs", "batch_size", "max_seq_length",
            "lora_r", "lora_alpha", "lora_dropout", "optimizer",
            "gradient_accumulation_steps", "warmup_steps", "bf16",
            "gradient_checkpointing", "use_unsloth",
        ]
        for key in display_keys:
            if key in config:
                sections.append(f"| {key} | {config[key]} |")
        sections.append("")

    # Dataset
    if dataset_info:
        sections.append("## Training Data\n")
        sections.append("| Field | Value |")
        sections.append("|-------|-------|")
        for key, value in dataset_info.items():
            if key.startswith("_"):
                continue
            sections.append(f"| {key} | {value} |")
        sections.append("")

    # Metrics
    if metrics:
        sections.append("## Evaluation Metrics\n")
        sections.append("| Metric | Value |")
        sections.append("|--------|-------|")
        for key, value in metrics.items():
            if isinstance(value, float):
                sections.append(f"| {key} | {value:.4f} |")
            else:
                sections.append(f"| {key} | {value} |")
        sections.append("")

    # Environment
    if environment:
        sections.append("## Training Environment\n")
        sections.append("| Component | Value |")
        sections.append("|-----------|-------|")
        for key, value in environment.items():
            if key == "packages":
                continue
            sections.append(f"| {key} | {value} |")
        sections.append("")

    # Intended Use
    sections.append("## Intended Use\n")
    if intended_use:
        sections.append(intended_use)
    else:
        sections.append(
            f"This model is a fine-tuned version of {base_model or 'a base LLM'} "
            f"using {task.upper()} training. It is intended for use in controlled "
            f"environments where the training data distribution is representative."
        )
    sections.append("")

    # Limitations
    sections.append("## Limitations\n")
    if limitations:
        sections.append(limitations)
    else:
        sections.append(
            "- May reproduce biases present in the training data\n"
            "- Performance may degrade on out-of-distribution inputs\n"
            "- Should not be used for safety-critical applications without additional evaluation\n"
            "- Fine-tuned on a specific dataset — generalization to other domains not guaranteed"
        )
    sections.append("")

    # Extra sections
    for title, content in (extra_sections or {}).items():
        sections.append(f"## {title}\n")
        sections.append(content)
        sections.append("")

    # Footer
    sections.append("---\n")
    sections.append("*Generated by LLM Forge*")

    return "\n".join(sections)
