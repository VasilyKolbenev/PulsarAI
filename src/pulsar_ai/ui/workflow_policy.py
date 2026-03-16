"""Governance policy validation for workflow and pipeline runs."""

from typing import Any

_GOVERNANCE_TYPES = {"agent", "a2a", "router", "gateway"}
_HIGH_RISK_LEVELS = {"high", "critical"}


def validate_workflow_nodes(nodes: list[dict[str, Any]]) -> list[str]:
    """Validate governance constraints for visual workflow nodes.

    Rule: for governance node types, risk_level in {high, critical}
    requires requires_approval=True.

    Args:
        nodes: React Flow node dicts.

    Returns:
        List of violation descriptions.
    """
    violations: list[str] = []

    for node in nodes:
        node_type = str(node.get("type", ""))
        if node_type not in _GOVERNANCE_TYPES:
            continue

        data = node.get("data", {}) or {}
        config = data.get("config", {}) or {}

        risk = str(config.get("risk_level", "medium")).lower()
        requires_approval = bool(config.get("requires_approval", False))

        if risk in _HIGH_RISK_LEVELS and not requires_approval:
            label = str(data.get("label", node.get("id", "unknown")))
            violations.append(f"{label} ({node_type}, risk={risk})")

    return violations


def validate_pipeline_config(pipeline_config: dict[str, Any]) -> list[str]:
    """Validate governance constraints for pipeline config steps.

    Args:
        pipeline_config: Parsed pipeline config with steps.

    Returns:
        List of violation descriptions.
    """
    violations: list[str] = []
    steps = pipeline_config.get("steps", []) or []

    for step in steps:
        step_type = str(step.get("type", ""))
        if step_type not in _GOVERNANCE_TYPES:
            continue

        config = step.get("config", {}) or {}
        risk = str(config.get("risk_level", "medium")).lower()
        requires_approval = bool(config.get("requires_approval", False))

        if risk in _HIGH_RISK_LEVELS and not requires_approval:
            name = str(step.get("name", "unknown"))
            violations.append(f"{name} ({step_type}, risk={risk})")

    return violations


def format_governance_error(violations: list[str]) -> str:
    """Format a user-facing governance validation error."""
    return (
        "Approval required: nodes/steps with high or critical risk must set "
        f"requires_approval=true. Invalid: {', '.join(violations)}"
    )
