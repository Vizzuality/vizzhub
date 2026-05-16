"""Pure helpers backing the capacity planner endpoints.

Kept private to the capacity API package — re-exported by ``planner.py``
where the FastAPI routes live. Tests that already import private names
(e.g. ``_mondays_in_month``) keep working because ``planner.py``
re-imports them, preserving the public name table.
"""

from datetime import date, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB, ProjectStatus
from app.core.models.user import UserDB
from app.core.services.capacity_insights import TARGET_FA_MAPPING
from app.core.sql_helpers import user_display_name_expr
from app.modules.capacity.models.capacity_plan import CapacityPlanDB


def _fa_short_name(fa_name: str | None) -> str:
    """Map full FA name to short code: 'Frontend Developer' → 'FE'."""
    if not fa_name:
        return ""
    return TARGET_FA_MAPPING.get(fa_name, fa_name)


def _user_name_expr():
    """Display-name expression for planner queries; thin alias of the shared helper."""
    return user_display_name_expr(UserDB)


def _mondays_between(start: date, end: date) -> list[str]:
    """Return list of Monday ISO date strings in range [start, end]."""
    current = start - timedelta(days=start.weekday())
    weeks = []
    while current <= end:
        weeks.append(current.isoformat())
        current += timedelta(weeks=1)
    return weeks


def _mondays_in_month(month_date: date) -> list[date]:
    """Return all Mondays that fall within the given month."""
    first_day = month_date.replace(day=1)
    if month_date.month == 12:
        last_day = first_day.replace(year=first_day.year + 1, month=1) - timedelta(days=1)
    else:
        last_day = first_day.replace(month=first_day.month + 1) - timedelta(days=1)

    mondays: list[date] = []
    current = first_day - timedelta(days=first_day.weekday())
    if current < first_day:
        current += timedelta(weeks=1)
    while current <= last_day:
        mondays.append(current)
        current += timedelta(weeks=1)
    return mondays


def _parse_date(value: str, name: str) -> date:
    """Parse YYYY-MM-DD string to date."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date format for {name}: {value}")


def _build_row_data(row) -> dict:
    """Build a single row dict from a query result row."""
    return {
        "user_id": str(row.user_id),
        "user_name": row.user_name,
        "functional_area": _fa_short_name(row.functional_area),
        "project_id": str(row.project_id),
        "project_name": row.project_name,
        "is_absence": row.is_absence,
        "is_other": not row.is_absence and not row.is_billable,
        "cells": {},
        "comments": {},
    }


def _process_rows(rows, group_by: str) -> dict[str, dict]:
    """Group query rows into groups_map keyed by group id."""
    groups_map: dict[str, dict] = {}
    rows_map: dict[str, dict] = {}

    for row in rows:
        if group_by == "project":
            group_key = str(row.project_id)
            group_name = row.project_name
            row_key = f"{row.project_id}:{row.user_id}"
        else:
            group_key = str(row.user_id)
            group_name = row.user_name
            row_key = f"{row.user_id}:{row.project_id}"

        if group_key not in groups_map:
            group_data: dict = {"id": group_key, "name": group_name, "rows": []}
            if group_by == "user":
                group_data["functional_area"] = _fa_short_name(row.functional_area)
            groups_map[group_key] = group_data

        if row_key not in rows_map:
            row_data = _build_row_data(row)
            rows_map[row_key] = row_data
            groups_map[group_key]["rows"].append(row_data)

        rows_map[row_key]["cells"][row.week_start.isoformat()] = row.percentage
        if row.comment:
            rows_map[row_key]["comments"][row.week_start.isoformat()] = row.comment

    return groups_map


async def _inject_empty_groups(
    db: AsyncSession, groups_map: dict[str, dict], group_by: str,
) -> None:
    """Add empty groups for all live projects / active reportable users."""
    if group_by == "project":
        stmt = (
            select(ProjectDB.id, ProjectDB.name)
            .where(ProjectDB.status != ProjectStatus.FINISHED)
            .where(ProjectDB.is_billable.is_(True))
            .order_by(ProjectDB.name)
        )
    else:
        stmt = (
            select(
                UserDB.id,
                _user_name_expr().label("name"),
                FunctionalAreaDB.name.label("functional_area"),
            )
            .outerjoin(FunctionalAreaDB, FunctionalAreaDB.id == UserDB.functional_area_id)
            .where(UserDB.active.is_(True))
            .where(UserDB.requires_project_reporting.is_(True))
            .order_by(UserDB.name)
        )

    for g in (await db.execute(stmt)).all():
        key = str(g.id)
        if key not in groups_map:
            group_data: dict = {"id": key, "name": g.name, "rows": []}
            if group_by == "user":
                group_data["functional_area"] = _fa_short_name(getattr(g, "functional_area", None))
            groups_map[key] = group_data


async def _inject_pinned_rows(
    db: AsyncSession, groups_map: dict[str, dict],
) -> None:
    """Ensure every user group has pinned rows for absence + Operations projects."""
    pinned_stmt = (
        select(ProjectDB.id, ProjectDB.name, ProjectDB.is_absence)
        .where(ProjectDB.status != ProjectStatus.FINISHED)
        .where(
            (ProjectDB.is_absence.is_(True))
            | (ProjectDB.name == "Operations")
        )
    )
    pinned_projects = (await db.execute(pinned_stmt)).all()

    for user_key, group in groups_map.items():
        existing_project_ids = {r["project_id"] for r in group["rows"]}
        for pp in pinned_projects:
            pp_id = str(pp.id)
            if pp_id not in existing_project_ids:
                group["rows"].append({
                    "user_id": user_key,
                    "user_name": group["name"],
                    "functional_area": "",
                    "project_id": pp_id,
                    "project_name": pp.name,
                    "is_absence": pp.is_absence,
                    "is_other": not pp.is_absence,
                    "cells": {},
                    "comments": {},
                })


async def _get_overallocation_warnings(
    db: AsyncSession, start_date: date, end_date: date,
) -> list[str]:
    """Return user IDs with weeks where allocations exceed 100%."""
    stmt = (
        select(CapacityPlanDB.user_id)
        .join(UserDB, CapacityPlanDB.user_id == UserDB.id)
        .where(CapacityPlanDB.week_start >= start_date)
        .where(CapacityPlanDB.week_start <= end_date)
        .where(UserDB.active.is_(True))
        .where(UserDB.requires_project_reporting.is_(True))
        .group_by(CapacityPlanDB.user_id, CapacityPlanDB.week_start)
        .having(func.sum(CapacityPlanDB.percentage) > 100)
    )
    warn_rows = (await db.execute(stmt)).all()
    return list({str(r.user_id) for r in warn_rows})


async def _upsert_batch(
    db: AsyncSession,
    batch: list,
    user_id: UUID,
    include_comment: bool,
) -> None:
    """Upsert a batch of cells. When include_comment is False the existing
    DB comment is preserved (percentage-only update)."""
    values = [
        {
            "project_id": cell.project_id,
            "user_id": cell.user_id,
            "week_start": cell.week_start,
            "percentage": cell.percentage,
            "comment": cell.comment,
            "created_by": user_id,
            "updated_by": user_id,
        }
        for cell in batch
    ]
    stmt = pg_insert(CapacityPlanDB).values(values)
    update_set: dict = {
        "percentage": stmt.excluded.percentage,
        "updated_by": stmt.excluded.updated_by,
        "updated_at": func.now(),
    }
    if include_comment:
        update_set["comment"] = stmt.excluded.comment
    stmt = stmt.on_conflict_do_update(
        constraint="uq_capacity_plan_cell",
        set_=update_set,
    )
    await db.execute(stmt)
