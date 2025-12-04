"""Structured logging with OpenTelemetry trace context."""

from contextvars import ContextVar
from typing import Any, Dict, cast

import structlog
from opentelemetry import trace

# Context variables for additional attributes
log_context: ContextVar[Dict[str, Any]] = ContextVar("log_context", default={})


class EnrichedLogger:
    """Logger with automatic OpenTelemetry context injection."""

    def __init__(self, logger: structlog.BoundLogger):
        self.logger = logger

    def _add_trace_context(self, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Add trace_id and span_id from current context."""
        span = trace.get_current_span()
        if span.is_recording():
            span_context = span.get_span_context()
            event_dict["trace_id"] = format(span_context.trace_id, "032x")
            event_dict["span_id"] = format(span_context.span_id, "016x")

        # Add context variables
        event_dict.update(log_context.get())

        return event_dict

    def bind(self, **kwargs: Any) -> "EnrichedLogger":
        """Add context to logger."""
        bound_logger = cast(structlog.BoundLogger, self.logger.bind(**kwargs))
        return EnrichedLogger(bound_logger)

    def info(self, msg: str, **kwargs: Any) -> None:
        kwargs = self._add_trace_context(kwargs)
        self.logger.info(msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        kwargs = self._add_trace_context(kwargs)
        self.logger.error(msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        kwargs = self._add_trace_context(kwargs)
        self.logger.warning(msg, **kwargs)

    def debug(self, msg: str, **kwargs: Any) -> None:
        kwargs = self._add_trace_context(kwargs)
        self.logger.debug(msg, **kwargs)


# Initialize structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Base logger
base_logger = structlog.get_logger()


def enrich_context(**kwargs: Any) -> EnrichedLogger:
    """Create logger with enriched context."""
    bound_logger = cast(structlog.BoundLogger, base_logger.bind(**kwargs))
    return EnrichedLogger(bound_logger)


def set_request_context(**kwargs: Any) -> None:
    """Set context for entire request. Used in middleware."""
    current_context = log_context.get()
    current_context.update(kwargs)
    log_context.set(current_context)
