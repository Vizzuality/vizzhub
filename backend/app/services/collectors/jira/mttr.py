"""
mttr - Mean Time To Repair (business hours)

== SPEC ==

Formula:
    mttr_hours = avg(resolution_time) for incidents/high-priority bugs

Definition:
    Average business hours between issue creation and resolution for:
    - All Incidents
    - Bugs with priority in (Highest, High, "Fix now")

    Business hours: Monday-Friday, 09:00-17:00 (8 hours/day)

JQL Query:
    project = "KEY" AND statusCategory = Done
    AND (type = Incident OR (type = Bug AND priority IN ("Highest", "High", "Fix now")))

Data Source:
    Jira API via /rest/api/3/search with fields: created, resolutiondate

Target:
    MTTR_t from config DB (default: 24 hours)

Normalization:
    Lower is better: min(1, target / max(value, 0.001))

Edge Cases:
    - No incidents: mttr = None (neutral)
    - Issue without resolution date: skip issue
    - Resolution before creation: skip issue (data error)

== END SPEC ==
"""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.collectors.jira.client import JiraClient


async def collect_mttr(client: "JiraClient", project_key: str) -> dict:
    """
    Collect MTTR metrics from Jira.

    Args:
        client: Authenticated JiraClient instance
        project_key: Jira project key (e.g., "PROJ")

    Returns:
        dict with incidents_count and mttr_hours
    """
    jql = (
        "statusCategory = Done AND "
        "(type = Incident OR (type = Bug AND priority IN ('Highest', 'High', 'Fix now')))"
    )

    issues = await client.search_issues(
        project_key,
        jql,
        fields=["created", "resolutiondate"],
        max_results=200,
    )

    if not issues:
        return {"incidents_count": 0, "mttr_hours": None}

    total_hours = 0.0
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
            hours = _business_hours_diff(created, resolved)
            if hours >= 0:
                total_hours += hours
                valid_count += 1

    mttr_hours = (total_hours / valid_count) if valid_count > 0 else None

    return {
        "incidents_count": valid_count,
        "mttr_hours": mttr_hours,
    }


def _parse_jira_datetime(dt_str: str) -> datetime | None:
    """Parse Jira datetime string to datetime object."""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _business_hours_diff(start: datetime, end: datetime) -> float:
    """
    Calculate business hours between two datetimes.

    Business hours: Monday-Friday, 09:00-17:00 (8 hours/day)
    """
    if end <= start:
        return 0.0

    work_start_hour = 9
    work_end_hour = 17
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

        current = current.replace(hour=0, minute=0, second=0, microsecond=0)
        current = current.replace(day=current.day + 1) if current.day < 28 else _next_day(current)

    return total_hours


def _next_day(dt: datetime) -> datetime:
    """Get next day handling month boundaries."""
    from datetime import timedelta
    return (dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
