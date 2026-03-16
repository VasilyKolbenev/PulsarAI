"""Batch inference runner for model evaluation."""

import json
import logging
from pathlib import Path
from typing import Any

from tqdm import tqdm

logger = logging.getLogger(__name__)


def run_evaluation(config: dict) -> dict:
    """Run batch evaluation on test data.

    Loads model, runs inference on test set, computes metrics.

    Args:
        config: Config dict with model_path, test_data_path, evaluation settings.

    Returns:
        Dict with accuracy, json_parse_rate, per_class metrics, report_path.
    """
    model_path = config.get("model_path")
    test_data_path = config.get("test_data_path")
    eval_config = config.get("evaluation", {})
    output_dir = config.get("output", {}).get("eval_dir", "./outputs/eval")

    if not model_path or not test_data_path:
        raise ValueError("model_path and test_data_path are required for evaluation")

    # Load model
    from pulsar_ai.model_loader import load_model

    model, tokenizer = load_model(config, model_path, trainable=False)

    # Load test data
    test_df = _load_test_data(config, test_data_path)

    # Get label columns and system prompt
    ds_config = config.get("dataset", {})
    label_columns = ds_config.get("label_columns", ["label"])
    system_prompt = _get_system_prompt(ds_config)

    # Run inference
    predictions = _batch_inference(
        model=model,
        tokenizer=tokenizer,
        test_df=test_df,
        system_prompt=system_prompt,
        text_column=ds_config.get("text_column", "text"),
        max_new_tokens=eval_config.get("max_new_tokens", 128),
    )

    # Compute metrics
    from pulsar_ai.evaluation.metrics import compute_metrics

    true_labels = []
    for _, row in test_df.iterrows():
        true_labels.append({col: row[col] for col in label_columns if col in row})

    results = compute_metrics(
        predictions=predictions,
        true_labels=true_labels,
        label_columns=label_columns,
    )

    # Save results
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results_path = Path(output_dir) / "eval_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    results["results_path"] = str(results_path)

    # Generate report
    from pulsar_ai.evaluation.report import generate_report

    report_path = generate_report(results, predictions, true_labels, output_dir)
    results["report_path"] = report_path

    logger.info("Evaluation complete. Report: %s", report_path)
    return results


def _load_test_data(config: dict, test_data_path: str) -> Any:
    """Load test data as DataFrame.

    Args:
        config: Full config dict.
        test_data_path: Path to test data file.

    Returns:
        Pandas DataFrame.
    """
    import pandas as pd

    path = Path(test_data_path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path)
    elif suffix in (".jsonl", ".json"):
        return pd.read_json(path, lines=suffix == ".jsonl")
    elif suffix == ".parquet":
        return pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported test data format: {suffix}")


def _get_system_prompt(ds_config: dict) -> str:
    """Get system prompt from config.

    Args:
        ds_config: Dataset config section.

    Returns:
        System prompt string.
    """
    system_prompt = ds_config.get("system_prompt", "")
    if ds_config.get("system_prompt_file"):
        from pulsar_ai.data.formatter import load_system_prompt

        system_prompt = load_system_prompt(ds_config["system_prompt_file"])
    return system_prompt


def _batch_inference(
    model: Any,
    tokenizer: Any,
    test_df: Any,
    system_prompt: str,
    text_column: str = "text",
    max_new_tokens: int = 128,
) -> list[dict]:
    """Run batch inference on test data.

    Args:
        model: Loaded model.
        tokenizer: Tokenizer.
        test_df: Test DataFrame.
        system_prompt: System prompt.
        text_column: Column with input text.
        max_new_tokens: Max tokens to generate.

    Returns:
        List of prediction dicts with raw_output and parsed fields.
    """
    import torch

    predictions = []

    for _, row in tqdm(test_df.iterrows(), total=len(test_df), desc="Evaluating"):
        user_text = str(row[text_column]).strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]

        input_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(input_text, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=1.0,
                pad_token_id=tokenizer.eos_token_id,
            )

        response = tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1] :],
            skip_special_tokens=True,
        ).strip()

        # Try to parse JSON
        parsed = _try_parse_json(response)
        predictions.append(
            {
                "input": user_text,
                "raw_output": response,
                "parsed": parsed,
                "parse_success": parsed is not None,
            }
        )

    parse_rate = sum(1 for p in predictions if p["parse_success"]) / max(len(predictions), 1)
    logger.info(
        "Inference complete: %d samples, %.1f%% JSON parse rate",
        len(predictions),
        parse_rate * 100,
    )
    return predictions


def _try_parse_json(text: str) -> dict | None:
    """Try to parse JSON from model output.

    Args:
        text: Raw model output string.

    Returns:
        Parsed dict or None if parsing fails.
    """
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting JSON from markdown code block
    if "```" in text:
        for block in text.split("```"):
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue
    # Try finding { ... } substring
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None
