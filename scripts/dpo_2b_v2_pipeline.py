"""Full DPO 2B v2 pipeline: train → update store → eval → save results.

Runs as a single script to ensure all steps complete atomically.

Usage:
    python scripts/dpo_2b_v2_pipeline.py
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

os.chdir(r"C:\Users\User\Desktop\pulsar-ai")
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("outputs/dpo_2b_v2_pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("pipeline")

EXPERIMENT_ID = "2338bcf6"
CONFIG_PATH = "configs/examples/cam-dpo-qwen3.5-2b.yaml"
BASE_MODEL = "Qwen/Qwen3.5-2B"
ADAPTER_OUTPUT = "outputs/cam-dpo-qwen3.5-2b-v2/lora"
EVAL_OUTPUT = "outputs/eval_cam-dpo-qwen3.5-2b-v2.json"


def step_train():
    """Step 1: Run DPO training."""
    from pulsar_ai.config import load_config
    from pulsar_ai.training.dpo import train_dpo
    from pulsar_ai.ui.experiment_store import ExperimentStore

    store = ExperimentStore()
    config = load_config(CONFIG_PATH)

    logger.info("=" * 60)
    logger.info("STEP 1: DPO Training")
    logger.info("  pairs: %s", config.get("dpo", {}).get("pairs_path"))
    logger.info("  output: %s", config.get("output", {}).get("dir"))
    logger.info("=" * 60)

    start = time.time()
    try:
        result = train_dpo(config)
        duration_min = int((time.time() - start) / 60)

        store.update_status(EXPERIMENT_ID, "completed")

        # Update final loss and duration
        experiments = store._load()
        for exp in experiments:
            if exp["id"] == EXPERIMENT_ID:
                exp["final_loss"] = result.get("final_loss")
                exp["duration_minutes"] = duration_min
                exp["completed_at"] = __import__("datetime").datetime.now().isoformat()
                exp["artifacts"]["adapter_path"] = ADAPTER_OUTPUT
                break
        store._save(experiments)

        logger.info("Training completed in %d min. Final loss: %s", duration_min, result.get("final_loss"))
        return result
    except Exception:
        store.update_status(EXPERIMENT_ID, "failed")
        logger.exception("Training failed!")
        raise


def step_eval():
    """Step 2: Run evaluation."""
    import torch
    from pulsar_ai.ui.experiment_store import ExperimentStore

    # Free GPU memory from training
    torch.cuda.empty_cache()

    logger.info("=" * 60)
    logger.info("STEP 2: Evaluation")
    logger.info("  model: %s", BASE_MODEL)
    logger.info("  adapter: %s", ADAPTER_OUTPUT)
    logger.info("=" * 60)

    # Use the eval script logic directly
    import pandas as pd
    from scripts_helper import run_eval_inline

    results = run_eval_inline(BASE_MODEL, ADAPTER_OUTPUT, EVAL_OUTPUT, EXPERIMENT_ID)
    return results


def run_eval_inline(base_model: str, adapter_path: str, output_path: str, exp_id: str) -> dict:
    """Run evaluation inline (avoiding subprocess issues)."""
    import pandas as pd
    import torch
    from tqdm import tqdm

    # Import eval components
    sys.path.insert(0, str(Path("scripts").resolve()))

    from pulsar_ai.ui.experiment_store import ExperimentStore
    from pulsar_ai.evaluation.metrics import compute_metrics as _compute, compute_f1

    SYSTEM_PROMPT_FILE = "prompts/cam_taxonomy.txt"
    TEST_DATA = "data/cam_intents_test.csv"
    LABEL_COLUMNS = ["domain", "skill"]
    TEXT_COLUMN = "phrase"

    # Load system prompt
    with open(SYSTEM_PROMPT_FILE, encoding="utf-8") as f:
        system_prompt = f.read().strip()

    test_df = pd.read_csv(TEST_DATA)
    logger.info("Test data: %d samples", len(test_df))

    # Load model
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel

    # Detect model class
    hf_config = AutoConfig.from_pretrained(base_model, trust_remote_code=True)
    architectures = getattr(hf_config, "architectures", []) or []
    model_cls = AutoModelForCausalLM
    for arch in architectures:
        if "ConditionalGeneration" in arch:
            import transformers
            cls = getattr(transformers, arch, None)
            if cls:
                model_cls = cls
                logger.info("Using %s for multimodal model", arch)
            break

    base = model_cls.from_pretrained(
        base_model, device_map="auto", torch_dtype=torch.bfloat16
    )
    model = PeftModel.from_pretrained(base, adapter_path, is_trainable=False)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    # Run inference
    predictions = []
    for _, row in tqdm(test_df.iterrows(), total=len(test_df), desc="Evaluating"):
        user_text = str(row[TEXT_COLUMN]).strip()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
        input_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(input_text, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs, max_new_tokens=128, do_sample=False,
                temperature=1.0, pad_token_id=tokenizer.eos_token_id,
            )

        response = tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        ).strip()

        # Parse JSON
        parsed = None
        text = response.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            if "{" in text and "}" in text:
                try:
                    parsed = json.loads(text[text.find("{"):text.rfind("}") + 1])
                except json.JSONDecodeError:
                    pass

        predictions.append({
            "input": user_text, "raw_output": response,
            "parsed": parsed, "parse_success": parsed is not None,
        })

    parse_rate = sum(1 for p in predictions if p["parse_success"]) / max(len(predictions), 1)
    logger.info("JSON Parse Rate: %.1f%%", parse_rate * 100)

    # Compute metrics
    true_labels = [{col: row[col] for col in LABEL_COLUMNS if col in row} for _, row in test_df.iterrows()]
    results = _compute(predictions=predictions, true_labels=true_labels, label_columns=LABEL_COLUMNS)
    f1_results = compute_f1(predictions, true_labels, column=LABEL_COLUMNS[0], average="weighted")
    if f1_results:
        results["f1_weighted"] = f1_results

    # Log results
    logger.info("=" * 50)
    logger.info("Accuracy: %.1f%%", results["overall_accuracy"] * 100)
    logger.info("JSON Parse Rate: %.1f%%", results["json_parse_rate"] * 100)
    if "f1_weighted" in results:
        logger.info("F1: %.1f%%", results["f1_weighted"].get("f1", 0) * 100)
    logger.info("=" * 50)

    # Save results
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("Results saved to %s", output_path)

    # Update experiment store
    try:
        store = ExperimentStore()
        store.set_eval_results(exp_id, results)
        logger.info("Eval results saved to experiment %s", exp_id)
    except Exception:
        logger.exception("Failed to save eval to store")

    # Cleanup
    del model, base
    torch.cuda.empty_cache()

    return results


def main():
    logger.info("Starting DPO 2B v2 full pipeline")
    logger.info("Experiment ID: %s", EXPERIMENT_ID)

    # Step 1: Train
    train_result = step_train()

    # Step 2: Eval
    eval_results = run_eval_inline(BASE_MODEL, ADAPTER_OUTPUT, EVAL_OUTPUT, EXPERIMENT_ID)

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("  Training loss: %s", train_result.get("final_loss"))
    logger.info("  Eval accuracy: %.1f%%", eval_results.get("overall_accuracy", 0) * 100)
    logger.info("  JSON parse:    %.1f%%", eval_results.get("json_parse_rate", 0) * 100)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
