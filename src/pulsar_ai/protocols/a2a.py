"""A2A (Agent-to-Agent) protocol support.

Implements Google's Agent-to-Agent protocol for inter-agent communication,
task delegation, and result streaming.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    """A2A task lifecycle states."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class AgentCard:
    """A2A Agent Card — describes an agent's capabilities.

    Published at /.well-known/agent.json per the A2A spec.
    """

    name: str = "pulsar-ai-agent"
    description: str = "Pulsar AI AI Agent"
    url: str = ""
    version: str = "1.0.0"
    skills: list[dict[str, str]] = field(default_factory=list)
    capabilities: dict[str, bool] = field(
        default_factory=lambda: {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        }
    )
    authentication: dict[str, Any] = field(
        default_factory=lambda: {
            "schemes": ["bearer"],
        }
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON response.

        Returns:
            Agent card as a dict.
        """
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "skills": self.skills,
            "capabilities": self.capabilities,
            "authentication": self.authentication,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentCard":
        """Create from dict."""
        return cls(
            name=data.get("name", "pulsar-ai-agent"),
            description=data.get("description", ""),
            url=data.get("url", ""),
            version=data.get("version", "1.0.0"),
            skills=data.get("skills", []),
            capabilities=data.get("capabilities", {}),
            authentication=data.get("authentication", {}),
        )


@dataclass
class A2ATask:
    """Represents a task in the A2A protocol."""

    id: str = ""
    state: TaskState = TaskState.SUBMITTED
    messages: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        """Serialize task to dict.

        Returns:
            Task as a dict.
        """
        return {
            "id": self.id,
            "status": {"state": self.state.value},
            "messages": self.messages,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


class A2AServer:
    """A2A Protocol server — receives tasks from other agents.

    Handles task submission, status queries, and result retrieval.

    Args:
        agent_card: AgentCard describing this agent.
        task_handler: Async-compatible callable(task: A2ATask) -> A2ATask.
    """

    def __init__(
        self,
        agent_card: AgentCard,
        task_handler: Any | None = None,
    ) -> None:
        self.agent_card = agent_card
        self._task_handler = task_handler
        self._tasks: dict[str, A2ATask] = {}

    def get_agent_card(self) -> dict[str, Any]:
        """Return the agent card for discovery.

        Returns:
            Agent card dict.
        """
        return self.agent_card.to_dict()

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle an incoming A2A JSON-RPC request.

        Args:
            request: JSON-RPC request with method and params.

        Returns:
            JSON-RPC response dict.
        """
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        handlers = {
            "tasks/send": self._handle_send,
            "tasks/get": self._handle_get,
            "tasks/cancel": self._handle_cancel,
        }

        handler = handlers.get(method)
        if not handler:
            return self._rpc_error(req_id, -32601, f"Method not found: {method}")

        return handler(req_id, params)

    def _handle_send(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tasks/send — create or continue a task.

        Args:
            req_id: JSON-RPC request ID.
            params: Request params with message.

        Returns:
            JSON-RPC response with task state.
        """
        task_id = params.get("id", str(uuid.uuid4()))
        message = params.get("message", {})

        if task_id in self._tasks:
            task = self._tasks[task_id]
        else:
            task = A2ATask(id=task_id)
            self._tasks[task_id] = task

        if message:
            task.messages.append(message)

        task.state = TaskState.WORKING
        task.updated_at = datetime.now(timezone.utc).isoformat()

        if self._task_handler:
            try:
                task = self._task_handler(task)
                self._tasks[task.id] = task
            except Exception as e:
                logger.error("Task handler failed for %s: %s", task_id, e)
                task.state = TaskState.FAILED
                task.metadata["error"] = str(e)

        return self._rpc_response(req_id, task.to_dict())

    def _handle_get(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tasks/get — retrieve task status.

        Args:
            req_id: JSON-RPC request ID.
            params: Request params with id.

        Returns:
            JSON-RPC response with task state.
        """
        task_id = params.get("id", "")
        task = self._tasks.get(task_id)
        if not task:
            return self._rpc_error(req_id, -32602, f"Task not found: {task_id}")
        return self._rpc_response(req_id, task.to_dict())

    def _handle_cancel(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tasks/cancel — cancel a running task.

        Args:
            req_id: JSON-RPC request ID.
            params: Request params with id.

        Returns:
            JSON-RPC response with updated task state.
        """
        task_id = params.get("id", "")
        task = self._tasks.get(task_id)
        if not task:
            return self._rpc_error(req_id, -32602, f"Task not found: {task_id}")

        task.state = TaskState.CANCELED
        task.updated_at = datetime.now(timezone.utc).isoformat()
        return self._rpc_response(req_id, task.to_dict())

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


@dataclass
class A2AClientConfig:
    """Configuration for connecting to a remote A2A agent."""

    agent_card_url: str = ""
    timeout: int = 300
    retry_count: int = 3

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "A2AClientConfig":
        """Create from dict."""
        return cls(
            agent_card_url=data.get("agent_card_url", ""),
            timeout=data.get("timeout", 300),
            retry_count=data.get("retry_count", 3),
        )


class A2AClient:
    """A2A Client — sends tasks to remote agents.

    Args:
        config: A2AClientConfig with endpoint details.
    """

    def __init__(self, config: A2AClientConfig) -> None:
        self.config = config
        self._agent_card: dict[str, Any] | None = None
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def build_send_request(
        self,
        message_text: str,
        task_id: str | None = None,
        role: str = "user",
    ) -> dict[str, Any]:
        """Build a tasks/send JSON-RPC request.

        Args:
            message_text: The message content.
            task_id: Optional existing task ID to continue.
            role: Message role (user or agent).

        Returns:
            JSON-RPC request dict.
        """
        params: dict[str, Any] = {
            "id": task_id or str(uuid.uuid4()),
            "message": {
                "role": role,
                "parts": [{"type": "text", "text": message_text}],
            },
        }
        return {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tasks/send",
            "params": params,
        }

    def build_get_request(self, task_id: str) -> dict[str, Any]:
        """Build a tasks/get JSON-RPC request.

        Args:
            task_id: Task ID to query.

        Returns:
            JSON-RPC request dict.
        """
        return {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tasks/get",
            "params": {"id": task_id},
        }

    def parse_response(self, response: dict[str, Any]) -> Any:
        """Parse a JSON-RPC response.

        Args:
            response: JSON-RPC response dict.

        Returns:
            Result data.

        Raises:
            RuntimeError: If response contains an error.
        """
        if "error" in response:
            err = response["error"]
            raise RuntimeError(f"A2A error {err.get('code')}: {err.get('message')}")
        return response.get("result")

    def set_agent_card(self, card: dict[str, Any]) -> None:
        """Cache agent card from discovery.

        Args:
            card: Agent card dict.
        """
        self._agent_card = card

    @property
    def agent_card(self) -> dict[str, Any] | None:
        """Get cached agent card."""
        return self._agent_card
