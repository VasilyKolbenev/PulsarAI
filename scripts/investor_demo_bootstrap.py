#!/usr/bin/env python
"""Prepare deterministic local demo data for investor presentations.

This script is safe to run multiple times (idempotent):
- Creates lightweight demo datasets if missing
- Seeds completed experiments with realistic metrics
- Seeds prompt templates
- Seeds a dedicated banking workflow demo
"""

from __future__ import annotations

import csv
import json
import sys
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pulsar_ai.prompts.store import PromptStore
from pulsar_ai.ui.workflow_store import WorkflowStore
from pulsar_ai.ui.routes.workflows import _TEMPLATES


DATA_DIR = ROOT / "data"
EXPERIMENTS_PATH = DATA_DIR / "experiments.json"
UPLOADS_DIR = DATA_DIR / "uploads"
BANKING_DIR = DATA_DIR / "banking"


def _load_json(path: Path, default):
    if not path.exists():
        return deepcopy(default)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def ensure_demo_datasets() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    BANKING_DIR.mkdir(parents=True, exist_ok=True)

    src_cam = DATA_DIR / "cam_intents.csv"
    dst_cam = UPLOADS_DIR / "demo_cam_intents.csv"
    if src_cam.exists() and not dst_cam.exists():
        dst_cam.write_bytes(src_cam.read_bytes())

    banking_csv = BANKING_DIR / "loan_applications.csv"
    if not banking_csv.exists():
        rows = [
            ["application_id", "client_id", "segment", "amount", "currency", "risk_hint", "channel"],
            ["A-1001", "C-5001", "retail", "250000", "RUB", "low", "mobile"],
            ["A-1002", "C-5002", "sme", "1800000", "RUB", "medium", "branch"],
            ["A-1003", "C-5003", "retail", "450000", "RUB", "high", "web"],
            ["A-1004", "C-5004", "corp", "12000000", "RUB", "critical", "rm"],
            ["A-1005", "C-5005", "retail", "900000", "RUB", "medium", "mobile"],
        ]
        with open(banking_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)



def _history(losses: list[float]) -> list[dict]:
    out = []
    for i, loss in enumerate(losses, start=1):
        out.append(
            {
                "step": i * 100,
                "epoch": round(i * 0.25, 2),
                "loss": round(loss, 4),
                "event": "metric",
                "time": datetime.now().isoformat(),
            }
        )
    return out


def _eval_payload(acc: float, f1: float, parse_rate: float) -> dict:
    return {
        "overall_accuracy": acc,
        "json_parse_rate": parse_rate,
        "f1_weighted": {
            "precision": round(f1 + 0.01, 4),
            "recall": round(f1 - 0.005, 4),
            "f1": f1,
        },
        "per_column": {
            "domain": {
                "accuracy": round(acc + 0.01, 4),
                "per_class": {
                    "PAYMENTS": {"accuracy": 0.95, "correct": 95, "count": 100},
                    "CARDS": {"accuracy": 0.9, "correct": 90, "count": 100},
                    "CREDIT": {"accuracy": 0.92, "correct": 92, "count": 100},
                },
            },
            "skill": {
                "accuracy": round(acc - 0.01, 4),
                "per_class": {
                    "balance": {"accuracy": 0.93, "correct": 93, "count": 100},
                    "transfer": {"accuracy": 0.9, "correct": 90, "count": 100},
                    "loan_status": {"accuracy": 0.91, "correct": 91, "count": 100},
                },
            },
        },
        "confusion_matrix": {
            "labels": ["PAYMENTS", "CARDS", "CREDIT"],
            "matrix": [
                [96, 3, 1],
                [5, 90, 5],
                [2, 6, 92],
            ],
        },
    }



def ensure_demo_experiments() -> None:
    experiments = _load_json(EXPERIMENTS_PATH, [])
    existing_names = {str(e.get("name", "")) for e in experiments}

    now = datetime.now()

    demo_items = [
        {
            "id": "demoq2b1",
            "name": "[DEMO] Qwen3.5-2B SFT Baseline",
            "status": "completed",
            "task": "sft",
            "model": "Qwen/Qwen3.5-2B",
            "dataset_id": "demo_cam_intents",
            "config": {
                "model": {"name": "Qwen/Qwen3.5-2B"},
                "dataset": {
                    "path": "data/cam_intents.csv",
                    "format": "csv",
                    "test_size": 0.15,
                },
                "training": {
                    "learning_rate": 0.0002,
                    "epochs": 3,
                    "batch_size": 1,
                    "gradient_accumulation": 16,
                    "max_seq_length": 512,
                    "optimizer": "adamw_8bit",
                    "warmup_steps": 50,
                    "seed": 42,
                },
            },
            "created_at": (now - timedelta(days=3)).isoformat(),
            "completed_at": (now - timedelta(days=3, minutes=-38)).isoformat(),
            "final_loss": 0.3142,
            "training_history": _history([1.124, 0.932, 0.781, 0.603, 0.487, 0.421, 0.372, 0.341, 0.325, 0.3142]),
            "eval_results": _eval_payload(acc=0.887, f1=0.881, parse_rate=0.96),
            "artifacts": {
                "strategy": "qlora",
                "adapter_dir": "./outputs/demo-qwen35-2b-sft/lora",
                "output_dir": "./outputs/demo-qwen35-2b-sft",
                "trainable_params": 20971520,
                "total_params": 2013265920,
                "trainable_pct": 1.04,
                "training_duration_min": 38,
                "adapter_size_mb": 84.2,
                "hyperparameters": {
                    "learning_rate": 0.0002,
                    "epochs": 3,
                    "batch_size": 1,
                    "gradient_accumulation": 16,
                    "max_seq_length": 512,
                    "optimizer": "adamw_8bit",
                    "warmup_steps": 50,
                    "seed": 42,
                },
                "lora": {
                    "r": 16,
                    "alpha": 32,
                    "dropout": 0.0,
                    "peft_type": "LORA",
                    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
                },
                "quantization": {
                    "load_in_4bit": True,
                    "bnb_4bit_quant_type": "nf4",
                    "bnb_4bit_compute_dtype": "bfloat16",
                },
                "hardware": {"gpu_name": "NVIDIA RTX 4090", "vram_gb": 24, "bf16": True},
                "dataset": {"path": "data/cam_intents.csv", "format": "csv", "test_size": 0.15},
            },
        },
        {
            "id": "demoq2b2",
            "name": "[DEMO] Qwen3.5-2B DPO Aligned",
            "status": "completed",
            "task": "dpo",
            "model": "Qwen/Qwen3.5-2B",
            "dataset_id": "demo_cam_intents",
            "config": {
                "model": {"name": "Qwen/Qwen3.5-2B"},
                "dpo": {"pairs_path": "./data/cam_dpo_pairs.jsonl", "beta": 0.1},
                "training": {
                    "learning_rate": 0.00005,
                    "epochs": 2,
                    "batch_size": 1,
                    "gradient_accumulation": 8,
                    "max_seq_length": 512,
                    "optimizer": "adamw_8bit",
                    "warmup_steps": 20,
                    "seed": 42,
                },
            },
            "created_at": (now - timedelta(days=2)).isoformat(),
            "completed_at": (now - timedelta(days=2, minutes=-22)).isoformat(),
            "final_loss": 0.2417,
            "training_history": _history([0.541, 0.482, 0.429, 0.381, 0.339, 0.305, 0.276, 0.256, 0.247, 0.2417]),
            "eval_results": _eval_payload(acc=0.924, f1=0.919, parse_rate=0.99),
            "artifacts": {
                "strategy": "qlora",
                "adapter_dir": "./outputs/demo-qwen35-2b-dpo/lora",
                "output_dir": "./outputs/demo-qwen35-2b-dpo",
                "trainable_params": 20971520,
                "total_params": 2013265920,
                "trainable_pct": 1.04,
                "training_duration_min": 22,
                "adapter_size_mb": 84.7,
                "hyperparameters": {
                    "learning_rate": 0.00005,
                    "epochs": 2,
                    "batch_size": 1,
                    "gradient_accumulation": 8,
                    "max_seq_length": 512,
                    "optimizer": "adamw_8bit",
                    "warmup_steps": 20,
                    "seed": 42,
                },
                "lora": {
                    "r": 16,
                    "alpha": 32,
                    "dropout": 0.0,
                    "peft_type": "LORA",
                    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
                },
                "quantization": {
                    "load_in_4bit": True,
                    "bnb_4bit_quant_type": "nf4",
                    "bnb_4bit_compute_dtype": "bfloat16",
                },
                "hardware": {"gpu_name": "NVIDIA RTX 4090", "vram_gb": 24, "bf16": True},
                "dataset": {"path": "data/cam_dpo_pairs.jsonl", "format": "jsonl", "test_size": 0.15},
            },
        },
    ]

    added = 0
    for item in demo_items:
        if item["name"] in existing_names:
            continue
        experiments.append(item)
        existing_names.add(item["name"])
        added += 1

    if added:
        _save_json(EXPERIMENTS_PATH, experiments)
    print(f"seed_experiments: added={added}")



def ensure_demo_prompts() -> None:
    store = PromptStore()
    existing = {p.get("name") for p in store.list_all()}

    added = 0
    if "[DEMO] Credit Underwriting Prompt" not in existing:
        created = store.create(
            name="[DEMO] Credit Underwriting Prompt",
            system_prompt=(
                "You are a bank underwriting assistant. "
                "Return strict JSON with fields: decision, confidence, reasons. "
                "Customer segment: {{segment}}; amount: {{amount}}."
            ),
            description="Investor demo prompt for underwriting agent",
            model="Qwen/Qwen3.5-2B",
            tags=["demo", "banking", "underwriting"],
        )
        store.add_version(
            created["id"],
            system_prompt=(
                "You are a bank underwriting assistant with AML context. "
                "Return strict JSON only: decision, confidence, reasons, escalation_required. "
                "Customer segment: {{segment}}; amount: {{amount}}; risk_hint: {{risk_hint}}."
            ),
            model="Qwen/Qwen3.5-2B",
            parameters={"temperature": 0.1, "top_p": 0.9},
        )
        added += 1

    if "[DEMO] Compliance Escalation Prompt" not in existing:
        store.create(
            name="[DEMO] Compliance Escalation Prompt",
            system_prompt=(
                "You are compliance reviewer. Return JSON with fields: "
                "escalate(bool), violations(list), notes(string). Input: {{payload}}"
            ),
            description="Investor demo prompt for compliance A2A node",
            model="Qwen/Qwen3.5-2B",
            tags=["demo", "banking", "compliance"],
        )
        added += 1

    print(f"seed_prompts: added={added}")



def ensure_demo_workflow() -> None:
    store = WorkflowStore()
    existing_names = {w.get("name") for w in store.list_all()}

    name = "[DEMO] Banking AgentOffice"
    added = 0
    if name not in existing_names:
        template = _TEMPLATES["banking_agentoffice"]
        store.save(
            name=name,
            nodes=deepcopy(template["nodes"]),
            edges=deepcopy(template["edges"]),
        )
        added = 1

    print(f"seed_workflow: added={added}")



def main() -> int:
    ensure_demo_datasets()
    ensure_demo_experiments()
    ensure_demo_prompts()
    ensure_demo_workflow()
    print("investor_demo_bootstrap: done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
