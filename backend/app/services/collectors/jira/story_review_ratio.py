"""
story_review_ratio - Ratio of stories with assigned reviewer

== SPEC ==

Formula:
    story_review_ratio = stories_with_reviewer / total_stories

Definition:
    Measures how many completed stories had a reviewer assigned.
    This indicates code review discipline.

JQL Queries:
    total:         project = "KEY" AND type = Story AND status = Done
    with_reviewer: project = "KEY" AND type = Story AND status = Done
                   AND reviewers IS NOT EMPTY

Data Source:
    Jira API via /rest/api/3/search/approximate-count

Target:
    Implied target is 1.0 (100% of stories should have reviewers)

Normalization:
    Higher is better: value (already 0-1)

Edge Cases:
    - No stories: ratio = None (neutral)
    - All stories have reviewers: ratio = 1.0 (perfect)
    - No reviewers field configured: returns 0

== END SPEC ==
"""

from datetime import date
from typing import TYPE_CHECKING

from app.services.collectors.jira.utils import build_jql_date_filter

if TYPE_CHECKING:
    from app.services.collectors.jira.client import JiraClient


async def collect_story_review_ratio(
    client: "JiraClient",
    project_key: str,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict:
    """
    Collect story review metrics from Jira.

    Args:
        client: Authenticated JiraClient instance
        project_key: Jira project key (e.g., "PROJ")
        period_start: Optional start date for punctual filtering (inclusive)
        period_end: Optional end date for filtering (inclusive)

    Returns:
        dict with total_stories and stories_with_reviewer counts
    """
    date_filter = build_jql_date_filter(period_start, period_end)

    total_filter = f"type = Story AND status = Done{date_filter}"
    reviewer_filter = f"type = Story AND status = Done AND reviewers IS NOT EMPTY{date_filter}"

    total_stories = await client.count_issues(
        project_key,
        total_filter,
    )

    stories_with_reviewer = await client.count_issues(
        project_key,
        reviewer_filter,
    )

    return {
        "total_stories": total_stories,
        "stories_with_reviewer": stories_with_reviewer,
    }


def calculate_story_review_ratio(
    total_stories: int, stories_with_reviewer: int
) -> float | None:
    """
    Calculate story review ratio from raw counts.

    Args:
        total_stories: Total number of completed stories
        stories_with_reviewer: Stories with reviewer assigned

    Returns:
        Ratio 0-1, or None if no stories
    """
    if total_stories <= 0:
        return None
    return min(1.0, max(0.0, stories_with_reviewer / total_stories))
