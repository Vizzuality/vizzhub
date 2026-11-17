"""Capacity MCP read tools.

Time rule: past = confirmed tracker reports (capacity_get_reported_*),
future = capacity planner (capacity_get_planned). Tool names and descriptions
state the side of the boundary so the model picks the right one.
"""

from __future__ import annotations

import calendar
from datetime import date
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from app.core.permissions import Action
from mcp_server.auth.permissions import mcp_requires
from mcp_server.data import capacity as capacity_data
from mcp_server.data.base import get_read_session
from mcp_server.tools._annotations import READ_ONLY
from mcp_server.tools._shared import to_json

VALID_FAS = ("BE", "Coms", "Design", "FE", "PM", "Sci")


def _parse_month(value: str | None, name: str) -> date | None:
    """Parse YYYY-MM to the first day of that month."""
    if value is None:
        return None
    try:
        year, month = value.split("-")[:2]
        return date(int(year), int(month), 1)
    except ValueError as exc:
        raise ToolError(f"Invalid {name}: {value!r}. Use YYYY-MM.") from exc


def _parse_plan_date(value: str | None, name: str, *, end: bool) -> date | None:
    """Parse YYYY-MM-DD, or YYYY-MM as the first (start) or last (end) day of the month."""
    if value is None:
        return None
    try:
        if len(value) == 7:
            first = _parse_month(value, name)
            if end:
                return first.replace(day=calendar.monthrange(first.year, first.month)[1])
            return first
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ToolError(f"Invalid {name}: {value!r}. Use YYYY-MM or YYYY-MM-DD.") from exc


def _parse_uuid(value: str | None, name: str) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError as exc:
        raise ToolError(f"Invalid {name}: {value!r}. Expected a UUID.") from exc


def _check_fa(fa: str | None) -> None:
    if fa is not None and fa not in VALID_FAS:
        raise ToolError(f"Invalid fa: {fa}. Use one of: {', '.join(VALID_FAS)}.")


@mcp_requires(Action.TRACKER_VIEW)
async def capacity_get_reported_overview(
    start_month: str | None = None,
    end_month: str | None = None,
) -> str:
    """PAST only: billable share by functional area, from confirmed tracker reports.

    Covers closed reporting periods only. Months after the last closed month are
    not confirmed yet and are never returned; for upcoming weeks or months use
    capacity_get_planned instead.

    Returns data_source, last_closed_month, and periods: one entry per month
    with each functional area (FE, BE, Design, PM, Sci, Coms) and its average
    billable %, absence % and user count. Default: the last 6 closed months.

    Args:
        start_month: First month, YYYY-MM.
        end_month: Last month, YYYY-MM. Truncated to the last closed month.
    """
    start = _parse_month(start_month, "start_month")
    end = _parse_month(end_month, "end_month")
    async with get_read_session() as session:
        return to_json(await capacity_data.get_reported_overview(session, start, end))


@mcp_requires(Action.TRACKER_VIEW)
async def capacity_get_reported_by_fa(
    fa: str,
    start_month: str | None = None,
    end_month: str | None = None,
) -> str:
    """PAST only: per-person breakdown of one functional area, from confirmed reports.

    Covers closed reporting periods only. For upcoming weeks or months use
    capacity_get_planned(fa=...) instead.

    Returns periods with, per person: user_id, name, billable %, absence %
    and number of billable projects. Default: the last 6 closed months.

    Args:
        fa: Functional area short code: FE, BE, Design, PM, Sci or Coms.
        start_month: First month, YYYY-MM.
        end_month: Last month, YYYY-MM. Truncated to the last closed month.
    """
    _check_fa(fa)
    start = _parse_month(start_month, "start_month")
    end = _parse_month(end_month, "end_month")
    async with get_read_session() as session:
        return to_json(await capacity_data.get_reported_by_fa(session, fa, start, end))


@mcp_requires(Action.TRACKER_VIEW)
async def capacity_get_reported_by_user(
    user_id: str,
    start_month: str | None = None,
    end_month: str | None = None,
) -> str:
    """PAST only: per-project breakdown of one person, from confirmed reports.

    Covers closed reporting periods only. For what a person is planned to do
    in upcoming weeks use capacity_get_planned(user_id=...) instead.

    Returns periods with the person's project percentages and absence %.
    Default: the last 6 closed months.

    Args:
        user_id: User UUID (from users_get_team or capacity_get_reported_by_fa).
        start_month: First month, YYYY-MM.
        end_month: Last month, YYYY-MM. Truncated to the last closed month.
    """
    _parse_uuid(user_id, "user_id")
    start = _parse_month(start_month, "start_month")
    end = _parse_month(end_month, "end_month")
    async with get_read_session() as session:
        return to_json(await capacity_data.get_reported_by_user(session, user_id, start, end))


@mcp_requires(Action.TRACKER_VIEW)
async def capacity_get_reported_average(
    view: str = "users",
    start_month: str | None = None,
    end_month: str | None = None,
) -> str:
    """PAST only: allocation averaged over closed periods, from confirmed reports.

    "users" view: each person with their project segments. "projects" view:
    each project with its people. Default: the last 3 closed periods. For
    upcoming allocation use capacity_get_planned instead.

    Args:
        view: "users" (default) or "projects".
        start_month: First month, YYYY-MM.
        end_month: Last month, YYYY-MM. Truncated to the last closed month.
    """
    if view not in ("users", "projects"):
        raise ToolError(f"Invalid view: {view}. Use 'users' or 'projects'.")
    start = _parse_month(start_month, "start_month")
    end = _parse_month(end_month, "end_month")
    async with get_read_session() as session:
        return to_json(await capacity_data.get_reported_average(session, view, start, end))


@mcp_requires(Action.CAPACITY_VIEW)
async def capacity_get_planned(
    start: str | None = None,
    end: str | None = None,
    user_id: str | None = None,
    project_id: str | None = None,
    fa: str | None = None,
) -> str:
    """FUTURE only: planned weekly allocation from the capacity planner.

    Covers the current week onward and never returns past weeks; for past
    months use the capacity_get_reported_* tools (confirmed reports). Use this
    for availability, upcoming staffing and who is free or overloaded.

    Returns data_source, range (first_week, last_week), assignments (one per
    person-project, with kind billable/absence/other and weeks: {Monday date:
    percentage}) and overallocated_weeks (person-weeks planned above 100%).
    A person with no assignment in a week has nothing planned that week.
    Default: the next 13 weeks.

    Args:
        start: First date, YYYY-MM-DD or YYYY-MM. Moved forward to the current week.
        end: Last date, YYYY-MM-DD or YYYY-MM (YYYY-MM means the end of that month).
        user_id: Only this person (UUID, from users_get_team).
        project_id: Only this project (UUID, from tracker_get_projects).
        fa: Only this functional area: FE, BE, Design, PM, Sci or Coms.
    """
    _check_fa(fa)
    start_date = _parse_plan_date(start, "start", end=False)
    end_date = _parse_plan_date(end, "end", end=True)
    async with get_read_session() as session:
        result = await capacity_data.get_planned(
            session,
            start_date,
            end_date,
            user_id=_parse_uuid(user_id, "user_id"),
            project_id=_parse_uuid(project_id, "project_id"),
            fa=fa,
        )
    return to_json(result)


def register_capacity_tools(server: FastMCP) -> None:
    """Register all Capacity read tools on the given MCP server instance."""
    server.tool(annotations=READ_ONLY)(capacity_get_reported_overview)
    server.tool(annotations=READ_ONLY)(capacity_get_reported_by_fa)
    server.tool(annotations=READ_ONLY)(capacity_get_reported_by_user)
    server.tool(annotations=READ_ONLY)(capacity_get_reported_average)
    server.tool(annotations=READ_ONLY)(capacity_get_planned)
