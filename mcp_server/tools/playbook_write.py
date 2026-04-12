"""Playbook write MCP tools — queue commands for human approval before execution."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from mcp_server.auth.permissions import mcp_requires
from mcp_server.data.base import get_mcp_user, get_write_session
from mcp_server.services.command_service import CommandService
from mcp_server.services.summary import generate_summary


def _to_json(data: Any) -> str:
    """Serialize data to indented JSON with safe date/uuid handling."""
    return json.dumps(data, indent=2, default=str)


async def _enqueue_playbook(action: str, target: str | None, payload: dict) -> str:
    """Shared helper: generate summary, enqueue command, return JSON response."""
    user = get_mcp_user()
    user_id = UUID(user.user_id)
    async with get_write_session() as session:
        summary = await generate_summary(session, "playbook", action, target, payload)
        svc = CommandService(session)
        cmd = await svc.enqueue(
            module="playbook",
            action=action,
            target=target,
            payload=payload,
            summary=summary,
            user_id=user_id,
        )
        return _to_json({
            "status": "queued",
            "command_id": str(cmd.id),
            "summary": cmd.summary,
            "message": f"Command queued. Use approve_command('{cmd.id}') to execute.",
        })


@mcp_requires("playbook:edit")
async def playbook_create_article(parent_slug: str, title: str) -> str:
    """Create a new playbook article under the given parent group.

    This does NOT execute immediately. The command is queued for human
    approval. Use approve_command() with the returned command_id to
    execute, or reject_command() to discard.

    Args:
        parent_slug: Slug of the parent group node (must be type "group").
        title: Title for the new article. A URL slug is generated automatically.

    Returns JSON with status, command_id, human-readable summary, and
    instructions for approval.
    """
    return await _enqueue_playbook(
        "create_article",
        target=parent_slug,
        payload={"title": title},
    )


@mcp_requires("playbook:edit")
async def playbook_update_article_content(slug: str, content: str) -> str:
    """Update the markdown content of a playbook article.

    This does NOT execute immediately. The command is queued for human
    approval. A new version is created when executed (version history
    is preserved). Use approve_command() to execute.

    Args:
        slug: Article slug (from playbook_get_tree or playbook_get_article).
        content: Full markdown content to replace the current version.
                 If the content starts with a different H1 title, the
                 article title and slug are updated automatically.

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    return await _enqueue_playbook(
        "update_article_content",
        target=slug,
        payload={"content": content},
    )


@mcp_requires("playbook:edit")
async def playbook_update_node(
    slug: str,
    title: str | None = None,
    parent_slug: str | None = None,
) -> str:
    """Rename or move a playbook tree node (article or group).

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

    return await _enqueue_playbook(
        "update_node",
        target=slug,
        payload=payload,
    )


@mcp_requires("playbook:edit")
async def playbook_delete_node(slug: str) -> str:
    """Delete a playbook tree node (article or group).

    This does NOT execute immediately. The command is queued for human
    approval. The node must be a leaf (no children). Deleting a group
    that has children will fail at execution time.

    Args:
        slug: Slug of the node to delete.

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    return await _enqueue_playbook(
        "delete_node",
        target=slug,
        payload={},
    )


def register_playbook_write_tools(server: FastMCP) -> None:
    """Register all Playbook write tools on the given MCP server instance."""
    server.tool()(playbook_create_article)
    server.tool()(playbook_update_article_content)
    server.tool()(playbook_update_node)
    server.tool()(playbook_delete_node)
