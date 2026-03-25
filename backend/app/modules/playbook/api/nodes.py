"""Playbook tree node CRUD endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import CurrentUser, DBSession
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.schemas.node import (
    NodeCreate,
    NodeResponse,
    NodeUpdate,
    ReorderRequest,
)
from app.modules.playbook.services.tree_service import (
    ensure_unique_slug,
    generate_slug,
    get_next_position,
    validate_depth,
    validate_not_circular,
)

router = APIRouter()


def _build_tree(nodes: list[PlaybookNodeDB], parent_id: UUID | None = None) -> list[dict]:
    """Recursively build nested tree from flat node list."""
    children = [n for n in nodes if n.parent_id == parent_id]
    children.sort(key=lambda n: n.position)
    result = []
    for node in children:
        item = {
            "id": node.id,
            "title": node.title,
            "slug": node.slug,
            "type": node.type,
            "parent_id": node.parent_id,
            "position": node.position,
            "is_public": node.is_public,
            "children": _build_tree(nodes, node.id),
        }
        result.append(item)
    return result


async def _count_descendants(db: AsyncSession, node_id: UUID) -> int:
    """Count all descendants of a node (recursive CTE)."""
    base = select(PlaybookNodeDB.id).where(PlaybookNodeDB.parent_id == node_id)
    cte = base.cte(name="descendants", recursive=True)
    recursive = select(PlaybookNodeDB.id).where(
        PlaybookNodeDB.parent_id == cte.c.id
    )
    cte = cte.union_all(recursive)
    result = await db.execute(select(sa_func.count()).select_from(cte))
    return result.scalar_one()


@router.get("/tree")
async def get_tree(db: DBSession, user: CurrentUser) -> list[dict]:
    result = await db.execute(
        select(PlaybookNodeDB).order_by(PlaybookNodeDB.position)
    )
    nodes = list(result.scalars().all())
    return _build_tree(nodes)


@router.post("/nodes", status_code=201)
async def create_node(
    data: NodeCreate, db: DBSession, user: CurrentUser
) -> NodeResponse:
    if not await validate_depth(db, data.parent_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum tree depth exceeded (10 levels)",
        )

    slug = generate_slug(data.title)
    slug = await ensure_unique_slug(db, slug, data.parent_id)
    position = await get_next_position(db, data.parent_id)

    user_id = UUID(user.user_id)
    node = PlaybookNodeDB(
        title=data.title,
        slug=slug,
        type=data.type,
        parent_id=data.parent_id,
        position=position,
        created_by_id=user_id,
        updated_by_id=user_id,
    )
    db.add(node)
    await db.flush()
    await db.refresh(node)
    return NodeResponse.model_validate(node)


@router.patch("/nodes/{node_id}", responses={404: {"description": "Node not found"}})
async def update_node(
    node_id: UUID, data: NodeUpdate, db: DBSession, user: CurrentUser
) -> NodeResponse:
    result = await db.execute(
        select(PlaybookNodeDB).where(PlaybookNodeDB.id == node_id)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    update = data.model_dump(exclude_unset=True)

    if "parent_id" in update and update["parent_id"] != node.parent_id:
        new_parent = update["parent_id"]
        if not await validate_not_circular(db, node_id, new_parent):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot move node under its own descendant",
            )
        if not await validate_depth(db, new_parent):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum tree depth exceeded (10 levels)",
            )

    for field, value in update.items():
        setattr(node, field, value)
    node.updated_by_id = UUID(user.user_id)
    await db.flush()
    await db.refresh(node)
    return NodeResponse.model_validate(node)


@router.delete("/nodes/{node_id}", responses={404: {"description": "Node not found"}})
async def delete_node(
    node_id: UUID, db: DBSession, user: CurrentUser
) -> dict:
    result = await db.execute(
        select(PlaybookNodeDB).where(PlaybookNodeDB.id == node_id)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    descendant_count = await _count_descendants(db, node_id)
    await db.delete(node)
    await db.flush()
    return {"deleted_count": descendant_count + 1}


@router.put("/nodes/reorder", responses={404: {"description": "Node not found"}})
async def reorder_nodes(
    data: ReorderRequest, db: DBSession, user: CurrentUser
) -> dict:
    node_ids = [item.id for item in data.items]
    result = await db.execute(
        select(PlaybookNodeDB).where(PlaybookNodeDB.id.in_(node_ids))
    )
    nodes_by_id = {n.id: n for n in result.scalars()}

    for item in data.items:
        node = nodes_by_id.get(item.id)
        if not node:
            raise HTTPException(
                status_code=404, detail=f"Node {item.id} not found"
            )
        node.parent_id = item.parent_id
        node.position = item.position
    await db.flush()
    return {"ok": True}
