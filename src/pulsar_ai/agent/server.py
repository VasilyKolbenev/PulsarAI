"""FastAPI server for agent interaction via REST API."""

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# Lazy imports — fastapi/uvicorn are optional dependencies
_app = None


def _get_app() -> Any:
    """Get or create the FastAPI app instance.

    Returns:
        FastAPI app.

    Raises:
        ImportError: If fastapi is not installed.
    """
    global _app
    if _app is not None:
        return _app

    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError as e:
        raise ImportError(
            "FastAPI is required for agent serving. "
            "Install it with: pip install pulsar-ai[agent-serve]"
        ) from e

    _app = FastAPI(
        title="Pulsar AI Agent Server",
        description="REST API for interacting with fine-tuned LLM agents",
        version="0.1.0",
    )
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return _app


# Module-level state for the running agent
_agent_instance = None
_agent_config: dict = {}
_sessions: dict[str, Any] = {}


def create_agent_app(config: dict) -> Any:
    """Create a FastAPI app configured with an agent.

    Args:
        config: Resolved agent config dict.

    Returns:
        FastAPI application instance with agent endpoints.
    """
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    from pulsar_ai.agent.base import BaseAgent
    from pulsar_ai.agent.builtin_tools import get_default_registry
    from pulsar_ai.agent.guardrails import GuardrailsConfig
    from pulsar_ai.agent.memory import ShortTermMemory

    app = FastAPI(
        title="Pulsar AI Agent Server",
        description="REST API for interacting with fine-tuned LLM agents",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Session storage: session_id -> BaseAgent
    sessions: dict[str, BaseAgent] = {}
    tools = get_default_registry()

    class ChatRequest(BaseModel):
        message: str
        session_id: str | None = None

    class ChatResponse(BaseModel):
        answer: str
        session_id: str
        trace: list[dict[str, Any]] = []

    class ToolInfo(BaseModel):
        name: str
        description: str

    class HealthResponse(BaseModel):
        status: str
        agent_name: str
        tools_count: int
        active_sessions: int

    def _get_or_create_session(session_id: str | None) -> tuple[str, BaseAgent]:
        """Get an existing session or create a new one.

        Args:
            session_id: Optional session ID.

        Returns:
            Tuple of (session_id, agent_instance).
        """
        if session_id and session_id in sessions:
            return session_id, sessions[session_id]

        new_id = session_id or str(uuid.uuid4())
        agent = BaseAgent.from_config(config, tools=tools)
        sessions[new_id] = agent
        logger.info("Created new session: %s", new_id)
        return new_id, agent

    @app.get("/v1/agent/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Check server health and agent status."""
        agent_name = config.get("agent", {}).get("name", "unknown")
        return HealthResponse(
            status="ok",
            agent_name=agent_name,
            tools_count=len(tools),
            active_sessions=len(sessions),
        )

    @app.post("/v1/agent/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        """Send a message to the agent and get a response.

        Args:
            request: Chat request with message and optional session_id.

        Returns:
            Agent response with answer and trace.
        """
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        session_id, agent = _get_or_create_session(request.session_id)

        try:
            answer = agent.run(request.message)
            return ChatResponse(
                answer=answer,
                session_id=session_id,
                trace=agent.trace,
            )
        except ConnectionError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Model server unreachable: {e}",
            )
        except Exception as e:
            logger.exception("Agent error in session %s", session_id)
            raise HTTPException(
                status_code=500,
                detail=f"Agent error: {e}",
            )

    @app.get("/v1/agent/tools", response_model=list[ToolInfo])
    def list_tools() -> list[ToolInfo]:
        """List all available agent tools."""
        return [
            ToolInfo(name=name, description=tools.get(name).description)
            for name in tools.list_tools()
        ]

    @app.delete("/v1/agent/sessions/{session_id}")
    def delete_session(session_id: str) -> dict[str, str]:
        """Delete a session and free memory.

        Args:
            session_id: Session to delete.

        Returns:
            Confirmation message.
        """
        if session_id in sessions:
            del sessions[session_id]
            return {"status": "deleted", "session_id": session_id}
        raise HTTPException(status_code=404, detail="Session not found")

    return app


def start_agent_server(config: dict, host: str = "0.0.0.0", port: int = 8081) -> None:
    """Start the agent server.

    Args:
        config: Resolved agent config dict.
        host: Server host.
        port: Server port.
    """
    try:
        import uvicorn
    except ImportError as e:
        raise ImportError(
            "uvicorn is required for agent serving. "
            "Install it with: pip install pulsar-ai[agent-serve]"
        ) from e

    app = create_agent_app(config)
    logger.info("Starting agent server on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
