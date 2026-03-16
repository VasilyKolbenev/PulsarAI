"""MCP (Model Context Protocol) server and client adapters.

Provides tool exposure and consumption through the Model Context Protocol,
supporting stdio, SSE, and streamable HTTP transports.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MCPToolDefinition:
    """Definition of a tool exposed through MCP."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server instance."""

    name: str = "pulsar-ai"
    transport: str = "stdio"
    host: str = "localhost"
    port: int = 3001
    tools: list[MCPToolDefinition] = field(default_factory=list)
    auth_token_env: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPServerConfig":
        """Create config from a dict.

        Args:
            data: Configuration dictionary.

        Returns:
            MCPServerConfig instance.
        """
        tools = [
            MCPToolDefinition(**t) if isinstance(t, dict) else t for t in data.get("tools", [])
        ]
        return cls(
            name=data.get("name", "pulsar-ai"),
            transport=data.get("transport", "stdio"),
            host=data.get("host", "localhost"),
            port=data.get("port", 3001),
            tools=tools,
            auth_token_env=data.get("auth_token_env", ""),
        )


class MCPServer:
    """MCP Server that exposes agent tools to external clients.

    Implements the Model Context Protocol server side, allowing
    other agents/applications to discover and invoke tools.

    Args:
        config: MCPServerConfig with transport and tool definitions.
        tool_handler: Callable that executes tool calls, signature:
            (tool_name: str, arguments: dict) -> Any
    """

    def __init__(
        self,
        config: MCPServerConfig,
        tool_handler: Any | None = None,
    ) -> None:
        self.config = config
        self._tool_handler = tool_handler
        self._running = False

    @property
    def tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions in MCP format.

        Returns:
            List of tool definition dicts.
        """
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema or {"type": "object", "properties": {}},
            }
            for t in self.config.tools
        ]

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle an incoming MCP JSON-RPC request.

        Args:
            request: JSON-RPC request dict with method and params.

        Returns:
            JSON-RPC response dict.
        """
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return self._rpc_response(
                req_id,
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {
                        "tools": {"listChanged": False},
                    },
                    "serverInfo": {
                        "name": self.config.name,
                        "version": "1.0.0",
                    },
                },
            )

        if method == "tools/list":
            return self._rpc_response(
                req_id,
                {
                    "tools": self.tool_definitions,
                },
            )

        if method == "tools/call":
            return self._handle_tool_call(req_id, params)

        return self._rpc_error(req_id, -32601, f"Method not found: {method}")

    def _handle_tool_call(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle a tools/call request.

        Args:
            req_id: JSON-RPC request ID.
            params: Request params with name and arguments.

        Returns:
            JSON-RPC response with tool result.
        """
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        known_names = {t.name for t in self.config.tools}
        if tool_name not in known_names:
            return self._rpc_error(req_id, -32602, f"Unknown tool: {tool_name}")

        if not self._tool_handler:
            return self._rpc_error(req_id, -32603, "No tool handler configured")

        try:
            result = self._tool_handler(tool_name, arguments)
            content = result if isinstance(result, str) else json.dumps(result)
            return self._rpc_response(
                req_id,
                {
                    "content": [{"type": "text", "text": content}],
                },
            )
        except Exception as e:
            logger.error("Tool execution failed: %s — %s", tool_name, e)
            return self._rpc_response(
                req_id,
                {
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "isError": True,
                },
            )

    @staticmethod
    def _rpc_response(req_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    @staticmethod
    def _rpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize server state for API responses.

        Returns:
            Dict with server config and tool definitions.
        """
        return {
            "name": self.config.name,
            "transport": self.config.transport,
            "host": self.config.host,
            "port": self.config.port,
            "tools": self.tool_definitions,
            "running": self._running,
        }


@dataclass
class MCPClientConfig:
    """Configuration for connecting to a remote MCP server."""

    endpoint_url: str = ""
    transport: str = "streamable_http"
    auth_token_env: str = ""
    timeout: int = 30

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPClientConfig":
        """Create config from a dict."""
        return cls(
            endpoint_url=data.get("endpoint_url", ""),
            transport=data.get("transport", "streamable_http"),
            auth_token_env=data.get("auth_token_env", ""),
            timeout=data.get("timeout", 30),
        )


class MCPClient:
    """MCP Client that discovers and invokes tools on a remote MCP server.

    Args:
        config: MCPClientConfig with endpoint and auth details.
    """

    def __init__(self, config: MCPClientConfig) -> None:
        self.config = config
        self._tools: list[dict[str, Any]] = []
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def build_request(self, method: str, params: dict | None = None) -> dict:
        """Build a JSON-RPC request for the MCP server.

        Args:
            method: MCP method name.
            params: Optional parameters.

        Returns:
            JSON-RPC request dict ready to send.
        """
        req: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params:
            req["params"] = params
        return req

    def parse_response(self, response: dict[str, Any]) -> Any:
        """Parse a JSON-RPC response from the MCP server.

        Args:
            response: JSON-RPC response dict.

        Returns:
            Result data from the response.

        Raises:
            RuntimeError: If the response contains an error.
        """
        if "error" in response:
            err = response["error"]
            raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")
        return response.get("result")

    @property
    def available_tools(self) -> list[dict[str, Any]]:
        """Get cached list of available tools."""
        return list(self._tools)

    def set_tools(self, tools: list[dict[str, Any]]) -> None:
        """Cache tool definitions received from the server.

        Args:
            tools: List of tool definition dicts.
        """
        self._tools = tools
