"""Per-project allocation view: people allocated to each live project."""

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB

from ._shared import _format_full_name, _get_finished_periods, _reportable_user_filter


async def get_allocation_projects(
    db: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Per-project user allocation averaged over finished periods.

    Shows active (status='live') projects ranked by avg number of people.
    Each project has segments for individual users.
    """
    periods = await _get_finished_periods(db, start_date, end_date)

    if not periods:
        return {"periods_used": [], "projects": []}

    num_periods = len(periods)
    period_ids = [p_id for p_id, _ in periods]
    period_dates = dict(periods)
    periods_used = [p_date.strftime("%Y-%m") for _, p_date in periods]

    rows = await db.execute(
        select(
            ReportPartDB.project_id,
            ProjectDB.name.label("project_name"),
            ReportDB.reporting_period_id,
            ReportDB.user_id,
            UserDB.first_name,
            UserDB.last_name,
            UserDB.name.label("full_name"),
            UserDB.email,
            ReportPartDB.percentage,
        )
        .join(ReportDB, ReportDB.id == ReportPartDB.report_id)
        .join(ProjectDB, ProjectDB.id == ReportPartDB.project_id)
        .join(UserDB, UserDB.id == ReportDB.user_id)
        .where(
            ReportPartDB.percentage.isnot(None),
            ReportDB.reporting_period_id.in_(period_ids),
            ProjectDB.status == "live",
            ProjectDB.is_billable.is_(True),
            *_reportable_user_filter(),
        )
    )

    proj_users: dict[object, dict[object, dict]] = defaultdict(dict)
    proj_names: dict[object, str] = {}
    proj_period_users: dict[object, dict[object, set]] = defaultdict(
        lambda: defaultdict(set),
    )

    for (
        proj_id,
        proj_name,
        pid,
        uid,
        fn,
        ln,
        full,
        email,
        pct,
    ) in rows:
        proj_names[proj_id] = proj_name
        user_map = proj_users[proj_id]
        if uid not in user_map:
            user_map[uid] = {
                "pct_sum": 0.0,
                "periods": set(),
                "name": _format_full_name(fn, ln, full, email),
            }
        user_map[uid]["pct_sum"] += float(pct)
        user_map[uid]["periods"].add(pid)
        proj_period_users[proj_id][pid].add(uid)

    projects_list = []
    for proj_id, user_map in proj_users.items():
        total_people_per_period = sum(len(users) for users in proj_period_users[proj_id].values())
        avg_people = round(total_people_per_period / num_periods, 2)

        all_user_ids: set = set()
        for users in proj_period_users[proj_id].values():
            all_user_ids.update(users)
        total_distinct = len(all_user_ids)

        segments = []
        for uid, info in user_map.items():
            avg_pct = round(info["pct_sum"] / num_periods, 4)
            active_months = sorted(
                [period_dates[pid].strftime("%Y-%m") for pid in info["periods"]],
                reverse=True,
            )
            segments.append(
                {
                    "user_id": str(uid),
                    "user_name": info["name"],
                    "avg_percentage": avg_pct,
                    "months_active": active_months,
                }
            )

        segments.sort(key=lambda s: -s["avg_percentage"])

        projects_list.append(
            {
                "project_id": str(proj_id),
                "name": proj_names[proj_id],
                "avg_people": avg_people,
                "total_distinct_people": total_distinct,
                "segments": segments,
            }
        )

    projects_list.sort(key=lambda p: (-p["avg_people"], p["name"]))

    return {"periods_used": periods_used, "projects": projects_list}
