"""Tests for remote compute security hardening (shlex, retry, validation)."""

from pathlib import Path

import pytest
from unittest.mock import patch, MagicMock

from pulsar_ai.compute.ssh import SSHConnection
from pulsar_ai.compute.remote_runner import RemoteJobRunner, _SAFE_TASK_RE, _SAFE_ID_RE
from pulsar_ai.compute.manager import ComputeTarget

# ── Input validation ──────────────────────────────────────────


class TestInputValidation:
    def test_safe_task_regex_allows_valid(self):
        assert _SAFE_TASK_RE.match("sft")
        assert _SAFE_TASK_RE.match("dpo")
        assert _SAFE_TASK_RE.match("sft-v2")
        assert _SAFE_TASK_RE.match("my_task_123")

    def test_safe_task_regex_blocks_injection(self):
        assert not _SAFE_TASK_RE.match("sft; rm -rf /")
        assert not _SAFE_TASK_RE.match("sft' && echo pwned")
        assert not _SAFE_TASK_RE.match("$(whoami)")
        assert not _SAFE_TASK_RE.match("")

    def test_safe_id_regex_allows_valid(self):
        assert _SAFE_ID_RE.match("abc12345")
        assert _SAFE_ID_RE.match("job-id-1")

    def test_safe_id_regex_blocks_injection(self):
        assert not _SAFE_ID_RE.match("../../../etc/passwd")
        assert not _SAFE_ID_RE.match("id; rm -rf /")
        assert not _SAFE_ID_RE.match("")


# ── Submit job validation ─────────────────────────────────────


class TestSubmitJobValidation:
    def _make_runner(self):
        target = ComputeTarget(
            id="t1",
            name="test",
            host="1.2.3.4",
            user="ubuntu",
            port=22,
            key_path=None,
            gpu_count=1,
            gpu_type="A100",
        )
        return RemoteJobRunner(target)

    def test_submit_job_rejects_malicious_task(self):
        runner = self._make_runner()
        with pytest.raises(ValueError, match="Invalid task name"):
            runner.submit_job(config={}, task="sft; rm -rf /")

    def test_submit_job_rejects_shell_metachar_task(self):
        runner = self._make_runner()
        with pytest.raises(ValueError, match="Invalid task name"):
            runner.submit_job(config={}, task="$(whoami)")


# ── Get status / cancel validation ────────────────────────────


class TestJobIdValidation:
    def _make_runner(self):
        target = ComputeTarget(
            id="t1",
            name="test",
            host="1.2.3.4",
            user="ubuntu",
            port=22,
            key_path=None,
            gpu_count=1,
            gpu_type="A100",
        )
        return RemoteJobRunner(target)

    def test_get_status_rejects_path_traversal(self):
        runner = self._make_runner()
        with pytest.raises(ValueError, match="Invalid job_id"):
            runner.get_status("../../etc/passwd")

    def test_cancel_rejects_injection(self):
        runner = self._make_runner()
        with pytest.raises(ValueError, match="Invalid job_id"):
            runner.cancel_job("id; rm -rf /")

    def test_stream_logs_rejects_injection(self):
        runner = self._make_runner()
        with pytest.raises(ValueError, match="Invalid job_id"):
            list(runner.stream_logs("../bad"))

    def test_download_artifacts_rejects_injection(self):
        runner = self._make_runner()
        with pytest.raises(ValueError, match="Invalid job_id"):
            runner.download_artifacts("id$(cmd)", Path("/tmp"))


# ── Shlex quoting in commands ─────────────────────────────────


class TestShlexQuoting:
    def test_tail_file_quotes_path(self):
        conn = SSHConnection(host="h", user="u")
        # Verify shlex.quote is used by checking the command
        with patch.object(conn, "exec_command", return_value=("line1\nline2", "", 0)) as mock:
            list(conn.tail_file("/path with spaces/log.txt", lines=10))
            cmd = mock.call_args[0][0]
            assert "'/path with spaces/log.txt'" in cmd


# ── SSH retry logic ───────────────────────────────────────────


class TestSSHRetry:
    @patch("pulsar_ai.compute.ssh.time.sleep")
    def test_connect_retries_on_failure(self, mock_sleep):
        conn = SSHConnection(host="unreachable", user="test")
        mock_paramiko = MagicMock()
        mock_client = MagicMock()
        mock_client.connect.side_effect = OSError("Connection refused")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.SSHException = Exception
        mock_paramiko.WarningPolicy.return_value = MagicMock()

        with patch.dict("sys.modules", {"paramiko": mock_paramiko}):
            with pytest.raises(ConnectionError, match="Failed to connect"):
                conn.connect(retries=3)

        assert mock_client.connect.call_count == 3
        assert mock_sleep.call_count == 2  # retries - 1

    @patch("pulsar_ai.compute.ssh.time.sleep")
    def test_connect_succeeds_on_second_attempt(self, mock_sleep):
        conn = SSHConnection(host="flaky", user="test")
        mock_paramiko = MagicMock()
        mock_client = MagicMock()
        mock_client.connect.side_effect = [OSError("timeout"), None]
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.SSHException = Exception
        mock_paramiko.WarningPolicy.return_value = MagicMock()

        with patch.dict("sys.modules", {"paramiko": mock_paramiko}):
            conn.connect(retries=3)

        assert mock_client.connect.call_count == 2
        assert conn._client is not None
