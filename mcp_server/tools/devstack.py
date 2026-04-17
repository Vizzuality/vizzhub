"""DevStack MCP tools — registered on the FastMCP server."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from mcp_server.auth.permissions import mcp_requires
from mcp_server.data.base import get_read_session
from mcp_server.data import devstack as devstack_data


@mcp_requires("devstack:view")
async def devstack_get_catalog() -> str:
    """Get the full DevStack catalog.

    Returns a JSON array of all active devstack entries. Each entry includes
    name, description, type, install_method, url/package, origin, and tech tags.
    """
    async with get_read_session() as session:
        data = await devstack_data.get_catalog(session)
    return json.dumps(data, indent=2, default=str)


def register_devstack_tools(server: FastMCP) -> None:
    """Register all DevStack tools on the given MCP server instance."""
    server.tool()(devstack_get_catalog)
