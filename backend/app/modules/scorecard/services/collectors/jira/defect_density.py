"""
defect_density - Defects per 100 resolved tasks

== SPEC ==

Formula:
    defect_density = (bugs_total / tasks_completed) * 100

JQL Queries:
    bugs:  project = "KEY" AND type = Bug
    tasks: project = "KEY" AND type in (Story, Task, Sub-task) AND statusCategory = Done

Data Source:
    Jira API via /rest/api/3/search/approximate-count

Target:
    DefDensity_t from config DB (default: 3 defects per 100 tasks)

Normalization:
    Lower is better: min(1, target / max(value, 0.001))

Edge Cases:
    - No tasks completed: defect_density = 0 (can't have defects without work)
    - No bugs: defect_density = 0 (perfect score)
    - No Jira data: defect_density = None (neutral in score calculation)

== END SPEC ==
"""

from datetime import date
from typing import TYPE_CHECKING

from app.modules.scorecard.services.collectors.jira.utils import build_jql_date_filter

if TYPE_CHECKING:
    from app.modules.scorecard.services.collectors.jira.client import JiraClient


async def collect_defect_density(
    client: "JiraClient",
    project_key: str,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict:
    """
    Collect defect density metrics from Jira.

    Args:
        client: Authenticated JiraClient instance
        project_key: Jira project key (e.g., "PROJ")
        period_start: Optional start date for punctual filtering (inclusive)
        period_end: Optional end date for filtering (inclusive)

    Returns:
        dict with bugs_total and tasks_completed counts
    """
    bugs_date_filter = build_jql_date_filter(period_start, period_end, "created")
    tasks_date_filter = build_jql_date_filter(period_start, period_end, "resolutiondate")

    bugs_filter = f"type = Bug{bugs_date_filter}"
    tasks_filter = f"type in (Story, Task, Sub-task) AND statusCategory = Done{tasks_date_filter}"

    bugs_total = await client.count_issues(
        project_key,
        bugs_filter,
    )

    tasks_completed = await client.count_issues(
        project_key,
        tasks_filter,
    )

    return {
        "bugs_total": bugs_total,
        "tasks_completed": tasks_completed,
    }


def calculate_defect_density(bugs_total: int, tasks_completed: int) -> float | None:
    """
    Calculate defect density from raw counts.

    Args:
        bugs_total: Total number of bugs in project
        tasks_completed: Number of completed tasks (Story, Task, Sub-task)

    Returns:
        Defects per 100 tasks, or None if no data
    """
    if tasks_completed <= 0:
        return 0.0
    return (bugs_total / tasks_completed) * 100
