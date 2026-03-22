"""Capacity insights endpoint."""

import re
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import get_capacity_insights

router = APIRouter()

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_MAX_RANGE_MONTHS = 24


def _parse_month(value: str) -> date:
    """Parse YYYY-MM string to first-of-month date."""
    if not _MONTH_RE.match(value):
        raise HTTPException(status_code=422, detail=f"Invalid date format: {value}")
    year, month = value.split("-")
    return date(int(year), int(month), 1)


@router.get("")
async def capacity_insights(
    db: DBSession,
    user: CurrentUser,
    start_date: str = Query(..., description="Start month (YYYY-MM)"),
    end_date: str = Query(..., description="End month (YYYY-MM)"),
) -> list[dict]:
    start = _parse_month(start_date)
    end = _parse_month(end_date)

    if start > end:
        raise HTTPException(
            status_code=422,
            detail="start_date must be <= end_date",
        )

    month_diff = (end.year - start.year) * 12 + (end.month - start.month)
    if month_diff >= _MAX_RANGE_MONTHS:
        raise HTTPException(
            status_code=422,
            detail=f"Date range must not exceed {_MAX_RANGE_MONTHS} months",
        )

    return await get_capacity_insights(db=db, start_date=start, end_date=end)
