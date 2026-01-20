"""
lead_time - Average lead time in business days

== SPEC ==

Formula:
    lead_time_days = avg(end_time - start_time) in business days

Definition:
    Average business days from when an issue enters "To Do" status
    to when it's resolved ("Done").

    Business day = 9 hours (09:00-18:00, Monday-Friday)

JQL Query:
    project = "KEY" AND type IN (Story, Task, Bug)
    AND statusCategory = Done
    AND resolutiondate >= -90d
    ORDER BY resolutiondate DESC

Data Source:
    Jira API via /rest/api/3/search with fields: created, resolutiondate

Target:
    LT_t from config DB (default: 5 days)

Normalization:
    Lower is better: min(1, target / max(value, 0.001))

Edge Cases:
    - No resolved issues: lead_time = None (neutral)
    - Issue without resolution date: skip issue
    - Resolution before creation: skip issue (data error)

== END SPEC ==
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.collectors.jira.client import JiraClient


async def collect_lead_time(client: "JiraClient", project_key: str) -> dict:
    """
    Collect lead time metrics from Jira.

    Args:
        client: Authenticated JiraClient instance
        project_key: Jira project key (e.g., "PROJ")

    Returns:
        dict with lead_time_days and sample_size
    """
    jql = (
        "type IN (Story, Task, Bug) AND statusCategory = Done "
        "AND resolutiondate >= -90d ORDER BY resolutiondate DESC"
    )

    issues = await client.search_issues(
        project_key,
        jql,
        fields=["created", "resolutiondate"],
        max_results=200,
    )

    if not issues:
        return {"lead_time_days": None, "sample_size": 0}

    total_days = 0.0
    valid_count = 0

    for issue in issues:
        fields = issue.get("fields", {})
        created_str = fields.get("created")
        resolved_str = fields.get("resolutiondate")

        if not created_str or not resolved_str:
            continue

        created = _parse_jira_datetime(created_str)
        resolved = _parse_jira_datetime(resolved_str)

        if created and resolved and resolved > created:
            days = _business_days_diff(created, resolved)
            if days >= 0:
                total_days += days
                valid_count += 1

    lead_time_days = (total_days / valid_count) if valid_count > 0 else None

    return {
        "lead_time_days": lead_time_days,
        "sample_size": valid_count,
    }


def _parse_jira_datetime(dt_str: str) -> datetime | None:
    """Parse Jira datetime string to datetime object."""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _business_days_diff(start: datetime, end: datetime) -> float:
    """
    Calculate business days between two datetimes.

    Business day = 9 hours (09:00-18:00, Monday-Friday)
    """
    if end <= start:
        return 0.0

    work_start_hour = 9
    work_end_hour = 18
    hours_per_day = work_end_hour - work_start_hour

    total_hours = 0.0
    current = start

    while current < end:
        weekday = current.weekday()

        if weekday < 5:
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

        next_day = (current + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        current = next_day

    return total_hours / hours_per_day if hours_per_day > 0 else 0.0
