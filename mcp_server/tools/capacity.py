"""Capacity MCP tools — registered on the FastMCP server."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.core.permissions import Action
from mcp_server.auth.permissions import mcp_requires
from mcp_server.data import capacity as capacity_data
from mcp_server.data.base import get_read_session
from mcp_server.tools._annotations import READ_ONLY


def _to_json(data: Any) -> str:
    """Serialize data to indented JSON with safe date/uuid handling."""
    return json.dumps(data, indent=2, default=str)


def _parse_month(value: str | None) -> date | None:
    """Parse YYYY-MM string to first-of-month date."""
    if value is None:
        return None
    try:
        parts = value.split("-")
        return date(int(parts[0]), int(parts[1]), 1)
    except (ValueError, IndexError):
        return None


@mcp_requires(Action.TRACKER_VIEW)
async def capacity_get_insights(
    start_month: str | None = None,
    end_month: str | None = None,
) -> str:
    """Get billable allocation overview by functional area and period.

    Returns a JSON array of periods. Each period has an array of
    functional areas (FE, BE, Design, PM, Sci, Coms) with their
    average billable percentage, absence percentage, and user count.
    Default range: last 6 months.

    Args:
        start_month: Start month as YYYY-MM (e.g. "2025-10"). Defaults to 6 months ago.
        end_month: End month as YYYY-MM (e.g. "2026-03"). Defaults to current month.
    """
    start = _parse_month(start_month)
    end = _parse_month(end_month)
    async with get_read_session() as session:
        result = await capacity_data.get_insights(session, start, end)
    return _to_json(result)


@mcp_requires(Action.TRACKER_VIEW)
async def capacity_get_fa_detail(
    fa: str,
    start_month: str | None = None,
    end_month: str | None = None,
) -> str:
    """Get per-user breakdown for a functional area.

    Returns a JSON array of periods with per-user billable percentage,
    absence percentage, and count of billable projects. Use this to
    drill into a specific FA from the overview.

    Args:
        fa: Functional area short code — FE, BE, Design, PM, Sci, or Coms.
        start_month: Start month as YYYY-MM. Defaults to 6 months ago.
        end_month: End month as YYYY-MM. Defaults to current month.
    """
    valid_fas = {"FE", "BE", "Design", "PM", "Sci", "Coms"}
    if fa not in valid_fas:
        return _to_json({"error": f"Invalid FA: {fa}. Use one of: {', '.join(sorted(valid_fas))}"})

    start = _parse_month(start_month)
    end = _parse_month(end_month)
    async with get_read_session() as session:
        result = await capacity_data.get_fa_detail(session, fa, start, end)
    return _to_json(result)


@mcp_requires(Action.TRACKER_VIEW)
async def capacity_get_user_detail(
    user_id: str,
    start_month: str | None = None,
    end_month: str | None = None,
) -> str:
    """Get per-project breakdown for a specific user.

    Returns a JSON array of periods with project allocations (name,
    percentage) and absence percentage. Use this to drill into a
    specific user from the FA detail view.

    Args:
        user_id: User UUID (from tracker_get_projects team data or capacity_get_fa_detail).
        start_month: Start month as YYYY-MM. Defaults to 6 months ago.
        end_month: End month as YYYY-MM. Defaults to current month.
    """
    start = _parse_month(start_month)
    end = _parse_month(end_month)
    async with get_read_session() as session:
        result = await capacity_data.get_user_detail(session, user_id, start, end)
    return _to_json(result)


@mcp_requires(Action.TRACKER_VIEW)
async def capacity_get_allocation(
    view: str = "users",
    start_month: str | None = None,
    end_month: str | None = None,
) -> str:
    """Get averaged allocation across finished periods.

    Returns allocation segments showing how time is distributed.
    In "users" view: per-user with project segments.
    In "projects" view: per-project with user segments.
    Default: last 3 finished periods.

    Args:
        view: "users" (default) or "projects".
        start_month: Start month as YYYY-MM. Optional.
        end_month: End month as YYYY-MM. Optional.
    """
    if view not in ("users", "projects"):
        return _to_json({"error": f"Invalid view: {view}. Use 'users' or 'projects'."})

    start = _parse_month(start_month)
    end = _parse_month(end_month)
    async with get_read_session() as session:
        result = await capacity_data.get_allocation(session, view, start, end)
    return _to_json(result)


def register_capacity_tools(server: FastMCP) -> None:
    """Register all Capacity tools on the given MCP server instance."""
    server.tool(annotations=READ_ONLY)(capacity_get_insights)
    server.tool(annotations=READ_ONLY)(capacity_get_fa_detail)
    server.tool(annotations=READ_ONLY)(capacity_get_user_detail)
    server.tool(annotations=READ_ONLY)(capacity_get_allocation)
