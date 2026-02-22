"""ISO snapshot API endpoints."""

import logging
import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.api.schemas.common import PaginatedResponse
from app.database import get_db
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.schemas import AccessSnapshotResponse, AccessSnapshotSummary
from app.modules.iso.services.collectors.google_workspace import (
    GoogleWorkspaceCollector,
)

logger = logging.getLogger(__name__)

DBSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter()


@router.post("/capture", response_model=AccessSnapshotResponse, status_code=201)
async def capture_snapshot(db: DBSession) -> AccessSnapshotDB:
    collector = GoogleWorkspaceCollector(db)
    try:
        snapshot = await collector.capture(run_mode="manual")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = await db.execute(
        select(AccessSnapshotDB)
        .where(AccessSnapshotDB.provider == "google_workspace")
        .where(AccessSnapshotDB.id != snapshot.id)
        .order_by(AccessSnapshotDB.captured_at.desc())
        .limit(1)
    )
    previous = result.scalar_one_or_none()

    review = AccessReviewDB(
        snapshot_id=snapshot.id,
        previous_snapshot_id=previous.id if previous else None,
        reviewer_id=snapshot.captured_by,
        status="draft",
        scope="All users and groups",
    )
    db.add(review)
    await db.flush()

    logger.info("Snapshot captured, review %s created in draft", review.id)
    return snapshot


@router.get("", response_model=PaginatedResponse[AccessSnapshotSummary])
async def list_snapshots(
    db: DBSession,
    provider: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    query = select(AccessSnapshotDB).order_by(AccessSnapshotDB.captured_at.desc())
    count_query = select(func.count(AccessSnapshotDB.id))

    if provider:
        query = query.where(AccessSnapshotDB.provider == provider)
        count_query = count_query.where(AccessSnapshotDB.provider == provider)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    snapshots = result.scalars().all()

    return {
        "items": snapshots,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total > 0 else 0,
    }


@router.get("/{snapshot_id}", response_model=AccessSnapshotResponse)
async def get_snapshot(snapshot_id: UUID, db: DBSession) -> AccessSnapshotDB:
    result = await db.execute(
        select(AccessSnapshotDB).where(AccessSnapshotDB.id == snapshot_id)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot
