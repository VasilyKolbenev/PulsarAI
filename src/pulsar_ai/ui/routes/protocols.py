"""API routes for protocol management (MCP, A2A, Gateway)."""

import logging

from fastapi import APIRouter

from pulsar_ai.protocols.mcp import MCPServer, MCPServerConfig
from pulsar_ai.protocols.a2a import A2AServer, AgentCard
from pulsar_ai.protocols.gateway import APIGateway, GatewayConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/protocols", tags=["protocols"])

# ── In-memory state for demo ───────────────────────────────────────

_mcp_server: MCPServer | None = None
_a2a_server: A2AServer | None = None
_gateway: APIGateway | None = None


@router.get("/mcp/status")
def mcp_status() -> dict:
    """Get MCP server status."""
    if not _mcp_server:
        return {"configured": False}
    return {"configured": True, **_mcp_server.to_dict()}


@router.post("/mcp/configure")
def mcp_configure(body: dict) -> dict:
    """Configure MCP server from request body."""
    global _mcp_server
    config = MCPServerConfig.from_dict(body)
    _mcp_server = MCPServer(config)
    logger.info("MCP server configured: %s", config.name)
    return {"status": "ok", **_mcp_server.to_dict()}


@router.get("/a2a/agent-card")
def a2a_agent_card() -> dict:
    """Get A2A agent card."""
    if not _a2a_server:
        return {"configured": False}
    return {"configured": True, **_a2a_server.get_agent_card()}


@router.post("/a2a/configure")
def a2a_configure(body: dict) -> dict:
    """Configure A2A server from request body."""
    global _a2a_server
    card = AgentCard.from_dict(body.get("agent_card", body))
    _a2a_server = A2AServer(card)
    logger.info("A2A server configured: %s", card.name)
    return {"status": "ok", **_a2a_server.get_agent_card()}


@router.get("/gateway/status")
def gateway_status() -> dict:
    """Get API gateway status."""
    if not _gateway:
        return {"configured": False}
    return {"configured": True, **_gateway.to_dict()}


@router.post("/gateway/configure")
def gateway_configure(body: dict) -> dict:
    """Configure API gateway from request body."""
    global _gateway
    config = GatewayConfig.from_dict(body)
    _gateway = APIGateway(config)
    logger.info("API gateway configured: %s", config.name)
    return {"status": "ok", **_gateway.to_dict()}


@router.get("/summary")
def protocols_summary() -> dict:
    """Get summary of all configured protocols."""
    return {
        "mcp": {
            "configured": _mcp_server is not None,
            "name": _mcp_server.config.name if _mcp_server else None,
            "transport": _mcp_server.config.transport if _mcp_server else None,
            "tools_count": len(_mcp_server.config.tools) if _mcp_server else 0,
        },
        "a2a": {
            "configured": _a2a_server is not None,
            "name": _a2a_server.agent_card.name if _a2a_server else None,
            "skills_count": len(_a2a_server.agent_card.skills) if _a2a_server else 0,
        },
        "gateway": {
            "configured": _gateway is not None,
            "name": _gateway.config.name if _gateway else None,
            "protocols": _gateway.config.protocols if _gateway else [],
            "agents_count": len(_gateway.registered_agents) if _gateway else 0,
        },
    }
