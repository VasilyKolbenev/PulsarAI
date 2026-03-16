"""Standalone evaluation script for trained LoRA adapters.

Loads base model in bf16 (no 4-bit) to avoid PEFT/bnb compatibility issues,
then runs batch inference on the test set and computes metrics.

Usage:
    python scripts/run_eval.py --model Qwen/Qwen3.5-0.8B --adapter outputs/cam-sft-qwen3.5-0.8b/lora
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd
import torch
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SYSTEM_PROMPT_FILE = "prompts/cam_taxonomy.txt"
TEST_DATA = "data/cam_intents_test.csv"
LABEL_COLUMNS = ["domain", "skill"]
TEXT_COLUMN = "phrase"


def load_system_prompt(path: str) -> str:
    """Load system prompt from file."""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def _resolve_model_class(model_name: str):
    """Detect multimodal models (Qwen 3.5) and return correct class."""
    from transformers import AutoConfig, AutoModelForCausalLM

    try:
        hf_config = AutoConfig.from_pretrained(model_name, trust_remote_code=True)
        architectures = getattr(hf_config, "architectures", []) or []
        if any("ConditionalGeneration" in a for a in architectures):
            import transformers

            arch_name = architectures[0]
            cls = getattr(transformers, arch_name, None)
            if cls is not None:
                logger.info("Using %s for multimodal model %s", arch_name, model_name)
                return cls
    except Exception:
        pass
    return AutoModelForCausalLM


def load_model_for_eval(base_model_name: str, adapter_path: str, use_4bit: bool = False):
    """Load base model + LoRA adapter for evaluation.

    Args:
        base_model_name: HuggingFace model name.
        adapter_path: Path to LoRA adapter directory.
        use_4bit: If True, load with 4-bit quantization (for large models).
    """
    from transformers import AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel

    model_cls = _resolve_model_class(base_model_name)
    logger.info("Loading base model: %s (class: %s, 4bit=%s)", base_model_name, model_cls.__name__, use_4bit)

    load_kwargs: dict = {
        "device_map": "auto",
        "torch_dtype": torch.bfloat16,
    }

    if use_4bit:
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

    base_model = model_cls.from_pretrained(base_model_name, **load_kwargs)

    logger.info("Loading adapter from: %s", adapter_path)
    model = PeftModel.from_pretrained(base_model, adapter_path, is_trainable=False)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    logger.info("Model loaded successfully")
    return model, tokenizer


def try_parse_json(text: str) -> dict | None:
    """Try to parse JSON from model output."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if "```" in text:
        for block in text.split("```"):
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None


def run_inference(model, tokenizer, test_df: pd.DataFrame, system_prompt: str) -> list[dict]:
    """Run inference on test data."""
    predictions = []

    for _, row in tqdm(test_df.iterrows(), total=len(test_df), desc="Evaluating"):
        user_text = str(row[TEXT_COLUMN]).strip()
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
                max_new_tokens=128,
                do_sample=False,
                temperature=1.0,
                pad_token_id=tokenizer.eos_token_id,
            )

        response = tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1] :],
            skip_special_tokens=True,
        ).strip()

        parsed = try_parse_json(response)
        predictions.append({
            "input": user_text,
            "raw_output": response,
            "parsed": parsed,
            "parse_success": parsed is not None,
        })

    parse_rate = sum(1 for p in predictions if p["parse_success"]) / max(len(predictions), 1)
    logger.info("Inference: %d samples, %.1f%% JSON parse rate", len(predictions), parse_rate * 100)
    return predictions


def compute_metrics(predictions: list[dict], test_df: pd.DataFrame) -> dict:
    """Compute accuracy, per-class metrics, confusion matrix, F1."""
    from pulsar_ai.evaluation.metrics import compute_metrics as _compute, compute_f1

    true_labels = []
    for _, row in test_df.iterrows():
        true_labels.append({col: row[col] for col in LABEL_COLUMNS if col in row})

    results = _compute(
        predictions=predictions,
        true_labels=true_labels,
        label_columns=LABEL_COLUMNS,
    )

    f1_results = compute_f1(predictions, true_labels, column=LABEL_COLUMNS[0], average="weighted")
    if f1_results:
        results["f1_weighted"] = f1_results

    return results


def update_experiment_store(experiment_id: str, results: dict) -> None:
    """Write eval results to ExperimentStore."""
    try:
        from pulsar_ai.ui.experiment_store import ExperimentStore

        store = ExperimentStore()
        store.set_eval_results(experiment_id, results)
        logger.info("Eval results saved to experiment %s", experiment_id)
    except Exception:
        logger.exception("Failed to save eval results to store")


def main():
    parser = argparse.ArgumentParser(description="Evaluate a fine-tuned LoRA adapter")
    parser.add_argument("--model", required=True, help="Base model name (e.g. Qwen/Qwen3.5-0.8B)")
    parser.add_argument("--adapter", required=True, help="Path to LoRA adapter directory")
    parser.add_argument("--experiment-id", default=None, help="Experiment ID to update in store")
    parser.add_argument("--test-data", default=TEST_DATA, help="Path to test CSV")
    parser.add_argument("--output", default=None, help="Output JSON path")
    parser.add_argument("--4bit", dest="use_4bit", action="store_true", help="Load with 4-bit quantization")
    args = parser.parse_args()

    system_prompt = load_system_prompt(SYSTEM_PROMPT_FILE)
    test_df = pd.read_csv(args.test_data)
    logger.info("Test data: %d samples", len(test_df))

    model, tokenizer = load_model_for_eval(args.model, args.adapter, use_4bit=args.use_4bit)
    predictions = run_inference(model, tokenizer, test_df, system_prompt)
    results = compute_metrics(predictions, test_df)

    # Print summary
    logger.info("=" * 50)
    logger.info("Model: %s + %s", args.model, args.adapter)
    logger.info("Accuracy: %.1f%%", results["overall_accuracy"] * 100)
    logger.info("JSON Parse Rate: %.1f%%", results["json_parse_rate"] * 100)
    if "f1_weighted" in results:
        logger.info("F1 (weighted): %.1f%%", results["f1_weighted"].get("f1", 0) * 100)
        logger.info("Precision: %.1f%%", results["f1_weighted"].get("precision", 0) * 100)
        logger.info("Recall: %.1f%%", results["f1_weighted"].get("recall", 0) * 100)
    logger.info("=" * 50)

    # Show per-sample results for misclassifications
    for pred in predictions:
        if not pred["parse_success"]:
            logger.warning("PARSE FAIL: '%s' -> '%s'", pred["input"], pred["raw_output"][:100])
        elif pred["parsed"]:
            # Find matching true label
            matching = test_df[test_df[TEXT_COLUMN] == pred["input"]]
            if not matching.empty:
                true_row = matching.iloc[0]
                for col in LABEL_COLUMNS:
                    if col in pred["parsed"] and str(pred["parsed"][col]).strip() != str(true_row[col]).strip():
                        logger.warning(
                            "MISMATCH [%s]: '%s' -> pred=%s, true=%s",
                            col, pred["input"][:40], pred["parsed"][col], true_row[col],
                        )

    # Save results
    output_path = args.output or f"outputs/eval_{Path(args.adapter).parent.name}.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("Results saved to %s", output_path)

    # Update experiment store if ID provided
    if args.experiment_id:
        update_experiment_store(args.experiment_id, results)

    # Clean up GPU memory
    del model
    torch.cuda.empty_cache()

    return results


if __name__ == "__main__":
    main()
