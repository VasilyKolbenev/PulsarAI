"""Tests for agent trace to training data conversion."""

import json
from pathlib import Path


from pulsar_ai.agent.data_gen import (
    trace_to_sft,
    trace_to_dpo_pair,
    export_traces_to_jsonl,
)


def _sample_trace() -> list[dict]:
    return [
        {"type": "llm_response", "content": "Thought: I need to search."},
        {"type": "tool_call", "tool": "search", "arguments": {"query": "test"}},
        {"type": "observation", "tool": "search", "result": "Found: test.py"},
        {"type": "answer", "content": "I found test.py in the project."},
    ]


def _simple_trace() -> list[dict]:
    return [
        {"type": "answer", "content": "The answer is 42."},
    ]


class TestTraceToSft:
    """Tests for trace_to_sft conversion."""

    def test_converts_trace_with_tools(self) -> None:
        result = trace_to_sft(
            trace=_sample_trace(),
            user_query="Find test files",
            system_prompt="You are helpful.",
        )
        assert result is not None
        messages = result["messages"]
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert "Action: search" in messages[2]["content"]
        assert "Final Answer:" in messages[2]["content"]

    def test_converts_simple_trace(self) -> None:
        result = trace_to_sft(
            trace=_simple_trace(),
            user_query="What is the answer?",
        )
        assert result is not None
        messages = result["messages"]
        assert len(messages) == 2  # user + assistant (no system)
        assert "The answer is 42." in messages[1]["content"]

    def test_returns_none_for_empty_trace(self) -> None:
        assert trace_to_sft([], "query") is None

    def test_returns_none_for_no_answer(self) -> None:
        trace = [{"type": "tool_call", "tool": "search", "arguments": {"query": "x"}}]
        assert trace_to_sft(trace, "query") is None

    def test_includes_system_prompt(self) -> None:
        result = trace_to_sft(
            trace=_simple_trace(),
            user_query="test",
            system_prompt="Be helpful.",
        )
        assert result is not None
        assert result["messages"][0]["role"] == "system"
        assert result["messages"][0]["content"] == "Be helpful."


class TestTraceToDpoPair:
    """Tests for trace_to_dpo_pair conversion."""

    def test_creates_dpo_pair(self) -> None:
        good = _sample_trace()
        bad = [{"type": "answer", "content": "I don't know."}]

        result = trace_to_dpo_pair(
            good_trace=good,
            bad_trace=bad,
            user_query="Find test files",
        )
        assert result is not None
        assert "prompt" in result
        assert "chosen" in result
        assert "rejected" in result
        assert "Action: search" in result["chosen"]
        assert "I don't know." in result["rejected"]

    def test_returns_none_for_same_responses(self) -> None:
        trace = _simple_trace()
        result = trace_to_dpo_pair(trace, trace, "query")
        assert result is None

    def test_returns_none_for_empty_traces(self) -> None:
        result = trace_to_dpo_pair([], [], "query")
        assert result is None

    def test_includes_system_in_prompt(self) -> None:
        good = _sample_trace()
        bad = [{"type": "answer", "content": "No idea."}]

        result = trace_to_dpo_pair(good, bad, "test", system_prompt="Be helpful")
        assert result is not None
        assert "Be helpful" in result["prompt"]


class TestExportTracesToJsonl:
    """Tests for JSONL export."""

    def test_exports_sft_examples(self, tmp_path: Path) -> None:
        traces = [
            {"trace": _sample_trace(), "query": "Find files"},
            {"trace": _simple_trace(), "query": "What's the answer?"},
        ]
        output = str(tmp_path / "train.jsonl")
        count = export_traces_to_jsonl(traces, output, format="sft")
        assert count == 2

        with open(output) as f:
            lines = f.readlines()
        assert len(lines) == 2
        example = json.loads(lines[0])
        assert "messages" in example

    def test_exports_dpo_examples(self, tmp_path: Path) -> None:
        traces = [
            {
                "good_trace": _sample_trace(),
                "bad_trace": [{"type": "answer", "content": "No idea."}],
                "query": "Find files",
            },
        ]
        output = str(tmp_path / "dpo.jsonl")
        count = export_traces_to_jsonl(traces, output, format="dpo")
        assert count == 1

        with open(output) as f:
            example = json.loads(f.readline())
        assert "prompt" in example
        assert "chosen" in example
        assert "rejected" in example

    def test_skips_invalid_traces(self, tmp_path: Path) -> None:
        traces = [
            {"trace": [], "query": "Empty"},
            {"trace": _simple_trace(), "query": "Valid"},
        ]
        output = str(tmp_path / "train.jsonl")
        count = export_traces_to_jsonl(traces, output, format="sft")
        assert count == 1

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        output = str(tmp_path / "deep" / "nested" / "train.jsonl")
        count = export_traces_to_jsonl(
            [{"trace": _simple_trace(), "query": "test"}],
            output,
            format="sft",
        )
        assert count == 1
        assert Path(output).exists()
