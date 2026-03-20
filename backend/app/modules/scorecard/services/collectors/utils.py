"""
Shared utilities for collectors.

This module contains common functions used across multiple
collector modules (Jira, GitHub) to avoid duplication.
"""

from datetime import datetime
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")

from fastapi import HTTPException, status

from app.core.exceptions import ConfigurationError

HTTP_CLIENT_TIMEOUT = 30.0


def parse_iso_datetime(dt_str: str | None) -> datetime | None:
    """
    Parse ISO format datetime string to datetime object.

    Handles both Jira and GitHub datetime formats, which both use
    ISO 8601 with 'Z' suffix for UTC.

    Args:
        dt_str: ISO format datetime string (e.g., "2024-01-15T10:30:00Z")

    Returns:
        datetime object or None if parsing fails or input is None
    """
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


async def execute_collector(
    collector: Any,
    collect_coro: Awaitable[T],
    source_name: str,
    close_fn: Callable[[], Awaitable[None]] | None = None,
) -> T:
    """
    Execute a collector coroutine with unified error handling.

    Args:
        collector: The collector instance (used to get close method if close_fn not provided)
        collect_coro: The coroutine to execute (e.g., collector.collect(...))
        source_name: Human-readable source name for error messages (e.g., "Jira", "GitHub")
        close_fn: Optional close function; defaults to collector.close()

    Returns:
        The result from the collect coroutine

    Raises:
        ConfigurationError: Re-raised as-is for configuration issues
        HTTPException: Wrapped exception with 500 status for other errors
    """
    close = close_fn if close_fn is not None else collector.close
    try:
        return await collect_coro
    except ConfigurationError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to collect {source_name} metrics: {type(e).__name__}",
        ) from e
    finally:
        await close()
