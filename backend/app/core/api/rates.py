"""Rates listing and admin CRUD endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, status

from app.core.api.deps import AdminUser, CurrentUser, DBSession, get_or_404
from app.core.models.rate import Rate, RateCreate, RateDB, RateUpdate

router = APIRouter()
logger = structlog.get_logger()

RATE_NOT_FOUND = "Rate not found"


@router.get("")
async def list_rates(
    db: DBSession,
    user: CurrentUser,
) -> list[Rate]:
    from sqlalchemy import select

    stmt = select(RateDB).order_by(RateDB.code)
    result = await db.execute(stmt)
    return [Rate.model_validate(r) for r in result.scalars().all()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_rate(
    data: RateCreate,
    db: DBSession,
    user: AdminUser,
) -> Rate:
    rate = RateDB(code=data.code, value=data.value)
    db.add(rate)
    await db.flush()
    await db.refresh(rate)
    logger.info("rate_created", rate_id=str(rate.id), code=rate.code, user_id=user.user_id)
    return Rate.model_validate(rate)


@router.patch(
    "/{rate_id}",
    responses={404: {"description": RATE_NOT_FOUND}},
)
async def update_rate(
    rate_id: UUID,
    data: RateUpdate,
    db: DBSession,
    user: AdminUser,
) -> Rate:
    rate = await get_or_404(db, RateDB, rate_id, RATE_NOT_FOUND)

    update = data.model_dump(exclude_unset=True)
    for field, value in update.items():
        setattr(rate, field, value)
    await db.flush()
    await db.refresh(rate)
    logger.info(
        "rate_updated",
        rate_id=str(rate.id),
        fields=sorted(update.keys()),
        user_id=user.user_id,
    )
    return Rate.model_validate(rate)


@router.delete(
    "/{rate_id}",
    responses={404: {"description": RATE_NOT_FOUND}},
)
async def delete_rate(
    rate_id: UUID,
    db: DBSession,
    user: AdminUser,
) -> dict:
    rate = await get_or_404(db, RateDB, rate_id, RATE_NOT_FOUND)
    await db.delete(rate)
    await db.flush()
    logger.info("rate_deleted", rate_id=str(rate_id), code=rate.code, user_id=user.user_id)
    return {"ok": True}
