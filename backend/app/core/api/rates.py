"""Rates listing endpoint."""

from fastapi import APIRouter
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from app.core.models.rate import Rate, RateDB

router = APIRouter()


@router.get("")
async def list_rates(
    db: DBSession,
    user: CurrentUser,
) -> list[Rate]:
    stmt = select(RateDB).order_by(RateDB.code)
    result = await db.execute(stmt)
    return [Rate.model_validate(r) for r in result.scalars().all()]
