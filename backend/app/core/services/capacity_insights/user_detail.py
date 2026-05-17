"""Per-project breakdown for a single user across reporting periods."""

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

from ._shared import _reportable_user_filter


async def get_capacity_user_detail(
    db: AsyncSession,
    user_id: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Per-project breakdown for a single user per period.

    Returns list of dicts sorted by period ascending, each containing
    'period' (YYYY-MM) and 'projects' list with per-project breakdown.

    Billable projects are listed individually with ``type=billable``.
    Non-billable non-absence work is rolled up into a single
    ``__other__`` pseudo-row with ``type=other`` (mirrors the
    "Other" segment from ``get_allocation_users``). Absence is
    summarised in the period-level ``absence_pct`` field and is also
    reflected as ``other_pct`` (sum of non-billable non-absence parts).

    Rows are deduplicated across functional areas: a user reporting the
    same project under multiple FAs collapses to a single entry with the
    summed percentage. Returns an empty list for users that do not pass
    the reportable filter (inactive or non-reporting users)."""
    uid = UUID(user_id)

    reportable = await db.execute(
        select(UserDB.id).where(UserDB.id == uid, *_reportable_user_filter())
    )
    if reportable.scalar_one_or_none() is None:
        return []

    periods_result = await db.execute(
        select(ReportingPeriodDB.id, ReportingPeriodDB.date)
        .where(
            ReportingPeriodDB.date >= start_date,
            ReportingPeriodDB.date <= end_date,
        )
        .order_by(ReportingPeriodDB.date)
    )
    periods = list(periods_result)
    if not periods:
        return []

    period_ids = [p_id for p_id, _ in periods]

    # GROUP BY (period, project) collapses same-project-multi-FA splits
    # into a single row with the summed percentage.
    report_rows = await db.execute(
        select(
            ReportDB.reporting_period_id,
            ProjectDB.id,
            ProjectDB.name,
            ProjectDB.is_billable,
            ProjectDB.is_absence,
            func.coalesce(func.sum(ReportPartDB.percentage), 0).label("percentage"),
        )
        .join(ReportPartDB, ReportPartDB.report_id == ReportDB.id)
        .join(ProjectDB, ProjectDB.id == ReportPartDB.project_id)
        .where(
            ReportPartDB.percentage.isnot(None),
            ReportDB.user_id == uid,
            ReportDB.reporting_period_id.in_(period_ids),
        )
        .group_by(
            ReportDB.reporting_period_id,
            ProjectDB.id,
            ProjectDB.name,
            ProjectDB.is_billable,
            ProjectDB.is_absence,
        )
    )

    period_projects: dict[object, list[tuple]] = {}
    for pid, proj_id, proj_name, is_billable, is_absence, pct in report_rows:
        period_projects.setdefault(pid, []).append(
            (str(proj_id), proj_name, bool(is_billable), bool(is_absence), float(pct))
        )

    return [
        _build_period_summary(period_date, period_projects.get(period_id, []))
        for period_id, period_date in periods
    ]


def _build_period_summary(
    period_date: date,
    entries: list[tuple],
) -> dict:
    """Roll up one period's report rows into billable list + absence + other."""
    projects: list[dict] = []
    absence_pct = 0.0
    other_pct = 0.0
    for proj_id, proj_name, is_billable, is_absence, pct in entries:
        if pct <= 0:
            continue
        if is_absence:
            absence_pct += pct
        elif is_billable:
            projects.append({
                "project_id": proj_id,
                "name": proj_name,
                "percentage": round(pct, 4),
                "type": "billable",
            })
        else:
            other_pct += pct
    projects.sort(key=lambda p: p["name"])
    if other_pct > 0:
        projects.append({
            "project_id": "__other__",
            "name": "Other",
            "percentage": round(other_pct, 4),
            "type": "other",
        })
    return {
        "period": period_date.strftime("%Y-%m"),
        "projects": projects,
        "absence_pct": round(absence_pct, 4),
        "other_pct": round(other_pct, 4),
    }
