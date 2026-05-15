"""
lead_time - Jira cycle time in business days (NOT DORA "Lead Time for Changes")

== SPEC ==

Formula:
    lead_time_days = median(resolution_time - first_in_progress_time) in business days

Definition:
    Median business days from when an issue first enters "In Progress" status
    until it's resolved ("Done"). This measures development cycle time,
    excluding backlog waiting time.

    Business day = 9 hours (09:00-18:00 UTC, Monday-Friday).
    Note: the business window is UTC, not the team's local TZ. Teams east
    or west of UTC may see slight under-counting; not corrected here.

    Important: this is NOT the DORA "Lead Time for Changes" metric (which
    measures commit -> production deploy). The classifier in dora.py uses
    business-day thresholds tuned for this Jira cycle-time measurement.

Aggregation:
    Median, not mean. Audit #7 (2026-05-15) moved from arithmetic mean to
    median so a single neglected ticket doesn't flip the team's tier.

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
from statistics import median
from typing import TYPE_CHECKING

from app.modules.scorecard.services.collectors.jira.utils import (
    build_jql_date_filter,
    business_days_diff,
    parse_jira_datetime,
)

if TYPE_CHECKING:
    from app.modules.scorecard.services.collectors.jira.client import JiraClient


IN_PROGRESS_STATUSES = frozenset({
    "in progress",
    "in development",
    "development",
    "work in progress",
    "wip",
    "code review",
    "qa",
})


def _calculate_issue_lead_time(issue: dict) -> float | None:
    """Calculate lead time for a single issue. Returns None if invalid."""
    fields = issue.get("fields", {})
    resolved_str = fields.get("resolutiondate")
    if not resolved_str:
        return None

    resolved = parse_jira_datetime(resolved_str)
    if not resolved:
        return None

    start_time = _find_first_in_progress(issue)
    if not start_time or resolved <= start_time:
        return None

    days = business_days_diff(start_time, resolved)
    return days if days >= 0 else None


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
    date_filter = build_jql_date_filter(period_start, period_end)
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

    lead_times = [
        lt for issue in issues
        if (lt := _calculate_issue_lead_time(issue)) is not None
    ]

    # Median (not mean): single outliers don't dominate the team's metric.
    # See audit #7 for the trade-off discussion.
    lead_time_days = float(median(lead_times)) if lead_times else None

    return {
        "lead_time_days": lead_time_days,
        "sample_size": len(lead_times),
    }


def _extract_in_progress_time(history: dict) -> datetime | None:
    """Extract in-progress transition time from a changelog history entry."""
    created_str = history.get("created")
    if not created_str:
        return None

    for item in history.get("items", []):
        if item.get("field") != "status":
            continue
        to_status = (item.get("toString") or "").lower()
        if to_status in IN_PROGRESS_STATUSES:
            return parse_jira_datetime(created_str)
    return None


def _find_first_in_progress(issue: dict) -> datetime | None:
    """Find the first transition to an In Progress status from changelog."""
    histories = issue.get("changelog", {}).get("histories", [])

    in_progress_times = [
        dt for history in histories
        if (dt := _extract_in_progress_time(history)) is not None
    ]

    return min(in_progress_times) if in_progress_times else None
