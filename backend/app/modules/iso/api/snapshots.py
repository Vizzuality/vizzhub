"""ISO snapshot API endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.schemas import AccessSnapshotResponse
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
