"""Capacity allocation endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import get_allocation_projects, get_allocation_users
from app.modules.capacity.api._validation import parse_month, validate_date_range

router = APIRouter()

MonthParam = Annotated[str | None, Query(description="Month (YYYY-MM)")]


def _parse_date_range(
    start_date: str | None,
    end_date: str | None,
) -> tuple[date, date] | tuple[None, None]:
    """Parse and validate optional month range params."""
    if not start_date or not end_date:
        return None, None
    start = parse_month(start_date)
    end = parse_month(end_date)
    validate_date_range(start, end)
    return start, end


@router.get("/users")
async def allocation_users(
    db: DBSession,
    user: CurrentUser,
    start_date: MonthParam = None,
    end_date: MonthParam = None,
) -> dict:
    start, end = _parse_date_range(start_date, end_date)
    return await get_allocation_users(db=db, start_date=start, end_date=end)


@router.get("/projects")
async def allocation_projects(
    db: DBSession,
    user: CurrentUser,
    start_date: MonthParam = None,
    end_date: MonthParam = None,
) -> dict:
    start, end = _parse_date_range(start_date, end_date)
    return await get_allocation_projects(db=db, start_date=start, end_date=end)
