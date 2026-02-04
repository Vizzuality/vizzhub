"""
Shared utilities for Jira collectors.

This module contains common functions used across multiple
Jira collector modules to avoid duplication.
"""

from datetime import date, datetime, timedelta

from app.services.collectors.utils import parse_iso_datetime

# Re-export for backwards compatibility
parse_jira_datetime = parse_iso_datetime


def build_jql_date_filter(
    period_start: date | None,
    period_end: date | None,
    date_field: str = "resolutiondate",
) -> str:
    """
    Build a JQL date filter clause for the given period and date field.

    Args:
        period_start: Optional start date (inclusive)
        period_end: Optional end date (inclusive)
        date_field: JQL date field to filter on (e.g., "resolutiondate", "created")

    Returns:
        JQL clause string (e.g., ' AND resolutiondate >= "2024-01-01" AND resolutiondate <= "2024-01-31"')
        or empty string if no period specified
    """
    parts = []
    if period_start:
        parts.append(f'{date_field} >= "{period_start.isoformat()}"')
    if period_end:
        parts.append(f'{date_field} <= "{period_end.isoformat()}"')
    return " AND " + " AND ".join(parts) if parts else ""


def business_time_diff(
    start: datetime,
    end: datetime,
    work_start_hour: int = 9,
    work_end_hour: int = 17,
) -> float:
    """
    Calculate business hours between two datetimes.

    Business hours: Monday-Friday, configurable work hours.

    Args:
        start: Start datetime
        end: End datetime
        work_start_hour: Hour when work day starts (default: 9)
        work_end_hour: Hour when work day ends (default: 17)

    Returns:
        Total business hours between start and end
    """
    if end <= start:
        return 0.0

    hours_per_day = work_end_hour - work_start_hour
    if hours_per_day <= 0:
        return 0.0

    total_hours = 0.0
    current = start

    while current < end:
        weekday = current.weekday()

        if weekday < 5:  # Monday-Friday
            day_start = current.replace(
                hour=work_start_hour, minute=0, second=0, microsecond=0
            )
            day_end = current.replace(
                hour=work_end_hour, minute=0, second=0, microsecond=0
            )

            work_start = max(current, day_start)
            work_end = min(end, day_end)

            if work_start < work_end:
                hours = (work_end - work_start).total_seconds() / 3600
                total_hours += min(hours, hours_per_day)

        # Move to next day
        next_day = (current + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        current = next_day

    return total_hours


def business_days_diff(
    start: datetime,
    end: datetime,
    work_start_hour: int = 9,
    work_end_hour: int = 18,
) -> float:
    """
    Calculate business days between two datetimes.

    Args:
        start: Start datetime
        end: End datetime
        work_start_hour: Hour when work day starts (default: 9)
        work_end_hour: Hour when work day ends (default: 18)

    Returns:
        Total business days between start and end
    """
    hours_per_day = work_end_hour - work_start_hour
    if hours_per_day <= 0:
        return 0.0

    total_hours = business_time_diff(start, end, work_start_hour, work_end_hour)
    return total_hours / hours_per_day
