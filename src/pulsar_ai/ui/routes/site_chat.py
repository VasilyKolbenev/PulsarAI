"""Chat proxy endpoint for the marketing landing page.

Proxies chat messages to OpenAI GPT-4o-mini with Pulsar AI product context.
"""

import logging
import os
import time
import uuid
from collections import defaultdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pulsar_ai.storage.session_store import SessionStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/site", tags=["site-chat"])

_session_store = SessionStore()
_rate_limits: dict[str, list[float]] = defaultdict(list)

MAX_HISTORY = 20
RATE_LIMIT = 10  # requests per minute
RATE_WINDOW = 60  # seconds

SYSTEM_PROMPT = """You are the Pulsar AI assistant on the product landing page.
Pulsar AI is a self-hosted, open-source platform for the full LLM lifecycle.

Key facts about Pulsar AI:
- Full-cycle platform: data preparation, fine-tuning (SFT + DPO), evaluation, deployment, monitoring
- 26 visual workflow node types in 7 categories: Data, Training, Agent, Protocols, Safety, Evaluation, Ops
- Visual DAG pipeline builder with C4-style grouping
- Built-in agent framework with ReAct + LangGraph, CrewAI, AutoGen support
- Protocol support: MCP (Model Context Protocol), A2A (Agent-to-Agent), API Gateway
- Guardrails engine: PII detection/masking, prompt injection defense, toxicity filtering
- LLM-as-Judge evaluation, A/B testing, canary deployment
- Observability: tracing, cost tracking, semantic cache
- Human feedback collection with DPO export (closed-loop flywheel)
- 809+ tests, production-ready
- Tech stack: FastAPI + React 19 + TypeScript + PyTorch + Transformers
- Serving: vLLM, llama.cpp, TGI, Ollama
- Self-hosted, Docker deployment available
- Open source (Apache 2.0 license)

Deployment & Pricing:
- Cloud (SaaS): From $49/user/month — managed platform, API access to GPT-4o/Claude/Llama/Mistral, auto-scaling GPU, fine-tuning as a service, free tier (2 GPU-hours/month)
- Self-Hosted: Custom pricing — turnkey on-premise deployment, air-gapped networks, Docker/Kubernetes, SSO/SAML, SOC2/HIPAA, dedicated support

Be helpful, concise, and professional. Answer questions about the product features,
pricing, deployment, and technical capabilities. If asked about something unrelated
to Pulsar AI, politely redirect the conversation. Respond in the same language as
the user's message."""


class ChatRequest(BaseModel):
    """Chat request from landing page widget."""

    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Chat response to landing page widget."""

    reply: str
    session_id: str


def _check_rate_limit(session_id: str) -> bool:
    """Check if session is within rate limit.

    Args:
        session_id: The session identifier.

    Returns:
        True if request is allowed, False if rate limited.
    """
    now = time.time()
    timestamps = _rate_limits[session_id]
    # Clean old entries
    _rate_limits[session_id] = [t for t in timestamps if now - t < RATE_WINDOW]
    if len(_rate_limits[session_id]) >= RATE_LIMIT:
        return False
    _rate_limits[session_id].append(now)
    return True


def _get_openai_key() -> str | None:
    """Get OpenAI API key from environment."""
    return os.environ.get("OPENAI_API_KEY", "").strip() or None


async def _call_openai(messages: list[dict[str, str]]) -> str:
    """Call OpenAI Chat Completions API.

    Args:
        messages: List of message dicts with role and content.

    Returns:
        Assistant reply text.

    Raises:
        HTTPException: If API call fails.
    """
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed, cannot call OpenAI API")
        raise HTTPException(
            status_code=503,
            detail="Chat service unavailable (httpx not installed)",
        )

    api_key = _get_openai_key()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Chat service unavailable (no API key configured)",
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            logger.error("OpenAI API error: %s %s", exc.response.status_code, exc.response.text)
            raise HTTPException(
                status_code=502,
                detail="Chat service error",
            )
        except (httpx.RequestError, KeyError, IndexError) as exc:
            logger.error("OpenAI request failed: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="Chat service temporarily unavailable",
            )


@router.post("/chat")
async def site_chat(req: ChatRequest) -> ChatResponse:
    """Handle chat message from landing page widget.

    Args:
        req: Chat request with message and optional session_id.

    Returns:
        Chat response with reply and session_id.
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session_id = req.session_id or str(uuid.uuid4())

    if not _check_rate_limit(session_id):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment.",
        )

    # Get or create persistent session
    session = _session_store.get_or_create(
        session_id, session_type="site_chat", ttl_hours=4
    )
    history = session["messages"]

    # Add user message
    _session_store.append_message(
        session_id, "user", req.message.strip(), max_messages=MAX_HISTORY
    )
    history.append({"role": "user", "content": req.message.strip()})

    # Trim local copy for OpenAI call
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    # Build messages for OpenAI
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    # Check if API key is available
    if not _get_openai_key():
        fallback = (
            "Thank you for your interest in Pulsar AI! Our AI assistant requires "
            "an OpenAI API key to be configured. Please use the consultation form "
            "below to get in touch with our team, or visit our GitHub repository "
            "for documentation."
        )
        _session_store.append_message(
            session_id, "assistant", fallback, max_messages=MAX_HISTORY
        )
        return ChatResponse(reply=fallback, session_id=session_id)

    reply = await _call_openai(messages)

    # Save assistant reply
    _session_store.append_message(
        session_id, "assistant", reply, max_messages=MAX_HISTORY
    )

    return ChatResponse(reply=reply, session_id=session_id)


@router.get("/chat/status")
async def chat_status() -> dict:
    """Check chat service availability."""
    has_key = _get_openai_key() is not None
    sessions = _session_store.list_sessions(session_type="site_chat")
    return {
        "available": has_key,
        "model": "gpt-4o-mini" if has_key else None,
        "active_sessions": len(sessions),
    }
