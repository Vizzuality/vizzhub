"""ISO snapshot API endpoints."""

import logging
import math
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import select, update
from sqlalchemy.sql import func

from app.api.deps import AdminUser, DBSession, limiter
from app.api.schemas.common import PaginatedResponse
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.schemas import (
    AccessReviewDetailResponse,
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
from app.modules.iso.api.helpers import load_review_with_actions

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/capture",
    response_model=AccessSnapshotResponse,
    status_code=201,
    responses={
        400: {"description": "Google Workspace not configured"},
        502: {"description": "Google Workspace API error"},
    },
)
@limiter.limit("5/minute")
async def capture_snapshot(
    request: Request, current_user: AdminUser, db: DBSession
) -> AccessSnapshotDB:
    collector = GoogleWorkspaceCollector(db)
    try:
        snapshot = await collector.capture(
            captured_by=UUID(current_user.user_id), run_mode="manual"
        )
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
@limiter.limit("30/minute")
async def list_snapshots(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    provider: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    query = (
        select(AccessSnapshotDB, AccessReviewDB.status)
        .outerjoin(
            AccessReviewDB,
            AccessReviewDB.snapshot_id == AccessSnapshotDB.id,
        )
        .order_by(AccessSnapshotDB.captured_at.desc())
    )
    count_query = select(func.count(AccessSnapshotDB.id))

    if provider:
        query = query.where(AccessSnapshotDB.provider == provider)
        count_query = count_query.where(AccessSnapshotDB.provider == provider)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    rows = result.all()

    items = []
    for snapshot, review_status in rows:
        items.append(
            {
                "id": snapshot.id,
                "provider": snapshot.provider,
                "captured_at": snapshot.captured_at,
                "captured_by": snapshot.captured_by,
                "data_version": snapshot.data_version,
                "summary": snapshot.summary,
                "created_at": snapshot.created_at,
                "review_status": review_status,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total > 0 else 0,
    }


@router.get(
    "/{snapshot_id}",
    response_model=AccessSnapshotResponse,
    responses={404: {"description": "Snapshot not found"}},
)
@limiter.limit("30/minute")
async def get_snapshot(
    request: Request, snapshot_id: UUID, current_user: AdminUser, db: DBSession
) -> AccessSnapshotDB:
    result = await db.execute(
        select(AccessSnapshotDB).where(AccessSnapshotDB.id == snapshot_id)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.delete(
    "/{snapshot_id}",
    status_code=204,
    responses={404: {"description": "Snapshot not found"}},
)
@limiter.limit("10/minute")
async def delete_snapshot(
    request: Request, snapshot_id: UUID, current_user: AdminUser, db: DBSession
) -> Response:
    result = await db.execute(
        select(AccessSnapshotDB).where(AccessSnapshotDB.id == snapshot_id)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    review_result = await db.execute(
        select(AccessReviewDB).where(AccessReviewDB.snapshot_id == snapshot_id)
    )
    review = review_result.scalar_one_or_none()

    if review:
        await db.execute(
            AccessReviewActionDB.__table__.delete().where(
                AccessReviewActionDB.review_id == review.id
            )
        )
        await db.delete(review)

    await db.execute(
        update(AccessReviewDB)
        .where(AccessReviewDB.previous_snapshot_id == snapshot_id)
        .values(previous_snapshot_id=None)
    )

    await db.delete(snapshot)
    await db.flush()

    return Response(status_code=204)


@router.get(
    "/{snapshot_id}/review",
    response_model=AccessReviewDetailResponse,
    responses={404: {"description": "Review not found"}},
)
@limiter.limit("30/minute")
async def get_snapshot_review(
    request: Request, snapshot_id: UUID, current_user: AdminUser, db: DBSession
) -> dict:
    result = await db.execute(
        select(AccessReviewDB).where(AccessReviewDB.snapshot_id == snapshot_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    return await load_review_with_actions(db, review)
