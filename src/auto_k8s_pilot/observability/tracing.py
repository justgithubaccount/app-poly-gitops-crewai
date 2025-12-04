"""OpenTelemetry tracing setup for FastAPI."""

import logging
from typing import Any, Dict

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from auto_k8s_pilot.settings import SETTINGS


def server_request_hook(span: Any, scope: Dict[str, Any]) -> None:
    """Custom hook to enrich spans with request attributes."""
    if path := scope.get("path"):
        span.set_attribute("http.url.path", path)

    if query_string := scope.get("query_string"):
        span.set_attribute("http.url.query", query_string.decode())

    if event_type := scope.get("type"):
        span.set_attribute("asgi.event_type", event_type)


def setup_tracing(app: Any) -> None:
    """
    Setup OpenTelemetry for traces.
    Production-ready configuration for Kubernetes.
    """
    # Resource with service and Kubernetes metadata
    resource = Resource(
        attributes={
            "service.name": SETTINGS.OTEL_SERVICE_NAME,
            "service.version": SETTINGS.APP_VERSION,
            "deployment.environment": SETTINGS.ENVIRONMENT,
            # Kubernetes metadata
            "k8s.pod.name": SETTINGS.K8S_POD_NAME or "unknown",
            "k8s.namespace": SETTINGS.K8S_NAMESPACE or "default",
            "k8s.node.name": SETTINGS.K8S_NODE_NAME or "unknown",
            "k8s.deployment.name": SETTINGS.K8S_DEPLOYMENT_NAME,
            "k8s.container.name": SETTINGS.K8S_CONTAINER_NAME,
            "k8s.pod.uid": SETTINGS.K8S_POD_UID or "unknown",
        }
    )

    # OTLP endpoint
    otlp_endpoint = SETTINGS.OTEL_EXPORTER_OTLP_ENDPOINT

    # For HTTP protocol add correct paths
    traces_endpoint = (
        f"{otlp_endpoint}/v1/traces"
        if not otlp_endpoint.endswith("/v1/traces")
        else otlp_endpoint
    )

    # === TRACES ===
    provider = TracerProvider(resource=resource)

    headers = None
    if SETTINGS.GRAFANA_TENANT_ID:
        headers = {"X-Scope-OrgID": SETTINGS.GRAFANA_TENANT_ID}

    otlp_trace_exporter = OTLPSpanExporter(
        endpoint=traces_endpoint,
        headers=headers,
    )

    trace_processor = BatchSpanProcessor(
        otlp_trace_exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        schedule_delay_millis=5000,
    )
    provider.add_span_processor(trace_processor)
    trace.set_tracer_provider(provider)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, SETTINGS.LOG_LEVEL.upper()))

    # Console handler
    if SETTINGS.ENVIRONMENT == "production":
        import json

        class JSONFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                log_obj = {
                    "timestamp": self.formatTime(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "pathname": record.pathname,
                    "lineno": record.lineno,
                }
                span = trace.get_current_span()
                if span.is_recording():
                    ctx = span.get_span_context()
                    log_obj["trace_id"] = format(ctx.trace_id, "032x")
                    log_obj["span_id"] = format(ctx.span_id, "016x")
                return json.dumps(log_obj)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(console_handler)
    else:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        root_logger.addHandler(console_handler)

    # FastAPI instrumentation
    FastAPIInstrumentor().instrument_app(
        app,
        tracer_provider=provider,
        server_request_hook=server_request_hook,
    )

    # Log successful initialization
    logger = logging.getLogger(__name__)
    logger.info(
        "OpenTelemetry initialized",
        extra={
            "otlp_endpoint": otlp_endpoint,
            "service_name": SETTINGS.OTEL_SERVICE_NAME,
            "environment": SETTINGS.ENVIRONMENT,
        },
    )
