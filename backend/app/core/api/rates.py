"""Rates listing and admin CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.api.deps import AdminUser, CurrentUser, DBSession
from app.core.models.rate import Rate, RateCreate, RateDB, RateUpdate

router = APIRouter()


@router.get("")
async def list_rates(
    db: DBSession,
    user: CurrentUser,
) -> list[Rate]:
    stmt = select(RateDB).order_by(RateDB.code)
    result = await db.execute(stmt)
    return [Rate.model_validate(r) for r in result.scalars().all()]


@router.post("", status_code=201)
async def create_rate(
    data: RateCreate,
    db: DBSession,
    user: AdminUser,
) -> Rate:
    rate = RateDB(code=data.code, value=data.value)
    db.add(rate)
    await db.flush()
    await db.refresh(rate)
    return Rate.model_validate(rate)


@router.patch("/{rate_id}", responses={404: {"description": "Rate not found"}})
async def update_rate(
    rate_id: UUID,
    data: RateUpdate,
    db: DBSession,
    user: AdminUser,
) -> Rate:
    result = await db.execute(select(RateDB).where(RateDB.id == rate_id))
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")

    update = data.model_dump(exclude_unset=True)
    for field, value in update.items():
        setattr(rate, field, value)
    await db.flush()
    await db.refresh(rate)
    return Rate.model_validate(rate)


@router.delete("/{rate_id}", responses={404: {"description": "Rate not found"}})
async def delete_rate(
    rate_id: UUID,
    db: DBSession,
    user: AdminUser,
) -> dict:
    result = await db.execute(select(RateDB).where(RateDB.id == rate_id))
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    await db.delete(rate)
    await db.flush()
    return {"ok": True}
