"""Behavioral tests for OpenTelemetry integration."""

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

from auto_k8s_pilot.observability import tracing
from auto_k8s_pilot.settings import SETTINGS, Settings


def _unexpected_exporter(*args, **kwargs):
    raise AssertionError("disabled telemetry attempted to create an OTLP exporter")


def test_settings_can_disable_otel_sdk(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")

    assert Settings().OTEL_SDK_DISABLED is True


def test_setup_tracing_skips_empty_endpoint(monkeypatch):
    monkeypatch.setattr(SETTINGS, "OTEL_EXPORTER_OTLP_ENDPOINT", "")
    monkeypatch.setattr(tracing, "OTLPSpanExporter", _unexpected_exporter)

    tracing.setup_tracing(FastAPI())


async def test_run_response_contains_current_trace_id(monkeypatch):
    from auto_k8s_pilot.api import RunRequest, flow_runner, run_flow_endpoint

    monkeypatch.setattr(
        flow_runner,
        "run_flow",
        lambda flow_name, inputs: {
            "final_answer": "ok",
            "steps": [],
            "metadata": {"total_duration_ms": 1},
        },
    )
    expected_trace_id = "1234567890abcdef1234567890abcdef"
    span_context = SpanContext(
        trace_id=int(expected_trace_id, 16),
        span_id=int("1234567890abcdef", 16),
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )

    with trace.use_span(NonRecordingSpan(span_context), end_on_exit=False):
        response = await run_flow_endpoint("k8s-healthcheck", RunRequest())

    assert response.metadata["trace_id"] == expected_trace_id
