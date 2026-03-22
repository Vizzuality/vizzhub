"""Capacity insights endpoint."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import get_capacity_insights
from app.modules.capacity.api._validation import parse_month, validate_date_range

router = APIRouter()


@router.get("")
async def capacity_insights(
    db: DBSession,
    user: CurrentUser,
    start_date: Annotated[str, Query(description="Start month (YYYY-MM)")],
    end_date: Annotated[str, Query(description="End month (YYYY-MM)")],
) -> list[dict]:
    start = parse_month(start_date)
    end = parse_month(end_date)
    validate_date_range(start, end)
    return await get_capacity_insights(db=db, start_date=start, end_date=end)
