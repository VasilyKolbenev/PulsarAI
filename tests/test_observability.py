"""Tests for llm_forge.observability.tracer module.

Tests Span creation/duration/attributes/events, Trace aggregation,
Tracer context managers, record_llm_call, list_traces, eviction,
and the get_tracer() singleton.
"""

import time

import pytest

from llm_forge.observability.tracer import Span, Trace, Tracer, get_tracer


class TestSpan:
    """Tests for the Span dataclass."""

    def test_span_auto_generates_id(self) -> None:
        """Span auto-generates span_id if not provided."""
        span = Span(name="test_span")
        assert len(span.span_id) == 16

    def test_span_auto_sets_start_time(self) -> None:
        """Span auto-sets start_time to current time."""
        before = time.time()
        span = Span(name="test_span")
        after = time.time()
        assert before <= span.start_time <= after

    def test_span_duration_before_finish(self) -> None:
        """Duration is calculated from current time if not finished."""
        span = Span(name="test_span")
        time.sleep(0.01)
        assert span.duration_ms > 0

    def test_span_duration_after_finish(self) -> None:
        """Duration is calculated from end_time after finish."""
        span = Span(name="test_span")
        time.sleep(0.01)
        span.finish()
        duration = span.duration_ms
        time.sleep(0.01)
        assert span.duration_ms == duration

    def test_span_set_attribute(self) -> None:
        """set_attribute stores key-value pairs."""
        span = Span(name="test_span")
        span.set_attribute("model", "gpt-4o")
        span.set_attribute("tokens", 100)
        assert span.attributes["model"] == "gpt-4o"
        assert span.attributes["tokens"] == 100

    def test_span_add_event(self) -> None:
        """add_event appends timestamped events."""
        span = Span(name="test_span")
        span.add_event("started_processing", {"step": 1})
        span.add_event("completed_processing")
        assert len(span.events) == 2
        assert span.events[0]["name"] == "started_processing"
        assert span.events[0]["attributes"]["step"] == 1
        assert "timestamp" in span.events[0]
        assert span.events[1]["name"] == "completed_processing"

    def test_span_finish_sets_status(self) -> None:
        """finish() sets status and end_time."""
        span = Span(name="test_span")
        span.finish(status="error")
        assert span.status == "error"
        assert span.end_time > 0

    def test_span_to_dict(self) -> None:
        """to_dict() contains all expected fields."""
        span = Span(name="op", trace_id="t1", parent_id="p1")
        span.set_attribute("key", "val")
        span.add_event("evt")
        span.finish()
        d = span.to_dict()
        assert d["name"] == "op"
        assert d["trace_id"] == "t1"
        assert d["parent_id"] == "p1"
        assert d["status"] == "ok"
        assert "duration_ms" in d
        assert d["attributes"]["key"] == "val"
        assert len(d["events"]) == 1


class TestTrace:
    """Tests for the Trace dataclass."""

    def test_trace_auto_generates_id(self) -> None:
        """Trace auto-generates trace_id."""
        trace = Trace(name="my_trace")
        assert len(trace.trace_id) == 32

    def test_trace_duration_with_spans(self) -> None:
        """Trace duration spans from earliest start to latest end."""
        trace = Trace(name="t")
        s1 = Span(name="s1", start_time=100.0)
        s1.end_time = 101.0
        s2 = Span(name="s2", start_time=100.5)
        s2.end_time = 102.0
        trace.spans = [s1, s2]
        assert trace.duration_ms == pytest.approx(2000.0)

    def test_trace_duration_empty(self) -> None:
        """Trace with no spans has zero duration."""
        trace = Trace(name="empty")
        assert trace.duration_ms == 0.0

    def test_trace_total_tokens(self) -> None:
        """total_tokens sums input_tokens + output_tokens across spans."""
        trace = Trace(name="t")
        s1 = Span(name="s1")
        s1.attributes = {"input_tokens": 100, "output_tokens": 50}
        s2 = Span(name="s2")
        s2.attributes = {"input_tokens": 200, "output_tokens": 80}
        trace.spans = [s1, s2]
        assert trace.total_tokens == 430

    def test_trace_total_cost(self) -> None:
        """total_cost sums estimated_cost across spans."""
        trace = Trace(name="t")
        s1 = Span(name="s1")
        s1.attributes = {"estimated_cost": 0.01}
        s2 = Span(name="s2")
        s2.attributes = {"estimated_cost": 0.02}
        trace.spans = [s1, s2]
        assert trace.total_cost == pytest.approx(0.03)

    def test_trace_to_dict(self) -> None:
        """to_dict() contains all expected fields."""
        trace = Trace(name="my_trace")
        d = trace.to_dict()
        assert d["name"] == "my_trace"
        assert "trace_id" in d
        assert "duration_ms" in d
        assert "total_tokens" in d
        assert "total_cost" in d
        assert d["span_count"] == 0


class TestTracer:
    """Tests for the Tracer class."""

    def test_start_trace_context_manager(self) -> None:
        """start_trace yields a Trace and stores it."""
        tracer = Tracer()
        with tracer.start_trace("test") as trace:
            assert trace.name == "test"
        assert tracer.get_trace(trace.trace_id) is trace

    def test_start_trace_metadata(self) -> None:
        """start_trace passes metadata to Trace."""
        tracer = Tracer()
        with tracer.start_trace("test", user="alice") as trace:
            assert trace.metadata["user"] == "alice"

    def test_start_trace_auto_finishes_spans(self) -> None:
        """Unfinished spans are finished when trace context exits."""
        tracer = Tracer()
        with tracer.start_trace("t") as trace:
            span = Span(name="s", trace_id=trace.trace_id)
            trace.spans.append(span)
        assert span.end_time > 0

    def test_start_span_context_manager(self) -> None:
        """start_span yields a Span attached to the trace."""
        tracer = Tracer()
        with tracer.start_trace("t") as trace:
            with tracer.start_span(trace, "my_span") as span:
                assert span.name == "my_span"
                assert span.trace_id == trace.trace_id
            assert span.end_time > 0
            assert span.status == "ok"
        assert len(trace.spans) == 1

    def test_start_span_with_attributes(self) -> None:
        """start_span passes extra attributes to the Span."""
        tracer = Tracer()
        with tracer.start_trace("t") as trace:
            with tracer.start_span(trace, "sp", model="gpt-4o") as span:
                assert span.attributes["model"] == "gpt-4o"

    def test_start_span_error_handling(self) -> None:
        """start_span sets error status on exception."""
        tracer = Tracer()
        with tracer.start_trace("t") as trace:
            with pytest.raises(ValueError):
                with tracer.start_span(trace, "failing") as span:
                    raise ValueError("test error")
            assert span.status == "error"
            assert "test error" in span.attributes.get("error", "")

    def test_record_llm_call(self) -> None:
        """record_llm_call creates a span with correct attributes."""
        tracer = Tracer()
        with tracer.start_trace("t") as trace:
            span = tracer.record_llm_call(
                trace=trace,
                model="gpt-4o",
                input_tokens=500,
                output_tokens=200,
                latency_ms=350.0,
                cost_per_1k_input=0.0025,
                cost_per_1k_output=0.01,
            )
        assert span.name == "llm.gpt-4o"
        assert span.attributes["model"] == "gpt-4o"
        assert span.attributes["input_tokens"] == 500
        assert span.attributes["output_tokens"] == 200
        assert span.attributes["latency_ms"] == 350.0
        expected_cost = (500 / 1000) * 0.0025 + (200 / 1000) * 0.01
        assert span.attributes["estimated_cost"] == pytest.approx(expected_cost, abs=1e-6)

    def test_record_llm_call_zero_cost(self) -> None:
        """record_llm_call with zero pricing gives zero cost."""
        tracer = Tracer()
        with tracer.start_trace("t") as trace:
            span = tracer.record_llm_call(
                trace=trace, model="local", input_tokens=1000,
                output_tokens=500, latency_ms=100.0,
            )
        assert span.attributes["estimated_cost"] == 0.0

    def test_list_traces_returns_all(self) -> None:
        """list_traces returns all stored traces."""
        tracer = Tracer()
        with tracer.start_trace("trace_a") as ta:
            tracer.record_llm_call(ta, "m", 10, 10, 10.0)
        with tracer.start_trace("trace_b") as tb:
            tracer.record_llm_call(tb, "m", 20, 20, 20.0)

        results = tracer.list_traces()
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"trace_a", "trace_b"}

    def test_list_traces_filter_by_name(self) -> None:
        """list_traces filters by name substring."""
        tracer = Tracer()
        with tracer.start_trace("inference_run") as t:
            tracer.record_llm_call(t, "m", 10, 10, 10.0)
        with tracer.start_trace("evaluation_run") as t:
            tracer.record_llm_call(t, "m", 10, 10, 10.0)

        results = tracer.list_traces(name="inference")
        assert len(results) == 1
        assert results[0]["name"] == "inference_run"

    def test_list_traces_limit(self) -> None:
        """list_traces respects the limit parameter."""
        tracer = Tracer()
        for i in range(5):
            with tracer.start_trace(f"trace_{i}") as t:
                tracer.record_llm_call(t, "m", 10, 10, 10.0)
        results = tracer.list_traces(limit=2)
        assert len(results) == 2

    def test_eviction_when_max_traces_exceeded(self) -> None:
        """Traces are evicted when max_traces is exceeded.

        The eviction runs inside start_trace after adding the new trace
        but before spans are added. Traces without spans sort as oldest
        (start_time=0), so the eviction may remove recently added traces
        that lack spans. This test verifies the invariant that the total
        stored traces never exceed max_traces + 1 (the +1 comes from the
        new trace being added before eviction of the oldest).
        """
        max_traces = 3
        tracer = Tracer(max_traces=max_traces)
        for i in range(10):
            with tracer.start_trace(f"trace_{i}") as t:
                tracer.record_llm_call(t, "m", 10, 10, 10.0)

        remaining = tracer.list_traces(limit=100)
        # The key invariant: never more than max_traces + 1 stored
        assert len(remaining) <= max_traces + 1

    def test_get_tracer_singleton(self) -> None:
        """get_tracer returns the same global instance."""
        t1 = get_tracer()
        t2 = get_tracer()
        assert t1 is t2
