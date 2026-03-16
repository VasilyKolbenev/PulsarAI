"""Generate fine-tuning data from agent execution traces.

Converts agent conversation traces into SFT and DPO training examples,
closing the loop: agent usage -> training data -> better model -> better agent.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def trace_to_sft(
    trace: list[dict[str, Any]],
    user_query: str,
    system_prompt: str = "",
) -> dict[str, Any] | None:
    """Convert a single agent trace to an SFT training example.

    Extracts the successful tool-calling sequence and final answer
    into a chat-formatted training example.

    Args:
        trace: Agent execution trace from BaseAgent.trace.
        user_query: Original user query.
        system_prompt: System prompt used by the agent.

    Returns:
        Dict with 'messages' list in chat format, or None if trace is invalid.
    """
    if not trace:
        return None

    # Find the final answer
    answers = [t for t in trace if t.get("type") == "answer"]
    if not answers:
        return None

    final_answer = answers[-1]["content"]

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": user_query})

    # Build the ideal assistant response including tool calls
    response_parts: list[str] = []
    for entry in trace:
        if entry["type"] == "tool_call":
            tool_name = entry.get("tool", "unknown")
            args = entry.get("arguments", entry.get("raw_arguments", ""))
            if isinstance(args, dict):
                args = json.dumps(args)
            response_parts.append(f"Thought: I need to use {tool_name}.")
            response_parts.append(f"Action: {tool_name}")
            response_parts.append(f"Action Input: {args}")
        elif entry["type"] == "observation":
            result = entry.get("result", "")
            response_parts.append(f"Observation: {result}")
        elif entry["type"] == "answer":
            response_parts.append("Thought: I have the information needed.")
            response_parts.append(f"Final Answer: {entry['content']}")

    if response_parts:
        messages.append(
            {
                "role": "assistant",
                "content": "\n".join(response_parts),
            }
        )
    else:
        messages.append({"role": "assistant", "content": final_answer})

    return {"messages": messages}


def trace_to_dpo_pair(
    good_trace: list[dict[str, Any]],
    bad_trace: list[dict[str, Any]],
    user_query: str,
    system_prompt: str = "",
) -> dict[str, str] | None:
    """Convert a pair of traces (good vs bad) into a DPO training example.

    Args:
        good_trace: Trace from a successful agent run.
        bad_trace: Trace from a less successful agent run.
        user_query: Original user query.
        system_prompt: System prompt used.

    Returns:
        Dict with 'prompt', 'chosen', 'rejected' fields, or None if invalid.
    """
    good_sft = trace_to_sft(good_trace, user_query, system_prompt)
    bad_sft = trace_to_sft(bad_trace, user_query, system_prompt)

    if not good_sft or not bad_sft:
        return None

    # Extract assistant response from each
    good_response = ""
    bad_response = ""
    for msg in good_sft["messages"]:
        if msg["role"] == "assistant":
            good_response = msg["content"]
    for msg in bad_sft["messages"]:
        if msg["role"] == "assistant":
            bad_response = msg["content"]

    if not good_response or not bad_response:
        return None
    if good_response == bad_response:
        return None

    prompt = user_query
    if system_prompt:
        prompt = f"[System: {system_prompt}]\n\n{user_query}"

    return {
        "prompt": prompt,
        "chosen": good_response,
        "rejected": bad_response,
    }


def export_traces_to_jsonl(
    traces: list[dict[str, Any]],
    output_path: str,
    format: str = "sft",
) -> int:
    """Export multiple trace records to a JSONL file.

    Args:
        traces: List of trace record dicts. Each should have:
            - 'trace': agent trace list
            - 'query': user query string
            - 'system_prompt': optional system prompt
            - For DPO: 'good_trace' and 'bad_trace' instead of 'trace'
        output_path: Path to output JSONL file.
        format: Output format ('sft' or 'dpo').

    Returns:
        Number of examples written.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(output, "w", encoding="utf-8") as f:
        for record in traces:
            query = record.get("query", "")
            system_prompt = record.get("system_prompt", "")

            if format == "sft":
                trace = record.get("trace", [])
                example = trace_to_sft(trace, query, system_prompt)
            elif format == "dpo":
                good = record.get("good_trace", [])
                bad = record.get("bad_trace", [])
                example = trace_to_dpo_pair(good, bad, query, system_prompt)
            else:
                logger.warning("Unknown format: %s", format)
                continue

            if example:
                f.write(json.dumps(example, ensure_ascii=False) + "\n")
                count += 1

    logger.info("Exported %d %s examples to %s", count, format, output_path)
    return count
