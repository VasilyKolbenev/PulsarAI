"""Guardrails configuration for agent safety and resource limits."""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GuardrailsConfig:
    """Safety and resource limits for agent execution.

    Args:
        max_iterations: Maximum ReAct loop iterations before forced stop.
        max_tokens: Maximum total tokens for a single agent run.
        banned_tools: Tool names the agent is not allowed to call.
        require_confirmation: Tool names that require user confirmation.
        max_tool_retries: Max retries per tool call on failure.
    """

    max_iterations: int = 15
    max_tokens: int = 8192
    banned_tools: list[str] = field(default_factory=list)
    require_confirmation: list[str] = field(default_factory=list)
    max_tool_retries: int = 2

    def check_iteration(self, current: int) -> bool:
        """Check if the current iteration is within limits.

        Args:
            current: Current iteration number (0-indexed).

        Returns:
            True if within limits, False if exceeded.
        """
        if current >= self.max_iterations:
            logger.warning("Agent hit max iterations limit (%d)", self.max_iterations)
            return False
        return True

    def check_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed to be called.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if allowed, False if banned.
        """
        if tool_name in self.banned_tools:
            logger.warning("Tool '%s' is banned by guardrails", tool_name)
            return False
        return True

    def needs_confirmation(self, tool_name: str) -> bool:
        """Check if a tool requires user confirmation.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if confirmation required.
        """
        return tool_name in self.require_confirmation

    @classmethod
    def from_config(cls, config: dict) -> "GuardrailsConfig":
        """Create GuardrailsConfig from a config dict.

        Args:
            config: Dict with guardrails settings.

        Returns:
            GuardrailsConfig instance.
        """
        guardrails = config.get("guardrails", {})
        return cls(
            max_iterations=guardrails.get("max_iterations", 15),
            max_tokens=guardrails.get("max_tokens", 8192),
            banned_tools=guardrails.get("banned_tools", []),
            require_confirmation=guardrails.get("require_confirmation", []),
            max_tool_retries=guardrails.get("max_tool_retries", 2),
        )
