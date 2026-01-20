"""
escaped_rate - Escaped defects per 100 resolved tasks

== SPEC ==

Formula:
    escaped_rate = (escaped_defects / tasks_resolved) * 100

Definition:
    Escaped defects are bugs found in Staging or Production environments.
    These are bugs that "escaped" the development/QA process.

JQL Queries:
    escaped: project = "KEY" AND type = Bug AND cf[10231] IN ("staging", "production")
             (cf[10231] is the "Environment" custom field)
    tasks:   project = "KEY" AND type in (Story, Task, Bug) AND statusCategory = Done

Data Source:
    Jira API via /rest/api/3/search/approximate-count

Target:
    Escaped_t from config DB (default: 1 per 100 tasks)

Normalization:
    Lower is better: min(1, target / max(value, 0.001))

Edge Cases:
    - No tasks resolved: escaped_rate = 0
    - No escaped defects: escaped_rate = 0 (perfect)
    - No Jira data: escaped_rate = None (neutral in score calculation)

== END SPEC ==
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.collectors.jira.client import JiraClient


async def collect_escaped_rate(client: "JiraClient", project_key: str) -> dict:
    """
    Collect escaped defects metrics from Jira.

    Args:
        client: Authenticated JiraClient instance
        project_key: Jira project key (e.g., "PROJ")

    Returns:
        dict with escaped_defects and tasks_resolved counts
    """
    escaped_defects = await client.count_issues(
        project_key,
        "type = Bug AND 'Environment' IN ('Staging', 'Production')",
    )

    tasks_resolved = await client.count_issues(
        project_key,
        "type in (Story, Task, Bug) AND statusCategory = Done",
    )

    return {
        "escaped_defects": escaped_defects,
        "tasks_resolved": tasks_resolved,
    }


def calculate_escaped_rate(escaped_defects: int, tasks_resolved: int) -> float | None:
    """
    Calculate escaped defect rate from raw counts.

    Args:
        escaped_defects: Number of bugs found in Staging/Production
        tasks_resolved: Number of resolved tasks (Story, Task, Bug)

    Returns:
        Escaped defects per 100 tasks, or None if no data
    """
    if tasks_resolved <= 0:
        return 0.0
    return (escaped_defects / tasks_resolved) * 100
