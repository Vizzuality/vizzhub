"""ISO MCP tools — registered on the FastMCP server."""

from __future__ import annotations

import json
from datetime import date

from mcp_server.data.base import get_read_session
from mcp_server.data import iso as iso_data
from mcp_server.server import mcp

from app.modules.iso_docs.services.registry_service import compute_row_fields


@mcp.tool()
async def iso_get_registries() -> str:
    """List all ISO registry types with their column schemas.

    Returns a JSON array of registry types. Each entry includes the slug
    (used as identifier in other tools), name, description, whether it
    uses yearly grouping, and the full column schema.
    """
    async with get_read_session() as session:
        types = await iso_data.get_registry_types(session)
    return json.dumps(
        [
            {
                "slug": rt.slug,
                "name": rt.name,
                "description": rt.description,
                "is_yearly": rt.is_yearly,
                "columns": rt.schema,
            }
            for rt in types
        ],
        indent=2,
        default=str,
    )


@mcp.tool()
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
            return json.dumps({"error": str(e)})

        effective_year = year
        if effective_year is None and rt.is_yearly:
            effective_year = date.today().year

        rows = await iso_data.get_registry_rows(session, node_id, effective_year)

    return json.dumps(
        {
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
        },
        indent=2,
        default=str,
    )
