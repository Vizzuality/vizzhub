"""
commitment_reliability - Sprint commitment reliability ratio

== SPEC ==

Formula:
    commitment_reliability = single_sprint_issues / committed_issues

Definition:
    Measures how often issues are completed within their original sprint
    vs being moved across multiple sprints.

    - committed_issues: Issues that were in at least 1 closed sprint
    - single_sprint_issues: Issues completed in exactly 1 sprint (no spillover)
    - multi_sprint_issues: Issues that touched more than 1 sprint

Data Source:
    Jira Agile API:
    - GET /rest/agile/1.0/board?projectKeyOrId=KEY&type=scrum
    - GET /rest/agile/1.0/board/{boardId}/sprint?state=closed
    - POST /rest/api/3/search/jql with sprint = {sprintId}

Target:
    Implied target is 1.0 (all issues completed in original sprint)

Normalization:
    Higher is better: value (already 0-1)

Edge Cases:
    - No scrum board: ratio = None (neutral)
    - No closed sprints: ratio = None (neutral)
    - No committed issues: ratio = None (neutral)

== END SPEC ==
"""

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.collectors.jira.client import JiraClient


def _empty_result() -> dict:
    """Return empty commitment reliability result."""
    return {
        "commitment_reliability": None,
        "committed_issues": 0,
        "single_sprint_issues": 0,
        "multi_sprint_issues": 0,
    }


def _parse_sprint_end_date(sprint: dict) -> date | None:
    """Parse sprint end date, returning None if invalid or missing."""
    end_date_str = sprint.get("endDate")
    if not end_date_str:
        return None
    try:
        return date.fromisoformat(end_date_str[:10])
    except (ValueError, TypeError):
        return None


def _is_sprint_within_period(
    sprint: dict,
    period_start: date | None,
    period_end: date | None,
) -> bool:
    """Check if sprint end date falls within the specified period."""
    sprint_end = _parse_sprint_end_date(sprint)
    if not sprint_end:
        return True
    if period_start and sprint_end < period_start:
        return False
    if period_end and sprint_end > period_end:
        return False
    return True


def _compute_reliability(issue_sprint_count: dict[str, set[int]]) -> dict:
    """Compute commitment reliability from issue-sprint mapping."""
    committed = 0
    single = 0
    multi = 0

    for sprints in issue_sprint_count.values():
        count = len(sprints)
        if count >= 1:
            committed += 1
            if count == 1:
                single += 1
            else:
                multi += 1

    ratio = (single / committed) if committed > 0 else None
    return {
        "commitment_reliability": ratio,
        "committed_issues": committed,
        "single_sprint_issues": single,
        "multi_sprint_issues": multi,
    }


async def collect_commitment_reliability(
    client: "JiraClient",
    project_key: str,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict:
    """
    Collect commitment reliability metrics from Jira.

    Args:
        client: Authenticated JiraClient instance
        project_key: Jira project key (e.g., "PROJ")
        period_start: Optional start date for punctual filtering (inclusive)
        period_end: Optional end date to filter sprints ended by this date

    Returns:
        dict with commitment_reliability ratio and detail counts
    """
    board = await _get_scrum_board(client, project_key)
    if not board:
        return _empty_result()

    closed_sprints = await _get_closed_sprints(client, board["id"], period_start, period_end)
    if not closed_sprints:
        return _empty_result()

    issue_sprint_count: dict[str, set[int]] = {}

    for sprint in closed_sprints:
        sprint_id = sprint["id"]
        issue_keys = await _get_sprint_issue_keys(client, sprint_id, project_key)

        for key in issue_keys:
            if key not in issue_sprint_count:
                issue_sprint_count[key] = set()
            issue_sprint_count[key].add(sprint_id)

    return _compute_reliability(issue_sprint_count)


async def _get_scrum_board(client: "JiraClient", project_key: str) -> dict | None:
    """Get the first scrum board for a project."""
    http_client = await client.get_client()

    try:
        response = await http_client.get(
            "/rest/agile/1.0/board",
            params={"projectKeyOrId": project_key, "type": "scrum", "maxResults": 1},
        )
        if response.status_code == 200:
            data = response.json()
            boards = data.get("values", [])
            return boards[0] if boards else None
    except Exception:
        pass
    return None


async def _get_closed_sprints(
    client: "JiraClient",
    board_id: int,
    period_start: date | None = None,
    period_end: date | None = None,
) -> list[dict]:
    """Get all closed sprints for a board, optionally filtered by date range."""
    http_client = await client.get_client()

    sprints = []
    start_at = 0
    batch_size = 50

    while True:
        try:
            response = await http_client.get(
                f"/rest/agile/1.0/board/{board_id}/sprint",
                params={"state": "closed", "startAt": start_at, "maxResults": batch_size},
            )
            if response.status_code != 200:
                break

            data = response.json()
            values = data.get("values", [])

            filtered = [
                sprint for sprint in values
                if _is_sprint_within_period(sprint, period_start, period_end)
            ]
            sprints.extend(filtered)

            if data.get("isLast", True) or not values:
                break
            start_at += len(values)
        except Exception:
            break

    return sprints


async def _get_sprint_issue_keys(
    client: "JiraClient", sprint_id: int, project_key: str
) -> list[str]:
    """Get all issue keys for a sprint."""
    jql = f"sprint = {sprint_id} AND project = {project_key}"

    issues = await client.search_issues(
        project_key,
        jql,
        fields=["key"],
        max_results=2000,
        skip_project_prefix=True,
    )

    return [issue.get("key", "") for issue in issues if issue.get("key")]
