"""Structured logging configuration using structlog."""

import logging
import os
import sys

import structlog


def _add_caller_info(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Add caller info (module, function, line) only for WARNING and above."""
    record: logging.LogRecord | None = event_dict.get("_record")
    if record and record.levelno >= logging.WARNING:
        event_dict["module"] = record.module
        event_dict["func_name"] = record.funcName
        event_dict["lineno"] = record.lineno
    return event_dict


def _drop_color_message(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Drop color_message key added by uvicorn."""
    event_dict.pop("color_message", None)
    return event_dict


def _add_service_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Add service-level context fields."""
    event_dict.setdefault("service", os.environ.get("SERVICE_NAME", "vizzhub-backend"))
    event_dict.setdefault("environment", os.environ.get("APP_ENV", "development"))
    release = os.environ.get("RELEASE")
    if release:
        event_dict.setdefault("release", release)
    return event_dict


def configure_logging(
    log_format: str = "console",
    log_level: str = "INFO",
) -> None:
    """Configure structured logging for the application.

    Args:
        log_format: 'json' for production, 'console' for development.
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR).
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_service_context,
        _drop_color_message,
        structlog.stdlib.ExtraAdder(),
        _add_caller_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    if log_format == "json":
        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    else:
        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(),
            ],
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    # Quiet noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore", "aiohttp"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
