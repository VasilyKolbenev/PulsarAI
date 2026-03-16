"""API routes for versioned prompt management."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pulsar_ai.prompts.store import PromptStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompts", tags=["prompts"])

_store = PromptStore()


class CreatePromptRequest(BaseModel):
    name: str
    system_prompt: str
    description: str = ""
    model: str = ""
    parameters: dict | None = None
    tags: list[str] | None = None


class UpdatePromptRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class AddVersionRequest(BaseModel):
    system_prompt: str
    model: str | None = None
    parameters: dict | None = None


class TestPromptRequest(BaseModel):
    variables: dict[str, str] = {}
    version: int | None = None


@router.get("")
async def list_prompts(tag: str | None = None) -> list[dict]:
    """List all prompts, optionally filtered by tag."""
    return _store.list_all(tag=tag)


@router.post("")
async def create_prompt(req: CreatePromptRequest) -> dict:
    """Create a new prompt."""
    return _store.create(
        name=req.name,
        system_prompt=req.system_prompt,
        description=req.description,
        model=req.model,
        parameters=req.parameters,
        tags=req.tags,
    )


@router.get("/{prompt_id}")
async def get_prompt(prompt_id: str) -> dict:
    """Get a prompt with all versions."""
    p = _store.get(prompt_id)
    if not p:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return p


@router.put("/{prompt_id}")
async def update_prompt(prompt_id: str, req: UpdatePromptRequest) -> dict:
    """Update prompt metadata."""
    p = _store.update(
        prompt_id,
        name=req.name,
        description=req.description,
        tags=req.tags,
    )
    if not p:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return p


@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: str) -> dict:
    """Delete a prompt."""
    if _store.delete(prompt_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Prompt not found")


@router.post("/{prompt_id}/versions")
async def add_version(prompt_id: str, req: AddVersionRequest) -> dict:
    """Add a new version to a prompt."""
    v = _store.add_version(
        prompt_id,
        system_prompt=req.system_prompt,
        model=req.model,
        parameters=req.parameters,
    )
    if not v:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return v


@router.get("/{prompt_id}/versions/{version}")
async def get_version(prompt_id: str, version: int) -> dict:
    """Get a specific version."""
    v = _store.get_version(prompt_id, version)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return v


@router.get("/{prompt_id}/diff")
async def diff_versions(prompt_id: str, v1: int, v2: int) -> dict:
    """Diff two versions of a prompt."""
    d = _store.diff_versions(prompt_id, v1, v2)
    if not d:
        raise HTTPException(status_code=404, detail="Version not found")
    return d


@router.post("/{prompt_id}/test")
async def test_prompt(prompt_id: str, req: TestPromptRequest) -> dict:
    """Test a prompt by rendering it with variables.

    Returns the rendered prompt text (no LLM call).
    """
    version_num = req.version
    if version_num:
        v = _store.get_version(prompt_id, version_num)
    else:
        p = _store.get(prompt_id)
        if not p:
            raise HTTPException(status_code=404, detail="Prompt not found")
        v = p["versions"][-1]

    if not v:
        raise HTTPException(status_code=404, detail="Version not found")

    rendered = v["system_prompt"]
    for key, val in req.variables.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", val)

    return {
        "version": v["version"],
        "rendered": rendered,
        "variables_used": list(req.variables.keys()),
        "variables_missing": [var for var in v["variables"] if var not in req.variables],
    }
