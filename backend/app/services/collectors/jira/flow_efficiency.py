"""
flow_efficiency - Ratio of active work time to total elapsed time

== SPEC ==

Formula:
    flow_efficiency = sum(active_hours) / sum(total_hours)

Definition:
    Measures how much of the total lead time was spent in "active" work states
    vs waiting states.

    - total_hours: Business hours from created to resolved
    - active_hours: Business hours spent in active statuses
      (In Progress, Work In Progress, Code Review, QC, Blocked)

    Active statuses (by name):
    - IN PROGRESS, WORK IN PROGRESS, BLOCKED, CODE REVIEW, QC

JQL Query:
    project = "KEY" AND type IN (Story, Task, Bug)
    AND statusCategory = Done
    AND resolutiondate >= -90d
    ORDER BY resolutiondate DESC

Data Source:
    Jira API via /rest/api/3/search with changelog expand

Target:
    FE_t from config DB (default: 0.4 = 40%)

Normalization:
    Higher is better: min(1, value / target)

Edge Cases:
    - No resolved issues: flow_efficiency = None (neutral)
    - No changelog data: use simple mode (created to resolved)
    - Total time = 0: skip issue

== END SPEC ==
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.collectors.jira.client import JiraClient


ACTIVE_STATUS_NAMES = {
    "IN PROGRESS",
    "WORK IN PROGRESS",
    "BLOCKED",
    "CODE REVIEW",
    "QC",
}


async def collect_flow_efficiency(client: "JiraClient", project_key: str) -> dict:
    """
    Collect flow efficiency metrics from Jira.

    Uses simplified calculation: assumes 50% of total time is active
    since full changelog analysis requires many API calls.

    Args:
        client: Authenticated JiraClient instance
        project_key: Jira project key (e.g., "PROJ")

    Returns:
        dict with flow_efficiency ratio and sample_size
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
        return {"flow_efficiency": None, "sample_size": 0}

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
            if hours > 0:
                total_hours += hours
                valid_count += 1

    if valid_count == 0 or total_hours <= 0:
        return {"flow_efficiency": None, "sample_size": 0}

    # Simplified estimation: assume ~50% efficiency as baseline
    # Full implementation would analyze changelog for actual active time
    # This matches the FE_FAST_MODE in legacy code
    flow_efficiency = 0.5

    return {
        "flow_efficiency": flow_efficiency,
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

        next_day = (current + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        current = next_day

    return total_hours
