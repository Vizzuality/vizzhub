"""ISO Docs metadata endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.core.api.deps import CurrentUser, DBSession
from app.modules.iso_docs.api.deps import IsoDocsEditor, is_iso_docs_editor
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.schemas.metadata import (
    MetadataResponse,
    MetadataSearchResult,
    MetadataUpdate,
)

router = APIRouter()


async def _get_parent_group_title(db: DBSession, node_id: UUID) -> str | None:
    """Get the title of the parent group for a page node."""
    Parent = aliased(IsoDocNodeDB)
    result = await db.execute(
        select(Parent.title)
        .join(IsoDocNodeDB, IsoDocNodeDB.parent_id == Parent.id)
        .where(IsoDocNodeDB.id == node_id)
    )
    return result.scalar_one_or_none()


async def _build_metadata_response(
    db: DBSession, meta: IsoDocMetadataDB, node_id: UUID
) -> MetadataResponse:
    """Build a MetadataResponse with the parent group title as category."""
    category = await _get_parent_group_title(db, node_id)
    resp = MetadataResponse.model_validate(meta)
    resp.category = category
    return resp


@router.get(
    "/pages/{node_id}/metadata",
    responses={
        403: {"description": "Access denied for confidential document"},
        404: {"description": "Metadata not found"},
    },
)
async def get_metadata(
    node_id: UUID, db: DBSession, user: CurrentUser
) -> MetadataResponse:
    result = await db.execute(
        select(IsoDocMetadataDB).where(IsoDocMetadataDB.node_id == node_id)
    )
    meta = result.scalar_one_or_none()
    if not meta:
        raise HTTPException(status_code=404, detail="Metadata not found")
    if meta.classification == "confidential" and not is_iso_docs_editor(user):
        raise HTTPException(status_code=403, detail="Access denied")
    return await _build_metadata_response(db, meta, node_id)


@router.put(
    "/pages/{node_id}/metadata",
    responses={404: {"description": "Node not found"}},
)
async def update_metadata(
    node_id: UUID, data: MetadataUpdate, db: DBSession, user: IsoDocsEditor
) -> MetadataResponse:
    node_result = await db.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.id == node_id)
    )
    if not node_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Node not found")

    result = await db.execute(
        select(IsoDocMetadataDB).where(IsoDocMetadataDB.node_id == node_id)
    )
    meta = result.scalar_one_or_none()

    update = data.model_dump(exclude_unset=True)

    if meta:
        for field, value in update.items():
            setattr(meta, field, value)
    else:
        meta = IsoDocMetadataDB(node_id=node_id, **update)
        db.add(meta)

    await db.flush()
    await db.refresh(meta)
    return await _build_metadata_response(db, meta, node_id)


@router.get("/metadata/search")
async def search_metadata(
    db: DBSession,
    user: CurrentUser,
    standard: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    clause: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> list[MetadataSearchResult]:
    ParentNode = aliased(IsoDocNodeDB)
    query = (
        select(
            IsoDocNodeDB.id.label("node_id"),
            IsoDocNodeDB.title,
            IsoDocMetadataDB.code,
            IsoDocMetadataDB.standard,
            IsoDocMetadataDB.clauses,
            ParentNode.title.label("category"),
            IsoDocMetadataDB.status,
        )
        .join(IsoDocMetadataDB, IsoDocMetadataDB.node_id == IsoDocNodeDB.id)
        .outerjoin(ParentNode, ParentNode.id == IsoDocNodeDB.parent_id)
    )

    if not is_iso_docs_editor(user):
        query = query.where(IsoDocMetadataDB.classification != "confidential")
    if standard:
        query = query.where(IsoDocMetadataDB.standard.any(standard))
    if category:
        query = query.where(ParentNode.title == category)
    if clause:
        query = query.where(IsoDocMetadataDB.clauses.any(clause))
    if status:
        query = query.where(IsoDocMetadataDB.status == status)

    result = await db.execute(query.order_by(IsoDocNodeDB.title))
    return [
        MetadataSearchResult(**row._mapping)
        for row in result.all()
    ]
