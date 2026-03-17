"""JWT token creation and verification for Pulsar AI.

Uses HS256 symmetric signing with a configurable secret.
Access tokens are short-lived (30 min), refresh tokens longer (7 days).
"""

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

logger = logging.getLogger(__name__)

# Configurable via environment
_JWT_SECRET: Optional[str] = None
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def _get_secret() -> str:
    """Get the JWT secret, generating a random one if not configured."""
    global _JWT_SECRET  # noqa: PLW0603
    if _JWT_SECRET is None:
        _JWT_SECRET = os.environ.get("PULSAR_JWT_SECRET", "").strip()
        if not _JWT_SECRET:
            _JWT_SECRET = secrets.token_urlsafe(48)
            logger.warning(
                "PULSAR_JWT_SECRET not set — using random secret. "
                "Tokens will be invalidated on restart."
            )
    return _JWT_SECRET


def create_access_token(
    user_id: str,
    email: str,
    role: str = "user",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a short-lived access token.

    Args:
        user_id: User ID to encode in the token.
        email: User email.
        role: User role.
        expires_delta: Custom expiration. Defaults to 30 minutes.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token.

    Args:
        user_id: User ID to encode.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def verify_token(token: str, expected_type: str = "access") -> Optional[dict]:
    """Verify and decode a JWT token.

    Args:
        token: Encoded JWT string.
        expected_type: Expected token type (``access`` or ``refresh``).

    Returns:
        Decoded payload dict, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != expected_type:
            logger.debug("Token type mismatch: expected %s, got %s", expected_type, payload.get("type"))
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except jwt.InvalidTokenError as exc:
        logger.debug("Invalid token: %s", exc)
        return None
