"""User management with bcrypt password hashing.

Provides CRUD and authentication for the ``users`` table.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

import bcrypt

from pulsar_ai.storage.database import Database, get_database

logger = logging.getLogger(__name__)


class UserStore:
    """Manages user accounts with secure password hashing.

    Args:
        db: Database instance. Falls back to the module singleton.
    """

    def __init__(self, db: Optional[Database] = None) -> None:
        self._db = db or get_database()

    def create_user(
        self,
        email: str,
        password: str,
        name: str = "",
        role: str = "user",
    ) -> dict:
        """Create a new user account.

        Args:
            email: Unique email address.
            password: Plaintext password (will be hashed).
            name: Display name.
            role: User role (``user`` or ``admin``).

        Returns:
            Dict with user fields (no password_hash).

        Raises:
            ValueError: If email is already registered.
        """
        existing = self._db.fetch_one(
            "SELECT id FROM users WHERE email = ?", (email,)
        )
        if existing:
            raise ValueError(f"Email already registered: {email}")

        user_id = str(uuid.uuid4())[:8]
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        now_iso = datetime.now().isoformat()

        self._db.execute(
            """
            INSERT INTO users (id, email, password_hash, name, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, email, password_hash, name, role, now_iso),
        )
        self._db.commit()
        logger.info("Created user '%s' (%s)", email, role)

        return {
            "id": user_id,
            "email": email,
            "name": name,
            "role": role,
            "created_at": now_iso,
        }

    def authenticate(self, email: str, password: str) -> Optional[dict]:
        """Verify email/password and return user dict on success.

        Args:
            email: User email.
            password: Plaintext password.

        Returns:
            User dict if credentials valid, None otherwise.
        """
        row = self._db.fetch_one(
            "SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)
        )
        if not row:
            return None

        stored_hash = row["password_hash"].encode("utf-8")
        if not bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            return None

        # Update last login
        self._db.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (datetime.now().isoformat(), row["id"]),
        )
        self._db.commit()

        return {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "role": row["role"],
            "created_at": row["created_at"],
        }

    def get_by_id(self, user_id: str) -> Optional[dict]:
        """Get user by ID.

        Args:
            user_id: User ID.

        Returns:
            User dict or None.
        """
        row = self._db.fetch_one(
            "SELECT id, email, name, role, created_at, last_login_at "
            "FROM users WHERE id = ? AND is_active = 1",
            (user_id,),
        )
        return dict(row) if row else None

    def list_users(self) -> list[dict]:
        """List all active users.

        Returns:
            List of user dicts (no password_hash).
        """
        rows = self._db.fetch_all(
            "SELECT id, email, name, role, created_at, last_login_at "
            "FROM users WHERE is_active = 1 ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]

    def update_user(
        self,
        user_id: str,
        name: Optional[str] = None,
        role: Optional[str] = None,
    ) -> bool:
        """Update user profile fields.

        Args:
            user_id: Target user ID.
            name: New display name.
            role: New role.

        Returns:
            True if user was updated.
        """
        updates: list[str] = []
        params: list[str] = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if role is not None:
            updates.append("role = ?")
            params.append(role)
        if not updates:
            return False

        params.append(user_id)
        cursor = self._db.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        self._db.commit()
        return cursor.rowcount > 0

    def deactivate_user(self, user_id: str) -> bool:
        """Soft-delete a user.

        Args:
            user_id: Target user ID.

        Returns:
            True if user was deactivated.
        """
        cursor = self._db.execute(
            "UPDATE users SET is_active = 0 WHERE id = ?", (user_id,)
        )
        self._db.commit()
        return cursor.rowcount > 0
