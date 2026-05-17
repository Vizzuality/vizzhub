"""Shared helpers for the ISO API layer."""

import math
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB


async def paginate(
    db: AsyncSession,
    query: Select,
    count_query: Select,
    page: int,
    page_size: int,
) -> dict:
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    items = result.scalars().all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total > 0 else 0,
    }


async def get_review_or_404(db: AsyncSession, review_id: UUID) -> AccessReviewDB:
    result = await db.execute(select(AccessReviewDB).where(AccessReviewDB.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


async def load_review_with_actions(db: AsyncSession, review: AccessReviewDB) -> dict:
    """Fetch a review's actions and build a dict suitable for response serialization."""
    actions_result = await db.execute(
        select(AccessReviewActionDB)
        .where(AccessReviewActionDB.review_id == review.id)
        .order_by(AccessReviewActionDB.created_at)
    )
    actions = actions_result.scalars().all()
    return {
        **{c.key: getattr(review, c.key) for c in review.__table__.columns},
        "actions": actions,
    }
