"""ISO write MCP tools — queue commands for human approval before execution."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.auth.permissions import mcp_requires
from mcp_server.tools._shared import enqueue_command


@mcp_requires("iso_docs:edit")
async def iso_create_page(parent_slug: str, title: str) -> str:
    """Create a new ISO document page under the given parent group.

    This does NOT execute immediately. The command is queued for human
    approval. Use approve_command() with the returned command_id to
    execute, or reject_command() to discard.

    Args:
        parent_slug: Slug of the parent group node (must be type "group").
        title: Title for the new page. A URL slug is generated automatically.

    Returns JSON with status, command_id, human-readable summary, and
    instructions for approval.
    """
    return await enqueue_command(
        "iso_docs", "create_page",
        target=parent_slug,
        payload={"title": title},
    )


@mcp_requires("iso_docs:edit")
async def iso_update_page_content(slug: str, content: str) -> str:
    """Update the markdown content of an ISO document page.

    This does NOT execute immediately. The command is queued for human
    approval. A new version is created when executed (version history
    is preserved). Use approve_command() to execute.

    Args:
        slug: Page slug (from iso_get_documents or iso_get_document).
        content: Full markdown content to replace the current version.
                 If the content starts with a different H1 title, the
                 page title and slug are updated automatically.

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    return await enqueue_command(
        "iso_docs", "update_page_content",
        target=slug,
        payload={"content": content},
    )


@mcp_requires("iso_docs:edit")
async def iso_update_page_metadata(
    slug: str,
    code: str | None = None,
    standard: list[str] | None = None,
    clauses: list[str] | None = None,
    classification: str | None = None,
    status: str | None = None,
    document_date: str | None = None,
    original_filename: str | None = None,
    guidance: str | None = None,
    changelog: list[dict] | None = None,
) -> str:
    """Update metadata fields on an ISO document page.

    This does NOT execute immediately. Only the fields you provide
    are updated; omitted fields remain unchanged. The command is
    queued for human approval.

    Args:
        slug: Page slug (from iso_get_documents).
        code: Document code (e.g. "POL-001", "PRO-012").
        standard: List of applicable standards (e.g. ["ISO 27001"]).
        clauses: List of clause references (e.g. ["A.5.1", "A.8.1"]).
        classification: Document classification (e.g. "internal", "public").
        status: Document status (e.g. "draft", "approved", "obsolete").
        document_date: Date string in ISO format (YYYY-MM-DD).
        original_filename: Original filename if imported from a file.
        guidance: Implementation guidance text.
        changelog: List of changelog entries, each a dict with keys
                   like "date", "description", "author". If author is
                   empty or "system", it is replaced with the user's name.

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    payload: dict = {}
    fields = {
        "code": code,
        "standard": standard,
        "clauses": clauses,
        "classification": classification,
        "status": status,
        "document_date": document_date,
        "original_filename": original_filename,
        "guidance": guidance,
        "changelog": changelog,
    }
    for key, value in fields.items():
        if value is not None:
            payload[key] = value

    return await enqueue_command(
        "iso_docs", "update_metadata",
        target=slug,
        payload=payload,
    )


@mcp_requires("iso_docs:edit")
async def iso_update_node(
    slug: str,
    title: str | None = None,
    parent_slug: str | None = None,
) -> str:
    """Rename or move an ISO document tree node (page or group).

    This does NOT execute immediately. The command is queued for human
    approval. You can rename, move, or both in a single command.

    Args:
        slug: Current slug of the node to update.
        title: New title. If provided, the slug is regenerated from the title.
        parent_slug: Slug of the new parent group. The node is moved
                     under this group. Cannot create circular references.

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if parent_slug is not None:
        payload["parent_slug"] = parent_slug

    return await enqueue_command(
        "iso_docs", "update_node",
        target=slug,
        payload=payload,
    )


@mcp_requires("iso_docs:edit")
async def iso_delete_node(slug: str) -> str:
    """Delete an ISO document tree node (page or group).

    This does NOT execute immediately. The command is queued for human
    approval. The node must be a leaf (no children). Deleting a group
    that has children will fail at execution time.

    Args:
        slug: Slug of the node to delete.

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    return await enqueue_command(
        "iso_docs", "delete_node",
        target=slug,
        payload={},
    )


@mcp_requires("iso_docs:edit")
async def iso_create_registry_row(
    slug: str,
    data: dict,
    year: int | None = None,
) -> str:
    """Create a new row in an ISO registry.

    This does NOT execute immediately. The command is queued for human
    approval. The data dict must match the registry's column schema.
    Use iso_get_registries to see available registries and their schemas.

    Args:
        slug: Registry slug (from iso_get_registries).
        data: Row data as a dict mapping column keys to values.
              Keys must match the registry's column schema.
        year: Required for yearly registries. The audit cycle year
              (e.g. 2025 for the 2025-2026 cycle). Ignored for
              non-yearly registries.

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    payload: dict = {"data": data}
    if year is not None:
        payload["year"] = year

    return await enqueue_command(
        "iso_docs", "create_registry_row",
        target=slug,
        payload=payload,
    )


@mcp_requires("iso_docs:edit")
async def iso_update_registry_row(
    slug: str,
    row_id: str,
    data: dict,
) -> str:
    """Update an existing row in an ISO registry.

    This does NOT execute immediately. The command is queued for human
    approval. Only the fields you provide in data are updated; other
    fields retain their current values (merge semantics).

    Args:
        slug: Registry slug (from iso_get_registries).
        row_id: UUID of the row to update (from iso_get_registry_rows).
        data: Partial row data — only the fields to change.

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    return await enqueue_command(
        "iso_docs", "update_registry_row",
        target=slug,
        payload={"row_id": row_id, "data": data},
    )


@mcp_requires("iso_docs:edit")
async def iso_delete_registry_row(slug: str, row_id: str) -> str:
    """Delete a row from an ISO registry.

    This does NOT execute immediately. The command is queued for human
    approval. The row is permanently removed when executed.

    Args:
        slug: Registry slug (from iso_get_registries).
        row_id: UUID of the row to delete (from iso_get_registry_rows).

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    return await enqueue_command(
        "iso_docs", "delete_registry_row",
        target=slug,
        payload={"row_id": row_id},
    )


def register_iso_write_tools(server: FastMCP) -> None:
    """Register all ISO write tools on the given MCP server instance."""
    server.tool()(iso_create_page)
    server.tool()(iso_update_page_content)
    server.tool()(iso_update_page_metadata)
    server.tool()(iso_update_node)
    server.tool()(iso_delete_node)
    server.tool()(iso_create_registry_row)
    server.tool()(iso_update_registry_row)
    server.tool()(iso_delete_registry_row)
