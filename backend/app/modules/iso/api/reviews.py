"""ISO access review API endpoints."""

import logging
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.sql import func

from app.api.deps import AdminUser, DBSession, limiter
from app.api.schemas.common import PaginatedResponse
from app.modules.iso.api.helpers import (
    get_review_or_404,
    load_review_with_actions,
    paginate,
)
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.schemas import (
    AccessReviewActionResponse,
    AccessReviewActionUpdate,
    AccessReviewDetailResponse,
    AccessReviewResponse,
    AccessReviewUpdate,
    ReviewStatus,
    SignReviewRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[AccessReviewResponse])
@limiter.limit("30/minute")
async def list_reviews(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    query = select(AccessReviewDB).order_by(AccessReviewDB.created_at.desc())
    count_query = select(func.count(AccessReviewDB.id))

    if status:
        query = query.where(AccessReviewDB.status == status)
        count_query = count_query.where(AccessReviewDB.status == status)

    return await paginate(db, query, count_query, page, page_size)


@router.get("/{review_id}", response_model=AccessReviewDetailResponse)
@limiter.limit("30/minute")
async def get_review(
    request: Request, review_id: UUID, current_user: AdminUser, db: DBSession
) -> dict:
    review = await get_review_or_404(db, review_id)
    return await load_review_with_actions(db, review)


@router.patch("/{review_id}", response_model=AccessReviewResponse)
@limiter.limit("10/minute")
async def update_review(
    request: Request,
    review_id: UUID,
    body: AccessReviewUpdate,
    current_user: AdminUser,
    db: DBSession,
) -> AccessReviewDB:
    review = await get_review_or_404(db, review_id)

    if review.status == ReviewStatus.SIGNED:
        raise HTTPException(status_code=409, detail="Cannot modify a signed review")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(review, field, value)
    await db.flush()
    await db.refresh(review)

    return review


@router.patch(
    "/{review_id}/actions/{action_id}",
    response_model=AccessReviewActionResponse,
)
@limiter.limit("10/minute")
async def update_action(
    request: Request,
    review_id: UUID,
    action_id: UUID,
    body: AccessReviewActionUpdate,
    current_user: AdminUser,
    db: DBSession,
) -> AccessReviewActionDB:
    review = await get_review_or_404(db, review_id)

    if review.status == ReviewStatus.SIGNED:
        raise HTTPException(
            status_code=409, detail="Cannot modify actions on a signed review"
        )

    action_result = await db.execute(
        select(AccessReviewActionDB).where(
            AccessReviewActionDB.id == action_id,
            AccessReviewActionDB.review_id == review_id,
        )
    )
    action = action_result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if isinstance(value, Enum):
            value = value.value
        setattr(action, field, value)
    if updates.get("action_taken"):
        action.approved_by = UUID(current_user.user_id)
    await db.flush()
    await db.refresh(action)

    return action


@router.post("/{review_id}/sign", response_model=AccessReviewResponse)
@limiter.limit("10/minute")
async def sign_review(
    request: Request,
    review_id: UUID,
    current_user: AdminUser,
    db: DBSession,
    body: SignReviewRequest | None = None,
) -> AccessReviewDB:
    review = await get_review_or_404(db, review_id)

    if review.status == ReviewStatus.SIGNED:
        raise HTTPException(status_code=409, detail="Review is already signed")

    if body and body.notes is not None:
        review.notes = body.notes

    if body and body.actions:
        action_ids = [a.action_id for a in body.actions]
        actions_result = await db.execute(
            select(AccessReviewActionDB).where(
                AccessReviewActionDB.id.in_(action_ids),
                AccessReviewActionDB.review_id == review_id,
            )
        )
        db_actions = {a.id: a for a in actions_result.scalars().all()}

        for decision in body.actions:
            db_action = db_actions.get(decision.action_id)
            if not db_action:
                raise HTTPException(
                    status_code=404,
                    detail=f"Action {decision.action_id} not found in this review",
                )
            db_action.action_taken = decision.action_taken.value
            db_action.justification = decision.justification
            db_action.exception_until = decision.exception_until
        await db.flush()

    unresolved_result = await db.execute(
        select(func.count(AccessReviewActionDB.id)).where(
            AccessReviewActionDB.review_id == review_id,
            AccessReviewActionDB.action_taken.is_(None),
        )
    )
    unresolved_count = unresolved_result.scalar() or 0

    if unresolved_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{unresolved_count} unresolved action(s) must be "
                f"completed before signing"
            ),
        )

    review.status = ReviewStatus.SIGNED
    review.signed_by = UUID(current_user.user_id)
    review.signed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(review)

    return review


@router.post("/{review_id}/unsign", response_model=AccessReviewResponse)
@limiter.limit("10/minute")
async def unsign_review(
    request: Request, review_id: UUID, current_user: AdminUser, db: DBSession
) -> AccessReviewDB:
    review = await get_review_or_404(db, review_id)

    if review.status != ReviewStatus.SIGNED:
        raise HTTPException(status_code=409, detail="Review is not signed")

    review.status = ReviewStatus.DRAFT
    review.signed_at = None
    review.signed_by = None
    await db.flush()
    await db.refresh(review)

    return review
