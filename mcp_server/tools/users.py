"""Users MCP tools — registered on the FastMCP server."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.data import users as users_data
from mcp_server.data.base import get_read_session
from mcp_server.tools._annotations import READ_ONLY


def _to_json(data: Any) -> str:
    """Serialize data to indented JSON with safe date/uuid handling."""
    return json.dumps(data, indent=2, default=str)


async def users_get_team(
    active_only: bool = True,
    functional_area: str | None = None,
) -> str:
    """Get the team directory — list of users with their role and area.

    Returns a JSON array of users with name, email, functional area,
    rate band, dedication (FTE), roles, and active status.
    Default: active users only.

    Args:
        active_only: If true (default), only return active users.
        functional_area: Filter by functional area name (e.g. "Frontend Developer", "PM").
    """
    async with get_read_session() as session:
        result = await users_data.get_team(
            session, active_only=active_only, functional_area=functional_area,
        )
    return _to_json(result)


async def users_get_detail(user_id: str) -> str:
    """Get full profile for a specific user.

    Returns a JSON object with name, email, functional area, rate band
    and value, dedication (FTE), roles, Slack display name, last login,
    and reporting requirement. Use the user_id from users_get_team,
    tracker_get_projects (team members), or capacity tools.

    Args:
        user_id: User UUID.
    """
    async with get_read_session() as session:
        result = await users_data.get_detail(session, user_id)
    if result is None:
        return _to_json({"error": f"User not found: {user_id}"})
    return _to_json(result)


async def users_get_functional_areas() -> str:
    """List all functional areas (team skill categories).

    Returns a JSON array of functional areas with id and name.
    Examples: Frontend Developer, Backend Developer, Designer, PM, Scientist, Communications.
    """
    async with get_read_session() as session:
        result = await users_data.get_functional_areas(session)
    return _to_json(result)


async def users_get_rates() -> str:
    """List all billing rate bands.

    Returns a JSON array of rate bands with id, code (A-D), and hourly value.
    Rate bands are assigned to users and determine billing cost.
    """
    async with get_read_session() as session:
        result = await users_data.get_rates(session)
    return _to_json(result)


def register_users_tools(server: FastMCP) -> None:
    """Register all Users tools on the given MCP server instance."""
    server.tool(annotations=READ_ONLY)(users_get_team)
    server.tool(annotations=READ_ONLY)(users_get_detail)
    server.tool(annotations=READ_ONLY)(users_get_functional_areas)
    server.tool(annotations=READ_ONLY)(users_get_rates)
