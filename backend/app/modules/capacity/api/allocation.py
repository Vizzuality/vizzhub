"""Capacity allocation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import get_allocation_users
from app.modules.capacity.api._validation import parse_month, validate_date_range

router = APIRouter()


@router.get("/users")
async def allocation_users(
    db: DBSession,
    user: CurrentUser,
    start_date: Annotated[str | None, Query(description="Start month (YYYY-MM)")] = None,
    end_date: Annotated[str | None, Query(description="End month (YYYY-MM)")] = None,
) -> dict:
    start = parse_month(start_date) if start_date else None
    end = parse_month(end_date) if end_date else None
    if start and end:
        validate_date_range(start, end)
    return await get_allocation_users(db=db, start_date=start, end_date=end)
