"""Analytical query for capacity insights.

Cross-module JOIN: core tables (users, functional_areas, projects)
+ tracker tables (reports, report_parts, reporting_periods).
Placed in core/services/ per architecture Rule 4.
"""

import logging
from datetime import date
from uuid import UUID

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


SHORT_TO_FA_NAME: dict[str, str] = {v: k for k, v in TARGET_FA_MAPPING.items()}


def _format_user_name(
    first_name: str | None,
    last_name: str | None,
    full_name: str | None = None,
    email: str | None = None,
) -> str:
    """Format as 'F. Lastname' with fallbacks: first/last > full_name > email prefix."""
    if first_name and last_name:
        return f"{first_name[0]}. {last_name}"
    if last_name:
        return last_name
    if first_name:
        return first_name
    if full_name:
        parts = full_name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}. {parts[-1]}"
        return full_name
    if email:
        local = email.split("@")[0]
        parts = local.replace("_", ".").split(".")
        if len(parts) >= 2:
            return f"{parts[0][0].upper()}. {parts[-1].capitalize()}"
        return local.capitalize()
    return "Unknown"


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
            UserDB.active.is_(True),
            UserDB.requires_project_reporting.is_(True),
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
            if not entry or entry[0] <= 0:
                continue
            fn, ln, full, em = user_info[uid]
            users_list.append({
                "user_id": uid,
                "name": _format_user_name(fn, ln, full, em),
                "billable_pct": round(entry[1], 4),
                "absence_pct": round(entry[2], 4),
                "billable_project_count": entry[3],
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
        .where(
            UserDB.active.is_(True),
            UserDB.requires_project_reporting.is_(True),
        )
    )
    result = []
    for uid, fn, ln, full_name, email in rows:
        result.append({
            "id": str(uid),
            "name": _format_user_name(fn, ln, full_name, email),
        })
    result.sort(key=lambda u: u["name"])
    return result


async def get_capacity_user_detail(
    db: AsyncSession,
    user_id: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Per-project breakdown for a single user per period.

    Returns list of dicts sorted by period ascending, each containing
    'period' (YYYY-MM) and 'projects' list with per-project breakdown.
    Only billable projects are listed individually; the remainder is 'others'.
    """
    uid = UUID(user_id)

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

    report_rows = await db.execute(
        select(
            ReportDB.reporting_period_id,
            ProjectDB.id,
            ProjectDB.name,
            ProjectDB.is_billable,
            ProjectDB.is_absence,
            ReportPartDB.percentage,
        )
        .join(ReportPartDB, ReportPartDB.report_id == ReportDB.id)
        .join(ProjectDB, ProjectDB.id == ReportPartDB.project_id)
        .where(
            ReportPartDB.percentage.isnot(None),
            ReportDB.user_id == uid,
            ReportDB.reporting_period_id.in_(period_ids),
        )
    )

    # {period_id: [(project_id, name, is_billable, is_absence, pct), ...]}
    period_projects: dict[object, list[tuple]] = {}
    for pid, proj_id, proj_name, is_billable, is_absence, pct in report_rows:
        period_projects.setdefault(pid, []).append(
            (str(proj_id), proj_name, bool(is_billable), bool(is_absence), float(pct))
        )

    result = []
    for period_id, period_date in periods:
        entries = period_projects.get(period_id, [])
        projects = []
        absence_pct = 0.0
        for proj_id, proj_name, is_billable, is_absence, pct in entries:
            if is_absence:
                absence_pct += pct
            elif is_billable and pct > 0:
                projects.append({
                    "project_id": proj_id,
                    "name": proj_name,
                    "percentage": round(pct, 4),
                })
        projects.sort(key=lambda p: p["name"])
        result.append({
            "period": period_date.strftime("%Y-%m"),
            "projects": projects,
            "absence_pct": round(absence_pct, 4),
        })

    return result


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

    report_subq = (
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
        result.append({
            "period": period_date.strftime("%Y-%m"),
            "functional_areas": fas,
        })

    return result


def _aggregate_fa_period(
    users_by_fa: dict[str, list],
    report_lookup: dict[tuple, tuple[float, float, float]],
    period_id: object,
) -> list[dict]:
    """Aggregate billable and absence % per FA for a single period."""
    fas = []
    for short, user_ids in sorted(users_by_fa.items()):
        if not user_ids:
            continue
        active_data = [
            (report_lookup[(uid, period_id)][1], report_lookup[(uid, period_id)][2])
            for uid in user_ids
            if (uid, period_id) in report_lookup and report_lookup[(uid, period_id)][0] > 0
        ]
        if not active_data:
            continue
        avg_billable = sum(b for b, _ in active_data) / len(active_data)
        avg_absence = sum(a for _, a in active_data) / len(active_data)
        fas.append({
            "short": short,
            "billable_pct": round(avg_billable, 4),
            "absence_pct": round(avg_absence, 4),
            "user_count": len(active_data),
        })
    return fas
