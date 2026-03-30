"""ISO Docs metadata endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from app.modules.iso_docs.api.deps import IsoDocsEditor
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.schemas.metadata import (
    MetadataResponse,
    MetadataSearchResult,
    MetadataUpdate,
)

router = APIRouter()


@router.get(
    "/pages/{node_id}/metadata",
    responses={404: {"description": "Metadata not found"}},
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
    return MetadataResponse.model_validate(meta)


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
    if "changelog" in update and update["changelog"] is not None:
        update["changelog"] = [entry.model_dump() for entry in data.changelog]

    if meta:
        for field, value in update.items():
            setattr(meta, field, value)
    else:
        meta = IsoDocMetadataDB(node_id=node_id, **update)
        db.add(meta)

    await db.flush()
    await db.refresh(meta)
    return MetadataResponse.model_validate(meta)


@router.get("/metadata/search")
async def search_metadata(
    db: DBSession,
    user: CurrentUser,
    standard: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    clause: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> list[MetadataSearchResult]:
    query = (
        select(
            IsoDocNodeDB.id.label("node_id"),
            IsoDocNodeDB.title,
            IsoDocMetadataDB.code,
            IsoDocMetadataDB.standard,
            IsoDocMetadataDB.clauses,
            IsoDocMetadataDB.category,
            IsoDocMetadataDB.status,
        )
        .join(IsoDocMetadataDB, IsoDocMetadataDB.node_id == IsoDocNodeDB.id)
    )

    if standard:
        query = query.where(IsoDocMetadataDB.standard.any(standard))
    if category:
        query = query.where(IsoDocMetadataDB.category == category)
    if clause:
        query = query.where(IsoDocMetadataDB.clauses.any(clause))
    if status:
        query = query.where(IsoDocMetadataDB.status == status)

    result = await db.execute(query.order_by(IsoDocNodeDB.title))
    rows = result.all()
    return [
        MetadataSearchResult(
            node_id=row.node_id,
            title=row.title,
            code=row.code,
            standard=row.standard,
            clauses=row.clauses,
            category=row.category,
            status=row.status,
        )
        for row in rows
    ]
