"""Portfolio MCP tools — registered on the FastMCP server."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.core.permissions import Action
from mcp_server.auth.permissions import mcp_requires
from mcp_server.data import portfolio as portfolio_data
from mcp_server.data.base import get_read_session
from mcp_server.tools._annotations import READ_ONLY
from mcp_server.tools._shared import to_json


@mcp_requires(Action.PORTFOLIO_VIEW)
async def portfolio_search_programs(query: str, limit: int = 10) -> str:
    """Full-text search over the program catalogue narrative.

    Searches program names plus profile narrative fields (objective,
    short description, impact story, web copy, main partner) using
    PostgreSQL full-text search with English stemming. Returns a JSON
    array ordered by relevance (name matches first): program_id, name,
    stage, a highlighted snippet, and the program URL.

    Args:
        query: Free-text search query (min 2 chars; websearch syntax
            supported, e.g. quoted phrases).
        limit: Max results (default 10, clamped to 50).
    """
    async with get_read_session() as session:
        rows = await portfolio_data.search_programs(session, query, limit)
    return to_json(rows)


def register_portfolio_tools(server: FastMCP) -> None:
    """Register all Portfolio tools on the given MCP server instance."""
    server.tool(annotations=READ_ONLY)(portfolio_search_programs)
