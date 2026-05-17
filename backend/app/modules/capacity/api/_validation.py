"""Shared validation helpers for capacity endpoints."""

import re
from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, Query

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
MAX_RANGE_MONTHS = 24


def parse_month(value: str) -> date:
    """Parse YYYY-MM string to first-of-month date."""
    if not MONTH_RE.match(value):
        raise HTTPException(status_code=422, detail=f"Invalid date format: {value}")
    year, month = value.split("-")
    return date(int(year), int(month), 1)


def validate_date_range(start: date, end: date) -> None:
    """Validate start <= end and range <= MAX_RANGE_MONTHS."""
    if start > end:
        raise HTTPException(status_code=422, detail="start_date must be <= end_date")
    month_diff = (end.year - start.year) * 12 + (end.month - start.month)
    if month_diff >= MAX_RANGE_MONTHS:
        raise HTTPException(
            status_code=422,
            detail=f"Date range must not exceed {MAX_RANGE_MONTHS} months",
        )


@dataclass(frozen=True)
class MonthRange:
    """Validated YYYY-MM range; first-of-month dates."""

    start: date
    end: date


def month_range_dep(
    start_date: Annotated[str, Query(description="Start month (YYYY-MM)")],
    end_date: Annotated[str, Query(description="End month (YYYY-MM)")],
) -> MonthRange:
    """FastAPI dependency: parse + validate a YYYY-MM range query pair."""
    start = parse_month(start_date)
    end = parse_month(end_date)
    validate_date_range(start, end)
    return MonthRange(start=start, end=end)


MonthRangeDep = Annotated[MonthRange, Depends(month_range_dep)]
