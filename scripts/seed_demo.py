"""Seed demo data for all UI components.

Run: python scripts/seed_demo.py
Creates realistic example data for investor demo presentation.
"""

import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path("./data")
UPLOADS_DIR = DATA_DIR / "uploads"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def seed_experiments() -> None:
    """Create demo experiments with realistic training curves."""
    experiments = []

    # 1. Completed SFT experiment — good result
    history_sft = []
    loss = 2.8
    for step in range(1, 301):
        loss = loss * 0.995 + random.gauss(0, 0.01)
        loss = max(loss, 0.35)
        history_sft.append({
            "step": step,
            "epoch": round(step / 100, 2),
            "loss": round(loss, 4),
        })

    experiments.append({
        "id": "demo-sft1",
        "name": "llama3-customer-support-sft",
        "status": "completed",
        "task": "sft",
        "model": "meta-llama/Llama-3.2-1B-Instruct",
        "config": {
            "model": {"name": "meta-llama/Llama-3.2-1B-Instruct"},
            "training": {
                "learning_rate": 2e-4,
                "epochs": 3,
                "batch_size": 4,
                "gradient_accumulation": 16,
                "max_seq_length": 2048,
            },
        },
        "created_at": (datetime.now() - timedelta(hours=6)).isoformat(),
        "completed_at": (datetime.now() - timedelta(hours=4)).isoformat(),
        "final_loss": round(history_sft[-1]["loss"], 4),
        "training_history": history_sft,
        "eval_results": {
            "accuracy": 0.847,
            "f1_score": 0.823,
            "perplexity": 4.21,
        },
        "artifacts": {"adapter_dir": "./outputs/llama3-cs-sft/adapter"},
    })

    # 2. Completed DPO experiment
    history_dpo = []
    loss = 0.69
    for step in range(1, 201):
        loss = loss * 0.997 + random.gauss(0, 0.005)
        loss = max(loss, 0.15)
        history_dpo.append({
            "step": step,
            "epoch": round(step / 67, 2),
            "loss": round(loss, 4),
        })

    experiments.append({
        "id": "demo-dpo1",
        "name": "qwen-code-dpo-v2",
        "status": "completed",
        "task": "dpo",
        "model": "Qwen/Qwen2.5-3B-Instruct",
        "config": {
            "model": {"name": "Qwen/Qwen2.5-3B-Instruct"},
            "training": {
                "learning_rate": 5e-5,
                "epochs": 3,
                "batch_size": 2,
            },
        },
        "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
        "completed_at": (datetime.now() - timedelta(hours=18)).isoformat(),
        "final_loss": round(history_dpo[-1]["loss"], 4),
        "training_history": history_dpo,
        "eval_results": {
            "chosen_reward_avg": 2.45,
            "rejected_reward_avg": -1.12,
            "reward_margin": 3.57,
        },
        "artifacts": {"adapter_dir": "./outputs/qwen-code-dpo/adapter"},
    })

    # 3. Running experiment
    history_run = []
    loss = 3.2
    for step in range(1, 121):
        loss = loss * 0.993 + random.gauss(0, 0.015)
        loss = max(loss, 0.8)
        history_run.append({
            "step": step,
            "epoch": round(step / 150, 2),
            "loss": round(loss, 4),
        })

    experiments.append({
        "id": "demo-run1",
        "name": "mistral-rag-assistant",
        "status": "running",
        "task": "sft",
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "config": {
            "model": {"name": "mistralai/Mistral-7B-Instruct-v0.3"},
            "training": {
                "learning_rate": 1e-4,
                "epochs": 5,
                "batch_size": 1,
                "gradient_accumulation": 32,
            },
        },
        "created_at": (datetime.now() - timedelta(hours=1)).isoformat(),
        "completed_at": None,
        "final_loss": round(history_run[-1]["loss"], 4),
        "training_history": history_run,
        "eval_results": None,
        "artifacts": {},
    })

    # 4. Failed experiment
    history_fail = []
    loss = 2.5
    for step in range(1, 46):
        loss = loss + random.gauss(0.02, 0.05)
        history_fail.append({
            "step": step,
            "epoch": round(step / 50, 2),
            "loss": round(loss, 4),
        })

    experiments.append({
        "id": "demo-fail",
        "name": "llama3-instruct-highLR",
        "status": "failed",
        "task": "sft",
        "model": "meta-llama/Llama-3.2-1B-Instruct",
        "config": {
            "model": {"name": "meta-llama/Llama-3.2-1B-Instruct"},
            "training": {
                "learning_rate": 1e-2,
                "epochs": 3,
                "batch_size": 8,
            },
        },
        "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
        "completed_at": (datetime.now() - timedelta(days=2, hours=-1)).isoformat(),
        "final_loss": round(history_fail[-1]["loss"], 4),
        "training_history": history_fail,
        "eval_results": None,
        "artifacts": {},
    })

    # 5. Queued experiment
    experiments.append({
        "id": "demo-queue",
        "name": "qwen-summarizer-v3",
        "status": "queued",
        "task": "sft",
        "model": "Qwen/Qwen2.5-1.5B-Instruct",
        "config": {
            "model": {"name": "Qwen/Qwen2.5-1.5B-Instruct"},
            "training": {"learning_rate": 2e-4, "epochs": 5},
        },
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "final_loss": None,
        "training_history": [],
        "eval_results": None,
        "artifacts": {},
    })

    with open(DATA_DIR / "experiments.json", "w", encoding="utf-8") as f:
        json.dump(experiments, f, ensure_ascii=False, indent=2)
    print(f"  Created {len(experiments)} experiments")


def seed_datasets() -> None:
    """Create demo dataset files."""
    # SFT dataset
    sft_rows = []
    topics = [
        ("How do I reset my password?", "To reset your password, go to Settings > Security > Reset Password. You'll receive a confirmation email."),
        ("What are your business hours?", "We're open Monday-Friday, 9 AM to 6 PM EST. Weekend support is available via email."),
        ("Can I get a refund?", "Yes, we offer a 30-day money-back guarantee. Contact support@example.com with your order ID."),
        ("How do I upgrade my plan?", "Navigate to Settings > Billing > Upgrade Plan. Choose your new tier and confirm payment."),
        ("Is there a mobile app?", "Yes! Our mobile app is available on both iOS and Android. Search 'Pulsar AI' in your app store."),
    ]
    for instruction, output in topics:
        for i in range(20):
            sft_rows.append(json.dumps({
                "instruction": instruction + (f" (variation {i})" if i > 0 else ""),
                "output": output,
            }))

    sft_path = UPLOADS_DIR / "demo-sft1.jsonl"
    with open(sft_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sft_rows))

    # DPO dataset
    dpo_rows = []
    pairs = [
        ("Write a Python function to sort a list", "def sort_list(lst):\n    return sorted(lst)", "def sort(l):\n    for i in range(len(l)):\n        for j in range(len(l)):\n            if l[i]<l[j]: l[i],l[j]=l[j],l[i]\n    return l"),
        ("Explain quantum computing", "Quantum computing uses quantum bits (qubits) that can exist in superposition states, enabling parallel computation.", "Its computers that use quantum stuff to be faster"),
    ]
    for prompt, chosen, rejected in pairs:
        for i in range(25):
            dpo_rows.append(json.dumps({
                "prompt": prompt + (f" #{i}" if i > 0 else ""),
                "chosen": chosen,
                "rejected": rejected,
            }))

    dpo_path = UPLOADS_DIR / "demo-dpo1.jsonl"
    with open(dpo_path, "w", encoding="utf-8") as f:
        f.write("\n".join(dpo_rows))

    # CSV dataset
    csv_path = UPLOADS_DIR / "demo-csv1.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("text,label,category\n")
        categories = ["support", "billing", "technical", "general"]
        for i in range(150):
            cat = categories[i % len(categories)]
            f.write(f'"Example text for {cat} query #{i}",{random.randint(0,1)},{cat}\n')

    print(f"  Created 3 dataset files ({sft_path.name}, {dpo_path.name}, {csv_path.name})")


def seed_prompts() -> None:
    """Create demo prompts with multiple versions."""
    prompts = [
        {
            "id": "demo-p1",
            "name": "Customer Support Agent",
            "description": "System prompt for customer-facing support chatbot",
            "current_version": 3,
            "tags": ["production", "agent", "support"],
            "created_at": (datetime.now() - timedelta(days=7)).isoformat(),
            "updated_at": (datetime.now() - timedelta(hours=2)).isoformat(),
            "versions": [
                {
                    "version": 1,
                    "system_prompt": "You are a helpful customer support agent for {{company}}. Answer questions about {{product}}.",
                    "variables": ["company", "product"],
                    "model": "",
                    "parameters": {},
                    "created_at": (datetime.now() - timedelta(days=7)).isoformat(),
                    "metrics": None,
                },
                {
                    "version": 2,
                    "system_prompt": "You are a professional customer support agent for {{company}}. Help users with {{product}} questions.\n\nRules:\n- Be concise and friendly\n- Always verify the user's account\n- Escalate billing issues to human agents",
                    "variables": ["company", "product"],
                    "model": "gpt-4",
                    "parameters": {"temperature": 0.3},
                    "created_at": (datetime.now() - timedelta(days=3)).isoformat(),
                    "metrics": {"avg_satisfaction": 4.2},
                },
                {
                    "version": 3,
                    "system_prompt": "You are {{role}} at {{company}}, specialized in {{product}} support.\n\nGuidelines:\n- Greet the user by name if available\n- Be concise, professional, and empathetic\n- For billing: verify account, then assist or escalate\n- For technical: provide step-by-step solutions\n- Always end with: \"Is there anything else I can help with?\"\n\nTone: {{tone}}",
                    "variables": ["role", "company", "product", "tone"],
                    "model": "gpt-4",
                    "parameters": {"temperature": 0.2, "max_tokens": 500},
                    "created_at": (datetime.now() - timedelta(hours=2)).isoformat(),
                    "metrics": {"avg_satisfaction": 4.6},
                },
            ],
        },
        {
            "id": "demo-p2",
            "name": "Code Review Agent",
            "description": "Automated code review with constructive feedback",
            "current_version": 2,
            "tags": ["development", "agent"],
            "created_at": (datetime.now() - timedelta(days=5)).isoformat(),
            "updated_at": (datetime.now() - timedelta(days=1)).isoformat(),
            "versions": [
                {
                    "version": 1,
                    "system_prompt": "Review the following {{language}} code. Find bugs and suggest improvements.\n\nCode:\n```\n{{code}}\n```",
                    "variables": ["language", "code"],
                    "model": "",
                    "parameters": {},
                    "created_at": (datetime.now() - timedelta(days=5)).isoformat(),
                    "metrics": None,
                },
                {
                    "version": 2,
                    "system_prompt": "You are a senior {{language}} developer doing a code review.\n\nReview criteria:\n1. Correctness: Are there bugs or logic errors?\n2. Performance: Any O(n^2) when O(n) is possible?\n3. Security: SQL injection, XSS, input validation?\n4. Style: Does it follow {{language}} conventions?\n\nProvide feedback as:\n- CRITICAL: Must fix before merge\n- WARNING: Should fix, non-blocking\n- SUGGESTION: Nice to have\n\nCode:\n```{{language}}\n{{code}}\n```",
                    "variables": ["language", "code"],
                    "model": "gpt-4",
                    "parameters": {"temperature": 0.1},
                    "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
                    "metrics": None,
                },
            ],
        },
        {
            "id": "demo-p3",
            "name": "Data Extraction",
            "description": "Extract structured data from unstructured text",
            "current_version": 1,
            "tags": ["extraction", "production"],
            "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
            "updated_at": (datetime.now() - timedelta(days=2)).isoformat(),
            "versions": [
                {
                    "version": 1,
                    "system_prompt": "Extract the following fields from the text:\n- name\n- email\n- phone\n- company\n\nReturn as JSON. If a field is missing, use null.\n\nText: {{input}}",
                    "variables": ["input"],
                    "model": "",
                    "parameters": {},
                    "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
                    "metrics": None,
                },
            ],
        },
    ]

    with open(DATA_DIR / "prompts.json", "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)
    print(f"  Created {len(prompts)} prompts ({sum(len(p['versions']) for p in prompts)} versions)")


def seed_workflows() -> None:
    """Create demo workflows with realistic node layouts."""
    workflows = []

    # 1. Full training pipeline
    workflows.append({
        "id": "demo-wf1",
        "name": "Customer Support Fine-Tuning",
        "nodes": [
            {"id": "n1", "type": "dataSource", "position": {"x": 50, "y": 200}, "data": {"label": "Support Tickets", "config": {"path": "data/support.jsonl", "format": "jsonl", "split": "train"}}},
            {"id": "n2", "type": "splitter", "position": {"x": 280, "y": 200}, "data": {"label": "Train/Val Split", "config": {"train_ratio": 0.9, "val_ratio": 0.1, "strategy": "random"}}},
            {"id": "n3", "type": "model", "position": {"x": 280, "y": 50}, "data": {"label": "Llama 3.2 1B", "config": {"model_id": "meta-llama/Llama-3.2-1B-Instruct", "quantization": "4bit"}}},
            {"id": "n4", "type": "training", "position": {"x": 520, "y": 120}, "data": {"label": "SFT Training", "config": {"task": "sft", "lr": 2e-4, "epochs": 3, "batch_size": 4, "lora_r": 16, "lora_alpha": 32, "optimizer": "adamw_8bit", "bf16": True}}},
            {"id": "n5", "type": "eval", "position": {"x": 760, "y": 120}, "data": {"label": "Evaluate", "config": {"batch_size": 8, "max_tokens": 512}}},
            {"id": "n6", "type": "conditional", "position": {"x": 1000, "y": 120}, "data": {"label": "Loss < 0.5?", "config": {"metric_name": "loss", "operator": "<", "threshold": 0.5}}},
            {"id": "n7", "type": "export", "position": {"x": 1240, "y": 50}, "data": {"label": "Export GGUF", "config": {"format": "gguf", "quantization": "q4_k_m"}}},
            {"id": "n8", "type": "serve", "position": {"x": 1240, "y": 200}, "data": {"label": "Deploy vLLM", "config": {"engine": "vllm", "port": 8000, "api_format": "openai"}}},
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n4", "sourceHandle": "train"},
            {"id": "e3", "source": "n3", "target": "n4"},
            {"id": "e4", "source": "n4", "target": "n5"},
            {"id": "e5", "source": "n5", "target": "n6"},
            {"id": "e6", "source": "n6", "target": "n7"},
            {"id": "e7", "source": "n7", "target": "n8"},
        ],
        "created_at": (datetime.now() - timedelta(days=3)).isoformat(),
        "updated_at": (datetime.now() - timedelta(hours=5)).isoformat(),
        "last_run": (datetime.now() - timedelta(hours=5)).isoformat(),
        "run_count": 4,
    })

    # 2. RAG Agent Pipeline
    workflows.append({
        "id": "demo-wf2",
        "name": "RAG Agent with Data Flywheel",
        "nodes": [
            {"id": "n1", "type": "dataSource", "position": {"x": 50, "y": 100}, "data": {"label": "Knowledge Base", "config": {"path": "data/docs.jsonl", "format": "jsonl"}}},
            {"id": "n2", "type": "model", "position": {"x": 50, "y": 300}, "data": {"label": "Qwen 3B", "config": {"model_id": "Qwen/Qwen2.5-3B-Instruct", "quantization": "4bit"}}},
            {"id": "n3", "type": "rag", "position": {"x": 300, "y": 100}, "data": {"label": "RAG Index", "config": {"embedding_model": "BAAI/bge-small-en-v1.5", "vector_store": "chroma", "chunk_size": 512, "top_k": 5}}},
            {"id": "n4", "type": "agent", "position": {"x": 550, "y": 200}, "data": {"label": "Support Agent", "config": {"framework": "pulsar-react", "tools": ["search", "calculator"], "memory_type": "short_term", "max_iterations": 10}}},
            {"id": "n5", "type": "dataGen", "position": {"x": 800, "y": 200}, "data": {"label": "Generate SFT Data", "config": {"output_format": "sft", "num_samples": 500, "include_reasoning": True, "filter_quality": True}}},
            {"id": "n6", "type": "training", "position": {"x": 1050, "y": 200}, "data": {"label": "Fine-Tune on Traces", "config": {"task": "sft", "lr": 1e-4, "epochs": 2}}},
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n3"},
            {"id": "e2", "source": "n2", "target": "n4"},
            {"id": "e3", "source": "n3", "target": "n4"},
            {"id": "e4", "source": "n4", "target": "n5"},
            {"id": "e5", "source": "n5", "target": "n6"},
            {"id": "e6", "source": "n2", "target": "n6"},
        ],
        "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
        "updated_at": (datetime.now() - timedelta(hours=1)).isoformat(),
        "last_run": (datetime.now() - timedelta(hours=1)).isoformat(),
        "run_count": 2,
    })

    # 3. Multi-Agent Router
    workflows.append({
        "id": "demo-wf3",
        "name": "Multi-Agent Code Assistant",
        "nodes": [
            {"id": "n1", "type": "model", "position": {"x": 50, "y": 200}, "data": {"label": "Mistral 7B", "config": {"model_id": "mistralai/Mistral-7B-Instruct-v0.3", "quantization": "8bit"}}},
            {"id": "n2", "type": "prompt", "position": {"x": 300, "y": 50}, "data": {"label": "Router Prompt", "config": {"template": "Classify: {{input}}", "variables": "input"}}},
            {"id": "n3", "type": "router", "position": {"x": 300, "y": 200}, "data": {"label": "Task Router", "config": {"strategy": "llm_classifier", "routes": ["code,docs,debug"], "fallback_route": "general"}}},
            {"id": "n4", "type": "agent", "position": {"x": 580, "y": 80}, "data": {"label": "Code Writer", "config": {"framework": "langgraph", "tools": ["code_exec", "file_read"], "max_iterations": 15}}},
            {"id": "n5", "type": "agent", "position": {"x": 580, "y": 220}, "data": {"label": "Doc Generator", "config": {"framework": "crewai", "tools": ["search", "write"], "max_iterations": 8}}},
            {"id": "n6", "type": "agent", "position": {"x": 580, "y": 360}, "data": {"label": "Debugger", "config": {"framework": "pulsar-react", "tools": ["code_exec", "trace", "search"], "max_iterations": 20}}},
            {"id": "n7", "type": "inference", "position": {"x": 850, "y": 220}, "data": {"label": "Merge Results", "config": {"max_tokens": 1024, "temperature": 0.3}}},
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n3"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4", "sourceHandle": "route_a"},
            {"id": "e4", "source": "n3", "target": "n5", "sourceHandle": "route_b"},
            {"id": "e5", "source": "n3", "target": "n6", "sourceHandle": "fallback"},
            {"id": "e6", "source": "n4", "target": "n7"},
            {"id": "e7", "source": "n5", "target": "n7"},
            {"id": "e8", "source": "n6", "target": "n7"},
        ],
        "created_at": (datetime.now() - timedelta(hours=12)).isoformat(),
        "updated_at": (datetime.now() - timedelta(hours=3)).isoformat(),
        "last_run": None,
        "run_count": 0,
    })

    with open(DATA_DIR / "workflows.json", "w", encoding="utf-8") as f:
        json.dump(workflows, f, ensure_ascii=False, indent=2)
    print(f"  Created {len(workflows)} workflows")


def main() -> None:
    """Seed all demo data."""
    print("Seeding demo data for Pulsar AI...")
    print()

    seed_experiments()
    seed_datasets()
    seed_prompts()
    seed_workflows()

    print()
    print("Done! Restart the server to see demo data in the UI.")
    print("  pulsar ui  OR  uvicorn pulsar_ai.ui.app:create_app --factory --port 8888")


if __name__ == "__main__":
    main()
