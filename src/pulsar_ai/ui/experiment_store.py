"""SQLite-backed experiment tracker for Web UI.

Replaces the legacy JSON load-mutate-save pattern with direct SQL
operations.  All public method signatures and return types are preserved
for backward compatibility with routes and CLI.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pulsar_ai.storage.database import Database, get_database
from pulsar_ai.storage.migration import migrate_experiments

logger = logging.getLogger(__name__)

DEFAULT_JSON_PATH = Path("./data/experiments.json")
try:
    DEFAULT_STALE_RUNNING_MINUTES = int(os.environ.get("PULSAR_STALE_RUNNING_MINUTES", "90"))
except ValueError:
    DEFAULT_STALE_RUNNING_MINUTES = 90


class ExperimentStore:
    """CRUD operations on experiments backed by SQLite.

    Provides the same public API as the legacy JSON store so that routes,
    CLI, and UI integrations require no changes.

    Args:
        db: Database instance.  Uses the module singleton when *None*.
    """

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()
        # Auto-migrate only when using the default singleton (production).
        # Explicit db= means the caller controls the lifecycle (e.g. tests).
        if db is None:
            self._auto_migrate_json()

    # ── Public API (signatures unchanged) ────────────────────────────

    def create(self, name: str, config: dict, task: str = "sft") -> str:
        """Create a new experiment entry.

        Args:
            name: Experiment name.
            config: Full training config dict.
            task: Training task type.

        Returns:
            Experiment ID.
        """
        exp_id = str(uuid.uuid4())[:8]
        now_iso = datetime.now().isoformat()
        model = (
            config.get("model", {}).get("name", "unknown")
            if isinstance(config.get("model"), dict)
            else config.get("model", "unknown")
        )
        dataset_id = config.get("_dataset_id", "")

        self._db.execute(
            """
            INSERT INTO experiments
                (id, name, status, task, model, dataset_id, config,
                 created_at, last_update_at, completed_at, final_loss,
                 eval_results, artifacts)
            VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, '{}')
            """,
            (
                exp_id,
                name,
                task,
                model,
                dataset_id,
                json.dumps(config, ensure_ascii=False, default=str),
                now_iso,
                now_iso,
            ),
        )
        self._db.commit()
        logger.info("Created experiment %s: %s", exp_id, name)
        return exp_id

    def update_status(self, exp_id: str, status: str) -> None:
        """Update experiment status.

        Args:
            exp_id: Experiment ID.
            status: New status (queued/running/completed/failed).
        """
        now_iso = datetime.now().isoformat()
        completed_at = now_iso if status in {"completed", "failed"} else None

        if completed_at:
            self._db.execute(
                """
                UPDATE experiments
                SET status = ?, last_update_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, now_iso, completed_at, exp_id),
            )
        else:
            self._db.execute(
                """
                UPDATE experiments
                SET status = ?, last_update_at = ?
                WHERE id = ?
                """,
                (status, now_iso, exp_id),
            )
        self._db.commit()

    def add_metrics(self, exp_id: str, metrics: dict) -> None:
        """Append training metrics to history.

        This is now an INSERT (append-only) instead of the old
        load-all → mutate → save-all pattern.

        Args:
            exp_id: Experiment ID.
            metrics: Dict with step, loss, epoch, etc.
        """
        recorded_at = (
            metrics.get("time")
            if isinstance(metrics.get("time"), str)
            else datetime.now().isoformat()
        )

        # Append metric row.
        self._db.execute(
            """
            INSERT INTO experiment_metrics (experiment_id, data, recorded_at)
            VALUES (?, ?, ?)
            """,
            (exp_id, json.dumps(metrics, ensure_ascii=False, default=str), recorded_at),
        )

        # Update denormalized fields on the experiment row.
        final_loss = metrics.get("loss") if metrics.get("loss") is not None else None
        if final_loss is not None:
            self._db.execute(
                """
                UPDATE experiments
                SET final_loss = ?, last_update_at = ?
                WHERE id = ?
                """,
                (final_loss, recorded_at, exp_id),
            )
        else:
            self._db.execute(
                """
                UPDATE experiments SET last_update_at = ? WHERE id = ?
                """,
                (recorded_at, exp_id),
            )
        self._db.commit()

    def set_artifacts(self, exp_id: str, artifacts: dict) -> None:
        """Store artifact paths for an experiment.

        Args:
            exp_id: Experiment ID.
            artifacts: Dict of artifact paths (adapter_dir, output_dir, etc.).
        """
        now_iso = datetime.now().isoformat()
        self._db.execute(
            "UPDATE experiments SET artifacts = ?, last_update_at = ? WHERE id = ?",
            (json.dumps(artifacts, ensure_ascii=False, default=str), now_iso, exp_id),
        )
        self._db.commit()

    def set_eval_results(self, exp_id: str, results: dict) -> None:
        """Store evaluation results.

        Args:
            exp_id: Experiment ID.
            results: Eval results dict.
        """
        now_iso = datetime.now().isoformat()
        self._db.execute(
            "UPDATE experiments SET eval_results = ?, last_update_at = ? WHERE id = ?",
            (json.dumps(results, ensure_ascii=False, default=str), now_iso, exp_id),
        )
        self._db.commit()

    def reconcile_stale_running(self, stale_after_minutes: int | None = None) -> int:
        """Mark stale running experiments as failed.

        Args:
            stale_after_minutes: Override threshold; defaults to env setting.

        Returns:
            Number of reconciled experiments.
        """
        threshold_min = (
            DEFAULT_STALE_RUNNING_MINUTES if stale_after_minutes is None else stale_after_minutes
        )
        if threshold_min <= 0:
            return 0

        now = datetime.now()
        cutoff = (now - timedelta(minutes=threshold_min)).isoformat()
        now_iso = now.isoformat()
        error_msg = (
            "Marked failed automatically: no progress updates "
            f"for more than {threshold_min} minutes"
        )

        # Fetch stale running experiments.
        stale = self._db.fetch_all(
            """
            SELECT id, artifacts FROM experiments
            WHERE status = 'running' AND last_update_at < ?
            """,
            (cutoff,),
        )

        if not stale:
            return 0

        for row in stale:
            artifacts = json.loads(row["artifacts"] or "{}")
            if "error" not in artifacts:
                artifacts["error"] = error_msg

            self._db.execute(
                """
                UPDATE experiments
                SET status = 'failed', completed_at = ?, last_update_at = ?,
                    artifacts = ?
                WHERE id = ?
                """,
                (
                    now_iso,
                    now_iso,
                    json.dumps(artifacts, ensure_ascii=False),
                    row["id"],
                ),
            )

        self._db.commit()
        logger.warning("Reconciled %d stale running experiments", len(stale))
        return len(stale)

    def get(self, exp_id: str) -> dict | None:
        """Get a single experiment by ID.

        Args:
            exp_id: Experiment ID.

        Returns:
            Experiment dict or None.
        """
        row = self._db.fetch_one("SELECT * FROM experiments WHERE id = ?", (exp_id,))
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_all(self, status: str | None = None) -> list[dict]:
        """List all experiments, optionally filtered by status.

        Args:
            status: Optional status filter.

        Returns:
            List of experiment dicts (newest first).
        """
        self.reconcile_stale_running()

        if status:
            rows = self._db.fetch_all(
                """
                SELECT * FROM experiments
                WHERE status = ?
                ORDER BY created_at DESC
                """,
                (status,),
            )
        else:
            rows = self._db.fetch_all("SELECT * FROM experiments ORDER BY created_at DESC")

        return [self._row_to_dict(r) for r in rows]

    def delete(self, exp_id: str) -> bool:
        """Delete an experiment.

        Metrics are cascade-deleted via FK constraint.

        Args:
            exp_id: Experiment ID.

        Returns:
            True if deleted, False if not found.
        """
        cursor = self._db.execute("DELETE FROM experiments WHERE id = ?", (exp_id,))
        self._db.commit()
        return cursor.rowcount > 0

    def migrate_from_json(self, json_path: Path | None = None) -> int:
        """One-time migration from a legacy JSON store file.

        Args:
            json_path: Path to ``experiments.json``.  Defaults to
                ``./data/experiments.json``.

        Returns:
            Number of migrated experiments.
        """
        path = json_path or DEFAULT_JSON_PATH
        return migrate_experiments(self._db, path)

    # ── Internals ────────────────────────────────────────────────────

    def _row_to_dict(self, row: dict) -> dict:
        """Convert a SQLite row + its metrics into the legacy dict format."""
        metrics_rows = self._db.fetch_all(
            """
            SELECT data FROM experiment_metrics
            WHERE experiment_id = ?
            ORDER BY id
            """,
            (row["id"],),
        )
        training_history = [json.loads(m["data"]) for m in metrics_rows]

        return {
            "id": row["id"],
            "name": row["name"],
            "status": row["status"],
            "task": row["task"],
            "model": row["model"] or "",
            "dataset_id": row["dataset_id"] or "",
            "config": json.loads(row["config"] or "{}"),
            "created_at": row["created_at"],
            "last_update_at": row["last_update_at"],
            "completed_at": row["completed_at"],
            "final_loss": row["final_loss"],
            "training_history": training_history,
            "eval_results": json.loads(row["eval_results"]) if row["eval_results"] else None,
            "artifacts": json.loads(row["artifacts"] or "{}"),
        }

    def _auto_migrate_json(self) -> None:
        """Auto-migrate from JSON if the SQLite table is empty and JSON exists."""
        count_row = self._db.fetch_one("SELECT COUNT(*) as cnt FROM experiments")
        if count_row and count_row["cnt"] > 0:
            return

        json_path = DEFAULT_JSON_PATH
        if not json_path.exists():
            return

        count = migrate_experiments(self._db, json_path)
        if count > 0:
            logger.info("Auto-migrated %d experiments from %s", count, json_path)

    # ── Legacy compat ────────────────────────────────────────────────
    # These static helpers are kept for any code that imported them.

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        """Parse an ISO datetime string, handling timezone normalization."""
        if not isinstance(value, str) or not value:
            return None
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
