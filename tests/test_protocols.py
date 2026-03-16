"""Tests for MCP, A2A, and Gateway protocol modules."""

import pytest
from unittest.mock import MagicMock

from pulsar_ai.protocols.mcp import (
    MCPServer,
    MCPServerConfig,
    MCPToolDefinition,
    MCPClient,
    MCPClientConfig,
)
from pulsar_ai.protocols.a2a import (
    A2AServer,
    A2AClient,
    A2AClientConfig,
    AgentCard,
    A2ATask,
    TaskState,
)
from pulsar_ai.protocols.gateway import (
    APIGateway,
    GatewayConfig,
    GatewayRoute,
)

# ── MCP Server ─────────────────────────────────────────────────────


class TestMCPServer:
    def _make_server(self, tool_handler=None):
        config = MCPServerConfig(
            name="test-server",
            transport="stdio",
            tools=[
                MCPToolDefinition(
                    name="search",
                    description="Search the web",
                    input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                ),
                MCPToolDefinition(name="calculator", description="Do math"),
            ],
        )
        return MCPServer(config, tool_handler=tool_handler)

    def test_initialize(self):
        server = self._make_server()
        resp = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert resp["result"]["protocolVersion"] == "2025-03-26"
        assert resp["result"]["serverInfo"]["name"] == "test-server"

    def test_tools_list(self):
        server = self._make_server()
        resp = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = resp["result"]["tools"]
        assert len(tools) == 2
        assert tools[0]["name"] == "search"
        assert tools[1]["name"] == "calculator"

    def test_tools_call_success(self):
        handler = MagicMock(return_value="42")
        server = self._make_server(tool_handler=handler)
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "calculator", "arguments": {"expr": "6*7"}},
            }
        )
        assert resp["result"]["content"][0]["text"] == "42"
        handler.assert_called_once_with("calculator", {"expr": "6*7"})

    def test_tools_call_unknown_tool(self):
        server = self._make_server()
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "nonexistent", "arguments": {}},
            }
        )
        assert "error" in resp
        assert resp["error"]["code"] == -32602

    def test_tools_call_no_handler(self):
        server = self._make_server(tool_handler=None)
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "search", "arguments": {}},
            }
        )
        assert "error" in resp
        assert resp["error"]["code"] == -32603

    def test_tools_call_handler_error(self):
        handler = MagicMock(side_effect=ValueError("boom"))
        server = self._make_server(tool_handler=handler)
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"query": "test"}},
            }
        )
        assert resp["result"]["isError"] is True
        assert "boom" in resp["result"]["content"][0]["text"]

    def test_unknown_method(self):
        server = self._make_server()
        resp = server.handle_request({"jsonrpc": "2.0", "id": 7, "method": "unknown/method"})
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_to_dict(self):
        server = self._make_server()
        d = server.to_dict()
        assert d["name"] == "test-server"
        assert d["transport"] == "stdio"
        assert len(d["tools"]) == 2

    def test_config_from_dict(self):
        config = MCPServerConfig.from_dict(
            {
                "name": "my-server",
                "transport": "sse",
                "port": 5000,
                "tools": [{"name": "t1", "description": "Tool 1"}],
            }
        )
        assert config.name == "my-server"
        assert config.transport == "sse"
        assert config.port == 5000
        assert len(config.tools) == 1


# ── MCP Client ─────────────────────────────────────────────────────


class TestMCPClient:
    def test_build_request(self):
        client = MCPClient(MCPClientConfig(endpoint_url="http://localhost:3001"))
        req = client.build_request("tools/list")
        assert req["method"] == "tools/list"
        assert req["jsonrpc"] == "2.0"
        assert req["id"] == 1

    def test_parse_response_success(self):
        client = MCPClient(MCPClientConfig())
        result = client.parse_response({"jsonrpc": "2.0", "id": 1, "result": {"tools": []}})
        assert result == {"tools": []}

    def test_parse_response_error(self):
        client = MCPClient(MCPClientConfig())
        with pytest.raises(RuntimeError, match="MCP error"):
            client.parse_response(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32601, "message": "Not found"},
                }
            )

    def test_set_and_get_tools(self):
        client = MCPClient(MCPClientConfig())
        client.set_tools([{"name": "search"}])
        assert client.available_tools == [{"name": "search"}]

    def test_incremental_ids(self):
        client = MCPClient(MCPClientConfig())
        r1 = client.build_request("a")
        r2 = client.build_request("b")
        assert r2["id"] == r1["id"] + 1


# ── A2A Server ─────────────────────────────────────────────────────


class TestA2AServer:
    def _make_server(self, task_handler=None):
        card = AgentCard(name="test-agent", description="Test", url="http://localhost")
        return A2AServer(card, task_handler=task_handler)

    def test_get_agent_card(self):
        server = self._make_server()
        card = server.get_agent_card()
        assert card["name"] == "test-agent"

    def test_send_task(self):
        server = self._make_server()
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tasks/send",
                "params": {
                    "id": "task-1",
                    "message": {"role": "user", "parts": [{"type": "text", "text": "hello"}]},
                },
            }
        )
        task = resp["result"]
        assert task["id"] == "task-1"
        assert task["status"]["state"] == "working"
        assert len(task["messages"]) == 1

    def test_send_task_with_handler(self):
        def handler(task):
            task.state = TaskState.COMPLETED
            task.artifacts.append({"type": "text", "text": "done"})
            return task

        server = self._make_server(task_handler=handler)
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tasks/send",
                "params": {"id": "task-2", "message": {"role": "user", "parts": []}},
            }
        )
        assert resp["result"]["status"]["state"] == "completed"
        assert len(resp["result"]["artifacts"]) == 1

    def test_send_task_handler_error(self):
        def handler(task):
            raise RuntimeError("handler failed")

        server = self._make_server(task_handler=handler)
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tasks/send",
                "params": {"id": "task-3", "message": {}},
            }
        )
        assert resp["result"]["status"]["state"] == "failed"

    def test_get_task(self):
        server = self._make_server()
        # First create a task
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tasks/send",
                "params": {"id": "task-4", "message": {}},
            }
        )
        # Then get it
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tasks/get",
                "params": {"id": "task-4"},
            }
        )
        assert resp["result"]["id"] == "task-4"

    def test_get_task_not_found(self):
        server = self._make_server()
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tasks/get",
                "params": {"id": "missing"},
            }
        )
        assert "error" in resp

    def test_cancel_task(self):
        server = self._make_server()
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tasks/send",
                "params": {"id": "task-5", "message": {}},
            }
        )
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tasks/cancel",
                "params": {"id": "task-5"},
            }
        )
        assert resp["result"]["status"]["state"] == "canceled"

    def test_unknown_method(self):
        server = self._make_server()
        resp = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "bad/method"})
        assert "error" in resp


# ── A2A Client ─────────────────────────────────────────────────────


class TestA2AClient:
    def test_build_send_request(self):
        client = A2AClient(A2AClientConfig(agent_card_url="http://agent"))
        req = client.build_send_request("Hello", task_id="t1")
        assert req["method"] == "tasks/send"
        assert req["params"]["id"] == "t1"
        assert req["params"]["message"]["parts"][0]["text"] == "Hello"

    def test_build_get_request(self):
        client = A2AClient(A2AClientConfig())
        req = client.build_get_request("t1")
        assert req["method"] == "tasks/get"
        assert req["params"]["id"] == "t1"

    def test_parse_response_success(self):
        client = A2AClient(A2AClientConfig())
        result = client.parse_response({"jsonrpc": "2.0", "id": 1, "result": {"id": "t1"}})
        assert result["id"] == "t1"

    def test_parse_response_error(self):
        client = A2AClient(A2AClientConfig())
        with pytest.raises(RuntimeError, match="A2A error"):
            client.parse_response(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32602, "message": "Not found"},
                }
            )

    def test_agent_card_cache(self):
        client = A2AClient(A2AClientConfig())
        assert client.agent_card is None
        client.set_agent_card({"name": "remote"})
        assert client.agent_card["name"] == "remote"


# ── A2A Data Classes ───────────────────────────────────────────────


class TestA2ADataClasses:
    def test_agent_card_to_dict(self):
        card = AgentCard(name="test", skills=[{"id": "s1", "name": "Search"}])
        d = card.to_dict()
        assert d["name"] == "test"
        assert len(d["skills"]) == 1

    def test_agent_card_from_dict(self):
        card = AgentCard.from_dict({"name": "remote", "version": "2.0"})
        assert card.name == "remote"
        assert card.version == "2.0"

    def test_task_auto_id(self):
        task = A2ATask()
        assert len(task.id) > 0
        assert task.state == TaskState.SUBMITTED

    def test_task_to_dict(self):
        task = A2ATask(id="t1")
        d = task.to_dict()
        assert d["id"] == "t1"
        assert d["status"]["state"] == "submitted"


# ── API Gateway ────────────────────────────────────────────────────


class TestAPIGateway:
    def _make_gateway(self, rate_limit=60):
        config = GatewayConfig(
            name="test-gw",
            rate_limit=rate_limit,
            routes=[
                GatewayRoute(path="/chat", agent_name="chatbot"),
                GatewayRoute(path="/search", agent_name="searcher"),
            ],
        )
        return APIGateway(config)

    def test_register_and_unregister_agent(self):
        gw = self._make_gateway()
        gw.register_agent("chatbot", lambda x: x)
        assert "chatbot" in gw.registered_agents
        assert gw.unregister_agent("chatbot") is True
        assert "chatbot" not in gw.registered_agents

    def test_unregister_missing(self):
        gw = self._make_gateway()
        assert gw.unregister_agent("missing") is False

    def test_route_request_success(self):
        gw = self._make_gateway()
        gw.register_agent("chatbot", lambda payload: {"answer": "hi"})
        result = gw.route_request("/chat", {"message": "hello"})
        assert result["status"] == 200
        assert result["result"]["answer"] == "hi"

    def test_route_request_no_route(self):
        gw = self._make_gateway()
        result = gw.route_request("/unknown", {})
        assert result["status"] == 404

    def test_route_request_no_agent(self):
        gw = self._make_gateway()
        result = gw.route_request("/chat", {})
        assert result["status"] == 503

    def test_route_request_handler_error(self):
        agent = MagicMock()
        agent.handle_request.side_effect = RuntimeError("fail")
        gw = self._make_gateway()
        gw.register_agent("chatbot", agent)
        result = gw.route_request("/chat", {})
        assert result["status"] == 500

    def test_route_request_handle_request_method(self):
        agent = MagicMock(spec=["handle_request"])
        agent.handle_request.return_value = {"ok": True}
        gw = self._make_gateway()
        gw.register_agent("chatbot", agent)
        result = gw.route_request("/chat", {"q": "hi"})
        assert result["status"] == 200
        agent.handle_request.assert_called_once_with({"q": "hi"})

    def test_rate_limiting(self):
        gw = self._make_gateway(rate_limit=2)
        gw.register_agent("chatbot", lambda x: "ok")
        r1 = gw.route_request("/chat", {}, client_id="user1")
        r2 = gw.route_request("/chat", {}, client_id="user1")
        r3 = gw.route_request("/chat", {}, client_id="user1")
        assert r1["status"] == 200
        assert r2["status"] == 200
        assert r3["status"] == 429

    def test_rate_limit_different_clients(self):
        gw = self._make_gateway(rate_limit=1)
        gw.register_agent("chatbot", lambda x: "ok")
        r1 = gw.route_request("/chat", {}, client_id="a")
        r2 = gw.route_request("/chat", {}, client_id="b")
        assert r1["status"] == 200
        assert r2["status"] == 200

    def test_to_dict(self):
        gw = self._make_gateway()
        gw.register_agent("chatbot", lambda x: x)
        d = gw.to_dict()
        assert d["name"] == "test-gw"
        assert "chatbot" in d["agents"]
        assert len(d["routes"]) == 2

    def test_config_from_dict(self):
        config = GatewayConfig.from_dict(
            {
                "protocols": "REST,gRPC",
                "auth_method": "jwt",
                "rate_limit": 100,
            }
        )
        assert config.protocols == ["REST", "gRPC"]
        assert config.auth_method == "jwt"
        assert config.rate_limit == 100

    def test_config_from_dict_list_protocols(self):
        config = GatewayConfig.from_dict({"protocols": ["REST", "GraphQL"]})
        assert config.protocols == ["REST", "GraphQL"]
