"""Analytical query for capacity insights.

Cross-module JOIN: core tables (users, functional_areas, projects)
+ tracker tables (reports, report_parts, reporting_periods).
Placed in core/services/ per architecture Rule 4.
"""

import logging
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

logger = logging.getLogger(__name__)

TARGET_FA_MAPPING: dict[str, str] = {
    "Frontend Developer": "FE",
    "Backend Developer": "BE",
    "Designer": "Design",
    "Project Manager": "PM",
    "Scientist": "Sci",
    "Communications": "Coms",
}


async def get_capacity_insights(
    db: AsyncSession,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Compute billable allocation % per target FA per period.

    Returns list of dicts sorted by period ascending, each containing
    'period' (YYYY-MM) and 'functional_areas' list.
    """
    fa_rows = list(await db.execute(
        select(FunctionalAreaDB.id, FunctionalAreaDB.name)
        .where(FunctionalAreaDB.name.in_(TARGET_FA_MAPPING.keys()))
    ))
    fa_id_to_short: dict = {}
    found_names: set[str] = set()
    for fa_id, fa_name in fa_rows:
        fa_id_to_short[fa_id] = TARGET_FA_MAPPING[fa_name]
        found_names.add(fa_name)

    for name in set(TARGET_FA_MAPPING.keys()) - found_names:
        logger.warning("Capacity insights: FA '%s' not found in database", name)

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
        select(UserDB.id, UserDB.functional_area_id)
        .where(
            UserDB.active.is_(True),
            UserDB.requires_project_reporting.is_(True),
            UserDB.functional_area_id.in_(fa_id_to_short.keys()),
        )
    )
    users_by_fa: dict[str, list] = {}
    for user_id, fa_id in eligible_users:
        short = fa_id_to_short[fa_id]
        users_by_fa.setdefault(short, []).append(user_id)

    billable_sum_subq = (
        select(
            ReportDB.user_id,
            ReportDB.reporting_period_id,
            func.coalesce(func.sum(
                case(
                    (ProjectDB.is_billable.is_(True), ReportPartDB.percentage),
                    else_=0,
                )
            ), 0).label("billable_pct"),
        )
        .join(ReportPartDB, ReportPartDB.report_id == ReportDB.id)
        .join(ProjectDB, ProjectDB.id == ReportPartDB.project_id)
        .where(ReportPartDB.percentage.isnot(None))
        .group_by(ReportDB.user_id, ReportDB.reporting_period_id)
        .subquery()
    )

    period_ids = [p_id for p_id, _ in periods]
    billable_rows = await db.execute(
        select(
            billable_sum_subq.c.user_id,
            billable_sum_subq.c.reporting_period_id,
            billable_sum_subq.c.billable_pct,
        ).where(billable_sum_subq.c.reporting_period_id.in_(period_ids))
    )

    billable_lookup: dict[tuple, float] = {}
    for user_id, period_id, pct in billable_rows:
        billable_lookup[(user_id, period_id)] = float(pct)

    result = []
    for period_id, period_date in periods:
        fas = []
        for short, user_ids in sorted(users_by_fa.items()):
            if not user_ids:
                continue
            total_billable = sum(
                billable_lookup.get((uid, period_id), 0.0)
                for uid in user_ids
            )
            avg_billable = total_billable / len(user_ids)
            fas.append({
                "short": short,
                "billable_pct": round(avg_billable, 4),
                "user_count": len(user_ids),
            })
        result.append({
            "period": period_date.strftime("%Y-%m"),
            "functional_areas": fas,
        })

    return result
