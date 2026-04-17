"""Devstack entries CRUD endpoints."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.core.api.deps import DBSession
from app.modules.devstack.api.deps import DevstackManager, DevstackViewer, get_entry_or_404
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.schemas import EntryCreate, EntryResponse, EntryUpdate

logger = structlog.get_logger()

router = APIRouter()


@router.get("")
async def list_entries(
    db: DBSession,
    user: DevstackViewer,
    type: str | None = None,
    required: bool | None = None,
    active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    query = select(DevstackEntryDB)
    count_query = select(func.count(DevstackEntryDB.id))

    if type is not None:
        query = query.where(DevstackEntryDB.type == type)
        count_query = count_query.where(DevstackEntryDB.type == type)
    if required is not None:
        query = query.where(DevstackEntryDB.required == required)
        count_query = count_query.where(DevstackEntryDB.required == required)
    if active is not None:
        query = query.where(DevstackEntryDB.active == active)
        count_query = count_query.where(DevstackEntryDB.active == active)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(DevstackEntryDB.name).offset(offset).limit(page_size)
    result = await db.execute(query)
    entries = result.scalars().all()

    return {
        "items": [EntryResponse.model_validate(e) for e in entries],
        "total": total,
    }


@router.get(
    "/{entry_id}",
    responses={404: {"description": "Devstack entry not found"}},
)
async def get_entry(
    entry_id: UUID,
    db: DBSession,
    user: DevstackViewer,
) -> EntryResponse:
    entry = await get_entry_or_404(db, entry_id)
    return EntryResponse.model_validate(entry)


@router.post(
    "",
    status_code=201,
    responses={409: {"description": "Entry name already exists"}},
)
async def create_entry(
    body: EntryCreate,
    db: DBSession,
    user: DevstackManager,
) -> EntryResponse:
    existing = await db.execute(
        select(DevstackEntryDB).where(DevstackEntryDB.name == body.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Entry name already exists")

    entry = DevstackEntryDB(**body.model_dump(), created_by_id=user.user_id)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    logger.info("devstack_entry_created", entry_id=str(entry.id), name=entry.name)
    return EntryResponse.model_validate(entry)


@router.put(
    "/{entry_id}",
    responses={404: {"description": "Devstack entry not found"}},
)
async def update_entry(
    entry_id: UUID,
    body: EntryUpdate,
    db: DBSession,
    user: DevstackManager,
) -> EntryResponse:
    entry = await get_entry_or_404(db, entry_id)

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(entry, field, value)
    entry.updated_by_id = user.user_id

    await db.commit()
    await db.refresh(entry)
    logger.info("devstack_entry_updated", entry_id=str(entry.id))
    return EntryResponse.model_validate(entry)


@router.delete(
    "/{entry_id}",
    status_code=204,
    responses={404: {"description": "Devstack entry not found"}},
)
async def delete_entry(
    entry_id: UUID,
    db: DBSession,
    user: DevstackManager,
) -> None:
    entry = await get_entry_or_404(db, entry_id)
    await db.delete(entry)
    await db.commit()
    logger.info("devstack_entry_deleted", entry_id=str(entry_id))
