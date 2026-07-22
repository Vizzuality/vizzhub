"""Tracker MCP tools — registered on the FastMCP server."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from app.core.permissions import Action
from mcp_server.auth.permissions import mcp_requires
from mcp_server.data import tracker as tracker_data
from mcp_server.data.base import get_read_session
from mcp_server.tools._annotations import READ_ONLY, READ_ONLY_OPEN_WORLD


def _to_json(data: Any) -> str:
    """Serialize data to indented JSON with safe date/uuid handling."""
    return json.dumps(data, indent=2, default=str)


@mcp_requires(Action.TRACKER_VIEW)
async def tracker_get_projects(
    status: str | None = None,
    is_billable: bool | None = None,
) -> str:
    """List all tracked projects with cost summary.

    Returns a JSON array of projects. Each entry includes name, code,
    status, budget, staff/non-staff costs, burn percentage, and income
    from paid invoices. Absence projects are excluded.

    Args:
        status: Filter by project status (proposal, live, finished).
        is_billable: Filter by billable flag (true/false).
    """
    async with get_read_session() as session:
        projects = await tracker_data.get_projects(
            session, status=status, is_billable=is_billable,
        )
    return _to_json(projects)


@mcp_requires(Action.TRACKER_VIEW)
async def tracker_get_project_detail(project_id: str) -> str:
    """Get full detail for a single project.

    Returns JSON with project info, budget lines (days/percentage per
    functional area), and cost summary with per-period breakdown
    (staff cost, non-staff cost, total per month).

    Args:
        project_id: Project UUID (from tracker_get_projects).
    """
    try:
        pid = UUID(project_id)
    except ValueError:
        return _to_json({"error": f"Invalid project_id: {project_id}"})

    async with get_read_session() as session:
        detail = await tracker_data.get_project_detail(session, pid)

    if detail is None:
        return _to_json({"error": f"Project '{project_id}' not found"})
    return _to_json(detail)


@mcp_requires(Action.TRACKER_VIEW)
async def tracker_get_project_time(
    project_id: str,
    group_by: str = "user",
) -> str:
    """Get time allocation for a project grouped by user or functional area.

    Returns JSON array of groups, each with total days, total cost,
    and a per-period breakdown. Use group_by="functional_area" to see
    effort by role instead of by person.

    Args:
        project_id: Project UUID (from tracker_get_projects).
        group_by: Grouping dimension — "user" (default) or "functional_area".
    """
    try:
        pid = UUID(project_id)
    except ValueError:
        return _to_json({"error": f"Invalid project_id: {project_id}"})

    if group_by not in ("user", "functional_area"):
        return _to_json({"error": f"Invalid group_by: {group_by}. Use 'user' or 'functional_area'."})

    async with get_read_session() as session:
        rows = await tracker_data.get_project_time(session, pid, group_by=group_by)
    return _to_json(rows)


@mcp_requires(Action.TRACKER_VIEW)
async def tracker_get_project_invoices(project_id: str) -> str:
    """Get invoices for a project with effective status.

    Returns JSON array of invoices ordered by due date. Each entry
    includes amount, milestone, due date, and effective status which
    accounts for postponements (a scheduled invoice past its due date
    becomes "pending_to_issue"; one with an active postponement shows
    as "postponed").

    Args:
        project_id: Project UUID (from tracker_get_projects).
    """
    try:
        pid = UUID(project_id)
    except ValueError:
        return _to_json({"error": f"Invalid project_id: {project_id}"})

    async with get_read_session() as session:
        invoices = await tracker_data.get_project_invoices(session, pid)
    return _to_json(invoices)


@mcp_requires(Action.TRACKER_VIEW)
async def tracker_get_project_progress(project_id: str) -> str:
    """Get progress history for a project.

    Returns JSON array of progress reports ordered by period (newest
    first). Each entry has percentage (0-100) representing completion,
    and delta (change from prior period, can be negative).

    Args:
        project_id: Project UUID (from tracker_get_projects).
    """
    try:
        pid = UUID(project_id)
    except ValueError:
        return _to_json({"error": f"Invalid project_id: {project_id}"})

    async with get_read_session() as session:
        progress = await tracker_data.get_project_progress(session, pid)
    return _to_json(progress)


@mcp_requires(Action.TRACKER_VIEW)
async def tracker_get_periods(status: str | None = None) -> str:
    """List reporting periods with report counts.

    Returns JSON array of periods ordered by date (newest first).
    Each entry includes status (unstarted, active, finished),
    base rate, total report count, and confirmed report count.

    Args:
        status: Filter by period status (unstarted, active, finished).
    """
    async with get_read_session() as session:
        periods = await tracker_data.get_periods(session, status=status)
    return _to_json(periods)


@mcp_requires(Action.TRACKER_VIEW)
async def tracker_get_user_jira_issues(
    user_id: str,
    start_date: str,
    end_date: str,
) -> str:
    """Get Jira issues assigned to a user in a date range.

    Returns issues that were In Progress or moved to Done during the
    period. Useful for understanding what a team member worked on.
    Cross-reference user_id from users_get_team or capacity_get_fa_detail.

    Args:
        user_id: User UUID (from users_get_team or capacity_get_fa_detail).
        start_date: Start of range (YYYY-MM-DD).
        end_date: End of range (YYYY-MM-DD).
    """
    try:
        uid = UUID(user_id)
    except ValueError:
        return _to_json({"error": f"Invalid user_id: {user_id}"})

    async with get_read_session() as session:
        result = await tracker_data.get_user_jira_issues(
            session, uid, start_date, end_date,
        )
    return _to_json(result)


@mcp_requires(Action.ALL)
async def tracker_get_moods(month: int, year: int) -> str:
    """Get team mood data for one month (admin-only).

    Mood is self-reported (1 = lowest, 5 = highest) when a person confirms
    their monthly report. Returns JSON with the mood distribution, average,
    response counts, and per-person responses (user_id, user_name, mood,
    feedback text) — so individual moods ARE attributable here. Also includes
    anonymous feedback texts, which are unattributable by design.

    Args:
        month: Calendar month (1-12).
        year: Calendar year (e.g. 2026).
    """
    if not 1 <= month <= 12:
        return _to_json({"error": f"Invalid month: {month}. Use 1-12."})

    async with get_read_session() as session:
        result = await tracker_data.get_moods(session, month=month, year=year)
    return _to_json(result)


@mcp_requires(Action.ALL)
async def tracker_get_moods_trend(
    months: int = 12,
    user_id: str | None = None,
) -> str:
    """Get mood trend over the last N months, per person (admin-only).

    Answers questions like "who has the lowest mood historically?" (see
    user_summary, sorted lowest average first) or "how has X's mood evolved?"
    (pass user_id to filter everything to one person). Returns JSON with:
    months[] (average, response count, and named responses per month) and
    user_summary[] (per-person average/min/max over the whole window).
    Mood scale is 1 (lowest) to 5 (highest).

    Args:
        months: Window size in months, ending at the current month
            (default 12, max 60).
        user_id: Optional user UUID (from users_get_team) to filter to
            one person.
    """
    uid: UUID | None = None
    if user_id is not None:
        try:
            uid = UUID(user_id)
        except ValueError:
            return _to_json({"error": f"Invalid user_id: {user_id}"})

    async with get_read_session() as session:
        result = await tracker_data.get_moods_trend(session, months=months, user_id=uid)
    return _to_json(result)


def register_tracker_tools(server: FastMCP) -> None:
    """Register all Tracker tools on the given MCP server instance."""
    server.tool(annotations=READ_ONLY)(tracker_get_projects)
    server.tool(annotations=READ_ONLY)(tracker_get_project_detail)
    server.tool(annotations=READ_ONLY)(tracker_get_project_time)
    server.tool(annotations=READ_ONLY)(tracker_get_project_invoices)
    server.tool(annotations=READ_ONLY)(tracker_get_project_progress)
    server.tool(annotations=READ_ONLY)(tracker_get_periods)
    # Reads live Jira, not our DB → open world.
    server.tool(annotations=READ_ONLY_OPEN_WORLD)(tracker_get_user_jira_issues)
    # Admin-only (Action.ALL) — mood data is person-attributable.
    server.tool(annotations=READ_ONLY)(tracker_get_moods)
    server.tool(annotations=READ_ONLY)(tracker_get_moods_trend)
