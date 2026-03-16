"""Multi-agent router — dispatches queries to specialized agents."""

import logging
import re
from typing import Any

from pulsar_ai.agent.base import BaseAgent

logger = logging.getLogger(__name__)


class AgentRoute:
    """A route mapping queries to a specialized agent.

    Args:
        name: Route/agent name.
        agent: The BaseAgent instance for this route.
        triggers: Keywords that indicate this agent should handle the query.
        description: Human-readable description of what this agent handles.
    """

    def __init__(
        self,
        name: str,
        agent: BaseAgent,
        triggers: list[str] | None = None,
        description: str = "",
    ) -> None:
        self.name = name
        self.agent = agent
        self.triggers = [t.lower() for t in (triggers or [])]
        self.description = description

    def match_score(self, query: str) -> float:
        """Calculate how well a query matches this route.

        Uses keyword matching with word boundary awareness.

        Args:
            query: User query string.

        Returns:
            Match score between 0.0 and 1.0.
        """
        if not self.triggers:
            return 0.0

        query_lower = query.lower()
        matches = 0
        for trigger in self.triggers:
            # Word boundary matching for better precision
            pattern = r"\b" + re.escape(trigger) + r"\b"
            if re.search(pattern, query_lower):
                matches += 1

        return matches / len(self.triggers) if self.triggers else 0.0


class RouterAgent:
    """Routes queries to the most appropriate specialized agent.

    Uses keyword-based scoring with a confidence threshold.
    Falls back to a default agent when no route matches.

    Args:
        routes: List of AgentRoute instances.
        fallback: Default agent when no route matches.
        confidence_threshold: Minimum score for a route to be selected.
    """

    def __init__(
        self,
        routes: list[AgentRoute],
        fallback: BaseAgent,
        confidence_threshold: float = 0.3,
    ) -> None:
        self.routes = routes
        self.fallback = fallback
        self.confidence_threshold = confidence_threshold
        self._last_route: str | None = None

    def route(self, query: str) -> tuple[str, BaseAgent]:
        """Select the best agent for a query.

        Args:
            query: User query string.

        Returns:
            Tuple of (route_name, agent_instance).
        """
        best_route: AgentRoute | None = None
        best_score = 0.0

        for route in self.routes:
            score = route.match_score(query)
            logger.debug(
                "Route '%s' scored %.2f for query: %s",
                route.name,
                score,
                query[:50],
            )
            if score > best_score:
                best_score = score
                best_route = route

        if best_route and best_score >= self.confidence_threshold:
            self._last_route = best_route.name
            logger.info(
                "Routing to '%s' (score=%.2f): %s",
                best_route.name,
                best_score,
                query[:80],
            )
            return best_route.name, best_route.agent

        self._last_route = "fallback"
        logger.info(
            "No route matched (best=%.2f < threshold=%.2f), using fallback",
            best_score,
            self.confidence_threshold,
        )
        return "fallback", self.fallback

    def run(self, query: str) -> dict[str, Any]:
        """Route a query and run the selected agent.

        Args:
            query: User query string.

        Returns:
            Dict with 'answer', 'route', and 'trace'.
        """
        route_name, agent = self.route(query)
        answer = agent.run(query)

        return {
            "answer": answer,
            "route": route_name,
            "trace": agent.trace,
        }

    @property
    def last_route(self) -> str | None:
        """Name of the last route used."""
        return self._last_route

    @classmethod
    def from_config(
        cls,
        config: dict,
        agent_factory: dict[str, BaseAgent] | None = None,
    ) -> "RouterAgent":
        """Create a RouterAgent from config.

        Args:
            config: Router config with 'router' section.
            agent_factory: Pre-built agents keyed by name.

        Returns:
            Configured RouterAgent.

        Raises:
            ValueError: If fallback agent is not found.
        """
        router_config = config.get("router", {})
        agent_factory = agent_factory or {}

        routes: list[AgentRoute] = []
        for route_def in router_config.get("agents", []):
            name = route_def["name"]
            triggers = route_def.get("triggers", [])
            description = route_def.get("description", "")

            if name in agent_factory:
                agent = agent_factory[name]
            else:
                logger.warning("Agent '%s' not in factory, creating from config", name)
                agent_config = route_def.get("config", {})
                if isinstance(agent_config, str):
                    from pulsar_ai.agent.loader import load_agent_config

                    agent_config = load_agent_config(agent_config)
                agent = BaseAgent.from_config(agent_config)

            routes.append(
                AgentRoute(
                    name=name,
                    agent=agent,
                    triggers=triggers,
                    description=description,
                )
            )

        fallback_name = router_config.get("fallback", "")
        if fallback_name and fallback_name in agent_factory:
            fallback = agent_factory[fallback_name]
        elif routes:
            fallback = routes[0].agent
        else:
            fallback = BaseAgent.from_config(config)

        threshold = router_config.get("confidence_threshold", 0.3)

        return cls(
            routes=routes,
            fallback=fallback,
            confidence_threshold=threshold,
        )
