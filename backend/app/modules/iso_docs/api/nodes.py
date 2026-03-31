"""ISO Docs tree node CRUD endpoints."""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import CurrentUser, DBSession
from app.modules.iso_docs.api.deps import IsoDocsEditor, is_iso_docs_editor
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.schemas.node import (
    NodeCreate,
    NodeResponse,
    NodeUpdate,
    ReorderRequest,
)
from app.modules.iso_docs.services.tree_service import (
    ensure_unique_slug,
    generate_slug,
    get_next_position,
    validate_depth,
    validate_not_circular,
)

logger = structlog.get_logger()

router = APIRouter()


def _build_tree(nodes: list[IsoDocNodeDB], parent_id: UUID | None = None) -> list[dict]:
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
            "children": _build_tree(nodes, node.id),
        }
        result.append(item)
    return result


async def _count_descendants(db: AsyncSession, node_id: UUID) -> int:
    """Count all descendants of a node (recursive CTE)."""
    base = select(IsoDocNodeDB.id).where(IsoDocNodeDB.parent_id == node_id)
    cte = base.cte(name="descendants", recursive=True)
    recursive = select(IsoDocNodeDB.id).where(
        IsoDocNodeDB.parent_id == cte.c.id
    )
    cte = cte.union_all(recursive)
    result = await db.execute(select(sa_func.count()).select_from(cte))
    return result.scalar_one()


@router.get("/tree")
async def get_tree(db: DBSession, user: CurrentUser) -> list[dict]:
    result = await db.execute(
        select(IsoDocNodeDB).order_by(IsoDocNodeDB.position)
    )
    nodes = list(result.scalars().all())

    if not is_iso_docs_editor(user):
        confidential_result = await db.execute(
            select(IsoDocMetadataDB.node_id).where(
                IsoDocMetadataDB.classification == "confidential"
            )
        )
        confidential_ids = {row[0] for row in confidential_result}
        nodes = [n for n in nodes if n.id not in confidential_ids]

    return _build_tree(nodes)


@router.post("/nodes", status_code=201)
async def create_node(
    data: NodeCreate, db: DBSession, user: IsoDocsEditor
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
    node = IsoDocNodeDB(
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
    logger.info("iso_doc_node_created", node_id=str(node.id), title=data.title, type=data.type)
    return NodeResponse.model_validate(node)


@router.patch("/nodes/{node_id}", responses={404: {"description": "Node not found"}})
async def update_node(
    node_id: UUID, data: NodeUpdate, db: DBSession, user: IsoDocsEditor
) -> NodeResponse:
    result = await db.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.id == node_id)
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

    if "title" in update and update["title"] != node.title:
        new_slug = generate_slug(update["title"])
        parent_for_slug = update.get("parent_id", node.parent_id)
        update["slug"] = await ensure_unique_slug(
            db, new_slug, parent_for_slug, exclude_id=node_id
        )

    for field, value in update.items():
        setattr(node, field, value)
    node.updated_by_id = UUID(user.user_id)
    await db.flush()
    await db.refresh(node)
    return NodeResponse.model_validate(node)


@router.delete("/nodes/{node_id}", responses={404: {"description": "Node not found"}})
async def delete_node(
    node_id: UUID, db: DBSession, user: IsoDocsEditor
) -> dict:
    result = await db.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.id == node_id)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    descendant_count = await _count_descendants(db, node_id)
    await db.delete(node)
    await db.flush()
    logger.info("iso_doc_node_deleted", node_id=str(node_id), deleted_count=descendant_count + 1)
    return {"deleted_count": descendant_count + 1}


@router.put("/nodes/reorder", responses={404: {"description": "Node not found"}})
async def reorder_nodes(
    data: ReorderRequest, db: DBSession, user: IsoDocsEditor
) -> dict:
    node_ids = [item.id for item in data.items]
    result = await db.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.id.in_(node_ids))
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
