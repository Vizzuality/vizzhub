"""Per-user allocation view: averages over recent finished periods."""

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB

from ._shared import (
    TARGET_FA_MAPPING,
    _format_full_name,
    _get_finished_periods,
    _reportable_user_filter,
)


def _build_user_segments(
    proj_map: dict[object, dict],
    num_periods: int,
    period_dates: dict,
) -> tuple[list[dict], int, set]:
    """Build segments for a single user's project allocation.

    Returns (segments, billable_appearances, billable_project_ids).
    """
    billable_segments: list[dict] = []
    billable_project_ids: set = set()
    billable_appearances = 0
    absence_pct_sum = 0.0
    absence_periods: set = set()
    other_pct_sum = 0.0
    other_periods: set = set()

    for proj_id, info in proj_map.items():
        if info["is_billable"]:
            active_months = sorted(
                [period_dates[pid].strftime("%Y-%m") for pid in info["periods"]],
                reverse=True,
            )
            billable_segments.append({
                "project_id": str(proj_id),
                "project_name": info["name"],
                "avg_percentage": round(info["pct_sum"] / num_periods, 4),
                "months_active": active_months,
                "type": "billable",
            })
            billable_project_ids.add(proj_id)
            billable_appearances += len(active_months)
        elif info["is_absence"]:
            absence_pct_sum += info["pct_sum"]
            absence_periods.update(info["periods"])
        else:
            other_pct_sum += info["pct_sum"]
            other_periods.update(info["periods"])

    billable_segments.sort(key=lambda s: -s["avg_percentage"])
    segments = list(billable_segments)

    if absence_pct_sum > 0:
        segments.append({
            "project_id": "__absence__",
            "project_name": "Absence",
            "avg_percentage": round(absence_pct_sum / num_periods, 4),
            "months_active": sorted(
                [period_dates[pid].strftime("%Y-%m") for pid in absence_periods],
                reverse=True,
            ),
            "type": "absence",
        })
    if other_pct_sum > 0:
        segments.append({
            "project_id": "__other__",
            "project_name": "Other",
            "avg_percentage": round(other_pct_sum / num_periods, 4),
            "months_active": sorted(
                [period_dates[pid].strftime("%Y-%m") for pid in other_periods],
                reverse=True,
            ),
            "type": "other",
        })

    return segments, billable_appearances, billable_project_ids


async def get_allocation_users(
    db: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Per-user project allocation averaged over finished periods.

    If start_date/end_date provided, uses finished periods in that range.
    Otherwise defaults to last 3 finished periods.
    Returns dict with 'periods_used' (desc order) and 'users' list.
    """
    periods = await _get_finished_periods(db, start_date, end_date)

    if not periods:
        return {"periods_used": [], "users": []}

    num_periods = len(periods)
    period_ids = [p_id for p_id, _ in periods]
    period_dates = dict(periods)
    periods_used = [p_date.strftime("%Y-%m") for _, p_date in periods]

    eligible_rows = await db.execute(
        select(
            UserDB.id, UserDB.first_name, UserDB.last_name,
            UserDB.name, UserDB.email, FunctionalAreaDB.name.label("fa_name"),
        )
        .outerjoin(FunctionalAreaDB, FunctionalAreaDB.id == UserDB.functional_area_id)
        .where(*_reportable_user_filter())
    )
    eligible_users = list(eligible_rows)

    if not eligible_users:
        return {"periods_used": periods_used, "users": []}

    user_ids = [uid for uid, _, _, _, _, _ in eligible_users]
    user_info = {
        uid: (fn, ln, full, em, TARGET_FA_MAPPING.get(fa_name, ""))
        for uid, fn, ln, full, em, fa_name in eligible_users
    }

    rows = await db.execute(
        select(
            ReportDB.user_id,
            ReportDB.reporting_period_id,
            ReportPartDB.project_id,
            ProjectDB.name,
            ProjectDB.is_billable,
            ProjectDB.is_absence,
            ReportPartDB.percentage,
        )
        .join(ReportPartDB, ReportPartDB.report_id == ReportDB.id)
        .join(ProjectDB, ProjectDB.id == ReportPartDB.project_id)
        .where(
            ReportPartDB.percentage.isnot(None),
            ReportDB.user_id.in_(user_ids),
            ReportDB.reporting_period_id.in_(period_ids),
        )
    )

    user_projects: dict[object, dict[object, dict]] = defaultdict(dict)
    for uid, pid, proj_id, proj_name, is_billable, is_absence, pct in rows:
        proj_map = user_projects[uid]
        if proj_id not in proj_map:
            proj_map[proj_id] = {
                "pct_sum": 0.0,
                "periods": set(),
                "name": proj_name,
                "is_billable": bool(is_billable),
                "is_absence": bool(is_absence),
            }
        proj_map[proj_id]["pct_sum"] += float(pct)
        proj_map[proj_id]["periods"].add(pid)

    users_list = []
    for uid in user_ids:
        proj_map = user_projects.get(uid)
        if not proj_map:
            continue

        segments, billable_appearances, billable_project_ids = _build_user_segments(
            proj_map, num_periods, period_dates,
        )

        fn, ln, full, em, fa_short = user_info[uid]
        users_list.append({
            "user_id": str(uid),
            "name": _format_full_name(fn, ln, full, em),
            "functional_area": fa_short,
            "avg_billable_projects": round(billable_appearances / num_periods, 4),
            "total_distinct_projects": len(billable_project_ids),
            "segments": segments,
        })

    users_list.sort(
        key=lambda u: (-u["avg_billable_projects"], u["name"]),
    )

    return {"periods_used": periods_used, "users": users_list}
