"""Tests for the OpenTelemetry tracing bootstrap (P1-22).

These tests run with OTEL disabled (default), so they verify the no-op contract:
- `traced_span` yields without raising even before init_tracing.
- `init_tracing` returns False when disabled.
- Attribute kwargs to traced_span are silently ignored when not enabled.
"""
from backend.app.tracing import init_tracing, traced_span
from backend.app.config import settings


def test_traced_span_is_noop_when_disabled():
    # Default settings has OTEL_ENABLED = False
    assert settings.OTEL_ENABLED is False
    enabled = init_tracing(app=None)
    assert enabled is False
    with traced_span("test.span", foo="bar", count=42) as span:
        assert span is None  # No tracer means yield None


def test_traced_span_can_be_nested_when_disabled():
    with traced_span("outer") as outer:
        assert outer is None
        with traced_span("inner", k="v") as inner:
            assert inner is None
