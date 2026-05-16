"""DevStack MCP tools — registered on the FastMCP server."""

from __future__ import annotations

import json
from typing import Literal

from mcp.server.fastmcp import FastMCP

from mcp_server.auth.permissions import mcp_requires
from app.core.permissions import Action
from mcp_server.data.base import get_read_session
from mcp_server.data import devstack as devstack_data


@mcp_requires(Action.DEVSTACK_VIEW)
async def devstack_get_catalog() -> str:
    """Get the full DevStack catalog.

    Returns a JSON array of all active devstack entries. Each entry includes
    name, description, type, install_method, url/package, origin, and tech tags.
    Use for sync, admin, or install flows. For dev-facing discovery, prefer
    devstack_discover.
    """
    async with get_read_session() as session:
        data = await devstack_data.get_catalog(session)
    return json.dumps(data, indent=2, default=str)


@mcp_requires(Action.DEVSTACK_VIEW)
async def devstack_discover(
    type: Literal["skill", "command", "plugin", "config", "agent"] | None = None,
    tech: list[str] | None = None,
    featured_only: bool = False,
) -> str:
    """Discover DevStack artifacts available for developers.

    Lightweight catalog view optimized for LLM consumption. Returns a compact
    JSON array with only `name`, `type`, and `description` — use when the dev
    asks "what skills/agents/commands are available?". For install details
    (URL, package, SHA), call devstack_get_catalog.

    Args:
        type: Filter by artifact type. Omit to include all types.
        tech: Filter by tech tags (any-match). E.g. ["python"] or ["react", "ts"].
        featured_only: If true, return only featured entries.
    """
    async with get_read_session() as session:
        data = await devstack_data.discover(
            session,
            type_=type,
            tech=tech,
            featured_only=featured_only,
        )
    return json.dumps(data, default=str)


@mcp_requires(Action.DEVSTACK_VIEW)
async def devstack_get_tech_radar(
    file: Literal["development", "devops", "tools-and-libraries", "data-science-gis"],
) -> str:
    """Fetch a Vizzuality Tech Radar file (markdown).

    Returns the raw markdown for the requested file. Use before suggesting any
    library, framework, or pattern — only the Adopt tier is auto-approved;
    Trial/Assess/Hold require team discussion.

    Args:
        file: Radar section name (without `.md`): "development", "devops",
            "tools-and-libraries", or "data-science-gis".
    """
    async with get_read_session() as session:
        content = await devstack_data.get_tech_radar(session, file)
    if content is None:
        return json.dumps({"error": f"Could not fetch tech-radar/{file}.md"})
    return content


@mcp_requires(Action.DEVSTACK_VIEW)
async def devstack_get_installable(name: str) -> str:
    """Get a ready-to-write installable for a DevStack catalog entry.

    Fetches the source from GitHub, injects `devstack_sha` into the YAML
    frontmatter, and returns the final `{target_path, content}` to be written
    verbatim. Use this instead of composing the frontmatter on the client —
    it eliminates drift between local files and the catalog.

    Supports only `github`-installed skills, commands, and agents. On failure
    returns a JSON object with `error` and `code` fields.

    Args:
        name: Catalog entry name (unique per catalog).
    """
    try:
        async with get_read_session() as session:
            data = await devstack_data.get_installable(session, name)
    except devstack_data.InstallableError as exc:
        return json.dumps({"error": exc.message, "code": exc.code})

    # Fire-and-log — never blocks the response.
    await devstack_data.track_install(name)

    return json.dumps(data)


def register_devstack_tools(server: FastMCP) -> None:
    """Register all DevStack tools on the given MCP server instance."""
    server.tool()(devstack_get_catalog)
    server.tool()(devstack_discover)
    server.tool()(devstack_get_tech_radar)
    server.tool()(devstack_get_installable)
