"""Capacity planner write MCP tools — queue commands for human approval.

Planner writes are future-only: no tool accepts a week before the current one.
"""

from __future__ import annotations

from datetime import timedelta

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from app.core.permissions import Action
from mcp_server.auth.permissions import mcp_requires
from mcp_server.data.capacity import current_monday
from mcp_server.tools._annotations import DESTRUCTIVE, WRITE
from mcp_server.tools._shared import enqueue_command
from mcp_server.tools.capacity import _parse_plan_date, _parse_uuid

MAX_WEEKS = 104
_PAST_WEEK_ERROR = (
    "The planner is future-only: {name} {value} is before the current week ({first}). "
    "Past allocation comes from confirmed tracker reports and cannot be planned."
)


@mcp_requires(Action.CAPACITY_MANAGE)
async def capacity_plan_set_allocation(
    user_id: str,
    project_id: str,
    percentage: int,
    start: str,
    end: str,
    comment: str | None = None,
) -> str:
    """Plan a person on a project at a fixed weekly percentage over a date range.

    FUTURE only: every week in the range must be the current week or later.
    This does NOT execute immediately. The command is queued for human
    approval; use approve_command() with the returned command_id once the
    user confirms, or reject_command() to discard.

    Sets the same percentage on every week (Monday) from start to end,
    replacing what is planned for that person on that project in those weeks.
    Other projects of the same person are untouched. A percentage of 0 clears
    those weeks.

    Args:
        user_id: User UUID (from users_get_team or capacity_get_planned).
        project_id: Project UUID (from tracker_get_projects or capacity_get_planned).
        percentage: Weekly allocation, 0-200 (100 = full week).
        start: First date, YYYY-MM-DD or YYYY-MM. Not before the current week.
        end: Last date, YYYY-MM-DD or YYYY-MM (YYYY-MM means the end of that month).
        comment: Optional note stored on each week (max 500 chars).

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    _parse_uuid(user_id, "user_id")
    _parse_uuid(project_id, "project_id")
    if not 0 <= percentage <= 200:
        raise ToolError("percentage must be between 0 and 200.")
    if comment is not None and len(comment) > 500:
        raise ToolError("comment must be 500 characters or fewer.")

    start_date = _parse_plan_date(start, "start", end=False)
    end_date = _parse_plan_date(end, "end", end=True)
    first_week = current_monday()
    first = start_date - timedelta(days=start_date.weekday())
    if first < first_week:
        raise ToolError(_PAST_WEEK_ERROR.format(name="start", value=start, first=first_week))
    if end_date < start_date:
        raise ToolError("end must be on or after start.")

    weeks = []
    week = first
    while week <= end_date:
        weeks.append(week.isoformat())
        week += timedelta(weeks=1)
    if len(weeks) > MAX_WEEKS:
        raise ToolError(f"Range covers {len(weeks)} weeks; the maximum is {MAX_WEEKS}.")

    payload: dict = {
        "user_id": user_id,
        "project_id": project_id,
        "percentage": percentage,
        "weeks": weeks,
    }
    if comment is not None:
        payload["comment"] = comment
    return await enqueue_command("capacity", "set_allocation", target=None, payload=payload)


@mcp_requires(Action.CAPACITY_MANAGE)
async def capacity_plan_clear_assignment(
    user_id: str,
    project_id: str,
    from_week: str | None = None,
) -> str:
    """Remove a person's planned weeks on a project from a week onward.

    FUTURE only: deletes planned weeks from from_week (default: the current
    week) onward. Earlier weeks are never touched. This does NOT execute
    immediately. The command is queued for human approval; use
    approve_command() with the returned command_id once the user confirms.

    Args:
        user_id: User UUID.
        project_id: Project UUID.
        from_week: First date to clear, YYYY-MM-DD or YYYY-MM. Not before the
            current week. Defaults to the current week.

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    _parse_uuid(user_id, "user_id")
    _parse_uuid(project_id, "project_id")
    first_week = current_monday()
    if from_week is None:
        start = first_week
    else:
        parsed = _parse_plan_date(from_week, "from_week", end=False)
        start = parsed - timedelta(days=parsed.weekday())
        if start < first_week:
            raise ToolError(
                _PAST_WEEK_ERROR.format(name="from_week", value=from_week, first=first_week)
            )
    return await enqueue_command(
        "capacity",
        "clear_assignment",
        target=None,
        payload={"user_id": user_id, "project_id": project_id, "from_week": start.isoformat()},
    )


def register_capacity_write_tools(server: FastMCP) -> None:
    """Register the Capacity planner write tools on the given MCP server instance."""
    server.tool(annotations=WRITE)(capacity_plan_set_allocation)
    server.tool(annotations=DESTRUCTIVE)(capacity_plan_clear_assignment)
