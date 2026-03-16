"""SSH connection wrapper for remote GPU operations."""

import logging
import shlex
import subprocess
import time
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds (exponential backoff: 2, 4, 8)


class SSHConnection:
    """Manages SSH connections to remote compute targets.

    Uses paramiko for SSH operations. Falls back to subprocess ssh
    if paramiko is unavailable.

    Args:
        host: Remote hostname or IP.
        user: SSH username.
        port: SSH port.
        key_path: Path to SSH private key file.
    """

    def __init__(
        self,
        host: str,
        user: str,
        port: int = 22,
        key_path: str | None = None,
    ) -> None:
        self.host = host
        self.user = user
        self.port = port
        self.key_path = key_path
        self._client = None

    def connect(self, retries: int = MAX_RETRIES) -> None:
        """Establish SSH connection with exponential backoff.

        Args:
            retries: Number of retry attempts on transient failure.
        """
        try:
            import paramiko
        except ImportError:
            logger.warning("paramiko not installed, SSH operations will use subprocess")
            self._client = None
            return

        client = paramiko.SSHClient()
        known_hosts = Path.home() / ".ssh" / "known_hosts"
        if known_hosts.exists():
            client.load_host_keys(str(known_hosts))
        client.set_missing_host_key_policy(paramiko.WarningPolicy())

        connect_kwargs: dict = {
            "hostname": self.host,
            "username": self.user,
            "port": self.port,
            "timeout": 10,
        }
        if self.key_path:
            connect_kwargs["key_filename"] = self.key_path

        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                client.connect(**connect_kwargs)
                self._client = client
                logger.info("SSH connected to %s@%s:%d", self.user, self.host, self.port)
                return
            except (OSError, paramiko.SSHException) as exc:
                last_exc = exc
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "SSH connect attempt %d/%d failed: %s — retrying in %ds",
                    attempt + 1,
                    retries,
                    exc,
                    delay,
                )
                if attempt < retries - 1:
                    time.sleep(delay)

        raise ConnectionError(
            f"Failed to connect to {self.user}@{self.host}:{self.port} "
            f"after {retries} attempts: {last_exc}"
        )

    def exec_command(self, cmd: str, timeout: int = 300) -> tuple[str, str, int]:
        """Execute a command on the remote host.

        Args:
            cmd: Command to execute.
            timeout: Timeout in seconds.

        Returns:
            Tuple of (stdout, stderr, exit_code).
        """
        if self._client is not None:

            stdin, stdout, stderr = self._client.exec_command(cmd, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            return stdout.read().decode(), stderr.read().decode(), exit_code

        # Fallback to subprocess
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-p", str(self.port)]
        if self.key_path:
            ssh_cmd.extend(["-i", self.key_path])
        ssh_cmd.append(f"{self.user}@{self.host}")
        ssh_cmd.append(cmd)

        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout, result.stderr, result.returncode

    def put_file(self, local: Path, remote: str) -> None:
        """Upload a file to the remote host.

        Args:
            local: Local file path.
            remote: Remote file path.
        """
        if self._client is not None:
            sftp = self._client.open_sftp()
            sftp.put(str(local), remote)
            sftp.close()
            return

        scp_cmd = ["scp", "-o", "StrictHostKeyChecking=accept-new", "-P", str(self.port)]
        if self.key_path:
            scp_cmd.extend(["-i", self.key_path])
        scp_cmd.extend([str(local), f"{self.user}@{self.host}:{remote}"])
        subprocess.run(scp_cmd, check=True, timeout=300)

    def get_file(self, remote: str, local: Path) -> None:
        """Download a file from the remote host.

        Args:
            remote: Remote file path.
            local: Local file path.
        """
        if self._client is not None:
            sftp = self._client.open_sftp()
            sftp.get(remote, str(local))
            sftp.close()
            return

        scp_cmd = ["scp", "-o", "StrictHostKeyChecking=accept-new", "-P", str(self.port)]
        if self.key_path:
            scp_cmd.extend(["-i", self.key_path])
        scp_cmd.extend([f"{self.user}@{self.host}:{remote}", str(local)])
        subprocess.run(scp_cmd, check=True, timeout=300)

    def tail_file(self, path: str, lines: int = 50) -> Generator[str, None, None]:
        """Tail a remote file and yield lines.

        Args:
            path: Remote file path.
            lines: Number of lines to read.

        Yields:
            Lines from the remote file.
        """
        stdout, _, _ = self.exec_command(f"tail -n {int(lines)} {shlex.quote(path)}")
        for line in stdout.splitlines():
            yield line

    def close(self) -> None:
        """Close the SSH connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("SSH connection closed")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()
