"""SQLite-backed compute target management for remote GPU resources."""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pulsar_ai.compute.ssh import SSHConnection
from pulsar_ai.storage.database import Database, get_database

logger = logging.getLogger(__name__)


@dataclass
class ComputeTarget:
    """A remote or local compute target."""

    id: str
    name: str
    host: str
    user: str
    port: int = 22
    key_path: str | None = None
    gpu_count: int = 0
    gpu_type: str = ""
    vram_gb: float = 0
    status: str = "unknown"
    added_at: str = ""
    last_seen: str | None = None


@dataclass
class ConnectionTestResult:
    """Result of testing SSH connection to a target."""

    success: bool
    message: str
    latency_ms: float = 0
    gpu_info: str = ""


class ComputeManager:
    """Manages compute targets backed by SQLite.

    Args:
        db: Database instance.  Uses the module singleton when *None*.
    """

    def __init__(self, db: Database | None = None) -> None:
        self._db = db or get_database()

    def add_target(
        self,
        name: str,
        host: str,
        user: str,
        port: int = 22,
        key_path: str | None = None,
    ) -> ComputeTarget:
        """Add a new compute target.

        Args:
            name: Display name for the target.
            host: Hostname or IP address.
            user: SSH username.
            port: SSH port.
            key_path: Path to SSH private key.

        Returns:
            Created ComputeTarget.
        """
        target_id = str(uuid.uuid4())[:8]
        now_iso = datetime.now().isoformat()

        self._db.execute(
            """
            INSERT INTO compute_targets
                (id, name, host, user, port, key_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (target_id, name, host, user, port, key_path or "", now_iso),
        )
        self._db.commit()
        logger.info("Added compute target: %s (%s@%s)", name, user, host)

        return ComputeTarget(
            id=target_id,
            name=name,
            host=host,
            user=user,
            port=port,
            key_path=key_path,
            added_at=now_iso,
        )

    def remove_target(self, target_id: str) -> bool:
        """Remove a compute target.

        Args:
            target_id: Target ID to remove.

        Returns:
            True if removed, False if not found.
        """
        cursor = self._db.execute("DELETE FROM compute_targets WHERE id = ?", (target_id,))
        self._db.commit()
        return cursor.rowcount > 0

    def get_target(self, target_id: str) -> ComputeTarget | None:
        """Get a single target by ID.

        Args:
            target_id: Target ID.

        Returns:
            ComputeTarget or None.
        """
        row = self._db.fetch_one("SELECT * FROM compute_targets WHERE id = ?", (target_id,))
        if row is None:
            return None
        return self._row_to_target(row)

    def list_targets(self) -> list[ComputeTarget]:
        """List all compute targets.

        Returns:
            List of ComputeTarget instances.
        """
        rows = self._db.fetch_all("SELECT * FROM compute_targets ORDER BY created_at")
        return [self._row_to_target(r) for r in rows]

    def test_connection(self, target_id: str) -> ConnectionTestResult:
        """Test SSH connection to a target.

        Args:
            target_id: Target to test.

        Returns:
            ConnectionTestResult with success/failure info.
        """
        target = self.get_target(target_id)
        if not target:
            return ConnectionTestResult(success=False, message="Target not found")

        import time

        start = time.monotonic()
        try:
            conn = SSHConnection(
                host=target.host,
                user=target.user,
                port=target.port,
                key_path=target.key_path,
            )
            conn.connect()
            stdout, stderr, code = conn.exec_command("echo ok", timeout=10)
            latency = (time.monotonic() - start) * 1000
            conn.close()

            if code != 0:
                return ConnectionTestResult(
                    success=False,
                    message=f"Command failed: {stderr.strip()}",
                    latency_ms=latency,
                )

            self._update_target(
                target_id,
                status="online",
                last_heartbeat=datetime.now().isoformat(),
            )

            return ConnectionTestResult(
                success=True,
                message="Connected successfully",
                latency_ms=round(latency, 1),
            )
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            self._update_target(target_id, status="offline")
            return ConnectionTestResult(
                success=False,
                message=str(e),
                latency_ms=round(latency, 1),
            )

    def detect_remote_hardware(self, target_id: str) -> dict[str, Any]:
        """Detect hardware on a remote target.

        Args:
            target_id: Target to probe.

        Returns:
            Dict with gpu_count, gpu_type, vram_gb.
        """
        target = self.get_target(target_id)
        if not target:
            return {"error": "Target not found"}

        try:
            conn = SSHConnection(
                host=target.host,
                user=target.user,
                port=target.port,
                key_path=target.key_path,
            )
            conn.connect()

            stdout, _, code = conn.exec_command(
                "nvidia-smi --query-gpu=count,name,memory.total "
                "--format=csv,noheader,nounits 2>/dev/null || echo 'no-gpu'",
                timeout=15,
            )
            conn.close()

            if "no-gpu" in stdout or code != 0:
                return {"gpu_count": 0, "gpu_type": "CPU only", "vram_gb": 0}

            lines = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
            if not lines:
                return {"gpu_count": 0, "gpu_type": "CPU only", "vram_gb": 0}

            parts = lines[0].split(",")
            gpu_count = len(lines)
            gpu_type = parts[1].strip() if len(parts) > 1 else "Unknown"
            vram_mb = float(parts[2].strip()) if len(parts) > 2 else 0
            vram_gb = round(vram_mb / 1024, 1)

            self._update_target(
                target_id,
                gpu_count=gpu_count,
                gpu_type=gpu_type,
                vram_gb=vram_gb,
                status="online",
                last_heartbeat=datetime.now().isoformat(),
            )

            return {
                "gpu_count": gpu_count,
                "gpu_type": gpu_type,
                "vram_gb": vram_gb,
            }
        except Exception as e:
            return {"error": str(e)}

    def _update_target(self, target_id: str, **kwargs: Any) -> None:
        """Update fields on a target."""
        if not kwargs:
            return
        set_clauses = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [target_id]
        self._db.execute(
            f"UPDATE compute_targets SET {set_clauses} WHERE id = ?",
            tuple(values),
        )
        self._db.commit()

    @staticmethod
    def _row_to_target(row: dict) -> ComputeTarget:
        """Convert a SQLite row to ComputeTarget dataclass."""
        return ComputeTarget(
            id=row["id"],
            name=row["name"],
            host=row["host"],
            user=row["user"],
            port=row.get("port", 22),
            key_path=row.get("key_path") or None,
            gpu_count=row.get("gpu_count", 0),
            gpu_type=row.get("gpu_type", ""),
            vram_gb=row.get("vram_gb", 0),
            status=row.get("status", "unknown"),
            added_at=row.get("created_at", ""),
            last_seen=row.get("last_heartbeat"),
        )
