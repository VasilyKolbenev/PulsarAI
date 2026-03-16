"""Tests for security hardening: CORS, calculator, SSH, remote runner."""

import os
from unittest.mock import patch, MagicMock

import pytest


class TestCorsConfiguration:
    """Tests for CORS origin configuration."""

    def test_default_cors_allows_localhost(self):
        """Without PULSAR_CORS_ORIGINS, localhost origins get CORS headers."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PULSAR_CORS_ORIGINS", None)
            from pulsar_ai.ui.app import create_app
            from fastapi.testclient import TestClient

            app = create_app()
            client = TestClient(app)
            resp = client.options(
                "/api/v1/health",
                headers={
                    "Origin": "http://localhost:8888",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert resp.headers.get("access-control-allow-origin") == "http://localhost:8888"

    def test_default_cors_blocks_unknown_origin(self):
        """Unknown origins should not get CORS allow header."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PULSAR_CORS_ORIGINS", None)
            from pulsar_ai.ui.app import create_app
            from fastapi.testclient import TestClient

            app = create_app()
            client = TestClient(app)
            resp = client.options(
                "/api/v1/health",
                headers={
                    "Origin": "https://evil.com",
                    "Access-Control-Request-Method": "GET",
                },
            )
            # Should not allow the evil origin
            allow_origin = resp.headers.get("access-control-allow-origin", "")
            assert "evil.com" not in allow_origin

    def test_custom_cors_from_env(self):
        """PULSAR_CORS_ORIGINS overrides default origins."""
        with patch.dict(
            os.environ,
            {"PULSAR_CORS_ORIGINS": "https://app.example.com,https://admin.example.com"},
        ):
            from pulsar_ai.ui.app import create_app
            from fastapi.testclient import TestClient

            app = create_app()
            client = TestClient(app)
            resp = client.options(
                "/api/v1/health",
                headers={
                    "Origin": "https://app.example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert resp.headers.get("access-control-allow-origin") == "https://app.example.com"


class TestSafeCalculator:
    """Tests for AST-based safe calculator."""

    def test_basic_arithmetic(self):
        from pulsar_ai.agent.builtin_tools import _calculate

        assert _calculate("2 + 3") == "5"
        assert _calculate("10 - 4") == "6"
        assert _calculate("3 * 7") == "21"
        assert _calculate("15 / 3") == "5.0"

    def test_complex_expression(self):
        from pulsar_ai.agent.builtin_tools import _calculate

        assert _calculate("(2 + 3) * 4") == "20"

    def test_power(self):
        from pulsar_ai.agent.builtin_tools import _calculate

        assert _calculate("2 ** 10") == "1024"

    def test_modulo(self):
        from pulsar_ai.agent.builtin_tools import _calculate

        assert _calculate("17 % 5") == "2"

    def test_negative_numbers(self):
        from pulsar_ai.agent.builtin_tools import _calculate

        assert _calculate("-5 + 3") == "-2"

    def test_float(self):
        from pulsar_ai.agent.builtin_tools import _calculate

        result = _calculate("3.14 * 2")
        assert float(result) == pytest.approx(6.28)

    def test_division_by_zero(self):
        from pulsar_ai.agent.builtin_tools import _calculate

        result = _calculate("1 / 0")
        assert "Error" in result

    def test_rejects_function_calls(self):
        from pulsar_ai.agent.builtin_tools import _calculate

        result = _calculate("__import__('os').system('ls')")
        assert "Error" in result

    def test_rejects_variable_names(self):
        from pulsar_ai.agent.builtin_tools import _calculate

        result = _calculate("abc + 1")
        assert "Error" in result

    def test_rejects_string_literals(self):
        from pulsar_ai.agent.builtin_tools import _calculate

        result = _calculate("'hello'")
        assert "Error" in result

    def test_rejects_list_comprehension(self):
        from pulsar_ai.agent.builtin_tools import _calculate

        result = _calculate("[x for x in range(10)]")
        assert "Error" in result


class TestRemoteRunnerNoHeredoc:
    """Tests that remote_runner uses SFTP instead of heredoc."""

    def test_write_remote_json_uses_put_file(self):
        from pulsar_ai.compute.remote_runner import RemoteJobRunner
        from pulsar_ai.compute.manager import ComputeTarget

        target = ComputeTarget(
            id="test",
            name="test",
            host="example.com",
            user="root",
            port=22,
        )
        runner = RemoteJobRunner(target)

        mock_conn = MagicMock()
        mock_conn.put_file = MagicMock()

        data = {"key": "value", "nested": {"a": 1}}
        runner._write_remote_json(mock_conn, data, "/tmp/test.json")

        # put_file should have been called (SFTP upload, not heredoc)
        mock_conn.put_file.assert_called_once()
        args = mock_conn.put_file.call_args
        assert str(args[0][1]) == "/tmp/test.json"

    def test_submit_job_no_heredoc_in_commands(self):
        """Ensure submit_job doesn't use cat heredoc for config writing."""
        from pulsar_ai.compute.remote_runner import RemoteJobRunner
        from pulsar_ai.compute.manager import ComputeTarget

        target = ComputeTarget(
            id="test",
            name="test",
            host="example.com",
            user="root",
            port=22,
            gpu_count=1,
        )
        runner = RemoteJobRunner(target)

        mock_conn = MagicMock()
        mock_conn.exec_command = MagicMock(return_value=("12345", "", 0))
        mock_conn.put_file = MagicMock()
        runner._conn = mock_conn

        runner.submit_job({"model": "test"}, task="sft")

        # Check no exec_command call contains FORGEEOF (heredoc marker)
        for call in mock_conn.exec_command.call_args_list:
            cmd = call[0][0]
            assert "FORGEEOF" not in cmd, f"Heredoc found in command: {cmd}"
