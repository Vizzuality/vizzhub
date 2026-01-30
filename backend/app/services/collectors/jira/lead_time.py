"""
lead_time - Average lead time in business days

== SPEC ==

Formula:
    lead_time_days = avg(resolution_time - first_in_progress_time) in business days

Definition:
    Average business days from when an issue first enters "In Progress" status
    until it's resolved ("Done"). This measures development cycle time,
    excluding backlog waiting time.

    Business day = 9 hours (09:00-18:00, Monday-Friday)

In Progress statuses (case-insensitive):
    - In Progress
    - In Development
    - Development
    - Work In Progress
    - WIP
    - Code Review
    - QA

JQL Query:
    project = "KEY" AND type IN (Story, Task, Bug)
    AND statusCategory = Done
    ORDER BY resolutiondate DESC

Data Source:
    Jira API via /rest/api/3/search with expand=changelog

Target:
    LT_t from config DB (default: 5 days)

Normalization:
    Lower is better: min(1, target / max(value, 0.001))

Edge Cases:
    - No resolved issues: lead_time = None (neutral)
    - Issue without In Progress transition: skip issue (no fallback)
    - Issue without resolution date: skip issue
    - Resolution before start: skip issue (data error)

== END SPEC ==
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from app.services.collectors.jira.utils import (
    business_days_diff,
    parse_jira_datetime,
)

if TYPE_CHECKING:
    from app.services.collectors.jira.client import JiraClient


IN_PROGRESS_STATUSES = {
    "in progress",
    "in development",
    "development",
    "work in progress",
    "wip",
    "code review",
    "qa",
}


async def collect_lead_time(
    client: "JiraClient",
    project_key: str,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict:
    """
    Collect lead time metrics from Jira.

    Args:
        client: Authenticated JiraClient instance
        project_key: Jira project key (e.g., "PROJ")
        period_start: Optional start date for punctual filtering (inclusive)
        period_end: Optional end date for filtering (inclusive)

    Returns:
        dict with lead_time_days and sample_size
    """
    date_filter = ""
    if period_start:
        date_filter += f' AND resolutiondate >= "{period_start.isoformat()}"'
    if period_end:
        date_filter += f' AND resolutiondate <= "{period_end.isoformat()}"'

    jql = (
        f"type IN (Story, Task, Bug) AND statusCategory = Done{date_filter} "
        "ORDER BY resolutiondate DESC"
    )

    issues = await client.search_issues(
        project_key,
        jql,
        fields=["created", "resolutiondate"],
        max_results=1000,
        expand=["changelog"],
    )

    if not issues:
        return {"lead_time_days": None, "sample_size": 0}

    total_days = 0.0
    valid_count = 0

    for issue in issues:
        fields = issue.get("fields", {})
        resolved_str = fields.get("resolutiondate")

        if not resolved_str:
            continue

        resolved = parse_jira_datetime(resolved_str)
        if not resolved:
            continue

        # Find first In Progress transition from changelog
        start_time = _find_first_in_progress(issue)

        # Skip issues without work transition (no fallback to created date)
        if not start_time:
            continue

        if resolved > start_time:
            days = business_days_diff(start_time, resolved)
            if days >= 0:
                total_days += days
                valid_count += 1

    lead_time_days = (total_days / valid_count) if valid_count > 0 else None

    return {
        "lead_time_days": lead_time_days,
        "sample_size": valid_count,
    }


def _find_first_in_progress(issue: dict) -> datetime | None:
    """
    Find the first transition to an In Progress status from changelog.

    Args:
        issue: Jira issue dict with changelog

    Returns:
        Datetime of first In Progress transition, or None if not found
    """
    changelog = issue.get("changelog", {})
    histories = changelog.get("histories", [])

    in_progress_times: list[datetime] = []

    for history in histories:
        created_str = history.get("created")
        if not created_str:
            continue

        for item in history.get("items", []):
            if item.get("field") == "status":
                to_status = (item.get("toString") or "").lower()
                if to_status in IN_PROGRESS_STATUSES:
                    dt = parse_jira_datetime(created_str)
                    if dt:
                        in_progress_times.append(dt)

    return min(in_progress_times) if in_progress_times else None
