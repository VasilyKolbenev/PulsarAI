"""Structured logging configuration for Pulsar AI.

Supports two output modes via ``PULSAR_LOG_FORMAT``:
- ``console`` (default): Pretty-printed colored output for development
- ``json``: Structured JSON output for production log aggregation

Uses structlog wrapping stdlib logging — zero migration needed for
existing ``logging.getLogger()`` calls throughout the codebase.

Usage::

    from pulsar_ai.logging_config import setup_logging
    setup_logging()  # Call once at application startup
"""

import logging
import os
import sys
from typing import Optional


def setup_logging(
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
) -> None:
    """Configure structured logging for the application.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to
            ``PULSAR_LOG_LEVEL`` env var or ``INFO``.
        log_format: Output format (``console`` or ``json``). Defaults to
            ``PULSAR_LOG_FORMAT`` env var or ``console``.
    """
    level_str = log_level or os.environ.get("PULSAR_LOG_LEVEL", "INFO")
    fmt = log_format or os.environ.get("PULSAR_LOG_FORMAT", "console")
    level = getattr(logging, level_str.upper(), logging.INFO)

    try:
        import structlog  # noqa: F401

        _setup_structlog(level, fmt)
    except ImportError:
        _setup_stdlib(level, fmt)


def _setup_structlog(level: int, fmt: str) -> None:
    """Configure structlog with stdlib integration."""
    import structlog

    # Shared processors for both formats
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if fmt == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib to use structlog formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _setup_stdlib(level: int, fmt: str) -> None:
    """Fallback: configure stdlib logging without structlog."""
    if fmt == "json":
        format_str = (
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","message":"%(message)s"}'
        )
    else:
        format_str = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

    logging.basicConfig(
        level=level,
        format=format_str,
        stream=sys.stderr,
        force=True,
    )
