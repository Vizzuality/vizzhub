"""Capacity data access — wraps core/services/capacity_insights.py for MCP."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.capacity_insights import (
    get_allocation_projects,
    get_allocation_users,
    get_capacity_fa_detail,
    get_capacity_insights,
    get_capacity_user_detail,
    get_reportable_users,
)


def _default_range() -> tuple[date, date]:
    """Default 6-month range ending at current month."""
    today = date.today()
    end = date(today.year, today.month, 1)
    start_month = today.month - 5
    start_year = today.year
    if start_month <= 0:
        start_month += 12
        start_year -= 1
    start = date(start_year, start_month, 1)
    return start, end


async def get_insights(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    """FA-level billable allocation overview by period."""
    start, end = start_date, end_date
    if start is None or end is None:
        start, end = _default_range()
    return await get_capacity_insights(session, start, end)


async def get_fa_detail(
    session: AsyncSession,
    fa: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    """Per-user breakdown for a functional area."""
    start, end = start_date, end_date
    if start is None or end is None:
        start, end = _default_range()
    return await get_capacity_fa_detail(session, fa, start, end)


async def get_user_detail(
    session: AsyncSession,
    user_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    """Per-project breakdown for a user."""
    start, end = start_date, end_date
    if start is None or end is None:
        start, end = _default_range()
    return await get_capacity_user_detail(session, user_id, start, end)


async def get_allocation(
    session: AsyncSession,
    view: str = "users",
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Averaged allocation by users or projects over finished periods."""
    if view == "projects":
        return await get_allocation_projects(session, start_date, end_date)
    return await get_allocation_users(session, start_date, end_date)


async def get_users(session: AsyncSession) -> list[dict]:
    """List reportable users for selectors."""
    return await get_reportable_users(session)
