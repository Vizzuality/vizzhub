"""Capacity planner CRUD endpoints."""

from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import CurrentUser, DBSession
from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB, ProjectStatus
from app.core.models.user import UserDB
from app.core.services.capacity_insights import TARGET_FA_MAPPING
from app.modules.capacity.models.capacity_plan import BulkCellUpdate, CapacityPlanDB

router = APIRouter()


def _fa_short_name(fa_name: str | None) -> str:
    """Map full FA name to short code: 'Frontend Developer' → 'FE'."""
    if not fa_name:
        return ""
    return TARGET_FA_MAPPING.get(fa_name, fa_name)


def _user_name_expr():
    """SQL expression for user display name: first+last > name > email prefix."""
    return func.coalesce(
        func.nullif(
            func.concat_ws(" ", func.nullif(UserDB.first_name, ""), func.nullif(UserDB.last_name, "")),
            "",
        ),
        UserDB.name,
        func.split_part(UserDB.email, "@", 1),
    )


def _mondays_between(start: date, end: date) -> list[str]:
    """Return list of Monday ISO date strings in range [start, end]."""
    current = start - timedelta(days=start.weekday())
    weeks = []
    while current <= end:
        weeks.append(current.isoformat())
        current += timedelta(weeks=1)
    return weeks


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
            groups_map[group_key] = {"id": group_key, "name": group_name, "rows": []}

        if row_key not in rows_map:
            row_data = _build_row_data(row)
            rows_map[row_key] = row_data
            groups_map[group_key]["rows"].append(row_data)

        rows_map[row_key]["cells"][row.week_start.isoformat()] = row.percentage

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
            select(UserDB.id, _user_name_expr().label("name"))
            .where(UserDB.active.is_(True))
            .where(UserDB.requires_project_reporting.is_(True))
            .order_by(UserDB.name)
        )

    for g in (await db.execute(stmt)).all():
        key = str(g.id)
        if key not in groups_map:
            groups_map[key] = {"id": key, "name": g.name, "rows": []}


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
        .group_by(CapacityPlanDB.user_id, CapacityPlanDB.week_start)
        .having(func.sum(CapacityPlanDB.percentage) > 100)
    )
    warn_rows = (await db.execute(stmt)).all()
    return list({str(r.user_id) for r in warn_rows})


@router.get("", responses={422: {"description": "Invalid date or group_by parameter"}})
async def get_planner(
    db: DBSession,
    user: CurrentUser,
    start: Annotated[str, Query(description="Start date (YYYY-MM-DD, Monday)")],
    end: Annotated[str, Query(description="End date (YYYY-MM-DD, Monday)")],
    group_by: Annotated[str, Query(description="Group by: project | user")] = "project",
) -> dict:
    start_date = _parse_date(start, "start")
    end_date = _parse_date(end, "end")

    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start must be <= end")

    if group_by not in ("project", "user"):
        raise HTTPException(status_code=422, detail="group_by must be 'project' or 'user'")

    weeks = _mondays_between(start_date, end_date)

    stmt = (
        select(
            CapacityPlanDB.project_id,
            ProjectDB.name.label("project_name"),
            ProjectDB.is_absence,
            ProjectDB.is_billable,
            CapacityPlanDB.user_id,
            _user_name_expr().label("user_name"),
            FunctionalAreaDB.name.label("functional_area"),
            CapacityPlanDB.week_start,
            CapacityPlanDB.percentage,
        )
        .join(ProjectDB, CapacityPlanDB.project_id == ProjectDB.id)
        .join(UserDB, CapacityPlanDB.user_id == UserDB.id)
        .outerjoin(FunctionalAreaDB, FunctionalAreaDB.id == UserDB.functional_area_id)
        .where(CapacityPlanDB.week_start >= start_date)
        .where(CapacityPlanDB.week_start <= end_date)
        .where(ProjectDB.status != ProjectStatus.FINISHED)
        .where(UserDB.active.is_(True))
        .order_by(ProjectDB.name, UserDB.name, CapacityPlanDB.week_start)
    )

    if group_by == "project":
        stmt = stmt.where(ProjectDB.is_billable.is_(True))

    rows = (await db.execute(stmt)).all()
    groups_map = _process_rows(rows, group_by)

    await _inject_empty_groups(db, groups_map, group_by)

    if group_by == "user":
        await _inject_pinned_rows(db, groups_map)

    sorted_groups = sorted(
        groups_map.values(),
        key=lambda g: (len(g["rows"]) == 0, g["name"].lower()),
    )

    warnings = await _get_overallocation_warnings(db, start_date, end_date)

    return {"groups": sorted_groups, "weeks": weeks, "warnings": warnings}


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


@router.get("/suggestions", responses={422: {"description": "Invalid date format"}})
async def get_planner_suggestions(
    db: DBSession,
    user: CurrentUser,
    month: Annotated[str, Query(description="Month (YYYY-MM-DD, first of month)")],
) -> dict:
    """Return planning-based allocation suggestions for a user's monthly report.

    Averages weekly planning data for the given month per project,
    then normalizes so all percentages sum to 100%.
    Others (Operations) is returned separately.
    """
    empty_response = {"suggestions": [], "others_percentage": None}

    month_date = _parse_date(month, "month")
    mondays = _mondays_in_month(month_date)

    if not mondays:
        return empty_response

    stmt = (
        select(
            CapacityPlanDB.project_id,
            ProjectDB.name.label("project_name"),
            ProjectDB.is_absence,
            ProjectDB.is_billable,
            func.sum(CapacityPlanDB.percentage).label("total_pct"),
        )
        .join(ProjectDB, CapacityPlanDB.project_id == ProjectDB.id)
        .where(CapacityPlanDB.user_id == user.user_id)
        .where(CapacityPlanDB.week_start.in_(mondays))
        .group_by(CapacityPlanDB.project_id, ProjectDB.name, ProjectDB.is_absence, ProjectDB.is_billable)
    )

    rows = (await db.execute(stmt)).all()

    grand_total = sum(r.total_pct for r in rows) if rows else 0
    if not grand_total:
        return empty_response

    others_pct: float | None = None
    suggestions: list[dict] = []

    for row in rows:
        normalized = round(row.total_pct / grand_total * 100, 1)
        is_others = not row.is_absence and not row.is_billable and row.project_name == "Operations"

        if is_others:
            others_pct = normalized
        else:
            suggestions.append({
                "project_id": str(row.project_id),
                "project_name": row.project_name,
                "percentage": normalized,
                "is_absence": row.is_absence,
            })

    suggestions.sort(key=lambda s: s["project_name"].lower())

    return {"suggestions": suggestions, "others_percentage": others_pct}


@router.patch(
    "/cells",
    responses={422: {"description": "Validation error"}},
)
async def update_cells(
    db: DBSession,
    user: CurrentUser,
    body: BulkCellUpdate,
) -> dict:
    if not body.updates:
        return {"updated": 0}

    deletes = []
    upserts = []

    for cell in body.updates:
        if cell.percentage is None or cell.percentage == 0:
            deletes.append(cell)
        else:
            upserts.append(cell)

    deleted_count = 0
    if deletes:
        stmt = delete(CapacityPlanDB).where(
            tuple_(
                CapacityPlanDB.project_id,
                CapacityPlanDB.user_id,
                CapacityPlanDB.week_start,
            ).in_([(c.project_id, c.user_id, c.week_start) for c in deletes])
        )
        result = await db.execute(stmt)
        deleted_count = result.rowcount

    upserted_count = 0
    if upserts:
        values = [
            {
                "project_id": cell.project_id,
                "user_id": cell.user_id,
                "week_start": cell.week_start,
                "percentage": cell.percentage,
                "created_by": user.user_id,
                "updated_by": user.user_id,
            }
            for cell in upserts
        ]
        stmt = pg_insert(CapacityPlanDB).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_capacity_plan_cell",
            set_={
                "percentage": stmt.excluded.percentage,
                "updated_by": stmt.excluded.updated_by,
                "updated_at": func.now(),
            },
        )
        await db.execute(stmt)
        upserted_count = len(upserts)

    await db.commit()
    return {"updated": upserted_count + deleted_count}


@router.delete(
    "/rows/{project_id}/{user_id}",
    responses={422: {"description": "Validation error"}},
)
async def delete_row(
    db: DBSession,
    user: CurrentUser,
    project_id: UUID,
    user_id: UUID,
) -> dict:
    stmt = delete(CapacityPlanDB).where(
        CapacityPlanDB.project_id == project_id,
        CapacityPlanDB.user_id == user_id,
    )
    result = await db.execute(stmt)
    await db.commit()
    return {"deleted": result.rowcount}


@router.get("/updated-at", responses={422: {"description": "Invalid date format"}})
async def get_updated_at(
    db: DBSession,
    user: CurrentUser,
    start: Annotated[str, Query(description="Start date (YYYY-MM-DD)")],
    end: Annotated[str, Query(description="End date (YYYY-MM-DD)")],
) -> dict:
    start_date = _parse_date(start, "start")
    end_date = _parse_date(end, "end")

    stmt = select(func.max(CapacityPlanDB.updated_at)).where(
        CapacityPlanDB.week_start >= start_date,
        CapacityPlanDB.week_start <= end_date,
    )
    result = await db.execute(stmt)
    max_updated = result.scalar_one_or_none()

    return {"updated_at": max_updated.isoformat() if max_updated else None}
