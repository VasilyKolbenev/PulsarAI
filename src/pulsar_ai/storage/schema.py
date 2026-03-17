"""SQLite schema definitions for Pulsar AI persistence layer.

Each table mirrors a JSON store entity.  JSON blobs are stored as TEXT
columns and parsed on read — this keeps the schema simple while still
giving us transactions, concurrent access, and crash recovery for free.

Schema version is tracked in ``_schema_meta`` so future migrations
can inspect the current version before applying ALTER TABLE / new tables.
"""

SCHEMA_VERSION = 3

BOOTSTRAP_SQL = """
-- ── Meta ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS _schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ── Experiments ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS experiments (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued',
    task            TEXT NOT NULL DEFAULT 'sft',
    model           TEXT DEFAULT '',
    dataset_id      TEXT DEFAULT '',
    config          TEXT DEFAULT '{}',
    created_at      TEXT NOT NULL,
    last_update_at  TEXT NOT NULL,
    completed_at    TEXT,
    final_loss      REAL,
    eval_results    TEXT,
    artifacts       TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_experiments_status
    ON experiments(status);

-- Append-only metrics history (one row per log_metrics call).
CREATE TABLE IF NOT EXISTS experiment_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id   TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    data            TEXT NOT NULL,
    recorded_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_experiment_metrics_exp
    ON experiment_metrics(experiment_id);

-- ── Prompts ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompts (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    current_version INTEGER NOT NULL DEFAULT 1,
    tags            TEXT DEFAULT '[]',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompt_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id       TEXT NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    system_prompt   TEXT NOT NULL,
    variables       TEXT DEFAULT '[]',
    model           TEXT DEFAULT '',
    parameters      TEXT DEFAULT '{}',
    metrics         TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(prompt_id, version)
);

CREATE INDEX IF NOT EXISTS idx_prompt_versions_pid
    ON prompt_versions(prompt_id);

-- ── Workflows ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workflows (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    nodes           TEXT DEFAULT '[]',
    edges           TEXT DEFAULT '[]',
    schema_version  INTEGER DEFAULT 2,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    last_run        TEXT,
    run_count       INTEGER DEFAULT 0
);

-- ── Runs (tracking.py) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    project         TEXT DEFAULT 'pulsar-ai',
    backend         TEXT DEFAULT 'local',
    status          TEXT NOT NULL,
    config          TEXT DEFAULT '{}',
    tags            TEXT DEFAULT '[]',
    metrics_history TEXT DEFAULT '[]',
    artifacts       TEXT DEFAULT '{}',
    results         TEXT DEFAULT '{}',
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    duration_s      REAL,
    environment     TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_runs_status  ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project);

-- ── API Keys ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    key_hash    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at  TEXT,
    revoked     INTEGER DEFAULT 0
);

-- ── Compute Targets ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS compute_targets (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    host            TEXT NOT NULL,
    user            TEXT NOT NULL,
    port            INTEGER DEFAULT 22,
    key_path        TEXT DEFAULT '',
    gpu_count       INTEGER DEFAULT 0,
    gpu_type        TEXT DEFAULT '',
    vram_gb         REAL DEFAULT 0,
    status          TEXT DEFAULT 'unknown',
    created_at      TEXT NOT NULL,
    last_heartbeat  TEXT
);

-- ── Jobs ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    experiment_id   TEXT,
    status          TEXT NOT NULL DEFAULT 'queued',
    job_type        TEXT NOT NULL DEFAULT 'sft',
    config          TEXT DEFAULT '{}',
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    error_message   TEXT,
    pid             INTEGER
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

-- ── Assistant Sessions ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assistant_sessions (
    id              TEXT PRIMARY KEY,
    session_type    TEXT NOT NULL DEFAULT 'assistant',
    messages        TEXT DEFAULT '[]',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    ttl_hours       INTEGER DEFAULT 24
);

-- ── Users ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    name            TEXT DEFAULT '',
    role            TEXT NOT NULL DEFAULT 'user',
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL,
    last_login_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ── API Key Events (audit trail) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS api_key_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id      TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    ip_address  TEXT DEFAULT ''
);
"""
