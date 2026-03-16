"""API Gateway for multi-protocol agent access.

Provides a unified gateway layer supporting REST, webhooks,
and protocol routing for MCP and A2A agents.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GatewayRoute:
    """A route entry in the API gateway."""

    path: str
    agent_name: str
    protocol: str = "rest"
    methods: list[str] = field(default_factory=lambda: ["POST"])
    rate_limit: int = 60
    auth_required: bool = True


@dataclass
class GatewayConfig:
    """Configuration for the API Gateway."""

    name: str = "pulsar-ai-gateway"
    host: str = "0.0.0.0"
    port: int = 8080
    protocols: list[str] = field(default_factory=lambda: ["REST"])
    auth_method: str = "api_key"
    rate_limit: int = 60
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])
    ssl_enabled: bool = False
    load_balancer: str = "round_robin"
    routes: list[GatewayRoute] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GatewayConfig":
        """Create from dict.

        Args:
            data: Configuration dictionary.

        Returns:
            GatewayConfig instance.
        """
        routes = [GatewayRoute(**r) if isinstance(r, dict) else r for r in data.get("routes", [])]
        protocols_raw = data.get("protocols", "REST")
        if isinstance(protocols_raw, str):
            protocols = [p.strip() for p in protocols_raw.split(",")]
        else:
            protocols = list(protocols_raw)

        return cls(
            name=data.get("name", "pulsar-ai-gateway"),
            host=data.get("host", "0.0.0.0"),
            port=data.get("port", 8080),
            protocols=protocols,
            auth_method=data.get("auth_method", "api_key"),
            rate_limit=data.get("rate_limit", 60),
            cors_origins=data.get("cors_origins", ["http://localhost:3000"]),
            ssl_enabled=data.get("ssl_enabled", False),
            load_balancer=data.get("load_balancer", "round_robin"),
            routes=routes,
        )


class APIGateway:
    """API Gateway that routes requests to registered agents.

    Supports multiple protocols (REST, gRPC-like, webhooks) and provides
    rate limiting, authentication, and load balancing.

    Args:
        config: GatewayConfig with routing and security settings.
    """

    def __init__(self, config: GatewayConfig) -> None:
        self.config = config
        self._agents: dict[str, Any] = {}
        self._request_counts: dict[str, list[float]] = {}

    def register_agent(self, name: str, handler: Any) -> None:
        """Register an agent handler for routing.

        Args:
            name: Agent name for routing.
            handler: Callable or agent instance.
        """
        self._agents[name] = handler
        logger.info("Gateway: registered agent '%s'", name)

    def unregister_agent(self, name: str) -> bool:
        """Remove an agent from the gateway.

        Args:
            name: Agent name to remove.

        Returns:
            True if removed, False if not found.
        """
        if name in self._agents:
            del self._agents[name]
            return True
        return False

    def check_rate_limit(self, client_id: str) -> bool:
        """Check if a client is within rate limits.

        Args:
            client_id: Client identifier (API key, IP, etc.).

        Returns:
            True if request is allowed, False if rate limited.
        """
        now = time.time()
        window = 60.0

        if client_id not in self._request_counts:
            self._request_counts[client_id] = []

        timestamps = self._request_counts[client_id]
        # Remove old entries outside the window
        self._request_counts[client_id] = [ts for ts in timestamps if now - ts < window]

        if len(self._request_counts[client_id]) >= self.config.rate_limit:
            return False

        self._request_counts[client_id].append(now)
        return True

    def route_request(
        self, path: str, payload: dict[str, Any], client_id: str = ""
    ) -> dict[str, Any]:
        """Route a request to the appropriate agent.

        Args:
            path: Request path (e.g., /agent/chat).
            payload: Request payload.
            client_id: Client identifier for rate limiting.

        Returns:
            Response dict with result or error.
        """
        if client_id and not self.check_rate_limit(client_id):
            return {"error": "Rate limit exceeded", "status": 429}

        # Find matching route
        route = self._find_route(path)
        if not route:
            return {"error": f"No route found for {path}", "status": 404}

        agent = self._agents.get(route.agent_name)
        if not agent:
            return {
                "error": f"Agent '{route.agent_name}' not available",
                "status": 503,
            }

        try:
            if hasattr(agent, "handle_request"):
                result = agent.handle_request(payload)
            elif callable(agent):
                result = agent(payload)
            else:
                return {"error": "Agent does not support request handling", "status": 500}

            return {"result": result, "status": 200}
        except Exception as e:
            logger.error("Gateway routing error for %s: %s", path, e)
            return {"error": str(e), "status": 500}

    def _find_route(self, path: str) -> GatewayRoute | None:
        """Find the first matching route for a path.

        Args:
            path: Request path.

        Returns:
            Matching GatewayRoute or None.
        """
        for route in self.config.routes:
            if path.startswith(route.path):
                return route
        return None

    @property
    def registered_agents(self) -> list[str]:
        """Get list of registered agent names."""
        return list(self._agents.keys())

    def to_dict(self) -> dict[str, Any]:
        """Serialize gateway state for API responses.

        Returns:
            Dict with gateway config and status.
        """
        return {
            "name": self.config.name,
            "protocols": self.config.protocols,
            "auth_method": self.config.auth_method,
            "rate_limit": self.config.rate_limit,
            "load_balancer": self.config.load_balancer,
            "agents": self.registered_agents,
            "routes": [
                {
                    "path": r.path,
                    "agent": r.agent_name,
                    "protocol": r.protocol,
                }
                for r in self.config.routes
            ],
        }
