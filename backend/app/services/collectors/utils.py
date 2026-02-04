"""
Shared utilities for collectors.

This module contains common functions used across multiple
collector modules (Jira, GitHub) to avoid duplication.
"""

from datetime import datetime

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
