"""Authentication API routes: login, register, refresh, me.

Mounted at ``/api/v1/auth``.
"""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pulsar_ai.storage.user_store import UserStore
from pulsar_ai.ui.jwt_utils import (
    create_access_token,
    create_refresh_token,
    verify_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_user_store: UserStore | None = None


def _get_store() -> UserStore:
    global _user_store  # noqa: PLW0603
    if _user_store is None:
        _user_store = UserStore()
    return _user_store


# ── Request / Response models ────────────────────────────────────


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> dict:
    """Authenticate with email and password, receive JWT tokens."""
    store = _get_store()
    user = store.authenticate(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(user["id"], user["email"], user["role"])
    refresh_token = create_refresh_token(user["id"])

    logger.info("User '%s' logged in", body.email)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest) -> dict:
    """Register a new user account."""
    store = _get_store()
    try:
        user = store.create_user(
            email=body.email,
            password=body.password,
            name=body.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    access_token = create_access_token(user["id"], user["email"], user["role"])
    refresh_token = create_refresh_token(user["id"])

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest) -> dict:
    """Exchange a refresh token for new access + refresh tokens."""
    payload = verify_token(body.refresh_token, expected_type="refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    store = _get_store()
    user = store.get_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(user["id"], user["email"], user["role"])
    new_refresh = create_refresh_token(user["id"])

    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me")
async def me(request: Request) -> dict:
    """Get current authenticated user."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
