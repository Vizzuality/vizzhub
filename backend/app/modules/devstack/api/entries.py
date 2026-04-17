"""Devstack entries CRUD endpoints."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import DBSession
from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.devstack.api.deps import DevstackManager, DevstackViewer, get_entry_or_404
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.schemas import EntryCreate, EntryResponse, EntryUpdate
from app.modules.devstack.services.github_sha import fetch_github_sha
from app.modules.devstack.services.sha_refresh import refresh_all_sources_tracked

logger = structlog.get_logger()


async def _resolve_github_sha(db: AsyncSession, entry: DevstackEntryDB) -> None:
    """Auto-fetch and set github_sha for github entries. No-op for npm entries."""
    if entry.install_method != "github" or not entry.url:
        return
    token = await IntegrationTokenService.get_token(db, "github")
    sha = await fetch_github_sha(entry.url, token)
    if sha:
        entry.github_sha = sha


router = APIRouter()


@router.get("")
async def list_entries(
    db: DBSession,
    user: DevstackViewer,
    search: str | None = None,
    type: str | None = None,
    required: bool | None = None,
    active: bool | None = None,
    featured: bool | None = None,
    sort_by: Annotated[
        str | None,
        Query(pattern=r"^(name|type|created_at)$"),
    ] = None,
    sort_dir: Annotated[
        str | None,
        Query(pattern=r"^(asc|desc)$"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    filters = []
    if search:
        filters.append(DevstackEntryDB.name.ilike(f"%{search}%"))
    if type is not None:
        filters.append(DevstackEntryDB.type == type)
    if required is not None:
        filters.append(DevstackEntryDB.required == required)
    if active is not None:
        filters.append(DevstackEntryDB.active == active)
    if featured is not None:
        filters.append(DevstackEntryDB.featured == featured)

    total_result = await db.execute(select(func.count(DevstackEntryDB.id)).where(*filters))
    total = total_result.scalar() or 0

    order_col = getattr(DevstackEntryDB, sort_by, DevstackEntryDB.name) if sort_by else DevstackEntryDB.name
    order_expr = order_col.desc() if sort_dir == "desc" else order_col.asc()

    offset = (page - 1) * page_size
    query = select(DevstackEntryDB).where(*filters).order_by(order_expr).offset(offset).limit(page_size)
    result = await db.execute(query)
    entries = result.scalars().all()

    return {
        "items": [EntryResponse.model_validate(e) for e in entries],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/refresh-shas",
    responses={403: {"description": "Not authorized"}},
)
async def refresh_shas(
    db: DBSession,
    user: DevstackManager,
) -> dict:
    return await refresh_all_sources_tracked(db)


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
    await _resolve_github_sha(db, entry)
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
    await _resolve_github_sha(db, entry)

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
