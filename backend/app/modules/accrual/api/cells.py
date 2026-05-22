"""HTTP endpoints for accrual cells and per-project operations."""

from datetime import date
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
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
from app.modules.accrual.services import cell_service, rate_resolver

logger = structlog.get_logger()
router = APIRouter()

AccrualViewer = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_VIEW))]
AccrualManager = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_MANAGE))]


def _parse_user_id(token: TokenData) -> UUID | None:
    return UUID(token.user_id) if token.user_id else None


async def _serialize(db: AsyncSession, cell: ProjectAccrualCellDB) -> dict:
    """Return the cell as a JSON-serialisable dict with eur_amount resolved for live cells."""
    project = await db.get(ProjectDB, cell.project_id)
    if cell.is_frozen:
        eur = cell.frozen_eur_amount
    else:
        rate = await rate_resolver.resolve_rate(
            db,
            project=project,
            year=cell.year,
            month=cell.month,
        )
        eur = (cell.amount / rate) if rate and rate != 0 else None

    return {
        "id": str(cell.id),
        "project_id": str(cell.project_id),
        "year": cell.year,
        "month": cell.month,
        "amount": str(cell.amount),
        "is_manual_override": cell.is_manual_override,
        "is_frozen": cell.is_frozen,
        "frozen_at": cell.frozen_at.isoformat() if cell.frozen_at else None,
        "frozen_rate": str(cell.frozen_rate) if cell.frozen_rate is not None else None,
        "frozen_eur_amount": (
            str(cell.frozen_eur_amount) if cell.frozen_eur_amount is not None else None
        ),
        "eur_amount": str(eur) if eur is not None else None,
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

    projects = [
        {
            "id": str(p.id),
            "name": p.name,
            "code": p.code,
            "currency": p.currency,
            "budget": str(p.budget) if p.budget is not None else None,
            "locked_fx_rate": str(p.locked_fx_rate) if p.locked_fx_rate is not None else None,
            "status": p.status,
            "start_date": p.start_date.isoformat() if p.start_date else None,
            "end_date": p.end_date.isoformat() if p.end_date else None,
            "project_manager_id": str(p.project_manager_id) if p.project_manager_id else None,
            "project_manager_name": pm_name,
        }
        for p, pm_name in rows
    ]

    project_ids = [UUID(p["id"]) for p in projects]
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
        cells_serialised = [await _serialize(db, c) for c in cells]

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
    return [await _serialize(db, c) for c in result.scalars().all()]


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
    return await _serialize(db, cell)


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
    return await _serialize(db, cell)


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
