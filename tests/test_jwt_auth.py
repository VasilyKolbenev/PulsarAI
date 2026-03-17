"""Tests for JWT authentication system."""

import uuid

import pytest

from pulsar_ai.storage.user_store import UserStore
from pulsar_ai.ui.jwt_utils import create_access_token, create_refresh_token, verify_token


def _unique_email() -> str:
    """Generate a unique email to avoid conflicts between test runs."""
    return f"test-{uuid.uuid4().hex[:8]}@example.com"


class TestUserStore:
    """Tests for UserStore CRUD operations."""

    def test_create_user(self) -> None:
        store = UserStore()
        email = _unique_email()
        user = store.create_user(email, "password123", name="Test User")
        assert user["email"] == email
        assert user["name"] == "Test User"
        assert user["role"] == "user"
        assert "id" in user

    def test_create_duplicate_email_raises(self) -> None:
        store = UserStore()
        email = _unique_email()
        store.create_user(email, "pass1")
        with pytest.raises(ValueError, match="already registered"):
            store.create_user(email, "pass2")

    def test_authenticate_valid(self) -> None:
        store = UserStore()
        email = _unique_email()
        store.create_user(email, "secret")
        user = store.authenticate(email, "secret")
        assert user is not None
        assert user["email"] == email

    def test_authenticate_wrong_password(self) -> None:
        store = UserStore()
        email = _unique_email()
        store.create_user(email, "secret")
        user = store.authenticate(email, "wrong")
        assert user is None

    def test_authenticate_nonexistent_email(self) -> None:
        store = UserStore()
        user = store.authenticate(_unique_email(), "pass")
        assert user is None

    def test_get_by_id(self) -> None:
        store = UserStore()
        created = store.create_user(_unique_email(), "pass")
        found = store.get_by_id(created["id"])
        assert found is not None
        assert found["email"] == created["email"]

    def test_deactivate_user(self) -> None:
        store = UserStore()
        email = _unique_email()
        user = store.create_user(email, "pass")
        store.deactivate_user(user["id"])
        assert store.authenticate(email, "pass") is None


class TestJWTTokens:
    """Tests for JWT token creation and verification."""

    def test_create_and_verify_access_token(self) -> None:
        token = create_access_token("user123", "test@example.com", "admin")
        payload = verify_token(token, expected_type="access")
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "admin"

    def test_create_and_verify_refresh_token(self) -> None:
        token = create_refresh_token("user456")
        payload = verify_token(token, expected_type="refresh")
        assert payload is not None
        assert payload["sub"] == "user456"

    def test_wrong_token_type_rejected(self) -> None:
        token = create_access_token("user123", "test@example.com")
        payload = verify_token(token, expected_type="refresh")
        assert payload is None

    def test_invalid_token_rejected(self) -> None:
        payload = verify_token("not.a.valid.token")
        assert payload is None

    def test_empty_token_rejected(self) -> None:
        payload = verify_token("")
        assert payload is None
