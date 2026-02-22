"""ISO access review API endpoints."""

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
from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.schemas import (
    AccessReviewDetailResponse,
    AccessReviewResponse,
)

logger = logging.getLogger(__name__)

DBSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter()


@router.get("", response_model=PaginatedResponse[AccessReviewResponse])
async def list_reviews(
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

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    reviews = result.scalars().all()

    return {
        "items": reviews,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total > 0 else 0,
    }


@router.get("/{review_id}", response_model=AccessReviewDetailResponse)
async def get_review(review_id: UUID, db: DBSession) -> dict:
    result = await db.execute(
        select(AccessReviewDB).where(AccessReviewDB.id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    actions_result = await db.execute(
        select(AccessReviewActionDB)
        .where(AccessReviewActionDB.review_id == review_id)
        .order_by(AccessReviewActionDB.created_at)
    )
    actions = actions_result.scalars().all()

    return {
        **{c.key: getattr(review, c.key) for c in review.__table__.columns},
        "actions": actions,
    }
