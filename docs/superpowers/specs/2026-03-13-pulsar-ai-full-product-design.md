# Pulsar AI — Full Product Design Spec

> Rebrand pulsar-ai to **Pulsar AI** and bring the platform from demo-ready to production-capable in 1-2 weeks, positioning it as **OpenJarvis + ClearML** — the closed-loop LLM platform.

## Context

pulsar-ai is a self-hosted MLOps platform for the full LLM lifecycle: data → training (SFT/DPO) → evaluation → export → serving → agent → data collection → retrain. It already has ~90 Python modules, 10 React pages, 26 workflow node types, MCP/A2A protocol support, and a ReAct agent framework.

**Current state**: strong demo base, but several subsystems use JSON file storage, runtime state is in-memory only, security has demo shortcuts, and the frontend needs polish.

**Target state**: production-capable platform under the Pulsar AI brand that an investor can demo live without fear of crashes, with professional visual quality and real depth behind the surface.

## Approach

Four parallel workstreams, each independently deliverable:

| Stream | Duration | Focus |
|--------|----------|-------|
| **Brand** | 2-3 days | Rename to Pulsar AI, landing page, README, positioning |
| **Core** | 5-7 days | SQLite migration, durable jobs, unified pipeline, security |
| **UI** | 3-5 days | Design system, page decomposition, lazy loading, UX |
| **Quality** | 2-3 days | Test stability, Docker, CI pipeline |

---

## Stream 1: Brand (2-3 days)

### 1.1 Rename pulsar-ai → Pulsar AI

**Python package**: `pulsar_ai` → `pulsar_ai`

Files to update:
- `pyproject.toml` — name, packages, entry points (`pulsar` → `pulsar`)
- All imports across `src/pulsar_ai/` → `src/pulsar_ai/`
- `src/pulsar_ai/` directory → `src/pulsar_ai/`
- `ui/package.json` — name field
- `Dockerfile`, `docker-compose.yml` — paths and labels
- `README.md`, `AGENTS.md`, `PRESENTATION.md` — all references
- `docs/` — all documentation
- `configs/` — any references to "forge" or "pulsar-ai"
- `.gitignore`, `Makefile` (if created)
- Test files — imports and fixtures

CLI commands change:
```
pulsar train <config>
pulsar eval --model <path>
pulsar export --model <path>
pulsar serve --model <path>
pulsar ui
```

Environment variables to rename:
- `PULSAR_ENV_FILE` → `PULSAR_ENV_FILE`
- `PULSAR_STAND_MODE` → `PULSAR_STAND_MODE`
- `PULSAR_CORS_ORIGINS` → `PULSAR_CORS_ORIGINS`
- `PULSAR_AUTH_ENABLED` → `PULSAR_AUTH_ENABLED`
- `PULSAR_STALE_RUNNING_MINUTES` → `PULSAR_STALE_RUNNING_MINUTES`
- `PULSAR_PORT` → `PULSAR_PORT`

**Deprecation mechanism**: Add a `get_env(name)` helper in a new `pulsar_ai/env.py` module that checks `PULSAR_{name}` first, falls back to `PULSAR_{name}` with a one-time deprecation warning via `warnings.warn()`. All modules use this helper instead of raw `os.getenv()`.

**Additional files needing env var updates** (beyond main source):
- `scripts/run_ui_server.py` — sets `os.environ["PULSAR_*"]` directly, CLI help strings reference old names
- `scripts/start_prod_ready_dev.ps1`, `scripts/start_investor_demo.ps1` — PowerShell env var setup
- `routes/settings.py` — reads PULSAR_* vars for settings display
- `tests/test_security.py` — references `PULSAR_CORS_ORIGINS` in assertions

Also update:
- API key prefix: `forge_` → `pulsar_` in `auth.py` key generation
- Site chat system prompt in `routes/site_chat.py` (references "Pulsar AI" and "MIT license")
- Dockerfile comment: "JSON stores" → "SQLite database"

### 1.2 Landing Page

New route `/` for unauthenticated users (the app dashboard moves to `/dashboard`).

**Content structure:**
1. **Hero section**: "Pulsar AI — The Closed-Loop LLM Platform"
   - Tagline: "From raw data to deployed agent. One platform, zero fragmentation."
   - Animated diagram: the training flywheel (data → train → deploy → agent → collect → retrain)
   - CTA: "Get Started" → `/dashboard`

2. **Five pillars** (our answer to OpenJarvis's 5 primitives):
   - **Train** — SFT + DPO + LoRA/QLoRA with hardware auto-detection
   - **Orchestrate** — Visual DAG builder with 26 node types
   - **Deploy** — One-click export to GGUF/vLLM/Ollama
   - **Monitor** — Real-time GPU/CPU, experiment tracking, cost tracking
   - **Evolve** — Agent traces → training data → better models (closed loop)

3. **Comparison table**: Pulsar AI vs OpenJarvis vs ClearML vs W&B vs LangSmith

4. **Architecture diagram** (simplified from PRESENTATION.md)

5. **Quick start**: `docker compose up` → `http://localhost:8888`

6. **Footer**: GitHub link, docs link, license (Apache 2.0)

### 1.3 README.md

Complete rewrite:
- New name, logo placeholder, badges
- One-paragraph pitch: "Pulsar AI is the open-source platform that closes the loop between LLM training and deployment..."
- Feature matrix (from PRESENTATION.md, updated)
- Quick start (Docker + pip)
- Architecture diagram
- Comparison with competitors
- Contributing section
- License: Apache 2.0 (aligning with OpenJarvis)

### 1.4 License

Switch from MIT to Apache 2.0 for:
- Patent protection (important for investors)
- Parity with OpenJarvis
- Enterprise-friendliness

---

## Stream 2: Core — Backend Production-Readiness (5-7 days)

### 2.1 Complete SQLite Migration

**What already exists:**
- `storage/schema.py` defines SQLite tables for experiments, experiment_metrics, prompts, prompt_versions, workflows, and runs
- `storage/migration.py` has `migrate_all()` with functions for experiments, prompts, workflows, and runs
- `ExperimentStore` is the **only store class** rewritten to use `Database` directly

**What needs to be done:** Rewrite 4 remaining store classes to use `Database` (following the ExperimentStore pattern). Schema and migrations are already in place for workflows and prompts.

**Important:** Before running any migration, back up `./data/` → `./data.bak/`.

| Store | Schema exists? | Migration exists? | Store class rewrite needed? |
|-------|---------------|-------------------|---------------------------|
| WorkflowStore | Yes (workflows table) | Yes | **Yes** — replace `_load()/_save()` JSON pattern |
| PromptStore | Yes (prompts + prompt_versions) | Yes | **Yes** — replace JSON pattern |
| ApiKeyStore | **No** | **No** | **Yes** — new table + migration + class rewrite |
| ComputeManager | **No** | **No** | **Yes** — new table + migration + class rewrite |

#### WorkflowStore (`ui/workflow_store.py` — current path, pre-rename)
- Rewrite class to use `Database.execute()` / `Database.fetch_all()` instead of JSON `_load()/_save()`
- Existing schema has: id, name, nodes, edges, schema_version, created_at, updated_at, last_run, run_count
- No viewport column needed (React Flow manages viewport state client-side)

#### PromptStore (`prompts/store.py` — current path, pre-rename)
- Rewrite class to use Database
- Schema already defines prompts + prompt_versions tables with all needed columns

#### ApiKeyStore (`ui/auth.py` — current path, pre-rename)
- **New work**: Add `api_keys` table to `BOOTSTRAP_SQL` in `schema.py`
- **New work**: Add `migrate_api_keys()` function to `migration.py`
- Table: id, name, key_hash, created_at, last_used_at, revoked_at, revoked
- Rewrite store class

#### ComputeManager (`compute/manager.py` — current path, pre-rename)
- **New work**: Add `compute_targets` table to `BOOTSTRAP_SQL` in `schema.py`
- **New work**: Add `migrate_compute_targets()` function to `migration.py`
- Table: id, name, host, user, key_path, gpu_count, gpu_type, vram_gb, created_at, last_heartbeat
- Rewrite store class

**Estimated effort**: 2-3 days (not 5, since schema/migration groundwork is done for 2 of 4 stores).

### 2.2 Durable Jobs and Sessions

#### Job Registry
- Current: `jobs.py` uses in-memory `_jobs: dict` with `_JOB_TTL_SECONDS = 3600` (1 hour)
- Target: SQLite table `jobs`: id, experiment_id, status, job_type, config (JSON), started_at, completed_at, error_message, pid
- **New work**: Add `jobs` table to `BOOTSTRAP_SQL` in `schema.py`
- On startup: reconcile stale `running` jobs (age > 90 min) → `failed` with reason "process restart"
- TTL cleanup: keep existing 1-hour TTL for in-memory cleanup; SQLite records retained for 7 days for audit

#### Assistant Sessions
- Current: `assistant.py` uses in-memory `_sessions: dict`
- Target: SQLite table `assistant_sessions`: id, session_type, messages (JSON), created_at, updated_at, ttl_hours
- **New work**: Add `assistant_sessions` table to `BOOTSTRAP_SQL` in `schema.py`
- Cleanup: sessions older than `ttl_hours` (default 24) removed on startup

#### Site Chat Sessions
- Current: in-memory in `routes/site_chat.py`
- Target: same `assistant_sessions` table with `session_type = 'site_chat'`

### 2.3 Unified Pipeline Execution

- `pipeline_run.py` WebSocket handler (lines 73-148) manually loops through steps, resolves conditions, dispatches, and tracks — duplicating what `PipelineExecutor.run()` (executor.py lines 36-95) already does
- Refactor to use `PipelineExecutor` as the single execution engine
- **Callback design**: Add `on_step_update: Callable[[str, str, dict], None]` parameter to `PipelineExecutor.__init__()`. The WS handler passes an async bridge: `lambda step_id, status, data: asyncio.run_coroutine_threadsafe(ws.send_json(...), loop)`
- WebSocket handler becomes a thin transport layer:
  1. Receives `run` command via WS
  2. Creates PipelineExecutor with the callback
  3. Runs executor in a thread pool (`asyncio.to_thread`) since executor is synchronous
  4. All step logic, status tracking, error handling in executor
- Also move `_recent_runs` in-memory dict to SQLite `runs` table (already defined in schema)
- The sync endpoint (`/api/v1/pipeline/run/sync`) also calls `PipelineExecutor.run()` — it simply passes `on_step_update=None` (no callback needed for sync)
- Benefits: consistent behavior, single place to add features (parallel execution, retry)

### 2.4 Security Hardening

1. **Remove API key from URL**: The `?api_key=xxx` bootstrap pattern exists in the frontend JS (client.ts reads from URL params and stores in localStorage). The Python backend auth middleware only checks `Authorization: Bearer` headers. Fix is frontend-side: remove URL param reading from `client.ts`, add a proper login page/modal instead
2. **No plaintext key logging**: Hash or mask keys in all log output
3. **Auth cookie**: Set `HttpOnly` + `Secure` + `SameSite=Strict` cookie for session
4. **Audit trail**: `api_key_events` table: id, key_id, event_type (created/used/revoked), timestamp, ip_address
5. **Demo mode**: Explicit `PULSAR_DEMO_MODE=true` env var that relaxes auth for demos

### 2.5 Remote Compute Hardening

1. **Safe command builder**: Use `shlex.quote()` for all shell arguments
2. **Bootstrap script**: Upload a known-good script via SFTP, execute it remotely
3. **Exit code capture**: Capture and store exit code, stderr, timeout flag for every remote command
4. **Retry policy**: Retry SSH connection failures (max 3 attempts, exponential backoff)
5. **Heartbeat**: Periodic SSH keepalive check, mark targets as `unreachable` if failed

---

## Stream 3: UI Polish (3-5 days)

### 3.1 Pulsar Design System

**Color palette** (dark-first):
- Background: `#0a0a0f` (near-black) → `#13131a` (cards) → `#1a1a24` (elevated)
- Text: `#e4e4e7` (primary) → `#a1a1aa` (muted)
- Accent: `#6366f1` (indigo-500) → `#8b5cf6` (violet-500) gradient
- Success: `#22c55e`, Warning: `#f59e0b`, Error: `#ef4444`
- Border: `#27272a` (subtle)

**Typography**:
- Body: Inter (already used, just enforce)
- Code/mono: JetBrains Mono
- Scale: text-xs(12), text-sm(14), text-base(16), text-lg(18), text-xl(20), text-2xl(24)

**Shared components** (extend existing `ui/` folder):
- `Card` with consistent padding, border, hover state
- `Badge` for status (running/completed/failed/queued)
- `MetricCard` for dashboard stats
- `StatusDot` animated indicator
- `EmptyState` with icon + message + CTA
- `Toast` notification system (replace silent catches)

### 3.2 Page Decomposition

**Experiments.tsx** (currently monolithic):
- → `ExperimentList` — table with filters, sort, search
- → `ExperimentDetail` — single experiment view with metrics
- → `ExperimentCompare` — side-by-side comparison
- → `MetricsPanel` — reusable loss/accuracy charts

**PromptLab.tsx** (currently monolithic):
- → `PromptList` — sidebar with prompt library
- → `PromptEditor` — main editing area
- → `PromptDiff` — version comparison
- → `PromptTestPanel` — template rendering test

**WorkflowBuilder.tsx** — already well decomposed (FlowCanvas, NodePalette, PropertiesPanel, 26 node components). No changes needed.

### 3.3 Lazy Loading

```tsx
// App.tsx — lazy load heavy pages
const WorkflowBuilder = lazy(() => import('./pages/WorkflowBuilder'))
const PromptLab = lazy(() => import('./pages/PromptLab'))
const Monitoring = lazy(() => import('./pages/Monitoring'))
```

This reduces initial bundle by ~40% (React Flow and Recharts are heavy).

### 3.4 UX Improvements

1. **Error handling**: Replace all `.catch(() => {})` with toast notifications
2. **Empty states**: Every page gets a helpful empty state with CTA
3. **Breadcrumbs**: Dashboard > Experiments > experiment-name
4. **Loading skeletons**: Replace spinners with content-shaped skeletons
5. **Keyboard shortcuts**: Ctrl+K for command palette (search experiments, workflows, prompts)

### 3.5 Dashboard Upgrade

Current dashboard has basic stats. Upgrade to:
- **Hero metrics**: Models trained, Experiments run, GPU hours used, Active agents
- **Quick actions**: "New Training", "New Workflow", "Open Agent Chat"
- **Recent activity feed**: Last 10 actions across all subsystems
- **System status**: GPU/CPU mini-charts (already exist), disk usage, active jobs

---

## Stream 4: Quality (2-3 days)

### 4.1 Test Stabilization

1. **Windows temp fix**: Configure `tmp_path_retention_policy = "none"` in `pyproject.toml`
2. **Test isolation**: Each test gets its own SQLite database via fixture
3. **Markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`
4. **Coverage target**: Maintain >80% on new code

### 4.2 Docker Production Config

**Note**: `docker-compose.yml` already exists but uses old `pulsar` naming (service name, volume, env vars). Rewrite with Pulsar naming.

```yaml
# docker-compose.yml (NEW FILE)
services:
  pulsar:
    build: .
    ports:
      - "8888:8888"
    volumes:
      - pulsar-data:/app/data  # Persist SQLite DB
    environment:
      - PULSAR_AUTH_ENABLED=true
      - PULSAR_CORS_ORIGINS=http://localhost:8888
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

volumes:
  pulsar-data:
```

### 4.3 CI Pipeline (GitHub Actions)

```yaml
# .github/workflows/ci.yml
jobs:
  backend:
    steps:
      - ruff check src/ tests/
      - mypy src/pulsar_ai/
      - pytest tests/ -x --cov=pulsar_ai --cov-report=xml
  frontend:
    steps:
      - npm ci
      - npm run lint
      - npm run build
  docker:
    steps:
      - docker build -t pulsar-ai .
```

### 4.4 Developer Experience

- `Makefile` (NEW FILE): dev, test, lint, build, docker, clean
- `.env.example` (NEW FILE): All `PULSAR_*` variables documented
- `CONTRIBUTING.md` (NEW FILE): Setup guide, coding standards, PR process
- Add `ruff` to dev dependencies in `pyproject.toml` (CI runs `ruff check` but it's not in deps)

---

## Execution Order

Within each stream, tasks are ordered by dependency:

**Stream 1 (Brand)**: 1.1 rename → 1.2 landing → 1.3 README → 1.4 license
**Stream 2 (Core)**: 2.1 SQLite → 2.2 durable jobs → 2.3 unified pipeline → 2.4 security → 2.5 remote
**Stream 3 (UI)**: 3.1 design system → 3.2 decomposition → 3.3 lazy loading → 3.4 UX → 3.5 dashboard
**Stream 4 (Quality)**: 4.1 tests → 4.2 Docker → 4.3 CI → 4.4 DX

**Cross-stream dependencies**:
- Stream 1 (rename) should complete before Stream 3 (UI) starts the landing page
- Stream 2 (SQLite) should complete before Stream 4 (tests) for proper test isolation fixtures
- Stream 3 (design system) should be done early so other UI work follows it

**Recommended start order**:
1. Day 1-2: Stream 1 (rename) + Stream 2.1 (SQLite migration) in parallel
2. Day 3-5: Stream 2.2-2.5 (backend) + Stream 3.1-3.2 (design system + decomposition)
3. Day 6-8: Stream 3.3-3.5 (UX polish) + Stream 4 (quality)
4. Day 9-10: Integration, final testing, landing page content polish

## Success Criteria

- [ ] All references to "pulsar-ai" replaced with "pulsar-ai" / "Pulsar AI"
- [ ] CLI commands work as `pulsar train/eval/export/serve/ui`
- [ ] Landing page renders at `/` with five pillars and comparison table
- [ ] All stores (workflows, prompts, API keys, compute targets) use SQLite
- [ ] Jobs and sessions survive process restart
- [ ] WebSocket pipeline execution uses PipelineExecutor
- [ ] No API keys in URL query strings or plaintext logs
- [ ] Design system applied: dark theme, consistent cards, badges, empty states
- [ ] Experiments and PromptLab pages decomposed into smaller components
- [ ] Heavy pages lazy-loaded (WorkflowBuilder, PromptLab, Monitoring)
- [ ] Silent `.catch(() => {})` replaced with toast notifications
- [ ] `pytest tests/` passes on Windows without PermissionError
- [ ] `docker compose up` starts the full platform successfully
- [ ] GitHub Actions CI runs backend + frontend checks
- [ ] README reflects Pulsar AI positioning vs OpenJarvis + ClearML

## Known Gaps Between PRESENTATION.md and Reality

These gaps exist but are **out of scope** for this 2-week sprint. They should be documented honestly for investors (show awareness, not deception):

| Claim | Reality | Action |
|-------|---------|--------|
| "LangGraph/CrewAI/AutoGen selector" | Only ReAct agent implemented | Remove from claims or mark as roadmap |
| "OpenTelemetry-style tracing" | Minimal observability module | Mark as roadmap |
| "809 automated tests" | ~48 test files exist, actual assertion count unverified | Verify and update metric |
| "Statistical winner detection" in A/B | Basic min/max/mean, no significance tests | Acknowledge as MVP |
| "RAG Pipeline" with vector stores | Config support exists, integration depth unverified | Verify before claiming |

**Recommendation for investor pitch**: Position these as "roadmap" items, not current features. Investors respect honesty about maturity levels more than inflated claims.

## Out of Scope

- Cloud SaaS deployment (future phase)
- True pipeline parallelism with asyncio.gather (future)
- RBAC / team features (future)
- Mobile-responsive UI (desktop-first for investor demo)
- Kubernetes deployment (Docker only for now)
