"""Durable job registry backed by SQLite.

Tracks long-running training, evaluation, and pipeline jobs with
persistent status, so jobs survive process restarts and can be
monitored from the UI.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from pulsar_ai.storage.database import Database, get_database

logger = logging.getLogger(__name__)

VALID_STATUSES = {"queued", "running", "completed", "failed", "cancelled"}


class JobRegistry:
    """CRUD for durable job tracking backed by SQLite.

    Args:
        db: Database instance.  Uses the module singleton when *None*.
    """

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()

    def create(
        self,
        job_type: str,
        config: dict[str, Any] | None = None,
        experiment_id: str | None = None,
    ) -> dict:
        """Create a new job in 'queued' status.

        Args:
            job_type: Job type (sft, eval, pipeline, etc.).
            config: Job configuration dict.
            experiment_id: Optional linked experiment ID.

        Returns:
            Created job dict.
        """
        job_id = str(uuid.uuid4())[:8]
        now_iso = datetime.now().isoformat()

        self._db.execute(
            """
            INSERT INTO jobs
                (id, experiment_id, status, job_type, config, started_at)
            VALUES (?, ?, 'queued', ?, ?, ?)
            """,
            (
                job_id,
                experiment_id,
                job_type,
                json.dumps(config or {}, ensure_ascii=False),
                now_iso,
            ),
        )
        self._db.commit()
        logger.info("Created job %s (type=%s)", job_id, job_type)
        return self.get(job_id)  # type: ignore[return-value]

    def get(self, job_id: str) -> dict | None:
        """Get a job by ID.

        Args:
            job_id: Job ID.

        Returns:
            Job dict or None.
        """
        row = self._db.fetch_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_all(self, status: str | None = None) -> list[dict]:
        """List all jobs, optionally filtered by status.

        Args:
            status: Optional status filter.

        Returns:
            List of job dicts (newest first).
        """
        if status:
            rows = self._db.fetch_all(
                "SELECT * FROM jobs WHERE status = ? ORDER BY started_at DESC",
                (status,),
            )
        else:
            rows = self._db.fetch_all("SELECT * FROM jobs ORDER BY started_at DESC")
        return [self._row_to_dict(r) for r in rows]

    def update_status(
        self,
        job_id: str,
        status: str,
        error_message: str | None = None,
        pid: int | None = None,
    ) -> bool:
        """Update job status.

        Args:
            job_id: Job ID.
            status: New status (queued/running/completed/failed/cancelled).
            error_message: Optional error message for failed jobs.
            pid: Optional process ID for running jobs.

        Returns:
            True if updated, False if job not found.
        """
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        updates = ["status = ?"]
        values: list[Any] = [status]

        if status in {"completed", "failed", "cancelled"}:
            updates.append("completed_at = ?")
            values.append(datetime.now().isoformat())

        if error_message is not None:
            updates.append("error_message = ?")
            values.append(error_message)

        if pid is not None:
            updates.append("pid = ?")
            values.append(pid)

        values.append(job_id)
        cursor = self._db.execute(
            f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?",
            tuple(values),
        )
        self._db.commit()
        return cursor.rowcount > 0

    def delete(self, job_id: str) -> bool:
        """Delete a job.

        Args:
            job_id: Job ID.

        Returns:
            True if deleted, False if not found.
        """
        cursor = self._db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        self._db.commit()
        return cursor.rowcount > 0

    def get_active_jobs(self) -> list[dict]:
        """Get all jobs that are queued or running.

        Returns:
            List of active job dicts.
        """
        rows = self._db.fetch_all("""
            SELECT * FROM jobs
            WHERE status IN ('queued', 'running')
            ORDER BY started_at
            """)
        return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row: dict) -> dict:
        """Convert a SQLite row to job dict."""
        return {
            "id": row["id"],
            "experiment_id": row.get("experiment_id"),
            "status": row["status"],
            "job_type": row.get("job_type", ""),
            "config": json.loads(row.get("config") or "{}"),
            "started_at": row["started_at"],
            "completed_at": row.get("completed_at"),
            "error_message": row.get("error_message"),
            "pid": row.get("pid"),
        }
