"""DevStack MCP tools — registered on the FastMCP server."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from mcp_server.auth.permissions import mcp_requires
from mcp_server.data.base import get_mcp_user, get_read_session, get_write_session
from mcp_server.data import devstack as devstack_data


@mcp_requires("devstack:view")
async def devstack_get_catalog() -> str:
    """Get the DevStack catalog for the current user.

    Returns a JSON array of devstack entries the user should have installed.
    Includes all required entries (org-wide tools) plus any optional entries
    the user has explicitly opted into. Each entry includes name, description,
    type, install_method, url/package, origin, tech tags, and the SHA of the
    last confirmed sync.
    """
    user = get_mcp_user()
    async with get_read_session() as session:
        data = await devstack_data.get_catalog_for_user(session, user.user_id)
    return json.dumps(data, indent=2, default=str)


@mcp_requires("devstack:view")
async def devstack_update_sync_status(entry_name: str, sha: str) -> str:
    """Record that a devstack entry has been synced to the given git SHA.

    Call this after successfully installing or updating a devstack entry
    to track the installed version. Updates the user's sync record for
    the named entry.

    Args:
        entry_name: Name of the devstack entry (from devstack_get_catalog).
        sha: Git commit SHA of the installed version.

    Returns JSON with status=ok on success, or an error if the entry is
    not found.
    """
    user = get_mcp_user()
    async with get_write_session() as session:
        found = await devstack_data.update_sync_status(
            session, user.user_id, entry_name, sha,
        )
    if not found:
        return json.dumps({"error": f"Entry not found: {entry_name}"})
    return json.dumps({"status": "ok", "entry_name": entry_name, "sha": sha})


def register_devstack_tools(server: FastMCP) -> None:
    """Register all DevStack tools on the given MCP server instance."""
    server.tool()(devstack_get_catalog)
    server.tool()(devstack_update_sync_status)
