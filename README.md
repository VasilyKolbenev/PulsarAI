<p align="center">
  <h1 align="center">Pulsar AI</h1>
  <p align="center">The open-source MLOps platform for the full LLM lifecycle</p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License: Apache 2.0"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-brightgreen.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/tests-passing-success.svg" alt="Tests: passing">
</p>

---

**Pulsar AI** is the open-source platform that closes the loop between LLM training and deployment. Fine-tune models with SFT and DPO, orchestrate pipelines with a visual DAG builder, deploy ReAct agents with tool access, evaluate with LLM-as-Judge -- then feed agent traces back into training data to build better models. Self-hosted, single-machine friendly, no vendor lock-in.

## Feature Matrix

| Capability | What you get |
|---|---|
| **Training** | SFT + DPO fine-tuning, LoRA / QLoRA / FSDP, hardware auto-detection |
| **Orchestration** | Visual DAG pipeline builder, 26 node types, YAML-driven |
| **Agents** | ReAct agent framework, MCP / A2A protocol support, tool registry |
| **Evaluation** | LLM-as-Judge, A/B testing, experiment tracking with SQLite |
| **Export** | GGUF quantization, vLLM, Ollama, HuggingFace Hub, model registry |
| **Monitoring** | Real-time GPU/CPU metrics, cost tracking, training dashboards |
| **Closed Loop** | Agent traces -> training data -> better models -> better agents |

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/pulsarai/pulsar-ai.git
cd pulsar-ai
docker compose up
```

Open **http://localhost:8888** -- the UI, API, and worker start automatically.

### pip

```bash
pip install -e ".[all]"

# Or pick what you need:
pip install -e ".[unsloth]"    # Unsloth (2-5x speedup on single GPU)
pip install -e ".[vllm]"       # vLLM serving
pip install -e ".[llamacpp]"   # llama.cpp serving
pip install -e ".[eval]"       # Evaluation plots
```

### Train your first model

```bash
# Fine-tune with SFT
pulsar train configs/examples/cam-sft.yaml

# Evaluate
pulsar eval --model ./outputs/cam-sft/lora --test-data data/test.csv

# Export to GGUF
pulsar export --model ./outputs/cam-sft/lora --format gguf --quant q4_k_m

# Launch the UI
pulsar ui
```

## Architecture

```
                          +------------------+
                          |   Pulsar UI      |
                          | React 19 + TS    |
                          +--------+---------+
                                   |
                          +--------v---------+
                          |   FastAPI         |
                          |   REST + WebSocket|
                          +--------+---------+
                                   |
          +------------+-----------+-----------+------------+
          |            |           |           |            |
  +-------v--+  +------v---+  +---v------+  +-v--------+  +v-----------+
  | Training  |  | Pipeline |  | Agent    |  | Eval     |  | Export     |
  | Engine    |  | DAG      |  | Runtime  |  | Engine   |  | Registry   |
  | SFT, DPO  |  | 26 nodes |  | ReAct    |  | Judge    |  | GGUF,vLLM  |
  | LoRA,QLoRA|  | YAML     |  | MCP,A2A  |  | A/B test |  | Ollama,Hub |
  +-----------+  +----------+  +----------+  +----------+  +------------+
          |            |           |           |            |
          +------------+-----------+-----------+------------+
                                   |
                          +--------v---------+
                          |   SQLite WAL     |
                          |   Experiments,   |
                          |   Traces, Metrics|
                          +------------------+

  Closed loop: Agent traces --> DPO pairs --> Fine-tune --> Deploy --> Trace
```

## Hardware Auto-Detection

Set `strategy: auto` (default) and Pulsar picks the optimal approach:

| Hardware | Strategy |
|---|---|
| 1 GPU, < 12 GB | QLoRA (4-bit) |
| 1 GPU, 12-24 GB | LoRA |
| 1 GPU, 24-48 GB | Full fine-tune |
| 2-4 GPUs, < 24 GB each | FSDP + QLoRA |
| 8+ GPUs, 40+ GB each | FSDP Full |

## Comparison

| Feature | Pulsar AI | OpenJarvis | ClearML | W&B | LangSmith |
|---|:---:|:---:|:---:|:---:|:---:|
| SFT / DPO training | Yes | -- | Plugin | -- | -- |
| Hardware auto-detect | Yes | -- | -- | -- | -- |
| Visual DAG pipelines | Yes | -- | Yes | -- | -- |
| Agent framework | Yes | Yes | -- | -- | Yes |
| MCP / A2A protocols | Yes | Yes | -- | -- | -- |
| LLM-as-Judge eval | Yes | -- | -- | Yes | Yes |
| Experiment tracking | Yes | -- | Yes | Yes | -- |
| GGUF / Ollama export | Yes | -- | -- | -- | -- |
| GPU monitoring | Yes | -- | Yes | Yes | -- |
| Closed-loop training | Yes | -- | -- | -- | -- |
| Self-hosted | Yes | Yes | Yes | -- | -- |
| Open source | Apache 2.0 | MIT | Apache 2.0 | -- | -- |
| Single-machine setup | Yes | Yes | -- | -- | -- |

## CLI Reference

```
pulsar train <config> [overrides...]       Fine-tune with SFT or DPO
pulsar eval --model <path> --test-data <p> Evaluate model quality
pulsar export --model <path> --format <f>  Export: gguf, merged, hub
pulsar serve --model <path> --backend <b>  Start inference server
pulsar agent serve                         Launch agent runtime
pulsar ui                                  Open web dashboard
```

## Project Structure

```
src/pulsar_ai/
  cli.py              CLI entry point
  config.py           YAML config with inheritance
  hardware.py         GPU detection and strategy selection
  training/           SFT, DPO, distributed training
  evaluation/         Batch inference, metrics, LLM-as-Judge
  export/             LoRA merge, GGUF, HuggingFace Hub
  serving/            llama.cpp, vLLM, Ollama backends
  agents/             ReAct runtime, MCP/A2A connectors
  pipelines/          DAG engine, 26 node types
  monitoring/         GPU/CPU metrics, cost tracking
frontend/
  src/                React 19, TypeScript, Tailwind CSS
configs/
  base.yaml           Shared defaults
  models/             Model-specific configs
  strategies/         Training strategy configs
  examples/           Ready-to-use experiments
```

## Contributing

Contributions are welcome. To get started:

```bash
git clone https://github.com/pulsarai/pulsar-ai.git
cd pulsar-ai
pip install -e ".[dev]"
pytest tests/
```

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Write tests for your changes
4. Ensure all tests pass: `pytest tests/`
5. Submit a pull request

Please follow the existing code style: type hints on all functions, Google-style docstrings, and PEP 8 naming.

## License

[Apache License 2.0](LICENSE)

Copyright 2025-2026 Pulsar AI Contributors
