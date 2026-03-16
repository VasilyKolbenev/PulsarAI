# Pulsar AI — Technical & Business Presentation

## What is Pulsar AI?

**Self-hosted, open-source platform for the full LLM lifecycle: from raw data to deployed agent.**

One platform replaces 5-7 separate tools in the typical LLM engineering stack.

---

## The Problem

Teams building LLM-powered products today juggle:
- **Training**: custom scripts, Weights & Biases, HuggingFace
- **Data management**: separate pipelines for preprocessing, splitting, generation
- **Agent orchestration**: LangChain, LangGraph, CrewAI — each with its own ecosystem
- **Serving**: vLLM, TGI, Ollama — manual setup per model
- **Monitoring**: Prometheus + Grafana or cloud-specific tools
- **Prompt engineering**: spreadsheets, ad-hoc scripts, no versioning

**Result**: fragmented workflow, vendor lock-in, no single source of truth.

---

## The Solution: Pulsar AI

| Capability | Description |
|-----------|-------------|
| **Fine-Tuning** | SFT + DPO with LoRA/QLoRA, Unsloth acceleration, 4/8-bit quantization |
| **Visual Workflow Builder** | Drag-and-drop DAG pipeline: 26 node types, C4-style groups, one-click run |
| **Agent Framework** | Built-in ReAct agent + LangGraph/CrewAI/AutoGen selector |
| **RAG Pipeline** | Vector store integration (Chroma, FAISS, Qdrant, Pinecone) |
| **Model Serving** | One-click deploy via vLLM, llama.cpp, TGI, Ollama |
| **Prompt Versioning** | Git-like prompt management: versions, diffs, test rendering |
| **Resource Monitoring** | Real-time GPU/CPU/RAM metrics via SSE, live charts |
| **Remote Compute** | SSH-based remote GPU management, hardware auto-detection |
| **Data Generation** | Agent traces → SFT/DPO training data (synthetic flywheel) |
| **Export** | GGUF, merged, LoRA, HuggingFace push |
| **Security** | API key auth, rate limiting, CORS hardening, safe eval |
| **Experiment Tracking** | Local/ClearML/W&B backends, dataset fingerprinting, environment capture |
| **HPO (Sweeps)** | Optuna-powered hyperparameter optimization with YAML configs |
| **Model Registry** | Version, stage, compare models (registered → staging → production) |
| **HuggingFace Hub** | Direct dataset loading from HF Hub with dedup and column filtering |
| **Pipeline Conditionals** | Conditional step execution based on metric thresholds |
| **Protocols** | MCP tool exposure, A2A agent delegation, API Gateway routing |
| **Guardrails** | Input/output guards: PII masking, injection detection, toxicity filter, JSON schema |
| **LLM-as-Judge** | Automated evaluation with customizable criteria and pairwise comparison |
| **A/B Testing** | Traffic splitting, metric collection, statistical winner detection |
| **Canary Deploy** | Gradual rollout with auto-rollback on error thresholds |
| **Observability** | OpenTelemetry-style tracing, per-span token/cost tracking |
| **Semantic Cache** | LLM response caching with TTL, LRU eviction, hit rate stats |
| **Cost Tracking** | Per-model/operation token cost estimation with budget alerts |
| **Human Feedback** | Thumbs/rating/preference collection → auto DPO pair export |
| **Dataset Versioning** | DVC-like version tracking with fingerprints, diffs, lineage |
| **Model Cards** | Auto-generated documentation from training config and metrics |
| **One-Click Run** | WebSocket pipeline execution with live per-node progress |
| **Self-Hosted** | Docker one-liner deployment, no cloud dependency |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Pulsar AI Web UI (React)                  │
│  Dashboard │ Experiments │ Datasets │ Workflows │ Prompts   │
│  Monitoring │ Compute │ Agent Chat │ Settings               │
├─────────────────────────────────────────────────────────────┤
│                    FastAPI Backend                            │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │Training │ │ Pipeline │ │ Agent    │ │ Resource       │  │
│  │  SFT    │ │ Executor │ │ ReAct    │ │ Monitor        │  │
│  │  DPO    │ │ DAG      │ │ Memory   │ │ GPU/CPU/RAM    │  │
│  │  LoRA   │ │ Topo-sort│ │ Tools    │ │ SSE streaming  │  │
│  └─────────┘ └──────────┘ └──────────┘ └────────────────┘  │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │ Dataset │ │ Compute  │ │ Prompt   │ │ Workflow       │  │
│  │ Upload  │ │ SSH Pool │ │ Version  │ │ Store          │  │
│  │ Preview │ │ Remote   │ │ Diff     │ │ JSON → DAG     │  │
│  │ JSONL/  │ │ GPU      │ │ Template │ │ Export config  │  │
│  │ CSV/    │ │ Detect   │ │ Test     │ │ 26 node types  │  │
│  │ Parquet │ │          │ │          │ │                │  │
│  └─────────┘ └──────────┘ └──────────┘ └────────────────┘  │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │Tracking │ │ HPO      │ │ Registry │ │ Protocols      │  │
│  │ Local   │ │ Optuna   │ │ Version  │ │ MCP Server     │  │
│  │ ClearML │ │ Sweeps   │ │ Stage    │ │ A2A Protocol   │  │
│  │ W&B     │ │ YAML     │ │ Compare  │ │ API Gateway    │  │
│  └─────────┘ └──────────┘ └──────────┘ └────────────────┘  │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │Guard-   │ │ Eval     │ │ Deploy   │ │ Observability  │  │
│  │ rails   │ │ LLM Judge│ │ Canary   │ │ Tracer         │  │
│  │ PII     │ │ A/B Test │ │ A/B      │ │ Cost Tracker   │  │
│  │ Inject  │ │ Compare  │ │ Rollback │ │ Cache          │  │
│  └─────────┘ └──────────┘ └──────────┘ └────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│        PyTorch + Transformers + PEFT + TRL + Accelerate      │
└─────────────────────────────────────────────────────────────┘
```

---

## Pipeline Parallelism Model

The workflow builder creates a **Directed Acyclic Graph (DAG)**:

1. User connects nodes visually (React Flow)
2. `WorkflowStore.to_pipeline_config()` converts to pipeline YAML
3. `PipelineExecutor._resolve_order()` performs **topological sort**
4. Steps execute in dependency order with **variable substitution** (`${step.output_key}`)

**Current model**: Sequential execution with automatic dependency resolution.
Independent branches (no shared edges) are resolved correctly but execute one at a time.

**Roadmap for true parallelism**:
- `asyncio.gather()` for independent branches (same-level nodes without edges)
- Distributed execution: different steps on different compute targets
- GPU memory-aware scheduling: auto-place training vs inference on separate GPUs

---

## Workflow Builder — 26 Node Types

### Data Layer
| Node | Purpose | Key Config |
|------|---------|-----------|
| **Data Source** | Load datasets (JSONL/CSV/Parquet/HF) | path, format, split |
| **Splitter** | Train/Val/Test split | ratios, strategy (random/stratified/temporal) |
| **Prompt** | Template engine with {{variables}} | template, variables |

### Training Layer
| Node | Purpose | Key Config |
|------|---------|-----------|
| **Model** | Select base model + quantization | model_id, quantization (4/8bit) |
| **Training** | SFT/DPO fine-tuning | 20+ params: LoRA, optimizer, bf16, checkpointing |
| **Evaluation** | Run benchmarks | batch_size, max_tokens |
| **Condition** | Branch on metrics (loss < 0.5?) | metric, operator, threshold |

### Agent Layer
| Node | Purpose | Key Config |
|------|---------|-----------|
| **Agent** | Build agent with framework choice | framework (Pulsar AI/LangGraph/CrewAI/AutoGen), tools, memory |
| **RAG** | Retrieval-Augmented Generation | embedding model, vector store, chunk_size, top_k |
| **Router** | Multi-agent routing | strategy (LLM/keyword/semantic), routes |
| **Inference** | Batch generation | temperature, top_p, max_tokens, streaming |
| **Data Gen** | Agent traces → training data | output_format (SFT/DPO/RLHF), num_samples |

### Deployment Layer
| Node | Purpose | Key Config |
|------|---------|-----------|
| **Export** | Convert model format | format (GGUF/merged/LoRA/HF), quantization |
| **Serve** | Deploy model endpoint | engine (vLLM/llama.cpp/TGI/Ollama), port |

### Protocol Layer
| Node | Purpose | Key Config |
|------|---------|-----------|
| **MCP** | Model Context Protocol server/client | role, transport (stdio/SSE/HTTP), tools, endpoint |
| **A2A** | Agent-to-Agent delegation (Google protocol) | protocol, delegation mode, agent card URL, timeout |
| **Gateway** | API gateway with multi-protocol routing | protocols (REST/gRPC/GraphQL), auth, rate limit, load balancer |

### Safety Layer
| Node | Purpose | Key Config |
|------|---------|-----------|
| **Input Guard** | Filter inputs: PII, injection, toxicity | rules, action (block/warn/mask), sensitivity |
| **Output Guard** | Validate outputs: JSON schema, PII leaks, length | validators, required_keys, max_length |

### Evaluation Layer
| Node | Purpose | Key Config |
|------|---------|-----------|
| **LLM Judge** | LLM-as-judge with criteria rubrics | criteria, judge_model, scale, comparison_mode |
| **A/B Test** | Compare models with traffic splitting | metric, traffic_split, min_samples, confidence |

### Ops Layer
| Node | Purpose | Key Config |
|------|---------|-----------|
| **Cache** | Semantic LLM response caching | strategy (exact/semantic), TTL, max_entries |
| **Canary** | Gradual model rollout with rollback | canary_weight, error_threshold, auto_rollback |
| **Feedback** | Human feedback → DPO training data | type (thumbs/rating/preference), export_format |
| **Tracer** | Observability spans with cost tracking | backend, cost_tracking, sample_rate |

### Structure
| Node | Purpose | Key Config |
|------|---------|-----------|
| **Group** | C4-level container for sub-workflows | c4_level (Context/Container/Component), collapsed |

---

## Key Differentiators

### 1. Closed-Loop Training Flywheel
```
Agent runs → traces collected → DataGen → SFT/DPO → improved model → better agent
```
No other platform offers this integrated feedback loop.

### 2. Protocol-Native Agent Ecosystem
MCP + A2A support means your agents can **expose tools** to any MCP client (Claude, Cursor, etc.) and **delegate tasks** to remote agents via the A2A protocol. Plus choose your framework per node — Pulsar ReAct, LangGraph, CrewAI, or AutoGen.

### 3. Self-Hosted by Design
- No data leaves your infrastructure
- Docker one-liner: `docker compose up`
- Runs on consumer GPUs (RTX 4090) through enterprise clusters (A100/H100)
- HIPAA/GDPR compliant by architecture

### 4. Visual-First Pipeline Design
Non-ML engineers can design workflows. ML engineers configure the details. Everyone sees the same DAG.

---

## Experiment Tracking & MLOps

### Pluggable Tracking Backends
```yaml
logging:
  tracker: clearml  # or: wandb, local, none
  project: my-project
  tags: [sft, production]
```

Every training run automatically captures:
- **Dataset fingerprint** (SHA-256) for reproducibility
- **Full environment** (Python version, packages, CUDA, GPU info)
- **Metrics** (loss, accuracy, throughput) with step-level logging
- **Artifacts** (adapter checkpoints, configs)

### Hyperparameter Optimization
```yaml
sweep:
  n_trials: 20
  metric: eval_loss
  direction: minimize
  search_space:
    lr: [1e-5, 5e-4, "log"]
    lora_r: [8, 64, "int"]
    optimizer: ["adamw_8bit", "adamw", "adafactor"]
```

Powered by Optuna — supports log-scale, integer, and categorical search spaces.

### Model Registry
```bash
pulsar registry register --name my-model --path ./output/lora
pulsar registry promote my-model-v3 --status production
pulsar registry list --status production
```

Full lifecycle: registered → staging → production → archived.

---

## Protocol Integration (MCP + A2A)

### MCP (Model Context Protocol)
Your fine-tuned agents can **expose tools** as MCP servers:
- Supports stdio, SSE, and Streamable HTTP transports
- Any MCP client (Claude Desktop, Cursor, custom) can discover and invoke tools
- JSON-RPC 2.0 compliant with full tools/list and tools/call support

### A2A (Agent-to-Agent Protocol)
Enable inter-agent communication following Google's A2A spec:
- Agent Cards for capability discovery (/.well-known/agent.json)
- Task delegation with lifecycle management (submitted → working → completed)
- Support for streaming, cancellation, and multi-turn conversations

### API Gateway
Unified access point for all your agents:
- Multi-protocol routing (REST, gRPC, GraphQL, webhooks)
- Built-in rate limiting and authentication (API key, OAuth2, JWT)
- Load balancing (round-robin, least connections, weighted)

---

## Security Posture

| Feature | Implementation |
|---------|---------------|
| **Authentication** | API key auth (SHA-256 hashed, Bearer token) |
| **Rate Limiting** | 60 req/min general, 5 req/min training |
| **CORS** | Configurable origins (env-based, no wildcard) |
| **No eval()** | AST-based safe math evaluator |
| **SSH Hardening** | known_hosts verification, no AutoAddPolicy |
| **No Injection** | SFTP file upload, no shell heredocs |
| **Secrets** | Environment variables only, never in code |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, TypeScript, Tailwind CSS, React Flow, Recharts |
| **Backend** | FastAPI, Uvicorn, SSE (Server-Sent Events) |
| **ML** | PyTorch, Transformers, PEFT, TRL, Accelerate, BitsAndBytes |
| **Agent** | Custom ReAct + LangGraph/CrewAI/AutoGen + MCP/A2A protocols |
| **Vector DB** | ChromaDB (built-in), FAISS/Qdrant/Pinecone (config) |
| **Serving** | vLLM, llama.cpp, TGI, Ollama |
| **Infra** | Docker, SSH (Paramiko), psutil, nvidia-ml-py |
| **Tracking** | Local + ClearML + Weights & Biases (pluggable) |
| **HPO** | Optuna-based hyperparameter sweeps |
| **Protocols** | MCP (server/client), A2A (Google Agent-to-Agent), API Gateway |
| **Guardrails** | PII detection, injection defense, toxicity filtering, JSON schema validation |
| **Evaluation** | LLM-as-Judge, A/B testing with statistical comparison |
| **Deployment** | Canary rollout, auto-rollback, A/B traffic splitting |
| **Caching** | Semantic LLM response cache with LRU eviction |
| **Cost** | Per-model token cost tracking with budget alerts |
| **Feedback** | Human-in-the-loop → DPO pair export |
| **Dataset Versioning** | Fingerprint-based version tracking with diffs and lineage |
| **Testing** | pytest (809 tests), >85% coverage |

---

## UI Pages (10 screens)

1. **Dashboard** — stat cards, GPU/CPU mini-charts, recent experiments, quick actions
2. **New Experiment** — 4-step wizard (setup → dataset → params → live progress)
3. **Experiments** — table with compare, detail view, loss charts
4. **Datasets** — drag-and-drop upload, preview with column view
5. **Workflow Builder** — visual DAG editor with 26 node types
6. **Prompt Lab** — version history, diff view, template testing
7. **Monitoring** — real-time GPU util/VRAM/temp/power + CPU/RAM charts
8. **Compute** — remote GPU targets, SSH test, hardware auto-detection
9. **Agent Chat** — interactive chat with fine-tuned agents
10. **Settings** — server info, API keys, hardware details

Plus: **Pulsar Co-pilot** (floating assistant widget on every page)

---

## Test Coverage

- **809 automated tests** covering all modules
- Training (SFT/DPO), Pipeline, Agent, Compute, UI routes, Auth, Security
- Protocols (MCP, A2A, Gateway), Tracking, HPO, Registry
- Guardrails, LLM Judge, A/B Testing, Canary, Cache, Cost, Feedback, Dataset Versioning
- CI-ready: `pytest tests/ -x -q`

---

## Deployment

### Cloud (SaaS)
Managed platform — sign up and start building immediately.
- API access to GPT-4o, Claude, Llama, Mistral and more
- Managed GPU compute with auto-scaling
- Free tier: 2 GPU-hours/month

### Self-Hosted
Turnkey deployment on your infrastructure:

```bash
# Docker (recommended)
docker compose up -d  # → http://localhost:8888

# From source
pip install -e ".[ui,dev]"
cd ui && npm install && npm run build
pulsar ui  # → http://localhost:8888
```

Environment variables:
- `PULSAR_PORT` — server port (default: 8888)
- `PULSAR_CORS_ORIGINS` — allowed origins
- `PULSAR_AUTH_ENABLED` — enable API key auth (default: false)

---

## Metrics

| Metric | Value |
|--------|-------|
| Python modules | ~65 files, ~12000 LOC |
| React components | ~45 files, ~6000 LOC |
| Test count | 809 |
| API endpoints | ~50 |
| Node types | 26 |
| Supported frameworks | 5 (Pulsar AI, LangGraph, CrewAI, AutoGen, Custom) |
| Supported protocols | 3 (MCP, A2A, API Gateway) |
| Supported model formats | 5 (GGUF, merged, LoRA, HF, custom) |
| Supported serving engines | 4 (vLLM, llama.cpp, TGI, Ollama) |
| Tracking backends | 3 (Local, ClearML, Weights & Biases) |

---

## Monetization Strategy

### Two Deployment Models

| Model | Price | Target | Features |
|-------|-------|--------|----------|
| **Cloud (SaaS)** | From $49/user/month | Startups, teams, individual devs | API access to GPT-4o/Claude/Llama/Mistral, managed GPU compute with auto-scaling, fine-tuning as a service, visual workflow builder, observability + tracing + cost tracking, team collaboration + RBAC, free tier (2 GPU-hours/month) |
| **Self-Hosted** | Custom pricing | Enterprise, regulated industries | Turnkey on-premise deployment, air-gapped / closed network support, any open-weight model locally, Docker/Kubernetes + GPU passthrough, SSO/SAML + audit log + SOC2/HIPAA, dedicated onboarding + support, SLA + custom integrations |

### Revenue Streams

**1. Cloud SaaS Subscriptions (Primary — 65% revenue)**
- Managed platform with API access to top models
- Pay per GPU-hour for fine-tuning: $0.50-$2.00/hr depending on GPU tier
- Subscription tiers starting at $49/user/month
- Zero-config deployment, auto-scaling
- Estimated: 500 teams x $500/month avg = $250K MRR

**2. Self-Hosted Enterprise Licenses (35% revenue)**
- Turnkey deployment into client's closed infrastructure
- Air-gapped network support for regulated industries
- Custom integrations (Databricks, Snowflake, internal systems)
- Dedicated support engineer + SLA
- Compliance packages (HIPAA, SOC2, FedRAMP)
- Estimated: 20 enterprises x $5K/month avg = $100K MRR

### Competitive Landscape

| Competitor | Weakness vs Pulsar AI |
|-----------|----------------------|
| **Weights & Biases** | Tracking only, no training/serving/agents |
| **Hugging Face** | No visual pipeline, no agent framework |
| **LangSmith** | Agents only, no training loop |
| **Anyscale/Ray** | Complex infra, no visual builder |
| **Modal** | Cloud-only, no self-hosted option |
| **Fine-tuning APIs** (OpenAI, Together) | Vendor lock-in, no self-hosted, limited control |

### Key Moat
**Closed-loop flywheel**: Agent runs → data generation → training → better agent.
No competitor offers this integrated cycle. Each iteration compounds the value.

### Go-to-Market

**Phase 1 (Months 1-3)**: Cloud SaaS launch + developer community
- Cloud platform with free tier (2 GPU-hours/month)
- GitHub, ProductHunt, HackerNews, Reddit /r/LocalLLaMA
- Target: 1000 GitHub stars, 50 paying cloud teams

**Phase 2 (Months 4-6)**: Self-Hosted offering
- Turnkey enterprise deployment package
- SOC2 compliance, SAML SSO
- Target: first 5 enterprise contracts

**Phase 3 (Months 7-12)**: Scale
- Cloud: 200+ paying teams
- Self-Hosted: 20 enterprise contracts
- Target: $100K MRR

---

## TAM/SAM/SOM

| Market | Size | Source |
|--------|------|--------|
| **TAM** — Global MLOps market | $23.4B by 2028 | MarketsandMarkets |
| **SAM** — LLM-specific tooling | ~$4B (17% of MLOps) | Estimated |
| **SOM** — Self-hosted LLM platforms | ~$400M (10% of SAM) | Year 1-3 addressable |

**Target**: Capture 1% SOM = $4M ARR within 2 years
