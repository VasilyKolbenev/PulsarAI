"""Remote job execution on SSH compute targets."""

import json
import logging
import re
import shlex
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generator

from pulsar_ai.compute.ssh import SSHConnection
from pulsar_ai.compute.manager import ComputeTarget

logger = logging.getLogger(__name__)

_SAFE_TASK_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass
class RemoteJobStatus:
    """Status of a remote training job."""

    job_id: str
    target_id: str
    status: str  # queued/running/completed/failed
    started_at: str
    log_tail: list[str]
    exit_code: int | None = None
    artifacts: dict | None = None


class RemoteJobRunner:
    """Runs training jobs on remote machines via SSH.

    Workflow:
    1. Sync config + data to remote
    2. Launch training via torchrun/python
    3. Stream logs back via SSH tail
    4. Download artifacts when done

    Args:
        target: ComputeTarget to run on.
    """

    REMOTE_WORK_DIR = "~/pulsar-ai-jobs"

    def __init__(self, target: ComputeTarget) -> None:
        self.target = target
        self._conn: SSHConnection | None = None

    def _write_remote_json(self, conn: SSHConnection, data: dict, remote_path: str) -> None:
        """Write JSON to a remote file via SFTP (no shell injection risk).

        Args:
            conn: Active SSH connection.
            data: Dictionary to serialize as JSON.
            remote_path: Destination path on the remote host.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(data, tmp, indent=2)
            tmp_path = Path(tmp.name)
        try:
            conn.put_file(tmp_path, remote_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def _get_connection(self) -> SSHConnection:
        """Get or create SSH connection."""
        if self._conn is None:
            self._conn = SSHConnection(
                host=self.target.host,
                user=self.target.user,
                port=self.target.port,
                key_path=self.target.key_path,
            )
            self._conn.connect()
        return self._conn

    def sync_files(self, local_paths: list[Path], remote_dir: str) -> None:
        """Upload files to the remote target.

        Args:
            local_paths: Local files to upload.
            remote_dir: Remote directory to put files in.
        """
        conn = self._get_connection()
        conn.exec_command(f"mkdir -p {shlex.quote(remote_dir)}")
        for path in local_paths:
            if path.exists():
                remote_path = f"{remote_dir}/{path.name}"
                conn.put_file(path, remote_path)
                logger.info("Synced %s → %s:%s", path, self.target.host, remote_path)

    def submit_job(
        self,
        config: dict,
        task: str = "sft",
    ) -> str:
        """Submit a training job to the remote target.

        Args:
            config: Training configuration dict.
            task: Training task type (sft/dpo).

        Returns:
            Job ID string.

        Raises:
            ValueError: If task contains unsafe characters.
        """
        if not _SAFE_TASK_RE.match(task):
            raise ValueError(f"Invalid task name: {task!r}")

        job_id = str(uuid.uuid4())[:8]
        conn = self._get_connection()

        remote_job_dir = f"{self.REMOTE_WORK_DIR}/{job_id}"
        conn.exec_command(f"mkdir -p {shlex.quote(remote_job_dir)}")

        # Write config to remote via SFTP (safe from shell injection)
        self._write_remote_json(conn, config, f"{remote_job_dir}/config.json")

        # Build training command — all interpolated values are quoted
        q_dir = shlex.quote(remote_job_dir)
        q_task = shlex.quote(task)
        num_gpus = self.target.gpu_count or 1
        if num_gpus > 1:
            train_cmd = (
                f"cd {q_dir} && "
                f"torchrun --nproc_per_node={int(num_gpus)} "
                f"-m pulsar_ai.training._distributed_entry "
                f"--config config.json --task {q_task}"
            )
        else:
            train_cmd = (
                f"cd {q_dir} && " f"python -m pulsar_ai.cli train config.json --task {q_task}"
            )

        # Launch in background with nohup
        q_log = shlex.quote(f"{remote_job_dir}/output.log")
        launch_cmd = f"nohup bash -c {shlex.quote(train_cmd)} " f"> {q_log} 2>&1 & " f"echo $!"

        stdout, stderr, code = conn.exec_command(launch_cmd)
        pid = stdout.strip()

        # Save job metadata
        meta = {
            "job_id": job_id,
            "target_id": self.target.id,
            "pid": pid,
            "task": task,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "remote_dir": remote_job_dir,
        }
        self._write_remote_json(conn, meta, f"{remote_job_dir}/job_meta.json")

        logger.info(
            "Submitted remote job %s on %s (PID: %s)",
            job_id,
            self.target.name,
            pid,
        )
        return job_id

    def get_status(self, job_id: str) -> RemoteJobStatus:
        """Get status of a remote job.

        Args:
            job_id: Job ID to check.

        Returns:
            RemoteJobStatus with current state.

        Raises:
            ValueError: If job_id contains unsafe characters.
        """
        if not _SAFE_ID_RE.match(job_id):
            raise ValueError(f"Invalid job_id: {job_id!r}")

        conn = self._get_connection()
        q_dir = shlex.quote(f"{self.REMOTE_WORK_DIR}/{job_id}")

        # Read job metadata
        stdout, _, code = conn.exec_command(f"cat {q_dir}/job_meta.json 2>/dev/null")
        if code != 0:
            return RemoteJobStatus(
                job_id=job_id,
                target_id=self.target.id,
                status="not_found",
                started_at="",
                log_tail=[],
            )

        meta = json.loads(stdout)
        pid = meta.get("pid", "")

        # Validate PID is numeric before using in shell
        if not str(pid).isdigit():
            logger.warning("Invalid PID %r in job metadata for %s", pid, job_id)
            return RemoteJobStatus(
                job_id=job_id,
                target_id=self.target.id,
                status="unknown",
                started_at=meta.get("started_at", ""),
                log_tail=[],
            )

        # Check if process is still running
        check_stdout, _, _ = conn.exec_command(
            f"kill -0 {int(pid)} 2>/dev/null && echo running || echo done"
        )
        is_running = "running" in check_stdout

        # Get log tail
        log_stdout, _, _ = conn.exec_command(f"tail -n 20 {q_dir}/output.log 2>/dev/null")
        log_lines = log_stdout.strip().splitlines() if log_stdout.strip() else []

        status = "running" if is_running else "completed"

        # Check exit code if done
        exit_code = None
        if not is_running:
            exit_stdout, _, _ = conn.exec_command(f"cat {q_dir}/exit_code 2>/dev/null")
            if exit_stdout.strip().isdigit():
                exit_code = int(exit_stdout.strip())
                if exit_code != 0:
                    status = "failed"

        return RemoteJobStatus(
            job_id=job_id,
            target_id=self.target.id,
            status=status,
            started_at=meta.get("started_at", ""),
            log_tail=log_lines,
            exit_code=exit_code,
        )

    def stream_logs(self, job_id: str, lines: int = 50) -> Generator[str, None, None]:
        """Stream log lines from a remote job.

        Args:
            job_id: Job ID.
            lines: Number of lines to tail.

        Yields:
            Log lines from the remote job.

        Raises:
            ValueError: If job_id contains unsafe characters.
        """
        if not _SAFE_ID_RE.match(job_id):
            raise ValueError(f"Invalid job_id: {job_id!r}")
        conn = self._get_connection()
        remote_log = f"{self.REMOTE_WORK_DIR}/{job_id}/output.log"
        yield from conn.tail_file(remote_log, lines=lines)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running remote job.

        Args:
            job_id: Job ID to cancel.

        Returns:
            True if cancelled, False otherwise.

        Raises:
            ValueError: If job_id contains unsafe characters.
        """
        if not _SAFE_ID_RE.match(job_id):
            raise ValueError(f"Invalid job_id: {job_id!r}")

        conn = self._get_connection()
        q_dir = shlex.quote(f"{self.REMOTE_WORK_DIR}/{job_id}")

        stdout, _, code = conn.exec_command(f"cat {q_dir}/job_meta.json 2>/dev/null")
        if code != 0:
            return False

        meta = json.loads(stdout)
        pid = meta.get("pid", "")
        if not str(pid).isdigit():
            logger.warning("Invalid PID %r in job %s", pid, job_id)
            return False

        _, _, kill_code = conn.exec_command(f"kill {int(pid)} 2>/dev/null")
        logger.info("Cancelled remote job %s (PID: %s)", job_id, pid)
        return True

    def download_artifacts(self, job_id: str, local_dir: Path) -> list[Path]:
        """Download job artifacts from remote.

        Args:
            job_id: Job ID.
            local_dir: Local directory to save artifacts.

        Returns:
            List of downloaded file paths.

        Raises:
            ValueError: If job_id contains unsafe characters.
        """
        if not _SAFE_ID_RE.match(job_id):
            raise ValueError(f"Invalid job_id: {job_id!r}")

        conn = self._get_connection()
        remote_job_dir = f"{self.REMOTE_WORK_DIR}/{job_id}"

        local_dir.mkdir(parents=True, exist_ok=True)

        # List remote artifacts
        stdout, _, _ = conn.exec_command(
            f"ls {shlex.quote(remote_job_dir + '/outputs/')} 2>/dev/null"
        )
        files = [f.strip() for f in stdout.splitlines() if f.strip()]

        downloaded = []
        for filename in files:
            remote_path = f"{remote_job_dir}/outputs/{filename}"
            local_path = local_dir / filename
            conn.get_file(remote_path, local_path)
            downloaded.append(local_path)
            logger.info("Downloaded %s → %s", remote_path, local_path)

        return downloaded

    def close(self) -> None:
        """Close the SSH connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
