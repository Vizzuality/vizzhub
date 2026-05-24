"""HTTP endpoints for accrual cells and per-project operations."""

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission
from app.core.services.exchange_rate_service import currency_to_code
from app.core.sql_helpers import user_display_name_expr
from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
from app.modules.accrual.schemas.accrual_cell import (
    BulkCellsRequest,
    CellUpdate,
    RedistributeRequest,
)
from app.modules.accrual.services import cell_service

logger = structlog.get_logger()
router = APIRouter()

AccrualViewer = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_VIEW))]
AccrualManager = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_MANAGE))]


def _parse_user_id(token: TokenData) -> UUID | None:
    return UUID(token.user_id) if token.user_id else None


# Health thresholds (diff_pct).
_HEALTH_WARNING_THRESHOLD = Decimal("5")
_HEALTH_CRITICAL_THRESHOLD = Decimal("20")


def _compute_health(
    *,
    budget: Decimal | None,
    sum_cells: Decimal,
    has_overrides: bool,
    code_is_duplicated: bool,
) -> dict:
    """Derive a project's accrual-grid health from cells + budget + code uniqueness.

    Statuses:
    - ``critical``: code shared with other projects (risk of ambiguous imputation),
      budget present but no cells at all, or |Σcells − budget| > 20%.
    - ``warning``: |Σcells − budget| ∈ (5%, 20%].
    - ``no_data``: cells exist but none came from the Excel importer (project is
      using uniform redistribute only — the CEO has no monthly forecast for it).
    - ``ok``: the rest.
    """
    reasons: list[str] = []
    diff_eur: Decimal | None = None
    diff_pct: Decimal | None = None

    if budget is not None and budget != 0:
        diff_eur = (sum_cells - budget).quantize(Decimal("0.01"))
        diff_pct = (abs(diff_eur) / budget * Decimal("100")).quantize(Decimal("0.01"))

    if code_is_duplicated:
        reasons.append("multi_project_dup_code")
    if budget is not None and budget > 0 and sum_cells == 0:
        reasons.append("no_cells")
    if not has_overrides and sum_cells > 0:
        reasons.append("no_excel_data")
    if diff_pct is not None and diff_pct > _HEALTH_WARNING_THRESHOLD:
        reasons.append("value_divergence")

    status_value: str
    if (
        code_is_duplicated
        or "no_cells" in reasons
        or (diff_pct is not None and diff_pct > _HEALTH_CRITICAL_THRESHOLD)
    ):
        status_value = "critical"
    elif diff_pct is not None and diff_pct > _HEALTH_WARNING_THRESHOLD:
        status_value = "warning"
    elif "no_excel_data" in reasons:
        status_value = "no_data"
    else:
        status_value = "ok"

    return {
        "status": status_value,
        "diff_eur": str(diff_eur) if diff_eur is not None else None,
        "diff_pct": float(diff_pct) if diff_pct is not None else None,
        "reasons": reasons,
    }


def _serialize(cell: ProjectAccrualCellDB) -> dict:
    """Cells are EUR-only, so ``amount`` IS the EUR figure. Frozen cells expose
    ``frozen_eur_amount`` as the immutable snapshot captured at period close."""
    return {
        "id": str(cell.id),
        "project_id": str(cell.project_id),
        "year": cell.year,
        "month": cell.month,
        "amount": str(cell.amount),
        "is_manual_override": cell.is_manual_override,
        "is_frozen": cell.is_frozen,
        "frozen_at": cell.frozen_at.isoformat() if cell.frozen_at else None,
        "frozen_eur_amount": (
            str(cell.frozen_eur_amount) if cell.frozen_eur_amount is not None else None
        ),
        "eur_amount": str(cell.amount),
        "source": cell.source,
        "updated_at": cell.updated_at.isoformat(),
    }


@router.get(
    "/grid",
    responses={400: {"description": "year_to must be >= year_from"}},
)
async def get_grid(
    db: DBSession,
    _: AccrualViewer,
    year_from: int,
    year_to: int,
    status: str | None = None,
    currency: str | None = None,
    project_manager_id: UUID | None = None,
) -> dict:
    """Joined projects + cells + month columns for the accrual admin grid.

    Filtering:
    - Non-billable projects are excluded unconditionally — the grid is
      a revenue-recognition tool, and non-billable engagements don't
      generate revenue.
    - status / project_manager_id / currency narrow the project set.
    - year_from / year_to additionally require the project to have BOTH
      start_date and end_date set, and the [start_date, end_date] range
      must overlap the requested year span. Projects without dates can't
      be redistributed across a timeline anyway (cell_service requires
      both), so they don't belong in the grid.

    The response also carries ``bounds`` (min/max year across the
    status+pm-filtered set, ignoring year+currency) and
    ``available_currencies`` (ISO-normalised set of currencies across
    that same set). The toolbar uses these to cap year-navigation arrows
    and populate the currency dropdown.
    """
    if year_to < year_from:
        raise HTTPException(status_code=400, detail="year_to must be >= year_from")

    pm = aliased(UserDB)
    stmt = (
        select(ProjectDB, user_display_name_expr(pm).label("pm_name"))
        .outerjoin(pm, ProjectDB.project_manager_id == pm.id)
        .where(ProjectDB.is_billable.is_(True))
        .where(ProjectDB.budget.is_not(None))
    )
    if status is not None:
        stmt = stmt.where(ProjectDB.status == status)
    if project_manager_id is not None:
        stmt = stmt.where(ProjectDB.project_manager_id == project_manager_id)

    result = await db.execute(stmt)
    rows = result.all()

    bounds_min = min(
        (p.start_date.year for p, _ in rows if p.start_date is not None),
        default=None,
    )
    bounds_max = max(
        (p.end_date.year for p, _ in rows if p.end_date is not None),
        default=None,
    )
    bounds = (
        {"min_year": bounds_min, "max_year": bounds_max}
        if bounds_min is not None and bounds_max is not None
        else None
    )
    available_currencies = sorted({currency_to_code(p.currency) for p, _ in rows if p.currency})

    if currency is not None:
        target_code = currency_to_code(currency)
        rows = [
            (project, pm_name)
            for project, pm_name in rows
            if project.currency and currency_to_code(project.currency) == target_code
        ]

    range_start = date(year_from, 1, 1)
    range_end = date(year_to, 12, 31)
    rows = [
        (project, pm_name)
        for project, pm_name in rows
        if project.start_date is not None
        and project.end_date is not None
        and project.start_date <= range_end
        and project.end_date >= range_start
    ]

    # Aggregate per-project totals across ALL cells (not just the visible range)
    # so the health badge stays stable when the user navigates years.
    project_ids = [p.id for p, _ in rows]
    sum_by_pid: dict[UUID, Decimal] = {}
    has_overrides_by_pid: dict[UUID, bool] = {}
    if project_ids:
        agg_result = await db.execute(
            select(
                ProjectAccrualCellDB.project_id,
                func.coalesce(func.sum(ProjectAccrualCellDB.amount), 0).label("total"),
                func.bool_or(ProjectAccrualCellDB.is_manual_override).label("has_overrides"),
            )
            .where(ProjectAccrualCellDB.project_id.in_(project_ids))
            .group_by(ProjectAccrualCellDB.project_id)
        )
        for pid, total, has_ov in agg_result.all():
            sum_by_pid[pid] = Decimal(str(total))
            has_overrides_by_pid[pid] = bool(has_ov)

    # Detect codes shared by more than one project in the full billable set
    # (not just the filtered subset). Multi-project codes inflate the risk of
    # ambiguous cell imputation, so we flag them as critical.
    dup_codes_result = await db.execute(
        select(ProjectDB.code)
        .where(ProjectDB.is_billable.is_(True))
        .where(ProjectDB.code.is_not(None))
        .group_by(ProjectDB.code)
        .having(func.count() > 1)
    )
    duplicated_codes = {row[0] for row in dup_codes_result.all()}

    projects: list[dict] = []
    for p, pm_name in rows:
        sum_cells = sum_by_pid.get(p.id, Decimal("0"))
        has_overrides = has_overrides_by_pid.get(p.id, False)
        health = _compute_health(
            budget=Decimal(p.budget) if p.budget is not None else None,
            sum_cells=sum_cells,
            has_overrides=has_overrides,
            code_is_duplicated=p.code in duplicated_codes if p.code else False,
        )
        projects.append(
            {
                "id": str(p.id),
                "name": p.name,
                "code": p.code,
                "currency": p.currency,
                "budget": str(p.budget) if p.budget is not None else None,
                "original_budget": str(p.original_budget)
                if p.original_budget is not None
                else None,
                "budget_eur": str(p.budget) if p.budget is not None else None,
                "status": p.status,
                "start_date": p.start_date.isoformat() if p.start_date else None,
                "end_date": p.end_date.isoformat() if p.end_date else None,
                "project_manager_id": str(p.project_manager_id) if p.project_manager_id else None,
                "project_manager_name": pm_name,
                "health": health,
            }
        )

    cells_serialised: list[dict] = []
    if project_ids:
        cells_result = await db.execute(
            select(ProjectAccrualCellDB)
            .where(
                ProjectAccrualCellDB.project_id.in_(project_ids),
                ProjectAccrualCellDB.year >= year_from,
                ProjectAccrualCellDB.year <= year_to,
            )
            .order_by(
                ProjectAccrualCellDB.project_id,
                ProjectAccrualCellDB.year,
                ProjectAccrualCellDB.month,
            )
        )
        cells = cells_result.scalars().all()
        cells_serialised = [_serialize(c) for c in cells]

    months = [
        {"year": year, "month": month}
        for year in range(year_from, year_to + 1)
        for month in range(1, 13)
    ]
    return {
        "projects": projects,
        "cells": cells_serialised,
        "months": months,
        "bounds": bounds,
        "available_currencies": available_currencies,
    }


@router.get("/projects/{project_id}/cells")
async def get_project_cells(
    project_id: UUID,
    db: DBSession,
    _: AccrualViewer,
) -> list[dict]:
    """Return all cells for a project ordered by (year, month)."""
    result = await db.execute(
        select(ProjectAccrualCellDB)
        .where(ProjectAccrualCellDB.project_id == project_id)
        .order_by(ProjectAccrualCellDB.year, ProjectAccrualCellDB.month)
    )
    return [_serialize(c) for c in result.scalars().all()]


@router.post("/projects/{project_id}/redistribute")
async def redistribute(
    project_id: UUID,
    payload: RedistributeRequest,
    db: DBSession,
    user: AccrualManager,
) -> dict:
    """Redistribute the project's budget across mutable months."""
    cells_updated = await cell_service.redistribute_for_project(
        db,
        project_id=project_id,
        force=payload.force,
    )
    logger.info(
        "accrual_redistribute_endpoint",
        project_id=str(project_id),
        cells_updated=cells_updated,
        force=payload.force,
        user_id=user.user_id,
    )
    return {"cells_updated": cells_updated}


@router.patch(
    "/cells/{cell_id}",
    responses={
        404: {"description": "Cell not found"},
        409: {"description": "Cell is frozen"},
    },
)
async def patch_cell(
    cell_id: UUID,
    payload: CellUpdate,
    db: DBSession,
    user: AccrualManager,
) -> dict:
    """Set a cell to an explicit amount, marking it as a manual override."""
    cell = await db.get(ProjectAccrualCellDB, cell_id)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    try:
        await cell_service.set_cell_amount(
            db,
            project_id=cell.project_id,
            year=cell.year,
            month=cell.month,
            amount=payload.amount,
            user_id=_parse_user_id(user),
        )
    except cell_service.CellFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.refresh(cell)
    return _serialize(cell)


@router.delete(
    "/cells/{cell_id}/override",
    responses={
        404: {"description": "Cell not found"},
        409: {"description": "Cell is frozen"},
    },
)
async def delete_override(
    cell_id: UUID,
    db: DBSession,
    user: AccrualManager,
) -> dict:
    """Clear a manual override and redistribute the freed budget across remaining months."""
    cell = await db.get(ProjectAccrualCellDB, cell_id)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    try:
        await cell_service.clear_override(
            db,
            project_id=cell.project_id,
            year=cell.year,
            month=cell.month,
        )
    except cell_service.CellFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.refresh(cell)
    logger.info(
        "accrual_override_cleared",
        cell_id=str(cell.id),
        project_id=str(cell.project_id),
        user_id=user.user_id,
    )
    return _serialize(cell)


@router.post(
    "/cells/bulk",
    responses={409: {"description": "Bulk write hit a frozen cell — entire batch reverted"}},
)
async def bulk_cells(
    payload: BulkCellsRequest,
    db: DBSession,
    user: AccrualManager,
) -> dict:
    """Apply many cell overrides atomically. A frozen cell aborts the whole batch."""
    try:
        results = await cell_service.bulk_set_cells(
            db,
            updates=[u.model_dump() for u in payload.updates],
            user_id=_parse_user_id(user),
        )
    except cell_service.CellFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    logger.info(
        "accrual_bulk_cells_endpoint",
        count=len(results),
        user_id=user.user_id,
    )
    return {"updated": len(results)}
