"""ISO Docs API dependencies."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission
from app.modules.iso_docs.models.node import IsoDocNodeDB

IsoDocsEditor = Annotated[TokenData, Depends(require_permission(Action.ISO_DOCS_EDIT))]

USER_VISIBLE_ROOT_SLUGS = {"policies", "procedures"}


def is_iso_docs_editor(user: TokenData) -> bool:
    return "*" in user.permissions or Action.ISO_DOCS_EDIT in user.permissions


async def get_visible_node_ids(db: AsyncSession) -> set[UUID]:
    """Return IDs of all nodes under user-visible root groups (inclusive)."""
    roots = await db.execute(
        select(IsoDocNodeDB.id).where(
            IsoDocNodeDB.slug.in_(USER_VISIBLE_ROOT_SLUGS),
            IsoDocNodeDB.parent_id.is_(None),
        )
    )
    root_ids = {row[0] for row in roots}
    if not root_ids:
        return set()

    all_nodes = (await db.execute(select(IsoDocNodeDB.id, IsoDocNodeDB.parent_id))).all()

    children_map: dict[UUID | None, list[UUID]] = {}
    for nid, pid in all_nodes:
        children_map.setdefault(pid, []).append(nid)

    visible: set[UUID] = set()
    stack = list(root_ids)
    while stack:
        nid = stack.pop()
        visible.add(nid)
        stack.extend(children_map.get(nid, []))
    return visible


async def check_user_access(
    db: AsyncSession,
    node_id: UUID,
    user: TokenData,
) -> None:
    """Raise 403 if a non-editor user tries to access a node outside visible roots."""
    if is_iso_docs_editor(user):
        return
    visible = await get_visible_node_ids(db)
    if node_id not in visible:
        raise HTTPException(status_code=403, detail="Access denied")
