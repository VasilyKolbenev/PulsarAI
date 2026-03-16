"""Migrate legacy JSON stores into SQLite.

Reads existing JSON files produced by ``ExperimentStore``,
``PromptStore``, ``WorkflowStore``, and ``RunTracker`` and inserts them
into the SQLite database.  The migration is **idempotent**: rows that
already exist (by primary key) are silently skipped via INSERT OR IGNORE.

Usage::

    from pulsar_ai.storage.database import Database
    from pulsar_ai.storage.migration import migrate_all

    db = Database()
    report = migrate_all(db)
    # report == {"experiments": 42, "prompts": 5, "workflows": 3, "runs": 18}
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pulsar_ai.storage.database import Database

logger = logging.getLogger(__name__)


def migrate_experiments(db: Database, json_path: Path) -> int:
    """Migrate experiments from a JSON array file.

    Args:
        db: Database instance.
        json_path: Path to ``experiments.json``.

    Returns:
        Number of migrated rows.
    """
    if not json_path.exists():
        logger.info("No experiments JSON at %s, skipping", json_path)
        return 0

    with open(json_path, encoding="utf-8") as f:
        experiments: list[dict[str, Any]] = json.load(f)

    migrated = 0
    with db.transaction() as conn:
        for exp in experiments:
            # Experiment row
            conn.execute(
                """
                INSERT OR IGNORE INTO experiments
                    (id, name, status, task, model, dataset_id, config,
                     created_at, last_update_at, completed_at, final_loss,
                     eval_results, artifacts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    exp["id"],
                    exp.get("name", ""),
                    exp.get("status", "queued"),
                    exp.get("task", "sft"),
                    exp.get("model", ""),
                    exp.get("dataset_id", ""),
                    json.dumps(exp.get("config", {}), ensure_ascii=False),
                    exp.get("created_at", datetime.now().isoformat()),
                    exp.get("last_update_at", datetime.now().isoformat()),
                    exp.get("completed_at"),
                    exp.get("final_loss"),
                    (
                        json.dumps(exp.get("eval_results"))
                        if exp.get("eval_results") is not None
                        else None
                    ),
                    json.dumps(exp.get("artifacts", {}), ensure_ascii=False),
                ),
            )

            # Metrics history rows
            history = exp.get("training_history", [])
            for entry in history:
                recorded_at = (
                    entry.get("time")
                    if isinstance(entry.get("time"), str)
                    else datetime.now().isoformat()
                )
                conn.execute(
                    """
                    INSERT INTO experiment_metrics
                        (experiment_id, data, recorded_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        exp["id"],
                        json.dumps(entry, ensure_ascii=False),
                        recorded_at,
                    ),
                )

            migrated += 1

    logger.info("Migrated %d experiments from %s", migrated, json_path)
    return migrated


def migrate_prompts(db: Database, json_path: Path) -> int:
    """Migrate prompts and their versions from a JSON array file.

    Args:
        db: Database instance.
        json_path: Path to ``prompts.json``.

    Returns:
        Number of migrated prompts.
    """
    if not json_path.exists():
        logger.info("No prompts JSON at %s, skipping", json_path)
        return 0

    with open(json_path, encoding="utf-8") as f:
        prompts: list[dict[str, Any]] = json.load(f)

    migrated = 0
    with db.transaction() as conn:
        for p in prompts:
            conn.execute(
                """
                INSERT OR IGNORE INTO prompts
                    (id, name, description, current_version, tags,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    p["id"],
                    p.get("name", ""),
                    p.get("description", ""),
                    p.get("current_version", 1),
                    json.dumps(p.get("tags", []), ensure_ascii=False),
                    p.get("created_at", datetime.now().isoformat()),
                    p.get("updated_at", datetime.now().isoformat()),
                ),
            )

            for v in p.get("versions", []):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO prompt_versions
                        (prompt_id, version, system_prompt, variables,
                         model, parameters, metrics, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p["id"],
                        v.get("version", 1),
                        v.get("system_prompt", ""),
                        json.dumps(v.get("variables", []), ensure_ascii=False),
                        v.get("model", ""),
                        json.dumps(v.get("parameters", {}), ensure_ascii=False),
                        json.dumps(v.get("metrics")) if v.get("metrics") is not None else None,
                        v.get("created_at", datetime.now().isoformat()),
                    ),
                )

            migrated += 1

    logger.info("Migrated %d prompts from %s", migrated, json_path)
    return migrated


def migrate_workflows(db: Database, json_path: Path) -> int:
    """Migrate workflows from a JSON array file.

    Args:
        db: Database instance.
        json_path: Path to ``workflows.json``.

    Returns:
        Number of migrated workflows.
    """
    if not json_path.exists():
        logger.info("No workflows JSON at %s, skipping", json_path)
        return 0

    with open(json_path, encoding="utf-8") as f:
        workflows: list[dict[str, Any]] = json.load(f)

    migrated = 0
    with db.transaction() as conn:
        for wf in workflows:
            conn.execute(
                """
                INSERT OR IGNORE INTO workflows
                    (id, name, nodes, edges, schema_version,
                     created_at, updated_at, last_run, run_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wf["id"],
                    wf.get("name", ""),
                    json.dumps(wf.get("nodes", []), ensure_ascii=False),
                    json.dumps(wf.get("edges", []), ensure_ascii=False),
                    wf.get("schema_version", 1),
                    wf.get("created_at", datetime.now().isoformat()),
                    wf.get("updated_at", datetime.now().isoformat()),
                    wf.get("last_run"),
                    wf.get("run_count", 0),
                ),
            )
            migrated += 1

    logger.info("Migrated %d workflows from %s", migrated, json_path)
    return migrated


def migrate_runs(db: Database, runs_dir: Path) -> int:
    """Migrate per-file run JSONs from the runs directory.

    Args:
        db: Database instance.
        runs_dir: Path to ``data/runs/`` directory with one JSON per run.

    Returns:
        Number of migrated runs.
    """
    if not runs_dir.exists():
        logger.info("No runs directory at %s, skipping", runs_dir)
        return 0

    migrated = 0
    with db.transaction() as conn:
        for run_file in runs_dir.glob("*.json"):
            try:
                with open(run_file, encoding="utf-8") as f:
                    run = json.load(f)
            except (json.JSONDecodeError, KeyError):
                logger.warning("Skipping malformed run file %s", run_file)
                continue

            conn.execute(
                """
                INSERT OR IGNORE INTO runs
                    (run_id, name, project, backend, status, config,
                     tags, metrics_history, artifacts, results,
                     started_at, finished_at, duration_s, environment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.get("run_id", run_file.stem),
                    run.get("name", ""),
                    run.get("project", "pulsar-ai"),
                    run.get("backend", "local"),
                    run.get("status", "unknown"),
                    json.dumps(run.get("config", {}), ensure_ascii=False),
                    json.dumps(run.get("tags", []), ensure_ascii=False),
                    json.dumps(run.get("metrics_history", []), ensure_ascii=False),
                    json.dumps(run.get("artifacts", {}), ensure_ascii=False),
                    json.dumps(run.get("results", {}), ensure_ascii=False),
                    run.get("started_at", datetime.now().isoformat()),
                    run.get("finished_at"),
                    run.get("duration_s"),
                    json.dumps(run.get("environment", {}), ensure_ascii=False),
                ),
            )
            migrated += 1

    logger.info("Migrated %d runs from %s", migrated, runs_dir)
    return migrated


def migrate_all(
    db: Database,
    data_dir: Path | None = None,
) -> dict[str, int]:
    """Run all JSON-to-SQLite migrations.

    Args:
        db: Database instance (schema must already be bootstrapped).
        data_dir: Root data directory containing JSON files.
            Defaults to ``./data``.

    Returns:
        Dict mapping entity name to number of migrated records.
    """
    data = data_dir or Path("./data")

    report = {
        "experiments": migrate_experiments(db, data / "experiments.json"),
        "prompts": migrate_prompts(db, data / "prompts.json"),
        "workflows": migrate_workflows(db, data / "workflows.json"),
        "runs": migrate_runs(db, data / "runs"),
    }

    total = sum(report.values())
    logger.info(
        "Migration complete: %d total records (%s)",
        total,
        ", ".join(f"{k}={v}" for k, v in report.items()),
    )
    return report
