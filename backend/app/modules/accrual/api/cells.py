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
from app.modules.accrual.models.accrual_line import AccrualLineDB
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB
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


def _diff_eur_pct(
    budget: Decimal | None, sum_cells: Decimal
) -> tuple[Decimal | None, Decimal | None]:
    if budget is None or budget == 0:
        return None, None
    diff_eur = (sum_cells - budget).quantize(Decimal("0.01"))
    diff_pct = (abs(diff_eur) / budget * Decimal("100")).quantize(Decimal("0.01"))
    return diff_eur, diff_pct


def _serialize(cell: ProjectAccrualCellDB) -> dict:
    """Cells are EUR-only, so ``amount`` IS the EUR figure. Frozen cells expose
    ``frozen_eur_amount`` as the immutable snapshot captured at period close."""
    return {
        "id": str(cell.id),
        "line_id": str(cell.line_id) if cell.line_id else None,
        "project_id": str(cell.project_id) if cell.project_id else None,
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


def _line_health(value_eur: Decimal | None, sum_cells: Decimal) -> dict:
    """A line's health = how close its scheduled cells are to its declared value.

    For Excel lines the cells are the CEO's verbatim monthly forecast and
    ``value_eur`` is the contract/total — a gap is a real "not fully scheduled"
    signal, not an error. Compared in the SAME currency (both EUR, same source),
    so there is no FX contamination.
    """
    diff_eur, diff_pct = _diff_eur_pct(value_eur, sum_cells)
    if value_eur is None or value_eur == 0:
        status_str = "no_data"
    elif diff_pct is not None and diff_pct > _HEALTH_CRITICAL_THRESHOLD:
        status_str = "critical"
    elif diff_pct is not None and diff_pct > _HEALTH_WARNING_THRESHOLD:
        status_str = "warning"
    else:
        status_str = "ok"
    return {
        "status": status_str,
        "diff_eur": str(diff_eur) if diff_eur is not None else None,
        "diff_pct": float(diff_pct) if diff_pct is not None else None,
    }


def _serialize_grid_line(
    line: AccrualLineDB,
    projects: list[tuple[ProjectDB, str | None]],
    *,
    sum_cells: Decimal,
) -> dict:
    return {
        "id": str(line.id),
        "name": line.name,
        "source": line.source,
        "excel_code": line.excel_code,
        "value_eur": str(line.value_eur),
        "value_orig": str(line.value_orig) if line.value_orig is not None else None,
        "currency": line.currency,
        "window_start": line.window_start.isoformat() if line.window_start else None,
        "window_end": line.window_end.isoformat() if line.window_end else None,
        "projects": [
            {
                "id": str(p.id),
                "code": p.code,
                "name": p.name,
                "status": p.status,
                "project_manager_id": str(p.project_manager_id) if p.project_manager_id else None,
                "project_manager_name": pm_name,
            }
            for p, pm_name in projects
        ],
        "health": _line_health(line.value_eur, sum_cells),
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
    source: str | None = None,
) -> dict:
    """Accrual grid: rows are **lines** (the revenue-recognition unit), not projects.

    Each line carries its linked projects as tags (0..N), its editable window, its
    value, and a health badge (Σcells vs value_eur, same-currency so no FX noise).
    Cells are keyed by ``line_id``.

    Filtering:
    - ``year_from`` / ``year_to``: keep lines whose window overlaps the span.
    - ``status`` / ``project_manager_id``: match on any LINKED project; unlinked
      lines are excluded when either is set.
    - ``currency``: match the line's own currency (Excel lines); lines without a
      currency are excluded when it is set.
    - ``source``: ``excel`` | ``team_budget`` | ``manual``.

    ``bounds`` (min/max window year over the status+pm+source-filtered set) and
    ``available_currencies`` drive the toolbar.
    """
    if year_to < year_from:
        raise HTTPException(status_code=400, detail="year_to must be >= year_from")

    pm = aliased(UserDB)
    lines = list((await db.execute(select(AccrualLineDB))).scalars().all())

    # line_id -> [(project, pm_name)]
    lp_rows = (
        await db.execute(
            select(AccrualLineProjectDB.line_id, ProjectDB, user_display_name_expr(pm).label("pm"))
            .join(ProjectDB, ProjectDB.id == AccrualLineProjectDB.project_id)
            .outerjoin(pm, ProjectDB.project_manager_id == pm.id)
        )
    ).all()
    projects_by_line: dict[UUID, list[tuple[ProjectDB, str | None]]] = {}
    for line_id, project, pm_name in lp_rows:
        projects_by_line.setdefault(line_id, []).append((project, pm_name))

    def _passes_filters(line: AccrualLineDB) -> bool:
        linked = projects_by_line.get(line.id, [])
        if status is not None and not any(p.status == status for p, _ in linked):
            return False
        if project_manager_id is not None and not any(
            p.project_manager_id == project_manager_id for p, _ in linked
        ):
            return False
        if source is not None and line.source != source:
            return False
        return True

    filtered = [line for line in lines if _passes_filters(line)]

    bounds_min = min(
        (line.window_start.year for line in filtered if line.window_start is not None),
        default=None,
    )
    bounds_max = max(
        (line.window_end.year for line in filtered if line.window_end is not None),
        default=None,
    )
    bounds = (
        {"min_year": bounds_min, "max_year": bounds_max}
        if bounds_min is not None and bounds_max is not None
        else None
    )
    available_currencies = sorted(
        {currency_to_code(line.currency) for line in filtered if line.currency}
    )

    if currency is not None:
        target_code = currency_to_code(currency)
        filtered = [
            line
            for line in filtered
            if line.currency and currency_to_code(line.currency) == target_code
        ]

    range_start = date(year_from, 1, 1)
    range_end = date(year_to, 12, 31)
    filtered = [
        line
        for line in filtered
        if line.window_start is not None
        and line.window_end is not None
        and line.window_start <= range_end
        and line.window_end >= range_start
    ]

    line_ids = [line.id for line in filtered]

    # Per-line total across ALL cells so the health badge is year-navigation stable.
    sum_by_line: dict[UUID, Decimal] = {}
    if line_ids:
        agg = await db.execute(
            select(
                ProjectAccrualCellDB.line_id,
                func.coalesce(func.sum(ProjectAccrualCellDB.amount), 0).label("total"),
            )
            .where(ProjectAccrualCellDB.line_id.in_(line_ids))
            .group_by(ProjectAccrualCellDB.line_id)
        )
        for lid, total in agg.all():
            sum_by_line[lid] = Decimal(str(total))

    lines_serialised = [
        _serialize_grid_line(
            line,
            projects_by_line.get(line.id, []),
            sum_cells=sum_by_line.get(line.id, Decimal("0")),
        )
        for line in filtered
    ]

    cells_serialised: list[dict] = []
    if line_ids:
        cells_result = await db.execute(
            select(ProjectAccrualCellDB)
            .where(
                ProjectAccrualCellDB.line_id.in_(line_ids),
                ProjectAccrualCellDB.year >= year_from,
                ProjectAccrualCellDB.year <= year_to,
            )
            .order_by(
                ProjectAccrualCellDB.line_id,
                ProjectAccrualCellDB.year,
                ProjectAccrualCellDB.month,
            )
        )
        cells_serialised = [_serialize(c) for c in cells_result.scalars().all()]

    months = [
        {"year": year, "month": month}
        for year in range(year_from, year_to + 1)
        for month in range(1, 13)
    ]
    return {
        "lines": lines_serialised,
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
