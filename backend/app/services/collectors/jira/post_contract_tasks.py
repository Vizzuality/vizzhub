"""
post_contract_tasks - Tasks created after contract end + grace period

== SPEC ==

Formula:
    post_contract_tasks = count of issues created >= (end_date + 30 days)

Definition:
    Measures how "cleanly" a project closes. Tasks created more than
    30 days after contract end indicate ongoing work that should have
    been completed or properly closed.

JQL Query:
    project = "KEY" AND type IN (Story, Task, Bug) AND created >= "YYYY-MM-DD"
    where date = end_date + 30 days

Data Source:
    Jira API via /rest/api/3/search/approximate-count

Target:
    PostContract_t from config DB (default: 3 tasks max)

Normalization:
    Lower is better: min(1, target / max(value, 0.001))
    If value = 0: score = 1.0 (perfect)

Edge Cases:
    - No end_date: return None (cannot calculate)
    - end_date in future: return None (project not finished)
    - No tasks after cutoff: return 0 (perfect)

== END SPEC ==
"""

from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.collectors.jira.client import JiraClient

GRACE_PERIOD_DAYS = 30


async def collect_post_contract_tasks(
    client: "JiraClient",
    project_key: str,
    end_date: date | None,
) -> dict:
    """
    Collect count of tasks created after contract end + grace period.

    Args:
        client: Authenticated JiraClient instance
        project_key: Jira project key (e.g., "PROJ")
        end_date: Project contract end date

    Returns:
        dict with post_contract_tasks count and cutoff_date
    """
    if end_date is None:
        return {
            "post_contract_tasks": None,
            "post_contract_cutoff": None,
        }

    cutoff_date = end_date + timedelta(days=GRACE_PERIOD_DAYS)

    if cutoff_date > date.today():
        return {
            "post_contract_tasks": None,
            "post_contract_cutoff": cutoff_date.isoformat(),
        }

    cutoff_str = cutoff_date.strftime("%Y-%m-%d")
    jql = f"type IN (Story, Task, Bug) AND created >= '{cutoff_str}'"

    count = await client.count_issues(project_key, jql)

    return {
        "post_contract_tasks": count,
        "post_contract_cutoff": cutoff_date.isoformat(),
    }
