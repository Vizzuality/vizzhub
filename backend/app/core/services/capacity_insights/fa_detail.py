"""Per-user billable allocation for a single FA + reportable user listing."""

from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

from ._shared import (
    SHORT_TO_FA_NAME,
    _format_user_name,
    _is_on_leave,
    _reportable_user_filter,
)


async def get_capacity_fa_detail(
    db: AsyncSession,
    fa_short: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Per-user billable allocation for a single FA per period.

    Returns list of dicts sorted by period ascending, each containing
    'period' (YYYY-MM) and 'users' list with per-user breakdown.
    """
    fa_name = SHORT_TO_FA_NAME.get(fa_short)
    if not fa_name:
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

    eligible_users = list(await db.execute(
        select(UserDB.id, UserDB.first_name, UserDB.last_name, UserDB.name, UserDB.email)
        .join(FunctionalAreaDB, FunctionalAreaDB.id == UserDB.functional_area_id)
        .where(
            *_reportable_user_filter(),
            FunctionalAreaDB.name == fa_name,
        )
    ))

    if not eligible_users:
        return [
            {"period": p_date.strftime("%Y-%m"), "users": []}
            for _, p_date in periods
        ]

    user_ids = [uid for uid, _, _, _, _ in eligible_users]
    user_info = {uid: (fn, ln, name, em) for uid, fn, ln, name, em in eligible_users}

    period_ids = [p_id for p_id, _ in periods]

    report_rows = await db.execute(
        select(
            ReportDB.user_id,
            ReportDB.reporting_period_id,
            func.coalesce(func.sum(ReportPartDB.percentage), 0).label("total_pct"),
            func.coalesce(func.sum(
                case(
                    (ProjectDB.is_billable.is_(True), ReportPartDB.percentage),
                    else_=0,
                )
            ), 0).label("billable_pct"),
            func.coalesce(func.sum(
                case(
                    (ProjectDB.is_absence.is_(True), ReportPartDB.percentage),
                    else_=0,
                )
            ), 0).label("absence_pct"),
            func.count(func.distinct(
                case(
                    (ProjectDB.is_billable.is_(True), ReportPartDB.project_id),
                    else_=None,
                )
            )).label("billable_project_count"),
        )
        .join(ReportPartDB, ReportPartDB.report_id == ReportDB.id)
        .join(ProjectDB, ProjectDB.id == ReportPartDB.project_id)
        .where(
            ReportPartDB.percentage.isnot(None),
            ReportDB.user_id.in_(user_ids),
            ReportDB.reporting_period_id.in_(period_ids),
        )
        .group_by(ReportDB.user_id, ReportDB.reporting_period_id)
    )

    report_lookup: dict[tuple, tuple[float, float, float, int]] = {}
    for uid, pid, total, billable, absence, proj_count in report_rows:
        report_lookup[(uid, pid)] = (float(total), float(billable), float(absence), int(proj_count))

    result = []
    for period_id, period_date in periods:
        users_list = []
        for uid in user_ids:
            entry = report_lookup.get((uid, period_id))
            if not entry:
                continue
            total, billable, absence, proj_count = entry
            if _is_on_leave(total, absence):
                continue
            other = max(0.0, total - billable - absence)
            fn, ln, full, em = user_info[uid]
            users_list.append({
                "user_id": uid,
                "name": _format_user_name(fn, ln, full, em),
                "billable_pct": round(billable, 4),
                "absence_pct": round(absence, 4),
                "other_pct": round(other, 4),
                "billable_project_count": proj_count,
            })
        users_list.sort(key=lambda u: u["name"])
        result.append({
            "period": period_date.strftime("%Y-%m"),
            "users": users_list,
        })

    return result


async def get_reportable_users(db: AsyncSession) -> list[dict]:
    """Return all active users that require project reporting, for selectors."""
    rows = await db.execute(
        select(UserDB.id, UserDB.first_name, UserDB.last_name, UserDB.name, UserDB.email)
        .where(*_reportable_user_filter())
    )
    result = []
    for uid, fn, ln, full_name, email in rows:
        result.append({
            "id": str(uid),
            "name": _format_user_name(fn, ln, full_name, email),
        })
    result.sort(key=lambda u: u["name"])
    return result
