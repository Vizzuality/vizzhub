"""Portfolio MCP tools — registered on the FastMCP server."""

from __future__ import annotations

from uuid import UUID

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


@mcp_requires(Action.PORTFOLIO_VIEW)
async def portfolio_get_program(program_id: str) -> str:
    """Get the full detail of a single program.

    Returns JSON with the program name, complete profile narrative
    (objective, short description, impact story, web copy, website URL,
    main partner, stage, on_website flag), assigned tags (term name,
    taxonomy slug, is_primary), clients, and every project iteration
    (name, status, start/end year, billable and scorecard flags), plus
    the program URL.

    Args:
        program_id: Program UUID (from portfolio_search_programs or
            portfolio_list_programs).
    """
    try:
        pid = UUID(program_id)
    except ValueError:
        return to_json({"error": f"Invalid program_id: {program_id}"})

    async with get_read_session() as session:
        detail = await portfolio_data.get_program(session, pid)

    if detail is None:
        return to_json({"error": f"Program '{program_id}' not found"})
    return to_json(detail)


@mcp_requires(Action.PORTFOLIO_VIEW)
async def portfolio_list_programs(
    stage: str | None = None,
    tags: list[str] | None = None,
    client: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> str:
    """Browse the program catalogue with optional filters and pagination.

    Returns JSON `{programs, total, pages, page}` where each program is a
    compact summary: program_id, name, stage, short_description (first
    200 chars), tag names, client names, projects_count, years span, and
    URL. Use portfolio_get_program for the full narrative. For free-text
    discovery prefer portfolio_search_programs.

    Args:
        stage: Filter by profile stage (exact match, e.g. "live").
        tags: Filter by taxonomy term names (case-insensitive exact
            match). Terms from the same taxonomy combine as OR, across
            taxonomies as AND. Unresolved names are reported in
            `unmatched_tags`.
        client: Filter by client name (case-insensitive substring; must
            resolve to exactly one client, otherwise candidates are
            returned).
        page: Page number (1-based).
        limit: Programs per page (default 20, clamped to 50).
    """
    async with get_read_session() as session:
        result = await portfolio_data.list_programs(
            session, stage=stage, tags=tags, client=client, page=page, limit=limit
        )
    return to_json(result)


@mcp_requires(Action.PORTFOLIO_VIEW)
async def portfolio_get_taxonomies() -> str:
    """List the taxonomies, their terms, and the existing program stages.

    Returns JSON `{taxonomies, stages}`. Each taxonomy has slug, name,
    cardinality (single/multi), allows_primary, and its active term names.
    Use these exact term names in the portfolio_list_programs `tags`
    filter and in portfolio_set_tags; use the stage values in the `stage`
    filter.
    """
    async with get_read_session() as session:
        result = await portfolio_data.get_taxonomies(session)
    return to_json(result)


@mcp_requires(Action.PORTFOLIO_VIEW)
async def portfolio_get_clients() -> str:
    """List all clients with their project counts.

    Returns a JSON array of `{client_id, name, projects_count}` ordered by
    name. Use these names in the portfolio_list_programs `client` filter.
    """
    async with get_read_session() as session:
        result = await portfolio_data.get_clients(session)
    return to_json(result)


def register_portfolio_tools(server: FastMCP) -> None:
    """Register all Portfolio tools on the given MCP server instance."""
    server.tool(annotations=READ_ONLY)(portfolio_search_programs)
    server.tool(annotations=READ_ONLY)(portfolio_get_program)
    server.tool(annotations=READ_ONLY)(portfolio_list_programs)
    server.tool(annotations=READ_ONLY)(portfolio_get_taxonomies)
    server.tool(annotations=READ_ONLY)(portfolio_get_clients)
