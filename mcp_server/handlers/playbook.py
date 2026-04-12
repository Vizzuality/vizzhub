"""Playbook command handler — dispatches 4 write actions to backend services."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.content_version_service import ContentVersionService
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.modules.playbook.services import tree_service

from mcp_server.handlers._shared import (
    delete_leaf_node,
    extract_h1,
    resolve_node_by_slug,
    update_node_tree,
)

logger = structlog.get_logger()

_versions = ContentVersionService(
    model_class=PlaybookPageVersionDB,
    entity_fk_field="node_id",
)


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

    parent = await resolve_node_by_slug(
        session, PlaybookNodeDB, target, expected_type="group",
    )
    title = payload.get("title")
    if not title:
        raise ValueError("payload.title is required")

    if not await tree_service.validate_depth(session, parent.id):
        raise ValueError("Maximum tree depth exceeded")

    slug = tree_service.generate_slug(title)
    slug = await tree_service.ensure_unique_slug(session, slug)
    position = await tree_service.get_next_position(session, parent.id)

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

    node = await resolve_node_by_slug(
        session, PlaybookNodeDB, target, expected_type="page",
    )
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

    h1_title = extract_h1(content)
    if h1_title and h1_title != node.title:
        node.title = h1_title
        node.slug = await tree_service.ensure_unique_slug(
            session, tree_service.generate_slug(h1_title), exclude_id=node.id,
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

    result = await update_node_tree(
        session, PlaybookNodeDB, target, payload, user_id,
        tree_service=tree_service,
    )
    logger.info(
        "mcp_playbook_node_updated",
        node_id=result["node_id"],
        slug=result["slug"],
    )
    return result


async def _delete_node(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (slug) is required for delete_node")

    await delete_leaf_node(session, PlaybookNodeDB, target)
    logger.info("mcp_playbook_node_deleted", slug=target)
    return {"ok": True}


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
