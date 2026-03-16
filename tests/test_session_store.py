"""Tests for SessionStore — durable chat session persistence."""

import pytest
from datetime import datetime, timedelta

from pulsar_ai.storage.database import Database
from pulsar_ai.storage.session_store import SessionStore


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def store(db):
    return SessionStore(db=db)


def test_get_or_create_new_session(store):
    session = store.get_or_create("s1", session_type="assistant")
    assert session["id"] == "s1"
    assert session["session_type"] == "assistant"
    assert session["messages"] == []
    assert session["ttl_hours"] == 24


def test_get_or_create_returns_existing(store):
    store.get_or_create("s1")
    store.append_message("s1", "user", "hello")
    session = store.get_or_create("s1")
    assert len(session["messages"]) == 1


def test_get_existing(store):
    store.get_or_create("s1")
    assert store.get("s1") is not None
    assert store.get("s1")["id"] == "s1"


def test_get_nonexistent(store):
    assert store.get("nope") is None


def test_get_messages_empty(store):
    store.get_or_create("s1")
    assert store.get_messages("s1") == []


def test_get_messages_nonexistent(store):
    assert store.get_messages("nope") == []


def test_append_message(store):
    store.get_or_create("s1")
    store.append_message("s1", "user", "hello")
    store.append_message("s1", "assistant", "hi there")
    msgs = store.get_messages("s1")
    assert len(msgs) == 2
    assert msgs[0] == {"role": "user", "content": "hello"}
    assert msgs[1] == {"role": "assistant", "content": "hi there"}


def test_append_message_with_trim(store):
    store.get_or_create("s1")
    for i in range(10):
        store.append_message("s1", "user", f"msg {i}", max_messages=5)
    msgs = store.get_messages("s1")
    assert len(msgs) == 5
    assert msgs[0]["content"] == "msg 5"


def test_set_messages(store):
    store.get_or_create("s1")
    store.set_messages("s1", [{"role": "user", "content": "replaced"}])
    msgs = store.get_messages("s1")
    assert len(msgs) == 1
    assert msgs[0]["content"] == "replaced"


def test_delete_session(store):
    store.get_or_create("s1")
    assert store.delete("s1") is True
    assert store.get("s1") is None


def test_delete_nonexistent(store):
    assert store.delete("nope") is False


def test_list_sessions(store):
    store.get_or_create("s1", session_type="assistant")
    store.get_or_create("s2", session_type="site_chat")
    store.get_or_create("s3", session_type="assistant")
    all_sessions = store.list_sessions()
    assert len(all_sessions) == 3


def test_list_sessions_by_type(store):
    store.get_or_create("s1", session_type="assistant")
    store.get_or_create("s2", session_type="site_chat")
    store.get_or_create("s3", session_type="assistant")
    assistant_sessions = store.list_sessions(session_type="assistant")
    assert len(assistant_sessions) == 2
    site_sessions = store.list_sessions(session_type="site_chat")
    assert len(site_sessions) == 1


def test_cleanup_expired(store, db):
    # Create a session and backdate it
    old_time = (datetime.now() - timedelta(hours=48)).isoformat()
    db.execute(
        "INSERT INTO assistant_sessions (id, session_type, messages, created_at, updated_at, ttl_hours) "
        "VALUES ('old', 'assistant', '[]', ?, ?, 24)",
        (old_time, old_time),
    )
    db.commit()
    store.get_or_create("fresh")
    deleted = store.cleanup_expired()
    assert deleted == 1
    assert store.get("old") is None
    assert store.get("fresh") is not None


def test_unicode_messages(store):
    store.get_or_create("s1")
    store.append_message("s1", "user", "Привет мир 🌍")
    msgs = store.get_messages("s1")
    assert msgs[0]["content"] == "Привет мир 🌍"


def test_session_type_default(store):
    session = store.get_or_create("s1")
    assert session["session_type"] == "assistant"


def test_custom_ttl(store):
    session = store.get_or_create("s1", ttl_hours=48)
    assert session["ttl_hours"] == 48
