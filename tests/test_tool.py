"""Tests for agent tool registry and @tool decorator."""

import pytest

from pulsar_ai.agent.tool import Tool, ToolRegistry, tool


def _dummy_tool_func(query: str) -> str:
    return f"result for {query}"


class TestTool:
    """Tests for Tool dataclass."""

    def test_execute_returns_string(self) -> None:
        t = Tool(name="search", description="Search", func=_dummy_tool_func)
        result = t.execute(query="hello")
        assert result == "result for hello"

    def test_execute_handles_exception(self) -> None:
        def bad_func() -> str:
            raise ValueError("boom")

        t = Tool(name="bad", description="Breaks", func=bad_func)
        result = t.execute()
        assert "Error:" in result
        assert "boom" in result

    def test_to_openai_format(self) -> None:
        t = Tool(
            name="search",
            description="Search files",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        )
        fmt = t.to_openai_format()
        assert fmt["type"] == "function"
        assert fmt["function"]["name"] == "search"
        assert fmt["function"]["description"] == "Search files"
        assert "query" in fmt["function"]["parameters"]["properties"]

    def test_to_openai_format_empty_parameters(self) -> None:
        t = Tool(name="noop", description="No-op")
        fmt = t.to_openai_format()
        assert fmt["function"]["parameters"]["type"] == "object"


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_and_get(self) -> None:
        registry = ToolRegistry()
        t = Tool(name="search", description="Search", func=_dummy_tool_func)
        registry.register(t)
        assert registry.get("search") is t

    def test_register_duplicate_raises(self) -> None:
        registry = ToolRegistry()
        t = Tool(name="search", description="Search", func=_dummy_tool_func)
        registry.register(t)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(t)

    def test_get_missing_raises(self) -> None:
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="not found"):
            registry.get("missing")

    def test_list_tools(self) -> None:
        registry = ToolRegistry()
        registry.register(Tool(name="a", description="A", func=_dummy_tool_func))
        registry.register(Tool(name="b", description="B", func=_dummy_tool_func))
        assert registry.list_tools() == ["a", "b"]

    def test_len(self) -> None:
        registry = ToolRegistry()
        assert len(registry) == 0
        registry.register(Tool(name="a", description="A", func=_dummy_tool_func))
        assert len(registry) == 1

    def test_contains(self) -> None:
        registry = ToolRegistry()
        registry.register(Tool(name="search", description="S", func=_dummy_tool_func))
        assert "search" in registry
        assert "missing" not in registry

    def test_to_openai_format(self) -> None:
        registry = ToolRegistry()
        registry.register(Tool(name="a", description="A", func=_dummy_tool_func))
        registry.register(Tool(name="b", description="B", func=_dummy_tool_func))
        fmt = registry.to_openai_format()
        assert len(fmt) == 2
        assert fmt[0]["function"]["name"] == "a"

    def test_to_react_prompt(self) -> None:
        registry = ToolRegistry()
        registry.register(
            Tool(
                name="search",
                description="Search for files",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
                func=_dummy_tool_func,
            )
        )
        prompt = registry.to_react_prompt()
        assert "search" in prompt
        assert "Search for files" in prompt
        assert "query" in prompt


class TestToolDecorator:
    """Tests for @tool decorator."""

    def test_basic_decorator(self) -> None:
        @tool(name="add", description="Add two numbers")
        def add(a: int, b: int) -> str:
            return str(a + b)

        assert isinstance(add, Tool)
        assert add.name == "add"
        assert add.description == "Add two numbers"
        assert add.execute(a=2, b=3) == "5"

    def test_decorator_infers_name_from_function(self) -> None:
        @tool()
        def my_search(query: str) -> str:
            """Search for things."""
            return query

        assert my_search.name == "my_search"
        assert my_search.description == "Search for things."

    def test_decorator_extracts_parameters(self) -> None:
        @tool(name="calc")
        def calc(expression: str, precision: int = 2) -> str:
            return expression

        params = calc.parameters
        assert params["type"] == "object"
        assert "expression" in params["properties"]
        assert "precision" in params["properties"]
        assert "expression" in params["required"]
        assert "precision" not in params.get("required", [])
