"""Data formatting utilities for training dataset preparation.

Builds chat-style examples for SFT and preference pairs for DPO training.
"""

import json
import logging
import random
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def build_chat_examples(
    df: pd.DataFrame,
    system_prompt: str,
    text_column: str,
    label_columns: list[str],
    output_format: str = "json",
) -> list[dict]:
    """Build chat-style training examples from a DataFrame.

    Each example has system/user/assistant messages, ready for SFT training.

    Args:
        df: Source DataFrame with text and label columns.
        system_prompt: System message for all examples.
        text_column: Column name containing input text.
        label_columns: Column names to include in assistant response.
        output_format: "json" for JSON-formatted labels, "text" for plain text.

    Returns:
        List of dicts with ``messages`` key (system, user, assistant).
    """
    examples: list[dict] = []

    for _, row in df.iterrows():
        text = str(row.get(text_column, "")).strip()
        if not text:
            continue

        # Build assistant response based on output format
        if output_format == "json":
            label_dict = {col: row[col] for col in label_columns}
            assistant_content = json.dumps(label_dict, ensure_ascii=False)
        else:
            # Plain text: join label values
            values = [str(row[col]) for col in label_columns]
            assistant_content = "\n".join(values) if len(values) > 1 else values[0]

        examples.append(
            {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                    {"role": "assistant", "content": assistant_content},
                ]
            }
        )

    logger.info(
        "Built %d chat examples from %d rows (format=%s)",
        len(examples),
        len(df),
        output_format,
    )
    return examples


def load_system_prompt(path: str) -> str:
    """Load a system prompt from a text file.

    Args:
        path: Path to the prompt file.

    Returns:
        Stripped prompt string.

    Raises:
        FileNotFoundError: If path does not exist.
    """
    prompt_path = Path(path)
    if not prompt_path.exists():
        raise FileNotFoundError(f"System prompt file not found: {path}")
    return prompt_path.read_text(encoding="utf-8").strip()


def build_dpo_pairs(
    errors_df: pd.DataFrame,
    all_data: pd.DataFrame,
    label_columns: list[str],
    n_synthetic: int = 0,
    seed: Optional[int] = None,
) -> list[dict]:
    """Build DPO preference pairs from classification errors.

    Creates ``(prompt, chosen, rejected)`` triplets:
    - From errors: chosen=true label, rejected=predicted label
    - Synthetic: random samples from all_data with swapped labels

    Args:
        errors_df: DataFrame with columns ``phrase``, ``true_<col>``, ``pred_<col>``.
        all_data: Full dataset for synthetic pair generation.
        label_columns: Label column names (used to find true/pred columns).
        n_synthetic: Number of synthetic pairs to generate.
        seed: Random seed for reproducibility.

    Returns:
        List of dicts with ``prompt``, ``chosen``, ``rejected`` keys.
    """
    if seed is not None:
        random.seed(seed)

    pairs: list[dict] = []

    # Build pairs from actual errors
    for _, row in errors_df.iterrows():
        prompt = str(row.get("phrase", ""))

        chosen_parts = []
        rejected_parts = []
        for col in label_columns:
            true_col = f"true_{col}"
            pred_col = f"pred_{col}"
            chosen_parts.append(str(row.get(true_col, "")))
            rejected_parts.append(str(row.get(pred_col, "")))

        chosen = "\n".join(chosen_parts) if len(chosen_parts) > 1 else chosen_parts[0]
        rejected = (
            "\n".join(rejected_parts) if len(rejected_parts) > 1 else rejected_parts[0]
        )

        if chosen != rejected:
            pairs.append(
                {"prompt": prompt, "chosen": chosen, "rejected": rejected}
            )

    # Generate synthetic pairs
    if n_synthetic > 0 and len(all_data) >= 2:
        unique_labels: dict[str, list[str]] = {}
        for col in label_columns:
            if col in all_data.columns:
                unique_labels[col] = list(all_data[col].dropna().unique())

        for _ in range(n_synthetic):
            idx = random.randint(0, len(all_data) - 1)
            sample = all_data.iloc[idx]
            prompt = str(sample.get("phrase", sample.get("text", "")))

            chosen_parts = []
            rejected_parts = []
            for col in label_columns:
                true_val = str(sample.get(col, ""))
                chosen_parts.append(true_val)
                # Pick a different label for rejected
                candidates = [
                    lbl for lbl in unique_labels.get(col, []) if str(lbl) != true_val
                ]
                if candidates:
                    rejected_parts.append(random.choice(candidates))
                else:
                    rejected_parts.append(true_val + "_wrong")

            chosen = (
                "\n".join(chosen_parts) if len(chosen_parts) > 1 else chosen_parts[0]
            )
            rejected = (
                "\n".join(rejected_parts)
                if len(rejected_parts) > 1
                else rejected_parts[0]
            )

            if chosen != rejected:
                pairs.append(
                    {"prompt": prompt, "chosen": chosen, "rejected": rejected}
                )

    logger.info(
        "Built %d DPO pairs (%d from errors, %d synthetic)",
        len(pairs),
        len(errors_df),
        n_synthetic,
    )
    return pairs
