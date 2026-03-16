"""Agent config loader — loads and resolves agent YAML configs."""

import importlib
import logging
from pathlib import Path
from typing import Any

import yaml

from pulsar_ai.config import deep_merge, load_yaml, resolve_config_path, CONFIGS_DIR

logger = logging.getLogger(__name__)

AGENT_CONFIGS_DIR = CONFIGS_DIR / "agents"


def load_agent_config(
    config_path: str,
    cli_overrides: dict[str, Any] | None = None,
) -> dict:
    """Load and resolve an agent config with inheritance.

    Args:
        config_path: Path to agent YAML config.
        cli_overrides: Optional key-value overrides.

    Returns:
        Fully resolved agent config dict.
    """
    config = load_yaml(config_path)

    # Resolve inheritance
    inherit_list = config.pop("inherit", [])
    merged: dict = {}
    for inherit_name in inherit_list:
        try:
            inherit_path = resolve_config_path(inherit_name, CONFIGS_DIR)
            inherited = load_yaml(inherit_path)
            merged = deep_merge(merged, inherited)
            logger.debug("Agent config inherited: %s", inherit_path)
        except FileNotFoundError:
            logger.warning("Inherited agent config not found: %s", inherit_name)

    merged = deep_merge(merged, config)

    # Load system prompt from file if specified
    agent_config = merged.get("agent", {})
    prompt_file = agent_config.get("system_prompt_file")
    if prompt_file and not agent_config.get("system_prompt"):
        prompt_path = Path(prompt_file)
        if not prompt_path.is_absolute():
            prompt_path = Path(config_path).parent / prompt_file
        if prompt_path.exists():
            agent_config["system_prompt"] = prompt_path.read_text(encoding="utf-8").strip()
            logger.debug("Loaded system prompt from %s", prompt_path)
        else:
            logger.warning("System prompt file not found: %s", prompt_path)
        merged["agent"] = agent_config

    # Apply CLI overrides
    if cli_overrides:
        from pulsar_ai.config import _set_nested

        for key, value in cli_overrides.items():
            _set_nested(merged, key, value)

    return merged


def load_tools_from_config(config: dict) -> list[dict[str, Any]]:
    """Extract tool definitions from agent config.

    Args:
        config: Resolved agent config dict.

    Returns:
        List of tool definition dicts with 'name', 'module', and optional 'inline'.
    """
    return config.get("tools", [])


def import_tool_module(module_path: str) -> Any:
    """Import a module containing tool definitions.

    Args:
        module_path: Dotted module path (e.g. 'pulsar_ai.agent.builtin_tools').

    Returns:
        Imported module.

    Raises:
        ImportError: If module cannot be imported.
    """
    try:
        return importlib.import_module(module_path)
    except ImportError as e:
        raise ImportError(f"Cannot import tool module '{module_path}': {e}") from e
