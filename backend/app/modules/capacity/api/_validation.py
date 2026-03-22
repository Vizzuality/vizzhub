"""Shared validation helpers for capacity endpoints."""

import re
from datetime import date

from fastapi import HTTPException

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
