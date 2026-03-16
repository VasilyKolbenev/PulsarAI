"""Pulsar Co-pilot — AI assistant with platform management tools.

Two operating modes:
- Command Mode: slash-commands (/status, /train, /workflows, etc.) — always available
- LLM Mode: GPT-4o-mini agent with 14 pulsar tools — when OPENAI_API_KEY is set
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from pulsar_ai.agent.tool import Tool, ToolRegistry, tool
from pulsar_ai.storage.session_store import SessionStore
from pulsar_ai.ui.experiment_store import ExperimentStore
from pulsar_ai.ui.jobs import submit_training_job, get_job, list_jobs, cancel_job

logger = logging.getLogger(__name__)

router = APIRouter(tags=["assistant"])

_store = ExperimentStore()
_session_store = SessionStore()


# ──────────────────────────────────────────────────────────
# Pulsar Tools — call backend in-process (no HTTP)
# ──────────────────────────────────────────────────────────


def _get_pulsar_tools() -> ToolRegistry:
    """Create a ToolRegistry with all pulsar platform tools.

    Returns:
        ToolRegistry with 14 pulsar tools.
    """
    registry = ToolRegistry()

    @tool(
        name="list_experiments", description="List recent training experiments with status and loss"
    )
    def list_experiments_tool(status: str = "", limit: int = 10) -> str:
        """List experiments, optionally filtered by status."""
        exps = _store.list_all(status=status or None)[:limit]
        if not exps:
            return "No experiments found."
        lines = []
        for e in exps:
            loss = f", loss={e['final_loss']:.4f}" if e.get("final_loss") else ""
            lines.append(f"- [{e['id']}] {e['name']} ({e['status']}{loss})")
        return "\n".join(lines)

    registry.register(list_experiments_tool)

    @tool(name="get_experiment", description="Get detailed info about a specific experiment by ID")
    def get_experiment_tool(experiment_id: str) -> str:
        """Get experiment details including config, metrics, artifacts."""
        exp = _store.get(experiment_id)
        if not exp:
            return f"Experiment {experiment_id} not found."
        info = {
            "id": exp["id"],
            "name": exp["name"],
            "status": exp["status"],
            "task": exp.get("task", "sft"),
            "model": exp.get("model", "unknown"),
            "final_loss": exp.get("final_loss"),
            "created_at": exp.get("created_at", ""),
            "artifacts": exp.get("artifacts", {}),
        }
        return json.dumps(info, indent=2)

    registry.register(get_experiment_tool)

    @tool(name="start_training", description="Start a new training experiment")
    def start_training_tool(
        name: str,
        model: str = "Qwen/Qwen2.5-3B-Instruct",
        dataset_path: str = "",
        task: str = "sft",
        epochs: int = 3,
        learning_rate: float = 2e-4,
        batch_size: int = 1,
        gradient_accumulation: int = 16,
    ) -> str:
        """Start training with given parameters."""
        if not dataset_path:
            return "Error: dataset_path is required. Use /datasets to see available datasets."
        config = {
            "model": {"name": model},
            "dataset": {"path": dataset_path},
            "training": {
                "epochs": epochs,
                "learning_rate": learning_rate,
                "batch_size": batch_size,
                "gradient_accumulation": gradient_accumulation,
                "max_seq_length": 512,
            },
            "output": {"dir": f"./outputs/{name}"},
        }
        exp_id = _store.create(name=name, config=config, task=task)
        job_id = submit_training_job(experiment_id=exp_id, config=config, task=task)
        return f"Training started! Job ID: {job_id}, Experiment ID: {exp_id}"

    registry.register(start_training_tool)

    @tool(name="check_training", description="Check status of running/recent training jobs")
    def check_training_tool() -> str:
        """Get current training job statuses."""
        jobs = list_jobs()
        if not jobs:
            return "No training jobs found."
        lines = []
        for j in jobs:
            lines.append(f"- Job {j['job_id']}: {j['status']} (experiment: {j['experiment_id']})")
        return "\n".join(lines)

    registry.register(check_training_tool)

    @tool(name="cancel_training", description="Cancel a running training job by job ID")
    def cancel_training_tool(job_id: str) -> str:
        """Cancel a training job."""
        if cancel_job(job_id):
            return f"Job {job_id} cancelled."
        return f"Could not cancel job {job_id}. It may have already completed or doesn't exist."

    registry.register(cancel_training_tool)

    @tool(name="list_datasets", description="List all uploaded datasets")
    def list_datasets_tool() -> str:
        """List datasets in the uploads directory."""
        from pathlib import Path
        import pandas as pd

        data_dir = Path("./data/uploads")
        if not data_dir.exists():
            return "No datasets uploaded yet."
        results = []
        for p in sorted(data_dir.iterdir()):
            if p.is_file() and p.suffix in (".csv", ".jsonl", ".parquet", ".xlsx"):
                try:
                    if p.suffix == ".csv":
                        rows = len(pd.read_csv(p))
                    elif p.suffix == ".jsonl":
                        rows = len(pd.read_json(p, lines=True))
                    else:
                        rows = "?"
                    results.append(
                        f"- [{p.stem}] {p.name} ({rows} rows, {p.stat().st_size / 1024:.1f} KB)"
                    )
                except Exception:
                    results.append(f"- [{p.stem}] {p.name} (error reading)")
        return "\n".join(results) if results else "No datasets found."

    registry.register(list_datasets_tool)

    @tool(name="preview_dataset", description="Preview first rows of a dataset")
    def preview_dataset_tool(dataset_id: str, rows: int = 5) -> str:
        """Show first N rows of a dataset."""
        from pathlib import Path
        import pandas as pd

        data_dir = Path("./data/uploads")
        for p in data_dir.iterdir():
            if p.stem == dataset_id:
                try:
                    if p.suffix == ".csv":
                        df = pd.read_csv(p)
                    elif p.suffix == ".jsonl":
                        df = pd.read_json(p, lines=True)
                    else:
                        return f"Preview not supported for {p.suffix}"
                    preview = df.head(rows).to_string(index=False)
                    return f"Columns: {list(df.columns)}\nRows: {len(df)}\n\n{preview}"
                except Exception as e:
                    return f"Error reading dataset: {e}"
        return f"Dataset {dataset_id} not found."

    registry.register(preview_dataset_tool)

    @tool(
        name="recommend_params",
        description="Recommend training hyperparameters based on model and dataset",
    )
    def recommend_params_tool(
        model: str = "Qwen/Qwen2.5-3B-Instruct",
        dataset_rows: int = 0,
    ) -> str:
        """Recommend training hyperparameters."""
        # Detect GPU
        gpu_vram = 0.0
        gpu_name = "CPU"
        try:
            from pulsar_ai.hardware import detect_hardware

            hw = detect_hardware()
            gpu_vram = hw.vram_per_gpu_gb
            gpu_name = hw.gpu_name
        except Exception:
            pass

        model_lower = model.lower()
        if "7b" in model_lower or "8b" in model_lower:
            lr, bs, ga = 1e-4, 1, 32
            seq_len = 512
        elif "3b" in model_lower:
            lr, bs, ga = 2e-4, 2, 16
            seq_len = 512
        elif "1b" in model_lower or "1.5b" in model_lower:
            lr, bs, ga = 3e-4, 4, 8
            seq_len = 1024
        else:
            lr, bs, ga = 2e-4, 2, 16
            seq_len = 512

        if gpu_vram >= 24:
            bs = min(bs * 2, 8)
            ga = max(ga // 2, 4)
        elif gpu_vram < 8 and gpu_vram > 0:
            bs = 1
            ga = 32

        epochs = 3
        if dataset_rows > 0:
            if dataset_rows < 100:
                epochs = 10
            elif dataset_rows < 1000:
                epochs = 5

        return (
            f"Recommended parameters for {model}:\n"
            f"  GPU: {gpu_name} ({gpu_vram:.1f} GB)\n"
            f"  Learning rate: {lr}\n"
            f"  Batch size: {bs}\n"
            f"  Gradient accumulation: {ga}\n"
            f"  Epochs: {epochs}\n"
            f"  Max sequence length: {seq_len}\n"
            f"  Optimizer: adamw_8bit\n"
            f"  Strategy: {'qlora' if gpu_vram < 24 else 'lora'}"
        )

    registry.register(recommend_params_tool)

    @tool(name="get_hardware", description="Get GPU and hardware information")
    def get_hardware_tool() -> str:
        """Detect hardware capabilities."""
        try:
            from pulsar_ai.hardware import detect_hardware

            hw = detect_hardware()
            return (
                f"GPUs: {hw.num_gpus}x {hw.gpu_name}\n"
                f"VRAM per GPU: {hw.vram_per_gpu_gb:.1f} GB\n"
                f"Total VRAM: {hw.total_vram_gb:.1f} GB\n"
                f"BF16: {'Yes' if hw.bf16_supported else 'No'}\n"
                f"Strategy: {hw.strategy}\n"
                f"Recommended batch size: {hw.recommended_batch_size}\n"
                f"Recommended grad accum: {hw.recommended_gradient_accumulation}"
            )
        except Exception as e:
            return f"Hardware detection failed: {e}"

    registry.register(get_hardware_tool)

    @tool(name="run_evaluation", description="Run evaluation on a trained experiment")
    def run_evaluation_tool(experiment_id: str, test_data_path: str) -> str:
        """Run evaluation on a trained model."""
        exp = _store.get(experiment_id)
        if not exp:
            return f"Experiment {experiment_id} not found."
        artifacts = exp.get("artifacts", {})
        model_path = artifacts.get("adapter_dir") or artifacts.get("output_dir")
        if not model_path:
            return "No trained model found for this experiment."
        return (
            f"Evaluation queued for experiment {experiment_id}.\n"
            f"Model: {model_path}\n"
            f"Test data: {test_data_path}"
        )

    registry.register(run_evaluation_tool)

    @tool(
        name="list_workflows", description="List saved visual workflows from the pipeline builder"
    )
    def list_workflows_tool() -> str:
        """List all saved workflows with IDs and stats."""
        from pulsar_ai.ui.workflow_store import WorkflowStore

        store = WorkflowStore()
        workflows = store.list_all()
        if not workflows:
            return "No saved workflows found. Create one in the Visual Builder."
        lines = []
        for wf in workflows:
            nodes = len(wf.get("nodes", []))
            edges = len(wf.get("edges", []))
            runs = wf.get("run_count", 0)
            lines.append(
                f"  [{wf['id']}] {wf['name']} — {nodes} nodes, " f"{edges} edges, {runs} runs"
            )
        return "Saved workflows:\n" + "\n".join(lines)

    registry.register(list_workflows_tool)

    @tool(name="get_workflow", description="Get details of a saved workflow by ID")
    def get_workflow_tool(workflow_id: str) -> str:
        """Get workflow details including nodes and edges."""
        from pulsar_ai.ui.workflow_store import WorkflowStore

        store = WorkflowStore()
        wf = store.get(workflow_id)
        if not wf:
            return f"Workflow '{workflow_id}' not found."
        nodes = wf.get("nodes", [])
        edges = wf.get("edges", [])
        lines = [f"Workflow: {wf['name']} [{wf['id']}]"]
        lines.append(f"Created: {wf.get('created_at', '?')}")
        lines.append(f"Updated: {wf.get('updated_at', '?')}")
        lines.append(f"Run count: {wf.get('run_count', 0)}")
        lines.append(f"\nNodes ({len(nodes)}):")
        for n in nodes:
            label = n.get("data", {}).get("label", n["id"])
            ntype = n.get("type", "default")
            lines.append(f"  - {label} (type={ntype})")
        lines.append(f"\nEdges ({len(edges)}):")
        for e in edges:
            lines.append(f"  - {e['source']} → {e['target']}")
        return "\n".join(lines)

    registry.register(get_workflow_tool)

    @tool(
        name="estimate_training_cost",
        description="Estimate GPU time and cost for a training run",
    )
    def estimate_training_cost_tool(
        model: str = "3B",
        dataset_rows: int = 1000,
        epochs: int = 3,
    ) -> str:
        """Estimate training duration and approximate cost.

        Args:
            model: Model size label (1B, 3B, 7B, 13B, 70B).
            dataset_rows: Number of training rows.
            epochs: Training epochs.
        """
        size_map = {
            "1B": (1, 0.5),
            "3B": (3, 1.0),
            "7B": (7, 2.5),
            "13B": (13, 5.0),
            "70B": (70, 30.0),
        }
        key = model.upper().replace("B", "") + "B"
        params_b, base_hours = size_map.get(key, (3, 1.0))

        # Rough heuristic: time scales with rows, epochs, model size
        row_factor = dataset_rows / 1000.0
        total_hours = base_hours * row_factor * epochs
        total_hours = max(0.1, round(total_hours, 2))

        # Cost estimate: ~$1/hr for A100-equivalent
        cost_per_hour = 1.0 if params_b <= 7 else 2.5
        total_cost = round(total_hours * cost_per_hour, 2)

        vram_needed = {
            "1B": "~4 GB",
            "3B": "~8 GB",
            "7B": "~16 GB",
            "13B": "~32 GB",
            "70B": "~80 GB (multi-GPU)",
        }.get(key, "~8 GB")

        return (
            f"Training estimate for {key} model:\n"
            f"  Dataset: {dataset_rows} rows × {epochs} epochs\n"
            f"  Estimated time: ~{total_hours} hours\n"
            f"  Estimated cost: ~${total_cost} (cloud GPU)\n"
            f"  VRAM required: {vram_needed} (QLoRA)\n"
            f"  Strategy: {'QLoRA' if params_b <= 13 else 'QLoRA + DeepSpeed'}"
        )

    registry.register(estimate_training_cost_tool)

    @tool(
        name="suggest_config",
        description="Suggest a training configuration for a given use case",
    )
    def suggest_config_tool(
        use_case: str = "chatbot",
        budget: str = "medium",
    ) -> str:
        """Suggest a training configuration.

        Args:
            use_case: One of chatbot, coding, classification, summarization.
            budget: One of low (consumer GPU), medium (single A100), high (multi-GPU).
        """
        configs = {
            "chatbot": {
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "method": "SFT + DPO",
                "dataset_format": "JSONL chat (messages array)",
                "min_rows": 500,
                "tips": "Use diverse conversation styles. Add system prompts.",
            },
            "coding": {
                "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
                "method": "SFT",
                "dataset_format": "instruction/input/output CSV",
                "min_rows": 1000,
                "tips": "Include edge cases and error handling examples.",
            },
            "classification": {
                "model": "Qwen/Qwen2.5-3B-Instruct",
                "method": "SFT",
                "dataset_format": "instruction/output CSV (label as output)",
                "min_rows": 200,
                "tips": "Balance classes. 3B is usually enough.",
            },
            "summarization": {
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "method": "SFT",
                "dataset_format": "instruction/input/output CSV",
                "min_rows": 300,
                "tips": "Vary text lengths. Include both short and long inputs.",
            },
        }
        cfg = configs.get(use_case.lower(), configs["chatbot"])

        budget_mod = ""
        if budget == "low":
            cfg["model"] = cfg["model"].replace("7B", "3B")
            budget_mod = "  Note: downgraded to 3B for low budget.\n"
        elif budget == "high":
            budget_mod = "  Note: consider full fine-tune or larger model.\n"

        return (
            f"Suggested config for '{use_case}' ({budget} budget):\n"
            f"  Model: {cfg['model']}\n"
            f"  Method: {cfg['method']}\n"
            f"  Dataset format: {cfg['dataset_format']}\n"
            f"  Min rows: {cfg['min_rows']}\n"
            f"{budget_mod}"
            f"  Tips: {cfg['tips']}"
        )

    registry.register(suggest_config_tool)

    return registry


# ──────────────────────────────────────────────────────────
# Command Parser
# ──────────────────────────────────────────────────────────

_CMD_PATTERN = re.compile(r"^/(\w+)\s*(.*)?$", re.DOTALL)
_KV_PATTERN = re.compile(r"(\w+)=(\S+)")

HELP_TEXT = """Available commands:
  /status              — Check training status and recent experiments
  /datasets            — List uploaded datasets
  /train name=X model=Y dataset=Z  — Start training
  /recommend model=X   — Get hyperparameter recommendations
  /hardware            — Show GPU info
  /experiments         — List all experiments
  /workflows           — List saved visual workflows
  /estimate model=3B rows=1000 epochs=3  — Estimate training cost
  /cancel job_id=X     — Cancel a training job
  /preview id=X        — Preview a dataset
  /help                — Show this help

Type freely for AI-powered answers (requires OPENAI_API_KEY)."""


def parse_command(message: str) -> dict[str, Any] | None:
    """Parse a slash command into tool calls.

    Args:
        message: User message starting with /.

    Returns:
        Dict with 'results' key containing tool outputs, or None if not a command.
    """
    match = _CMD_PATTERN.match(message.strip())
    if not match:
        return None

    cmd = match.group(1).lower()
    args_str = (match.group(2) or "").strip()
    kwargs = dict(_KV_PATTERN.findall(args_str))

    tools = _get_pulsar_tools()
    results = []

    if cmd == "help":
        return {"results": [HELP_TEXT]}

    elif cmd == "status":
        results.append(tools.get("check_training").execute())
        results.append(tools.get("list_experiments").execute(limit=5))

    elif cmd == "datasets":
        results.append(tools.get("list_datasets").execute())

    elif cmd == "train":
        name = kwargs.get("name", "unnamed")
        model = kwargs.get("model", "Qwen/Qwen2.5-3B-Instruct")
        dataset = kwargs.get("dataset", "")
        if not dataset:
            return {
                "results": [
                    "Error: dataset is required. Usage: /train name=X model=Y dataset=path/to/data.csv"
                ]
            }
        results.append(
            tools.get("start_training").execute(
                name=name,
                model=model,
                dataset_path=dataset,
            )
        )

    elif cmd == "recommend":
        model = kwargs.get("model", "Qwen/Qwen2.5-3B-Instruct")
        rows = int(kwargs.get("rows", "0"))
        results.append(tools.get("recommend_params").execute(model=model, dataset_rows=rows))

    elif cmd == "hardware":
        results.append(tools.get("get_hardware").execute())

    elif cmd == "experiments":
        status = kwargs.get("status", "")
        results.append(tools.get("list_experiments").execute(status=status))

    elif cmd == "cancel":
        job_id = kwargs.get("job_id", args_str)
        if not job_id:
            return {"results": ["Usage: /cancel job_id=X"]}
        results.append(tools.get("cancel_training").execute(job_id=job_id))

    elif cmd == "workflows":
        results.append(tools.get("list_workflows").execute())

    elif cmd == "estimate":
        model = kwargs.get("model", "3B")
        rows = int(kwargs.get("rows", "1000"))
        epochs = int(kwargs.get("epochs", "3"))
        results.append(
            tools.get("estimate_training_cost").execute(
                model=model,
                dataset_rows=rows,
                epochs=epochs,
            )
        )

    elif cmd == "preview":
        ds_id = kwargs.get("id", args_str)
        if not ds_id:
            return {"results": ["Usage: /preview id=dataset_id"]}
        results.append(tools.get("preview_dataset").execute(dataset_id=ds_id))

    else:
        return {"results": [f"Unknown command: /{cmd}\n\n{HELP_TEXT}"]}

    return {"results": results}


# ──────────────────────────────────────────────────────────
# LLM Mode
# ──────────────────────────────────────────────────────────


def _check_llm_available() -> bool:
    """Check if an LLM backend is available.

    Returns:
        True if OPENAI_API_KEY is configured.
    """
    import os

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    return bool(key)


def _get_or_create_session(session_id: str | None) -> tuple[str, list[dict]]:
    """Get or create a chat session backed by SQLite.

    Args:
        session_id: Optional existing session ID.

    Returns:
        Tuple of (session_id, message_history).
    """
    sid = session_id or str(uuid.uuid4())[:12]
    session = _session_store.get_or_create(sid, session_type="assistant")
    return session["id"], session["messages"]


def _build_system_prompt(context: dict | None = None) -> str:
    """Build the system prompt for the Pulsar Co-pilot.

    Args:
        context: Optional UI context with page, active_jobs.

    Returns:
        Complete system prompt string.
    """
    ctx_lines = []
    if context:
        page = context.get("page", "unknown")
        ctx_lines.append(f"User is currently on page: {page}")
        active = context.get("active_jobs", [])
        if active:
            ctx_lines.append(f"Active training jobs: {len(active)}")
            for job in active[:3]:
                ctx_lines.append(
                    f"  - Job {job.get('job_id', '?')}: {job.get('status', '?')} "
                    f"(experiment: {job.get('experiment_id', '?')})"
                )
    ctx_block = "\n".join(ctx_lines)

    return (
        "You are Pulsar Co-pilot, the built-in AI assistant for the Pulsar AI platform.\n\n"
        "## Platform Overview\n"
        "Pulsar AI is a self-hosted, open-source platform for the full LLM lifecycle:\n"
        "- 26 visual workflow node types in 7 categories: Data, Training, Agent, "
        "Protocols, Safety, Evaluation, Ops\n"
        "- Visual DAG pipeline builder for orchestrating multi-step ML workflows\n"
        "- Fine-tuning: SFT and DPO with LoRA/QLoRA, Unsloth 2x speedup\n"
        "- Supported models: Qwen, Llama, Mistral, Gemma via HuggingFace\n"
        "- Serving: vLLM, llama.cpp, TGI, Ollama\n"
        "- Agent framework: ReAct loops, tool calling, guardrails\n"
        "- Evaluation: LLM-as-Judge, A/B testing, custom metrics\n"
        "- Observability: tracing, cost tracking, semantic cache\n\n"
        "## Your Capabilities\n"
        "You have tools to:\n"
        "- List and inspect training experiments and their metrics\n"
        "- Start, monitor, and cancel training jobs\n"
        "- List and preview uploaded datasets\n"
        "- Recommend hyperparameters based on model size, dataset, and hardware\n"
        "- Detect GPU hardware and VRAM\n"
        "- Run evaluations on trained models\n"
        "- List and inspect saved visual workflows\n"
        "- Estimate training cost and duration\n"
        "- Suggest training configs for common use cases\n\n"
        "## How to Help\n"
        "- Fine-tuning setup: help choose model, dataset format, hyperparameters. "
        "Suggest QLoRA for GPUs under 24GB.\n"
        "- Hyperparameter tuning: use recommend_params tool, explain reasoning. "
        "batch_size x gradient_accumulation = effective batch size.\n"
        "- Dataset management: help with dataset formats (CSV with instruction/input/output, "
        "or JSONL chat format). Preview datasets to check quality.\n"
        "- GPU monitoring: check hardware, explain VRAM requirements "
        "(1B~4GB, 3B~8GB, 7B~16GB with QLoRA).\n"
        "- Troubleshooting: if training fails, check status, suggest lowering batch size "
        "or sequence length, or switching to QLoRA.\n\n"
        "## Slash Commands (always available)\n"
        "Users can also use: /status, /datasets, /train, /recommend, /hardware, "
        "/experiments, /workflows, /estimate, /cancel, /preview, /help\n\n"
        "## Response Style\n"
        "- Be concise and actionable. Prefer bullet points.\n"
        "- Mention relevant slash commands as shortcuts.\n"
        "- Use tool calls to get real data before answering.\n"
        "- Respond in the same language as the user's message.\n\n"
        "## Current Context\n"
        f"{ctx_block if ctx_block else 'No additional context available.'}"
    )


def _run_llm_mode(
    message: str,
    session_id: str,
    context: dict | None = None,
) -> dict[str, Any]:
    """Run the assistant in LLM mode with pulsar tools via OpenAI API.

    Args:
        message: User message.
        session_id: Session ID.
        context: Optional UI context (page, active_jobs).

    Returns:
        Dict with answer, tool_calls trace.
    """
    import os
    from pulsar_ai.agent.base import BaseAgent
    from pulsar_ai.agent.client import ModelClient
    from pulsar_ai.agent.memory import ShortTermMemory
    from pulsar_ai.agent.guardrails import GuardrailsConfig

    tools = _get_pulsar_tools()
    system_prompt = _build_system_prompt(context)

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    client = ModelClient(
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        timeout=30,
        api_key=api_key,
    )
    memory = ShortTermMemory(max_tokens=8192, system_prompt=system_prompt)
    guardrails = GuardrailsConfig(max_iterations=5, max_tokens=16384)

    # Restore session history (only user/assistant messages for OpenAI compat)
    sid, history = _get_or_create_session(session_id)
    for msg in history:
        if msg["role"] in ("user", "assistant"):
            memory.add(msg["role"], msg["content"])

    agent = BaseAgent(
        client=client,
        tools=tools,
        memory=memory,
        guardrails=guardrails,
        use_native_tools=True,
    )

    answer = agent.run(message)

    # Persist to SQLite
    _session_store.append_message(sid, "user", message)
    _session_store.append_message(sid, "assistant", answer)

    return {
        "answer": answer,
        "session_id": sid,
        "actions": agent.trace,
    }


# ──────────────────────────────────────────────────────────
# FastAPI Router
# ──────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Assistant chat request."""

    message: str
    session_id: str | None = None
    context: dict | None = None


class ChatResponse(BaseModel):
    """Assistant chat response."""

    answer: str
    session_id: str
    actions: list[dict[str, Any]] = []
    mode: str = "command"


class StatusResponse(BaseModel):
    """Platform status for the assistant widget."""

    active_jobs: list[dict[str, Any]]
    recent_experiments: list[dict[str, Any]]
    llm_available: bool


@router.post("/assistant/chat", response_model=ChatResponse)
async def assistant_chat(req: ChatRequest) -> ChatResponse:
    """Chat with the Pulsar Co-pilot.

    Routes to command mode or LLM mode depending on input.
    """
    message = req.message.strip()
    if not message:
        return ChatResponse(
            answer="Type a command (start with /) or a question. Try /help",
            session_id=req.session_id or str(uuid.uuid4())[:12],
            mode="command",
        )

    sid = req.session_id or str(uuid.uuid4())[:12]

    # Command mode
    if message.startswith("/"):
        result = parse_command(message)
        if result:
            answer = "\n\n".join(result["results"])
            return ChatResponse(
                answer=answer,
                session_id=sid,
                mode="command",
            )

    # LLM mode
    if _check_llm_available():
        try:
            result = _run_llm_mode(message, sid, context=req.context)
            return ChatResponse(
                answer=result["answer"],
                session_id=result["session_id"],
                actions=result.get("actions", []),
                mode="llm",
            )
        except Exception as e:
            logger.exception("LLM mode failed")
            return ChatResponse(
                answer=f"LLM error: {e}\n\nTip: Use slash commands (/help) for direct access.",
                session_id=sid,
                mode="command",
            )

    # Fallback: no LLM, no command
    return ChatResponse(
        answer=(
            "No LLM server connected. Use slash commands for direct access:\n\n" f"{HELP_TEXT}"
        ),
        session_id=sid,
        mode="command",
    )


@router.get("/assistant/status", response_model=StatusResponse)
async def assistant_status() -> StatusResponse:
    """Get platform status for the co-pilot widget."""
    jobs = list_jobs()
    active = [j for j in jobs if j["status"] == "running"]
    recent = _store.list_all()[:5]
    llm_ok = _check_llm_available()

    return StatusResponse(
        active_jobs=active,
        recent_experiments=[
            {"id": e["id"], "name": e["name"], "status": e["status"]} for e in recent
        ],
        llm_available=llm_ok,
    )


@router.delete("/assistant/session/{session_id}")
async def delete_session(session_id: str) -> dict:
    """Delete an assistant session."""
    if _session_store.delete(session_id):
        return {"status": "deleted"}
    return {"status": "not_found"}
