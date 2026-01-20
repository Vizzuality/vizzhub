"""
defect_density - Defects per 100 resolved tasks

== SPEC ==

Formula:
    defect_density = (bugs_resolved / tasks_resolved) × 100

JQL Queries:
    bugs:  project = "KEY" AND type = Bug AND statusCategory = Done
    tasks: project = "KEY" AND type in (Story, Task, Sub-task) AND statusCategory = Done

Data Source:
    Jira API via /rest/api/3/search/approximate-count

Target:
    DefDensity_t from config DB (default: 3 defects per 100 tasks)

Normalization:
    Lower is better: min(1, target / max(value, 0.001))

Edge Cases:
    - No tasks resolved: defect_density = 0 (can't have defects without work)
    - No bugs resolved: defect_density = 0 (perfect score)
    - No Jira data: defect_density = None (neutral in score calculation)

== END SPEC ==
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.collectors.jira.client import JiraClient


async def collect_defect_density(client: "JiraClient", project_key: str) -> dict:
    """
    Collect defect density metrics from Jira.

    Args:
        client: Authenticated JiraClient instance
        project_key: Jira project key (e.g., "PROJ")

    Returns:
        dict with bugs_closed and tasks_completed counts
    """
    bugs_closed = await client.count_issues(
        project_key,
        "type = Bug AND statusCategory = Done",
    )

    tasks_completed = await client.count_issues(
        project_key,
        "type in (Story, Task, Sub-task) AND statusCategory = Done",
    )

    return {
        "bugs_closed": bugs_closed,
        "tasks_completed": tasks_completed,
    }


def calculate_defect_density(bugs_closed: int, tasks_completed: int) -> float | None:
    """
    Calculate defect density from raw counts.

    Args:
        bugs_closed: Number of resolved bugs
        tasks_completed: Number of resolved tasks (Story, Task, Sub-task)

    Returns:
        Defects per 100 tasks, or None if no data
    """
    if tasks_completed <= 0:
        return 0.0
    return (bugs_closed / tasks_completed) * 100
