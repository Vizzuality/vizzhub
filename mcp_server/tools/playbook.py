"""Playbook MCP tools — registered on the FastMCP server."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.data.base import get_read_session
from mcp_server.data import playbook as playbook_data


def _to_json(data: Any) -> str:
    """Serialize data to indented JSON with safe date/uuid handling."""
    return json.dumps(data, indent=2, default=str)


async def playbook_get_tree() -> str:
    """Get the playbook navigation tree.

    Returns a hierarchical JSON structure of all playbook articles
    and groups. Each node has an id, title, slug, type (page or group),
    and children. Use slugs with playbook_get_article to fetch content.
    """
    async with get_read_session() as session:
        tree = await playbook_data.get_tree(session)
    return _to_json(tree)


async def playbook_get_article(slug: str) -> str:
    """Get the full content of a playbook article by slug.

    Returns JSON with title, full markdown content, version number,
    and publication status. Slugs are listed in the playbook tree.

    Args:
        slug: Article slug (from playbook_get_tree).
    """
    async with get_read_session() as session:
        article = await playbook_data.get_article(session, slug)

    if article is None:
        return _to_json({"error": f"Article '{slug}' not found"})
    return _to_json(article)


async def playbook_search_articles(query: str) -> str:
    """Search playbook articles by title and content.

    Returns a JSON array of matching articles with title, slug,
    and a content summary. Searches both titles and full markdown
    content using substring matching.

    Args:
        query: Search terms (e.g. "onboarding process").
    """
    async with get_read_session() as session:
        results = await playbook_data.search_articles(session, query)
    return _to_json(results)


def register_playbook_tools(server: FastMCP) -> None:
    """Register all Playbook tools on the given MCP server instance."""
    server.tool()(playbook_get_tree)
    server.tool()(playbook_get_article)
    server.tool()(playbook_search_articles)
