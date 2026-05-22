"""HTTP endpoints for accrual cells and per-project operations."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.models.project import ProjectDB
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission
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
            user_id=UUID(user.user_id) if user.user_id else None,
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
    updates = [
        {
            "project_id": update.project_id,
            "year": update.year,
            "month": update.month,
            "amount": update.amount,
        }
        for update in payload.updates
    ]
    try:
        results = await cell_service.bulk_set_cells(
            db,
            updates=updates,
            user_id=UUID(user.user_id) if user.user_id else None,
        )
    except cell_service.CellFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    logger.info(
        "accrual_bulk_cells_endpoint",
        count=len(results),
        user_id=user.user_id,
    )
    return {"updated": len(results)}
