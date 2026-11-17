"""Capacity data access for MCP.

Time rule: the past is answered from confirmed tracker reports (closed reporting
periods only), the future from the capacity planner (current week onward). No
reader crosses that boundary; a request on the wrong side gets a redirect note.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB, ProjectStatus
from app.core.models.user import UserDB
from app.core.services.capacity_insights import (
    TARGET_FA_MAPPING,
    get_allocation_projects,
    get_allocation_users,
    get_capacity_fa_detail,
    get_capacity_insights,
    get_capacity_user_detail,
    get_reportable_users,
)
from app.core.sql_helpers import user_display_name_expr
from app.modules.capacity.public import CapacityPlanDB
from app.modules.tracker.models import ReportingPeriodDB

REPORTED_SOURCE = "Confirmed tracker reports, closed reporting periods only"
PLANNED_SOURCE = "Capacity planner (weekly plan), current week onward"
DEFAULT_REPORTED_MONTHS = 6
DEFAULT_PLANNED_WEEKS = 13


def current_monday(today: date | None = None) -> date:
    """Monday of the current ISO week: the first week the planner covers."""
    today = today or date.today()
    return today - timedelta(days=today.weekday())


def _months_back(month: date, count: int) -> date:
    """First day of the month ``count - 1`` months before ``month``."""
    index = month.year * 12 + (month.month - 1) - (count - 1)
    return date(index // 12, index % 12 + 1, 1)


async def last_closed_month(session: AsyncSession) -> date | None:
    """Month of the latest finished reporting period: the last month with confirmed data."""
    return await session.scalar(
        select(func.max(ReportingPeriodDB.date)).where(ReportingPeriodDB.status == "finished")
    )


def _planner_redirect(last_closed: date | None) -> str:
    covered = last_closed.strftime("%Y-%m") if last_closed else "none yet"
    return (
        f"No confirmed report data for this range (last closed month: {covered}). "
        "Months after that are not confirmed yet; for future allocation use "
        "capacity_get_planned."
    )


async def _reported_window(
    session: AsyncSession,
    start: date | None,
    end: date | None,
) -> tuple[date, date, date] | dict:
    """Clamp a requested month range to closed periods.

    Returns ``(start, end, last_closed)`` or a redirect payload when nothing in
    the range is confirmed yet.
    """
    last_closed = await last_closed_month(session)
    if last_closed is None or (start is not None and start > last_closed):
        return {"data_source": REPORTED_SOURCE, "periods": [], "note": _planner_redirect(last_closed)}
    clamped_end = min(end, last_closed) if end else last_closed
    clamped_start = start or _months_back(clamped_end, DEFAULT_REPORTED_MONTHS)
    if clamped_start > clamped_end:
        return {"data_source": REPORTED_SOURCE, "periods": [], "note": _planner_redirect(last_closed)}
    return clamped_start, clamped_end, last_closed


def _reported_payload(result, last_closed: date, requested_end: date | None) -> dict:
    payload: dict = {
        "data_source": REPORTED_SOURCE,
        "last_closed_month": last_closed.strftime("%Y-%m"),
    }
    if isinstance(result, dict):
        payload.update(result)
    else:
        payload["periods"] = result
    if requested_end and requested_end > last_closed:
        payload["note"] = (
            f"Range truncated at {last_closed:%Y-%m}, the last closed month. "
            "For later months use capacity_get_planned."
        )
    return payload


async def get_reported_overview(
    session: AsyncSession, start: date | None = None, end: date | None = None
) -> dict:
    """FA-level billable share per closed period."""
    window = await _reported_window(session, start, end)
    if isinstance(window, dict):
        return window
    s, e, last_closed = window
    return _reported_payload(await get_capacity_insights(session, s, e), last_closed, end)


async def get_reported_by_fa(
    session: AsyncSession, fa: str, start: date | None = None, end: date | None = None
) -> dict:
    """Per-person breakdown of one FA per closed period."""
    window = await _reported_window(session, start, end)
    if isinstance(window, dict):
        return window
    s, e, last_closed = window
    return _reported_payload(await get_capacity_fa_detail(session, fa, s, e), last_closed, end)


async def get_reported_by_user(
    session: AsyncSession, user_id: str, start: date | None = None, end: date | None = None
) -> dict:
    """Per-project breakdown of one person per closed period."""
    window = await _reported_window(session, start, end)
    if isinstance(window, dict):
        return window
    s, e, last_closed = window
    result = await get_capacity_user_detail(session, user_id, s, e)
    return _reported_payload(result, last_closed, end)


async def get_reported_average(
    session: AsyncSession,
    view: str = "users",
    start: date | None = None,
    end: date | None = None,
) -> dict:
    """Allocation averaged over closed periods, by user or by project."""
    if start is None and end is None:
        last_closed = await last_closed_month(session)
        if last_closed is None:
            return {"data_source": REPORTED_SOURCE, "note": _planner_redirect(None)}
        s, e = None, None
    else:
        window = await _reported_window(session, start, end)
        if isinstance(window, dict):
            return window
        s, e, last_closed = window
    if view == "projects":
        result = await get_allocation_projects(session, s, e)
    else:
        result = await get_allocation_users(session, s, e)
    return _reported_payload(result, last_closed, end)


def _reported_redirect_for_plan() -> str:
    return (
        "The planner only covers the current week onward. "
        "For past months use the capacity_get_reported_* tools (confirmed reports)."
    )


async def get_planned(
    session: AsyncSession,
    start: date | None = None,
    end: date | None = None,
    *,
    user_id: UUID | None = None,
    project_id: UUID | None = None,
    fa: str | None = None,
    today: date | None = None,
) -> dict:
    """Weekly planned allocation from the current week onward.

    One entry per person-project assignment with its weekly percentages, plus
    the weeks where a person is planned above 100%.
    """
    first_week = current_monday(today)
    if end is not None and end < first_week:
        return {"data_source": PLANNED_SOURCE, "assignments": [], "note": _reported_redirect_for_plan()}

    range_start = max(start, first_week) if start else first_week
    range_start -= timedelta(days=range_start.weekday())
    range_end = end or range_start + timedelta(weeks=DEFAULT_PLANNED_WEEKS - 1)

    fa_names = [name for name, short in TARGET_FA_MAPPING.items() if short == fa] if fa else []

    stmt = (
        select(
            CapacityPlanDB.user_id,
            user_display_name_expr(UserDB).label("user_name"),
            FunctionalAreaDB.name.label("functional_area"),
            CapacityPlanDB.project_id,
            ProjectDB.name.label("project_name"),
            ProjectDB.is_billable,
            ProjectDB.is_absence,
            CapacityPlanDB.week_start,
            CapacityPlanDB.percentage,
            CapacityPlanDB.comment,
        )
        .join(ProjectDB, CapacityPlanDB.project_id == ProjectDB.id)
        .join(UserDB, CapacityPlanDB.user_id == UserDB.id)
        .outerjoin(FunctionalAreaDB, FunctionalAreaDB.id == UserDB.functional_area_id)
        .where(CapacityPlanDB.week_start >= range_start)
        .where(CapacityPlanDB.week_start <= range_end)
        .where(ProjectDB.status != ProjectStatus.FINISHED)
        .where(UserDB.active.is_(True))
        .where(UserDB.requires_project_reporting.is_(True))
        .order_by(UserDB.name, ProjectDB.name, CapacityPlanDB.week_start)
    )
    if user_id:
        stmt = stmt.where(CapacityPlanDB.user_id == user_id)
    if project_id:
        stmt = stmt.where(CapacityPlanDB.project_id == project_id)
    if fa:
        stmt = stmt.where(FunctionalAreaDB.name.in_(fa_names))

    assignments: dict[tuple, dict] = {}
    weekly_totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    names: dict[str, str] = {}
    for row in (await session.execute(stmt)).all():
        key = (row.user_id, row.project_id)
        week = row.week_start.isoformat()
        if key not in assignments:
            assignments[key] = {
                "user_id": str(row.user_id),
                "user_name": row.user_name,
                "functional_area": TARGET_FA_MAPPING.get(row.functional_area or "", row.functional_area),
                "project_id": str(row.project_id),
                "project_name": row.project_name,
                "kind": "absence" if row.is_absence else "billable" if row.is_billable else "other",
                "weeks": {},
                "comments": {},
            }
        assignments[key]["weeks"][week] = row.percentage
        if row.comment:
            assignments[key]["comments"][week] = row.comment
        weekly_totals[str(row.user_id)][week] += row.percentage
        names[str(row.user_id)] = row.user_name

    overallocated = [
        {"user_id": uid, "user_name": names[uid], "week": week, "total_percentage": total}
        for uid, weeks in weekly_totals.items()
        for week, total in sorted(weeks.items())
        if total > 100
    ]

    payload: dict = {
        "data_source": PLANNED_SOURCE,
        "range": {"first_week": range_start.isoformat(), "last_week": range_end.isoformat()},
        "assignments": list(assignments.values()),
        "overallocated_weeks": overallocated,
    }
    if start is not None and start < first_week:
        payload["note"] = (
            f"Range starts at the current week ({first_week.isoformat()}). "
            "For earlier months use the capacity_get_reported_* tools."
        )
    return payload


async def get_users(session: AsyncSession) -> list[dict]:
    """List reportable users for selectors."""
    return await get_reportable_users(session)
