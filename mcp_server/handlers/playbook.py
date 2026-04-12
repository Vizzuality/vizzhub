"""Playbook command handler — dispatches 4 write actions to backend services."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.content_version_service import ContentVersionService
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.modules.playbook.services.tree_service import (
    ensure_unique_slug,
    generate_slug,
    get_next_position,
    validate_depth,
    validate_not_circular,
)

logger = structlog.get_logger()

MODULE = "playbook"

_versions = ContentVersionService(
    model_class=PlaybookPageVersionDB,
    entity_fk_field="node_id",
)


async def _resolve_node_by_slug(
    session: AsyncSession, slug: str, *, expected_type: str | None = None,
) -> PlaybookNodeDB:
    """Find a playbook node by slug. Raises ValueError if not found or wrong type."""
    result = await session.execute(
        select(PlaybookNodeDB).where(PlaybookNodeDB.slug == slug)
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise ValueError(f"Node with slug '{slug}' not found")
    if expected_type and node.type != expected_type:
        raise ValueError(
            f"Node '{slug}' is type '{node.type}', expected '{expected_type}'"
        )
    return node


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


async def _create_article(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (parent_slug) is required for create_article")

    parent = await _resolve_node_by_slug(session, target, expected_type="group")
    title = payload.get("title")
    if not title:
        raise ValueError("payload.title is required")

    if not await validate_depth(session, parent.id):
        raise ValueError("Maximum tree depth exceeded")

    slug = generate_slug(title)
    slug = await ensure_unique_slug(session, slug)
    position = await get_next_position(session, parent.id)

    node = PlaybookNodeDB(
        title=title,
        slug=slug,
        type="page",
        parent_id=parent.id,
        position=position,
        created_by_id=user_id,
        updated_by_id=user_id,
    )
    session.add(node)
    await session.flush()
    await session.refresh(node)

    logger.info(
        "mcp_playbook_article_created",
        node_id=str(node.id),
        slug=slug,
        title=title,
    )
    return {"node_id": str(node.id), "slug": slug, "title": title}


async def _update_article_content(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (slug) is required for update_article_content")

    node = await _resolve_node_by_slug(session, target, expected_type="page")
    content = payload.get("content")
    if content is None:
        raise ValueError("payload.content is required")

    expected_version = payload.get("expected_version")
    new_version, conflict = await _versions.save_version(
        session,
        entity_id=node.id,
        content=content,
        user_id=user_id,
        expected_version=expected_version,
    )

    h1_title = _extract_h1(content)
    if h1_title and h1_title != node.title:
        node.title = h1_title
        node.slug = await ensure_unique_slug(
            session, generate_slug(h1_title), exclude_id=node.id,
        )
        node.updated_by_id = user_id
        await session.flush()

    logger.info(
        "mcp_playbook_content_updated",
        node_id=str(node.id),
        version=new_version,
        conflict=conflict,
    )
    return {
        "node_id": str(node.id),
        "version": new_version,
        "conflict": conflict,
    }


async def _update_node(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (slug) is required for update_node")

    node = await _resolve_node_by_slug(session, target)

    if "parent_slug" in payload:
        parent_slug = payload["parent_slug"]
        parent = await _resolve_node_by_slug(
            session, parent_slug, expected_type="group",
        )
        if not await validate_not_circular(session, node.id, parent.id):
            raise ValueError("Cannot move node under its own descendant")
        if not await validate_depth(session, parent.id):
            raise ValueError("Maximum tree depth exceeded")
        node.parent_id = parent.id

    if "title" in payload:
        new_title = payload["title"]
        node.title = new_title
        node.slug = await ensure_unique_slug(
            session, generate_slug(new_title), exclude_id=node.id,
        )

    node.updated_by_id = user_id
    await session.flush()
    await session.refresh(node)

    logger.info(
        "mcp_playbook_node_updated",
        node_id=str(node.id),
        slug=node.slug,
    )
    return {
        "node_id": str(node.id),
        "slug": node.slug,
        "title": node.title,
        "parent_id": str(node.parent_id) if node.parent_id else None,
    }


async def _delete_node(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (slug) is required for delete_node")

    node = await _resolve_node_by_slug(session, target)

    result = await session.execute(
        select(sa_func.count())
        .select_from(PlaybookNodeDB)
        .where(PlaybookNodeDB.parent_id == node.id)
    )
    child_count = result.scalar_one()
    if child_count > 0:
        raise ValueError(
            f"Node '{target}' has children. Delete children first."
        )

    await session.delete(node)
    await session.flush()

    logger.info("mcp_playbook_node_deleted", slug=target)
    return {"ok": True}


def _extract_h1(content: str) -> str | None:
    """Extract H1 title from markdown content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped and not stripped.startswith("#"):
            break
    return None


# ---------------------------------------------------------------------------
# Action dispatch
# ---------------------------------------------------------------------------

_ACTIONS: dict[str, object] = {
    "create_article": _create_article,
    "update_article_content": _update_article_content,
    "update_node": _update_node,
    "delete_node": _delete_node,
}


async def execute(
    action: str,
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    """Dispatch a playbook write action to the appropriate handler."""
    handler = _ACTIONS.get(action)
    if handler is None:
        raise ValueError(f"Unknown playbook action: '{action}'")
    return await handler(target, payload, user_id, session)
