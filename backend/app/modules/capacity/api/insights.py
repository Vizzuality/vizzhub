"""Capacity insights endpoint."""

from fastapi import APIRouter

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import get_capacity_insights
from app.modules.capacity.api._validation import MonthRangeDep

router = APIRouter()


@router.get("")
async def capacity_insights(
    db: DBSession,
    user: CurrentUser,
    months: MonthRangeDep,
) -> list[dict]:
    return await get_capacity_insights(db=db, start_date=months.start, end_date=months.end)
