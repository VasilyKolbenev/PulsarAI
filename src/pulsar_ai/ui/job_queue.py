"""Job queue abstraction for training job execution.

Supports two backends:
- ``LocalJobQueue``: ThreadPoolExecutor (default, single-node)
- ``RedisJobQueue``: Redis-backed distributed queue

Selected via ``PULSAR_REDIS_URL`` environment variable.
"""

import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class JobQueue(ABC):
    """Abstract interface for job queuing and execution."""

    @abstractmethod
    def submit(self, job_type: str, config: dict, experiment_id: str = "") -> str:
        """Submit a job and return its ID."""

    @abstractmethod
    def get_status(self, job_id: str) -> Optional[dict]:
        """Get job status by ID."""

    @abstractmethod
    def cancel(self, job_id: str) -> bool:
        """Cancel a running or queued job."""

    @abstractmethod
    def list_jobs(self, status: Optional[str] = None) -> list[dict]:
        """List jobs, optionally filtered by status."""


class LocalJobQueue(JobQueue):
    """In-process job queue using ThreadPoolExecutor.

    This is the default backend — runs training jobs in background threads.
    Suitable for single-node deployments.
    """

    def __init__(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        self._executor = ThreadPoolExecutor(max_workers=1)
        self._jobs: dict[str, dict] = {}

    def submit(self, job_type: str, config: dict, experiment_id: str = "") -> str:
        """Submit a job to the thread pool."""
        job_id = str(uuid.uuid4())[:8]
        self._jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "experiment_id": experiment_id,
            "status": "queued",
            "config": config,
            "submitted_at": datetime.now().isoformat(),
            "completed_at": None,
            "error": None,
        }
        logger.info("Job %s queued (type=%s)", job_id, job_type)
        return job_id

    def get_status(self, job_id: str) -> Optional[dict]:
        """Get job status."""
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        """Cancel a job."""
        job = self._jobs.get(job_id)
        if job and job["status"] in ("queued", "running"):
            job["status"] = "cancelled"
            return True
        return False

    def list_jobs(self, status: Optional[str] = None) -> list[dict]:
        """List all jobs."""
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j["status"] == status]
        return sorted(jobs, key=lambda j: j["submitted_at"], reverse=True)

    def shutdown(self) -> None:
        """Shutdown the executor."""
        self._executor.shutdown(wait=False)


class RedisJobQueue(JobQueue):
    """Redis-backed distributed job queue.

    Uses Redis lists for job queuing and hashes for status tracking.
    Workers poll the queue and process jobs.

    Requires: ``pip install pulsar-ai[redis]``

    Args:
        redis_url: Redis connection URL (e.g. ``redis://localhost:6379``).
    """

    QUEUE_KEY = "pulsar:jobs:queue"
    JOB_PREFIX = "pulsar:job:"

    def __init__(self, redis_url: str) -> None:
        try:
            import redis as redis_lib
        except ImportError as exc:
            raise ImportError(
                "redis is required for Redis job queue. "
                "Install with: pip install pulsar-ai[redis]"
            ) from exc

        self._redis = redis_lib.from_url(redis_url, decode_responses=True)
        self._redis.ping()
        logger.info("Redis job queue connected: %s", redis_url)

    def submit(self, job_type: str, config: dict, experiment_id: str = "") -> str:
        """Submit a job to the Redis queue."""
        job_id = str(uuid.uuid4())[:8]
        job_data = {
            "id": job_id,
            "type": job_type,
            "experiment_id": experiment_id,
            "status": "queued",
            "config": json.dumps(config),
            "submitted_at": datetime.now().isoformat(),
            "completed_at": "",
            "error": "",
        }
        # Store job data in a hash
        self._redis.hset(f"{self.JOB_PREFIX}{job_id}", mapping=job_data)
        # Push to queue for workers
        self._redis.lpush(self.QUEUE_KEY, job_id)
        logger.info("Job %s queued in Redis (type=%s)", job_id, job_type)
        return job_id

    def get_status(self, job_id: str) -> Optional[dict]:
        """Get job status from Redis."""
        data = self._redis.hgetall(f"{self.JOB_PREFIX}{job_id}")
        if not data:
            return None
        if "config" in data:
            data["config"] = json.loads(data["config"])
        return data

    def cancel(self, job_id: str) -> bool:
        """Cancel a job in Redis."""
        key = f"{self.JOB_PREFIX}{job_id}"
        status = self._redis.hget(key, "status")
        if status in ("queued", "running"):
            self._redis.hset(key, "status", "cancelled")
            # Remove from queue if still there
            self._redis.lrem(self.QUEUE_KEY, 0, job_id)
            return True
        return False

    def list_jobs(self, status: Optional[str] = None) -> list[dict]:
        """List all jobs from Redis."""
        keys = self._redis.keys(f"{self.JOB_PREFIX}*")
        jobs = []
        for key in keys:
            data = self._redis.hgetall(key)
            if data:
                if "config" in data:
                    data["config"] = json.loads(data["config"])
                if status is None or data.get("status") == status:
                    jobs.append(data)
        return sorted(jobs, key=lambda j: j.get("submitted_at", ""), reverse=True)


_queue: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    """Get the configured job queue singleton.

    Returns:
        LocalJobQueue or RedisJobQueue based on PULSAR_REDIS_URL.
    """
    global _queue  # noqa: PLW0603
    if _queue is not None:
        return _queue

    redis_url = os.environ.get("PULSAR_REDIS_URL", "").strip()
    if redis_url:
        _queue = RedisJobQueue(redis_url)
    else:
        _queue = LocalJobQueue()
    return _queue
