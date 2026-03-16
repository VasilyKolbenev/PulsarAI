"""Tests for API key audit trail (api_key_events table)."""

import pytest

from pulsar_ai.storage.database import Database
from pulsar_ai.ui.auth import ApiKeyStore


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def store(db):
    return ApiKeyStore(db=db)


def test_generate_key_logs_created_event(store):
    store.generate_key("test-key")
    events = store.get_events(event_type="created")
    assert len(events) == 1
    assert events[0]["event_type"] == "created"
    assert events[0]["key_id"] != ""


def test_verify_valid_key_logs_verified_event(store):
    key = store.generate_key("test-key")
    store.verify(key, ip_address="127.0.0.1")
    events = store.get_events(event_type="verified")
    assert len(events) == 1
    assert events[0]["ip_address"] == "127.0.0.1"


def test_verify_invalid_key_logs_auth_failed(store):
    store.verify("bad_key", ip_address="10.0.0.1")
    events = store.get_events(event_type="auth_failed")
    assert len(events) == 1
    assert events[0]["ip_address"] == "10.0.0.1"
    assert events[0]["key_id"] == ""


def test_revoke_logs_revoked_event(store):
    store.generate_key("my-key")
    store.revoke("my-key")
    events = store.get_events(event_type="revoked")
    assert len(events) == 1


def test_get_events_filter_by_key_id(store):
    k1 = store.generate_key("key-a")
    k2 = store.generate_key("key-b")
    store.verify(k1)
    store.verify(k2)
    # Get all created events and pick one key_id
    created = store.get_events(event_type="created")
    key_id = created[0]["key_id"]
    key_events = store.get_events(key_id=key_id)
    assert all(e["key_id"] == key_id for e in key_events)


def test_get_events_limit(store):
    for i in range(10):
        store.generate_key(f"key-{i}")
    events = store.get_events(limit=5)
    assert len(events) == 5


def test_get_events_no_filters(store):
    store.generate_key("test")
    events = store.get_events()
    assert len(events) >= 1


def test_multiple_auth_failures_logged(store):
    for _ in range(3):
        store.verify("wrong_key")
    events = store.get_events(event_type="auth_failed")
    assert len(events) == 3
