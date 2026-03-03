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

from datetime import date
from typing import TYPE_CHECKING

from app.modules.scorecard.services.collectors.jira.utils import (
    build_jql_date_filter,
    business_time_diff,
    parse_jira_datetime,
)

if TYPE_CHECKING:
    from app.modules.scorecard.services.collectors.jira.client import JiraClient


async def collect_mttr(
    client: "JiraClient",
    project_key: str,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict:
    """
    Collect MTTR metrics from Jira.

    Args:
        client: Authenticated JiraClient instance
        project_key: Jira project key (e.g., "PROJ")
        period_start: Optional start date for punctual filtering (inclusive)
        period_end: Optional end date for filtering (inclusive)

    Returns:
        dict with incidents_count and mttr_hours
    """
    date_filter = build_jql_date_filter(period_start, period_end)
    jql = (
        f"statusCategory = Done{date_filter} AND "
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

        created = parse_jira_datetime(created_str)
        resolved = parse_jira_datetime(resolved_str)

        if created and resolved and resolved > created:
            hours = business_time_diff(created, resolved)
            if hours >= 0:
                total_hours += hours
                valid_count += 1

    mttr_hours = (total_hours / valid_count) if valid_count > 0 else None

    return {
        "incidents_count": valid_count,
        "mttr_hours": mttr_hours,
    }
