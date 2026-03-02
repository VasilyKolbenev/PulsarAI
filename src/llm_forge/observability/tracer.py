"""LLM operation tracer — lightweight OpenTelemetry-style tracing.

Captures spans for every LLM call, pipeline step, and agent action
with timing, token counts, and cost estimation.
"""

import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """A single traced operation."""

    name: str
    trace_id: str = ""
    span_id: str = ""
    parent_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.span_id:
            self.span_id = uuid.uuid4().hex[:16]
        if not self.start_time:
            self.start_time = time.time()

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds."""
        if not self.end_time:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add a timestamped event to the span."""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def finish(self, status: str = "ok") -> None:
        """Mark span as complete."""
        self.end_time = time.time()
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


@dataclass
class Trace:
    """A collection of spans forming a complete trace."""

    trace_id: str = ""
    name: str = ""
    spans: list[Span] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.trace_id:
            self.trace_id = uuid.uuid4().hex

    @property
    def duration_ms(self) -> float:
        """Total trace duration."""
        if not self.spans:
            return 0.0
        start = min(s.start_time for s in self.spans)
        end = max(s.end_time or time.time() for s in self.spans)
        return (end - start) * 1000

    @property
    def total_tokens(self) -> int:
        """Sum of all token counts across spans."""
        total = 0
        for span in self.spans:
            total += span.attributes.get("input_tokens", 0)
            total += span.attributes.get("output_tokens", 0)
        return total

    @property
    def total_cost(self) -> float:
        """Sum of estimated costs across spans."""
        return sum(s.attributes.get("estimated_cost", 0.0) for s in self.spans)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "duration_ms": self.duration_ms,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
            "metadata": self.metadata,
        }


class Tracer:
    """Lightweight tracer for LLM operations.

    Captures traces with spans for pipeline steps, LLM calls, tool use, etc.
    Stores traces in memory with configurable max size.

    Args:
        max_traces: Maximum number of traces to keep in memory.
    """

    def __init__(self, max_traces: int = 1000) -> None:
        self._traces: dict[str, Trace] = {}
        self._max_traces = max_traces
        self._active_spans: dict[str, Span] = {}

    @contextmanager
    def start_trace(self, name: str, **metadata: Any) -> Generator[Trace, None, None]:
        """Start a new trace context.

        Args:
            name: Trace name.
            **metadata: Additional metadata.

        Yields:
            The active Trace.
        """
        trace = Trace(name=name, metadata=metadata)
        self._traces[trace.trace_id] = trace

        self._evict_if_needed()

        try:
            yield trace
        finally:
            for span in trace.spans:
                if not span.end_time:
                    span.finish(status="ok")

    @contextmanager
    def start_span(
        self, trace: Trace, name: str, parent_id: str = "", **attributes: Any,
    ) -> Generator[Span, None, None]:
        """Start a new span within a trace.

        Args:
            trace: Parent trace.
            name: Span name.
            parent_id: Parent span ID for nesting.
            **attributes: Span attributes.

        Yields:
            The active Span.
        """
        span = Span(
            name=name,
            trace_id=trace.trace_id,
            parent_id=parent_id,
            attributes=dict(attributes),
        )
        trace.spans.append(span)
        self._active_spans[span.span_id] = span

        try:
            yield span
        except Exception as e:
            span.finish(status="error")
            span.set_attribute("error", str(e))
            raise
        else:
            span.finish(status="ok")
        finally:
            self._active_spans.pop(span.span_id, None)

    def record_llm_call(
        self,
        trace: Trace,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        parent_id: str = "",
        cost_per_1k_input: float = 0.0,
        cost_per_1k_output: float = 0.0,
        **attributes: Any,
    ) -> Span:
        """Record an LLM API call as a span.

        Args:
            trace: Parent trace.
            model: Model name.
            input_tokens: Input token count.
            output_tokens: Output token count.
            latency_ms: Call latency in ms.
            parent_id: Parent span ID.
            cost_per_1k_input: Cost per 1K input tokens.
            cost_per_1k_output: Cost per 1K output tokens.
            **attributes: Extra attributes.

        Returns:
            The recorded Span.
        """
        cost = (
            (input_tokens / 1000) * cost_per_1k_input
            + (output_tokens / 1000) * cost_per_1k_output
        )

        span = Span(
            name=f"llm.{model}",
            trace_id=trace.trace_id,
            parent_id=parent_id,
            attributes={
                "type": "llm_call",
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "estimated_cost": round(cost, 6),
                **attributes,
            },
        )
        span.end_time = span.start_time + (latency_ms / 1000)
        span.status = "ok"
        trace.spans.append(span)
        return span

    def get_trace(self, trace_id: str) -> Trace | None:
        """Get a trace by ID."""
        return self._traces.get(trace_id)

    def list_traces(self, limit: int = 50, name: str = "") -> list[dict[str, Any]]:
        """List recent traces.

        Args:
            limit: Maximum number of traces to return.
            name: Filter by trace name.

        Returns:
            List of trace summary dicts.
        """
        traces = list(self._traces.values())
        if name:
            traces = [t for t in traces if name in t.name]

        traces.sort(key=lambda t: t.spans[0].start_time if t.spans else 0, reverse=True)

        return [
            {
                "trace_id": t.trace_id,
                "name": t.name,
                "duration_ms": t.duration_ms,
                "span_count": len(t.spans),
                "total_tokens": t.total_tokens,
                "total_cost": t.total_cost,
            }
            for t in traces[:limit]
        ]

    def _evict_if_needed(self) -> None:
        """Remove oldest traces if over capacity."""
        if len(self._traces) <= self._max_traces:
            return

        sorted_ids = sorted(
            self._traces.keys(),
            key=lambda tid: (
                self._traces[tid].spans[0].start_time
                if self._traces[tid].spans else 0
            ),
        )

        to_remove = len(self._traces) - self._max_traces
        for tid in sorted_ids[:to_remove]:
            del self._traces[tid]


# Global tracer instance
_tracer = Tracer()


def get_tracer() -> Tracer:
    """Get the global tracer instance."""
    return _tracer
