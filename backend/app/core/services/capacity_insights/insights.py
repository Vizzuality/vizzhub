"""Overview view: billable allocation per target FA per period."""

from datetime import date

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

from ._shared import TARGET_FA_MAPPING, _is_on_leave, _reportable_user_filter

logger = structlog.get_logger()


def _aggregate_fa_period(
    users_by_fa: dict[str, list],
    report_lookup: dict[tuple, tuple[float, float, float]],
    period_id: object,
) -> list[dict]:
    """Aggregate billable, absence and other % per FA for a single period.

    Users on effective leave (zero report or all-absence report) are
    excluded from the denominator — they had no billable capacity to
    contribute. Other (= total - billable - absence, clamped at 0)
    captures internal/admin/training work so consumers can read
    context, not just a depressed billable number."""
    fas = []
    for short, user_ids in sorted(users_by_fa.items()):
        if not user_ids:
            continue
        total_billable = 0.0
        total_absence = 0.0
        total_other = 0.0
        count = 0
        for uid in user_ids:
            entry = report_lookup.get((uid, period_id))
            if not entry:
                continue
            total, billable, absence = entry
            if _is_on_leave(total, absence):
                continue
            other = max(0.0, total - billable - absence)
            total_billable += billable
            total_absence += absence
            total_other += other
            count += 1
        if not count:
            continue
        fas.append(
            {
                "short": short,
                "billable_pct": round(total_billable / count, 4),
                "absence_pct": round(total_absence / count, 4),
                "other_pct": round(total_other / count, 4),
                "user_count": count,
            }
        )
    return fas


async def get_capacity_insights(
    db: AsyncSession,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Compute billable allocation % per target FA per period.

    Returns list of dicts sorted by period ascending, each containing
    'period' (YYYY-MM) and 'functional_areas' list.
    """
    fa_rows = list(
        await db.execute(
            select(FunctionalAreaDB.id, FunctionalAreaDB.name).where(
                FunctionalAreaDB.name.in_(TARGET_FA_MAPPING.keys())
            )
        )
    )
    fa_id_to_short: dict = {}
    found_names: set[str] = set()
    for fa_id, fa_name in fa_rows:
        fa_id_to_short[fa_id] = TARGET_FA_MAPPING[fa_name]
        found_names.add(fa_name)

    for name in set(TARGET_FA_MAPPING.keys()) - found_names:
        logger.warning("functional_area_not_found", fa_name=name)

    if not fa_id_to_short:
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

    eligible_users = await db.execute(
        select(UserDB.id, UserDB.functional_area_id).where(
            *_reportable_user_filter(),
            UserDB.functional_area_id.in_(fa_id_to_short.keys()),
        )
    )
    users_by_fa: dict[str, list] = {}
    for user_id, fa_id in eligible_users:
        short = fa_id_to_short[fa_id]
        users_by_fa.setdefault(short, []).append(user_id)

    report_subq = (
        select(
            ReportDB.user_id,
            ReportDB.reporting_period_id,
            func.coalesce(func.sum(ReportPartDB.percentage), 0).label("total_pct"),
            func.coalesce(
                func.sum(
                    case(
                        (ProjectDB.is_billable.is_(True), ReportPartDB.percentage),
                        else_=0,
                    )
                ),
                0,
            ).label("billable_pct"),
            func.coalesce(
                func.sum(
                    case(
                        (ProjectDB.is_absence.is_(True), ReportPartDB.percentage),
                        else_=0,
                    )
                ),
                0,
            ).label("absence_pct"),
        )
        .join(ReportPartDB, ReportPartDB.report_id == ReportDB.id)
        .join(ProjectDB, ProjectDB.id == ReportPartDB.project_id)
        .where(ReportPartDB.percentage.isnot(None))
        .group_by(ReportDB.user_id, ReportDB.reporting_period_id)
        .subquery()
    )

    period_ids = [p_id for p_id, _ in periods]
    report_rows = await db.execute(
        select(
            report_subq.c.user_id,
            report_subq.c.reporting_period_id,
            report_subq.c.total_pct,
            report_subq.c.billable_pct,
            report_subq.c.absence_pct,
        ).where(report_subq.c.reporting_period_id.in_(period_ids))
    )

    # (user_id, period_id) -> (total_pct, billable_pct, absence_pct)
    report_lookup: dict[tuple, tuple[float, float, float]] = {}
    for user_id, period_id, total, billable, absence in report_rows:
        report_lookup[(user_id, period_id)] = (float(total), float(billable), float(absence))

    result = []
    for period_id, period_date in periods:
        fas = _aggregate_fa_period(users_by_fa, report_lookup, period_id)
        result.append(
            {
                "period": period_date.strftime("%Y-%m"),
                "functional_areas": fas,
            }
        )

    return result
