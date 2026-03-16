"""Base agent with ReAct (Reasoning + Action) loop."""

import json
import logging
import re
from typing import Any

from pulsar_ai.agent.client import ModelClient
from pulsar_ai.agent.guardrails import GuardrailsConfig
from pulsar_ai.agent.memory import ShortTermMemory
from pulsar_ai.agent.tool import ToolRegistry

logger = logging.getLogger(__name__)

# ReAct text patterns for models without native tool calling
_ACTION_PATTERN = re.compile(
    r"Action:\s*(\w+)\s*\nAction Input:\s*(.+?)(?:\n|$)",
    re.DOTALL,
)
_FINAL_ANSWER_PATTERN = re.compile(
    r"Final Answer:\s*(.+)",
    re.DOTALL,
)


class AgentStoppedError(Exception):
    """Raised when agent is stopped by guardrails."""


class BaseAgent:
    """ReAct agent that reasons and acts using tools.

    Supports two modes:
    1. Native tool calling — if the model server supports OpenAI tool_calls
    2. ReAct text fallback — parses Thought/Action/Observation from plain text

    Args:
        client: ModelClient for LLM inference.
        tools: ToolRegistry with available tools.
        memory: ShortTermMemory for conversation history.
        guardrails: GuardrailsConfig for safety limits.
        use_native_tools: If True, use OpenAI tool_calls format. If False, use
            ReAct text parsing. If None, auto-detect.
    """

    REACT_SYSTEM_SUFFIX = """
You are a helpful AI assistant with access to tools.

To use a tool, respond with exactly this format:
Thought: <your reasoning about what to do next>
Action: <tool_name>
Action Input: <JSON arguments>

After receiving the tool result as an Observation, continue reasoning.

When you have the final answer, respond with:
Thought: <your final reasoning>
Final Answer: <your complete answer to the user>

IMPORTANT: Always start with a Thought. Use tools when needed. Give a Final Answer when done.
"""

    def __init__(
        self,
        client: ModelClient,
        tools: ToolRegistry,
        memory: ShortTermMemory | None = None,
        guardrails: GuardrailsConfig | None = None,
        use_native_tools: bool | None = None,
    ) -> None:
        self.client = client
        self.tools = tools
        self.memory = memory or ShortTermMemory()
        self.guardrails = guardrails or GuardrailsConfig()
        self.use_native_tools = use_native_tools
        self._trace: list[dict[str, Any]] = []

    def run(self, user_input: str, max_steps: int | None = None) -> str:
        """Run the agent on a user query.

        Args:
            user_input: The user's message.
            max_steps: Override max iterations for this run.

        Returns:
            The agent's final answer string.

        Raises:
            AgentStoppedError: If guardrails stop the agent.
        """
        effective_max = max_steps or self.guardrails.max_iterations
        self._trace = []

        # Inject tool descriptions into system prompt for ReAct mode
        if not self.use_native_tools and self.memory.message_count == 0:
            tool_block = self.tools.to_react_prompt()
            system_content = f"{tool_block}\n{self.REACT_SYSTEM_SUFFIX}"
            self.memory.add("system", system_content)
        elif self.memory.message_count == 0:
            self.memory.add("system", "You are a helpful AI assistant.")

        self.memory.add("user", user_input)

        for step in range(effective_max):
            if not self.guardrails.check_iteration(step):
                logger.warning("Agent stopped: max iterations reached (%d)", step)
                return self._force_final_answer()

            result = self._step()
            if result is not None:
                return result

        logger.warning("Agent exhausted all %d steps without final answer", effective_max)
        return self._force_final_answer()

    def _step(self) -> str | None:
        """Execute a single ReAct step.

        Returns:
            Final answer string if the agent is done, None to continue.
        """
        messages = self.memory.get_messages()

        if self.use_native_tools:
            return self._step_native(messages)
        else:
            return self._step_react(messages)

    def _step_native(self, messages: list[dict[str, str]]) -> str | None:
        """Step using native OpenAI tool calling.

        Args:
            messages: Current conversation messages.

        Returns:
            Final answer string or None to continue.
        """
        response = self.client.chat(
            messages=messages,
            tools=self.tools.to_openai_format() if len(self.tools) > 0 else None,
        )

        content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])

        if not tool_calls:
            # No tool calls — this is the final answer
            self.memory.add("assistant", content)
            self._trace.append({"type": "answer", "content": content})
            return content

        # Build OpenAI-format tool_calls for the assistant message
        openai_tool_calls = [
            {
                "id": tc.get("id", f"call_{i}"),
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc["arguments"]),
                },
            }
            for i, tc in enumerate(tool_calls)
        ]
        self.memory.add("assistant", content or "", tool_calls=openai_tool_calls)

        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc["arguments"]
            call_id = tc.get("id", "")

            self._trace.append(
                {
                    "type": "tool_call",
                    "tool": tool_name,
                    "arguments": tool_args,
                }
            )

            observation = self._execute_tool(tool_name, tool_args)
            self.memory.add("tool", observation, tool_call_id=call_id)
            self._trace.append(
                {
                    "type": "observation",
                    "tool": tool_name,
                    "result": observation,
                }
            )

        return None

    def _step_react(self, messages: list[dict[str, str]]) -> str | None:
        """Step using ReAct text parsing.

        Args:
            messages: Current conversation messages.

        Returns:
            Final answer string or None to continue.
        """
        response = self.client.chat(messages=messages)
        text = response.get("content", "")

        self._trace.append({"type": "llm_response", "content": text})

        # Check for Final Answer
        final_match = _FINAL_ANSWER_PATTERN.search(text)
        if final_match:
            answer = final_match.group(1).strip()
            self.memory.add("assistant", text)
            self._trace.append({"type": "answer", "content": answer})
            return answer

        # Check for Action
        action_match = _ACTION_PATTERN.search(text)
        if action_match:
            tool_name = action_match.group(1).strip()
            raw_args = action_match.group(2).strip()

            self._trace.append(
                {
                    "type": "tool_call",
                    "tool": tool_name,
                    "raw_arguments": raw_args,
                }
            )

            # Parse arguments
            try:
                tool_args = json.loads(raw_args)
            except json.JSONDecodeError:
                # Treat as a single string argument
                tool_args = {"input": raw_args}

            observation = self._execute_tool(tool_name, tool_args)

            # Add the assistant's reasoning + observation to memory
            self.memory.add("assistant", text)
            self.memory.add("user", f"Observation: {observation}")
            self._trace.append(
                {
                    "type": "observation",
                    "tool": tool_name,
                    "result": observation,
                }
            )
            return None

        # No action or final answer — treat as intermediate thought,
        # nudge the model to continue
        self.memory.add("assistant", text)
        self.memory.add(
            "user",
            "Please continue. Use an Action to call a tool, " "or provide a Final Answer.",
        )
        return None

    def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        """Execute a tool with guardrails checks.

        Args:
            name: Tool name.
            args: Tool arguments.

        Returns:
            String result from the tool.
        """
        if not self.guardrails.check_tool_allowed(name):
            return f"Error: Tool '{name}' is not allowed by guardrails."

        if name not in self.tools:
            available = self.tools.list_tools()
            return f"Error: Tool '{name}' not found. Available tools: {available}"

        tool_obj = self.tools.get(name)
        logger.info("Executing tool: %s(%s)", name, args)

        result = tool_obj.execute(**args)
        logger.debug("Tool '%s' result: %s", name, result[:200])
        return result

    def _force_final_answer(self) -> str:
        """Force the agent to give a final answer based on current context.

        Returns:
            Best-effort final answer string.
        """
        self.memory.add(
            "user",
            "You must provide your Final Answer now based on what you know so far.",
        )
        response = self.client.chat(messages=self.memory.get_messages())
        content = response.get("content", "I was unable to complete the task.")

        # Try to extract a Final Answer from the response
        final_match = _FINAL_ANSWER_PATTERN.search(content)
        if final_match:
            return final_match.group(1).strip()
        return content

    @property
    def trace(self) -> list[dict[str, Any]]:
        """Get the execution trace of the last run.

        Returns:
            List of trace entries (tool calls, observations, answers).
        """
        return list(self._trace)

    @classmethod
    def from_config(
        cls,
        config: dict,
        tools: ToolRegistry | None = None,
    ) -> "BaseAgent":
        """Create a BaseAgent from a config dict.

        Args:
            config: Full agent config dict.
            tools: Optional pre-built ToolRegistry.

        Returns:
            Configured BaseAgent instance.
        """
        model_config = config.get("model", {})
        client = ModelClient(
            base_url=model_config.get("base_url", "http://localhost:8080/v1"),
            model=model_config.get("name", "default"),
            timeout=model_config.get("timeout", 120),
        )

        agent_config = config.get("agent", {})
        system_prompt = agent_config.get("system_prompt", "")

        memory_config = config.get("memory", {})
        memory = ShortTermMemory(
            max_tokens=memory_config.get("max_tokens", 4096),
            system_prompt=system_prompt,
        )

        guardrails = GuardrailsConfig.from_config(config)

        return cls(
            client=client,
            tools=tools or ToolRegistry(),
            memory=memory,
            guardrails=guardrails,
            use_native_tools=config.get("agent", {}).get("native_tools"),
        )
