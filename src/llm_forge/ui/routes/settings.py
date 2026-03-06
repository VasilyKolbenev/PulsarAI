"""Settings API routes: server info and API key management."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/settings", tags=["settings"])


class GenerateKeyRequest(BaseModel):
    """Request body for API key generation."""

    name: str = "default"


@router.get("")
async def get_settings(request: Request) -> dict:
    """Get server configuration info."""
    cors_env = os.environ.get("FORGE_CORS_ORIGINS", "")
    cors_origins = (
        [o.strip() for o in cors_env.split(",") if o.strip()]
        if cors_env
        else ["http://localhost:3000", "http://localhost:8888"]
    )
    return {
        "version": "0.1.0",
        "auth_enabled": getattr(request.app.state, "auth_enabled", False),
        "stand_mode": getattr(request.app.state, "stand_mode", "dev"),
        "env_profile": os.environ.get("FORGE_ENV_FILE", ".env"),
        "cors_origins": cors_origins,
        "data_dir": str(Path("./data").resolve()),
    }


@router.get("/keys")
async def list_keys(request: Request) -> list[dict]:
    """List API key names (no secrets)."""
    key_store = getattr(request.app.state, "key_store", None)
    if key_store is None:
        return []
    return key_store.list_keys()


@router.post("/keys")
async def generate_key(request: Request, req: GenerateKeyRequest) -> dict:
    """Generate a new API key. Returns the plaintext key once."""
    key_store = getattr(request.app.state, "key_store", None)
    if key_store is None:
        raise HTTPException(status_code=500, detail="Key store not initialized")
    raw_key = key_store.generate_key(req.name)
    return {"name": req.name, "key": raw_key}


@router.delete("/keys/{name}")
async def revoke_key(request: Request, name: str) -> dict:
    """Revoke all API keys with the given name."""
    key_store = getattr(request.app.state, "key_store", None)
    if key_store is None:
        raise HTTPException(status_code=500, detail="Key store not initialized")
    if key_store.revoke(name):
        return {"status": "revoked", "name": name}
    raise HTTPException(status_code=404, detail=f"Key '{name}' not found")
