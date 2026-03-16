"""Tool registry and @tool decorator for agent tool calling."""

import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """A callable tool that an agent can invoke.

    Args:
        name: Unique tool identifier.
        description: Human-readable description for the LLM.
        parameters: JSON Schema dict describing expected arguments.
        func: The callable to execute when the tool is invoked.
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    func: Callable[..., str] = field(repr=False, default=lambda: "")

    def execute(self, **kwargs: Any) -> str:
        """Execute the tool with given arguments.

        Args:
            **kwargs: Tool arguments matching the parameters schema.

        Returns:
            String result of tool execution.
        """
        try:
            result = self.func(**kwargs)
            return str(result)
        except Exception as e:
            logger.error("Tool '%s' failed: %s", self.name, e)
            return f"Error: {e}"

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling format.

        Returns:
            Dict compatible with OpenAI tools API.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
                or {
                    "type": "object",
                    "properties": {},
                },
            },
        }


class ToolRegistry:
    """Registry holding available tools for an agent.

    Provides lookup, registration, and serialization of tools
    to OpenAI-compatible format for LLM tool calling.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool_obj: Tool) -> None:
        """Register a tool in the registry.

        Args:
            tool_obj: Tool instance to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool_obj.name in self._tools:
            raise ValueError(f"Tool '{tool_obj.name}' is already registered")
        self._tools[tool_obj.name] = tool_obj
        logger.debug("Registered tool: %s", tool_obj.name)

    def get(self, name: str) -> Tool:
        """Get a tool by name.

        Args:
            name: Tool name to look up.

        Returns:
            The Tool instance.

        Raises:
            KeyError: If tool is not found.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found. Available: {list(self._tools.keys())}")
        return self._tools[name]

    def list_tools(self) -> list[str]:
        """List all registered tool names.

        Returns:
            List of tool name strings.
        """
        return list(self._tools.keys())

    def to_openai_format(self) -> list[dict[str, Any]]:
        """Convert all tools to OpenAI function-calling format.

        Returns:
            List of tool dicts compatible with OpenAI API.
        """
        return [t.to_openai_format() for t in self._tools.values()]

    def to_react_prompt(self) -> str:
        """Generate tool description block for ReAct text prompting.

        Returns:
            Formatted string describing all available tools.
        """
        lines = ["You have access to the following tools:\n"]
        for t in self._tools.values():
            lines.append(f"- {t.name}: {t.description}")
            if t.parameters and t.parameters.get("properties"):
                props = t.parameters["properties"]
                params_str = ", ".join(f"{k} ({v.get('type', 'any')})" for k, v in props.items())
                lines.append(f"  Parameters: {params_str}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


def _extract_parameters_from_func(func: Callable) -> dict[str, Any]:
    """Extract JSON Schema parameters from function signature.

    Args:
        func: Function to inspect.

    Returns:
        JSON Schema dict for the function parameters.
    """
    sig = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []

    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    for name, param in sig.parameters.items():
        prop: dict[str, Any] = {}
        annotation = param.annotation

        if annotation != inspect.Parameter.empty:
            prop["type"] = type_map.get(annotation, "string")
        else:
            prop["type"] = "string"

        if param.default == inspect.Parameter.empty:
            required.append(name)
        else:
            prop["default"] = param.default

        properties[name] = prop

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def tool(name: str | None = None, description: str = "") -> Callable[[Callable[..., str]], Tool]:
    """Decorator to create a Tool from a function.

    Args:
        name: Tool name (defaults to function name).
        description: Tool description (defaults to function docstring).

    Returns:
        Decorator that wraps a function into a Tool instance.

    Example:
        @tool(name="add", description="Add two numbers")
        def add(a: int, b: int) -> str:
            return str(a + b)
    """

    def decorator(func: Callable[..., str]) -> Tool:
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "").strip()
        parameters = _extract_parameters_from_func(func)

        return Tool(
            name=tool_name,
            description=tool_desc,
            parameters=parameters,
            func=func,
        )

    return decorator
