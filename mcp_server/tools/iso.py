"""ISO MCP tools — registered on the FastMCP server."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.data.base import get_read_session
from mcp_server.data import iso as iso_data
from mcp_server.auth.permissions import mcp_requires

from app.modules.iso_docs.services.registry_service import compute_row_fields


def _to_json(data: Any) -> str:
    """Serialize data to indented JSON with safe date/uuid handling."""
    return json.dumps(data, indent=2, default=str)


@mcp_requires("iso_docs:edit")
async def iso_get_registries() -> str:
    """List all ISO registry types with their column schemas.

    Returns a JSON array of registry types. Each entry includes the slug
    (used as identifier in other tools), name, description, whether it
    uses yearly grouping, and the full column schema.
    """
    async with get_read_session() as session:
        types = await iso_data.get_registry_types(session)
    return _to_json([
        {
            "slug": rt.slug,
            "name": rt.name,
            "description": rt.description,
            "is_yearly": rt.is_yearly,
            "columns": rt.schema,
        }
        for rt in types
    ])


@mcp_requires("iso_docs:edit")
async def iso_get_registry_rows(slug: str, year: int | None = None) -> str:
    """Get all rows from an ISO registry by its slug.

    Args:
        slug: Registry type slug (from iso_get_registries).
        year: Optional year filter for yearly registries. Defaults to
              current year if the registry uses yearly grouping.

    Returns JSON with registry metadata, column schema, and all rows
    with computed fields populated.
    """
    async with get_read_session() as session:
        try:
            rt, node_id = await iso_data.resolve_registry_node(session, slug)
        except ValueError as e:
            return _to_json({"error": str(e)})

        effective_year = year
        if effective_year is None and rt.is_yearly:
            effective_year = date.today().year

        rows = await iso_data.get_registry_rows(session, node_id, effective_year)

    return _to_json({
        "registry": rt.name,
        "slug": rt.slug,
        "year": effective_year,
        "total_rows": len(rows),
        "columns": rt.schema,
        "rows": [
            {
                "id": str(row.id),
                "row_index": row.row_index,
                "data": compute_row_fields(rt.schema, row.data),
            }
            for row in rows
        ],
    })


async def iso_get_documents(
    category: str | None = None, search: str | None = None,
) -> str:
    """List ISO documents (policies, procedures, plans) with metadata.

    Args:
        category: Filter by category (policy, procedure, plan, record, etc.).
        search: Filter by title (substring match). For full-text content
                search, use iso_search_documents instead.

    Returns JSON array of documents with slug, title, category,
    version, and a summary of the content.
    """
    async with get_read_session() as session:
        docs = await iso_data.get_documents(
            session, category=category, title_search=search,
        )
    return _to_json(docs)


async def iso_get_document(slug: str) -> str:
    """Get the full content of a single ISO document by slug.

    Args:
        slug: Document slug (from iso_get_documents).

    Returns JSON with title, category, version, and the full
    markdown content of the document.
    """
    async with get_read_session() as session:
        try:
            doc = await iso_data.get_document(session, slug)
        except ValueError as e:
            return _to_json({"error": str(e)})
    return _to_json(doc)


@mcp_requires("iso_docs:edit")
async def iso_list_notes(node_slug: str, include_done: bool = False) -> str:
    """List audit notes attached to an ISO doc node.

    Notes are short markdown messages captured by editors during audits
    (e.g. "auditor flagged version mismatch"). They can be attached to
    any node type — pages, registries, widgets, or groups.

    Args:
        node_slug: Slug of the node (document, registry, or group).
        include_done: If false (default) only pending notes are returned;
                      if true, completed notes are included as well.

    Returns JSON with the node's slug/title/type plus the list of notes,
    each with content, author, timestamps, and done status.
    """
    async with get_read_session() as session:
        try:
            data = await iso_data.get_node_notes(session, node_slug, include_done)
        except ValueError as e:
            return _to_json({"error": str(e)})
    return _to_json(data)


@mcp_requires("iso_docs:edit")
async def iso_list_pending_notes() -> str:
    """List all pending audit notes across every ISO node.

    Useful for review during an audit: returns every not-done note
    alongside the node it belongs to (slug + title + type) so the
    caller can group or follow up.

    Returns JSON array of notes sorted by node title then creation date.
    """
    async with get_read_session() as session:
        notes = await iso_data.get_pending_notes(session)
    return _to_json(notes)


async def iso_search_documents(query: str) -> str:
    """Full-text search across ISO document content.

    Args:
        query: Search terms (e.g. "encryption remote access").

    Returns JSON array of matching documents with snippet, section
    heading, and rank. Rank is a PostgreSQL ts_rank value useful
    only for ordering — it is not a normalized 0-1 score.
    """
    async with get_read_session() as session:
        results = await iso_data.search_documents(session, query)
    return _to_json(results)


def register_iso_tools(server: FastMCP) -> None:
    """Register all ISO tools on the given MCP server instance."""
    server.tool()(iso_get_registries)
    server.tool()(iso_get_registry_rows)
    server.tool()(iso_get_documents)
    server.tool()(iso_get_document)
    server.tool()(iso_search_documents)
    server.tool()(iso_list_notes)
    server.tool()(iso_list_pending_notes)
