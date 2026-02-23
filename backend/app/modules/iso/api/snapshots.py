"""ISO snapshot API endpoints."""

import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.sql import func

from app.api.deps import AdminUser, DBSession
from app.api.schemas.common import PaginatedResponse
from app.modules.iso.api.helpers import paginate
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.schemas import (
    AccessSnapshotResponse,
    AccessSnapshotSummary,
    ReviewStatus,
)
from app.modules.iso.services.collectors.google_workspace import (
    GoogleWorkspaceCollector,
)
from app.modules.iso.services.diff_engine import (
    build_diff_summary,
    compute_diff,
    create_review_actions,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/capture", response_model=AccessSnapshotResponse, status_code=201)
async def capture_snapshot(
    current_user: AdminUser, db: DBSession
) -> AccessSnapshotDB:
    collector = GoogleWorkspaceCollector(db)
    try:
        snapshot = await collector.capture(run_mode="manual")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except httpx.HTTPStatusError as e:
        logger.warning("Google Workspace API error: %s", e.response.status_code)
        raise HTTPException(
            status_code=502, detail="Google Workspace API error"
        ) from e
    except httpx.RequestError:
        logger.exception("Google Workspace connection error")
        raise HTTPException(
            status_code=502, detail="Failed to connect to Google Workspace"
        )

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
        status=ReviewStatus.DRAFT,
        scope="All users and groups",
    )
    db.add(review)
    await db.flush()

    if previous:
        domain = snapshot.source_metadata.get("domain", "")
        changes = compute_diff(snapshot.data, previous.data, domain)
        review.diff_summary = build_diff_summary(changes)
        await create_review_actions(db, review.id, changes)
        await db.flush()

    logger.info("Snapshot captured, review %s created in draft", review.id)
    return snapshot


@router.get("", response_model=PaginatedResponse[AccessSnapshotSummary])
async def list_snapshots(
    current_user: AdminUser,
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

    return await paginate(db, query, count_query, page, page_size)


@router.get("/{snapshot_id}", response_model=AccessSnapshotResponse)
async def get_snapshot(
    snapshot_id: UUID, current_user: AdminUser, db: DBSession
) -> AccessSnapshotDB:
    result = await db.execute(
        select(AccessSnapshotDB).where(AccessSnapshotDB.id == snapshot_id)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot
