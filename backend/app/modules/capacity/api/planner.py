"""Capacity planner CRUD endpoints."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select, tuple_

from app.core.api.deps import CurrentUser, DBSession
from app.core.auth import TokenData
from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB, ProjectStatus
from app.core.models.user import UserDB
from app.core.permissions import Action, require_permission
from app.modules.capacity.api._helpers import (
    _get_overallocation_warnings,
    _inject_empty_groups,
    _inject_pinned_rows,
    _mondays_between,
    _mondays_in_month,
    _parse_date,
    _process_rows,
    _upsert_batch,
    _user_name_expr,
)
from app.modules.capacity.models.capacity_plan import BulkCellUpdate, CapacityPlanDB

CapacityManager = Annotated[TokenData, Depends(require_permission(Action.CAPACITY_MANAGE))]
CapacityViewer = Annotated[TokenData, Depends(require_permission(Action.CAPACITY_VIEW))]

router = APIRouter()
logger = structlog.get_logger()

# Re-exported for `from app.modules.capacity.api.planner import _mondays_in_month`
# (test_mondays_in_month.py). Keep these names importable from this module.
__all__ = [
    "router",
    "delete_row",
    "get_planner",
    "get_planner_suggestions",
    "get_updated_at",
    "update_cells",
    "_mondays_in_month",
]


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
            CapacityPlanDB.comment,
        )
        .join(ProjectDB, CapacityPlanDB.project_id == ProjectDB.id)
        .join(UserDB, CapacityPlanDB.user_id == UserDB.id)
        .outerjoin(FunctionalAreaDB, FunctionalAreaDB.id == UserDB.functional_area_id)
        .where(CapacityPlanDB.week_start >= start_date)
        .where(CapacityPlanDB.week_start <= end_date)
        .where(ProjectDB.status != ProjectStatus.FINISHED)
        .where(UserDB.active.is_(True))
        .where(UserDB.requires_project_reporting.is_(True))
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
        .where(ProjectDB.status != ProjectStatus.FINISHED)
        .group_by(
            CapacityPlanDB.project_id, ProjectDB.name, ProjectDB.is_absence, ProjectDB.is_billable
        )
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
            suggestions.append(
                {
                    "project_id": str(row.project_id),
                    "project_name": row.project_name,
                    "percentage": normalized,
                    "is_absence": row.is_absence,
                }
            )

    suggestions.sort(key=lambda s: s["project_name"].lower())

    return {"suggestions": suggestions, "others_percentage": others_pct}


@router.patch(
    "/cells",
    responses={422: {"description": "Validation error"}},
)
async def update_cells(
    db: DBSession,
    user: CapacityManager,
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
        with_comment = [c for c in upserts if "comment" in c.model_fields_set]
        without_comment = [c for c in upserts if "comment" not in c.model_fields_set]
        if with_comment:
            await _upsert_batch(db, with_comment, user.user_id, include_comment=True)
        if without_comment:
            await _upsert_batch(db, without_comment, user.user_id, include_comment=False)
        upserted_count = len(upserts)

    await db.flush()
    logger.info(
        "capacity_cells_updated",
        actor_id=user.user_id,
        upserted=upserted_count,
        deleted=deleted_count,
    )
    return {"updated": upserted_count + deleted_count}


@router.delete(
    "/rows/{project_id}/{user_id}",
    responses={422: {"description": "Validation error"}},
)
async def delete_row(
    db: DBSession,
    user: CapacityManager,
    project_id: UUID,
    user_id: UUID,
) -> dict:
    stmt = delete(CapacityPlanDB).where(
        CapacityPlanDB.project_id == project_id,
        CapacityPlanDB.user_id == user_id,
    )
    result = await db.execute(stmt)
    logger.info(
        "capacity_row_deleted",
        actor_id=user.user_id,
        project_id=str(project_id),
        target_user_id=str(user_id),
        rows=result.rowcount,
    )
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
