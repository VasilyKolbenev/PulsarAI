"""Tests for environment variable helper with deprecation."""
import os
import warnings

import pytest

from llm_forge.env import get_env, _warned


@pytest.fixture(autouse=True)
def _reset_warned_state():
    """Clear _warned set between tests to avoid cross-test pollution."""
    _warned.clear()
    yield
    _warned.clear()


def test_get_env_reads_pulsar_prefix(monkeypatch):
    monkeypatch.setenv("PULSAR_PORT", "9999")
    assert get_env("PORT") == "9999"


def test_get_env_falls_back_to_forge_prefix(monkeypatch):
    monkeypatch.delenv("PULSAR_PORT", raising=False)
    monkeypatch.setenv("FORGE_PORT", "8888")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = get_env("PORT")
        assert result == "8888"
        assert len(w) == 1
        assert "FORGE_PORT" in str(w[0].message)


def test_get_env_returns_default_when_neither_set(monkeypatch):
    monkeypatch.delenv("PULSAR_PORT", raising=False)
    monkeypatch.delenv("FORGE_PORT", raising=False)
    assert get_env("PORT", "8888") == "8888"


def test_get_env_pulsar_takes_precedence(monkeypatch):
    monkeypatch.setenv("PULSAR_PORT", "9999")
    monkeypatch.setenv("FORGE_PORT", "8888")
    assert get_env("PORT") == "9999"


def test_forge_warning_only_once(monkeypatch):
    """Deprecation warning fires only once per variable name."""
    monkeypatch.delenv("PULSAR_PORT", raising=False)
    monkeypatch.setenv("FORGE_PORT", "8888")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        get_env("PORT")
        get_env("PORT")  # second call -- no new warning
        assert len(w) == 1
