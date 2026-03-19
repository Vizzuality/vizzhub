"""Budget line CRUD endpoints (bulk replace)."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select

from app.core.api.deps import CurrentUser, DBSession
from app.core.models.functional_area import FunctionalAreaDB
from app.modules.tracker.models.budget_line import BudgetLineDB
from app.modules.tracker.schemas.budget_line import (
    BudgetLineBulkRequest,
    BudgetLineResponse,
)

from fastapi import APIRouter

router = APIRouter()


async def _list_budget_lines(
    db: DBSession, project_id: UUID,
) -> list[BudgetLineResponse]:
    """Fetch budget lines with functional area names joined."""
    stmt = (
        select(BudgetLineDB, FunctionalAreaDB.name)
        .outerjoin(
            FunctionalAreaDB,
            BudgetLineDB.functional_area_id == FunctionalAreaDB.id,
        )
        .where(BudgetLineDB.project_id == project_id)
        .order_by(FunctionalAreaDB.name.asc().nulls_last(), BudgetLineDB.created_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        BudgetLineResponse(
            id=line.id,
            project_id=line.project_id,
            functional_area_id=line.functional_area_id,
            functional_area_name=fa_name,
            days=line.days,
            percentage=float(line.percentage * 100) if line.percentage is not None else None,
            details=line.details,
        )
        for line, fa_name in rows
    ]


@router.get("/{project_id}/budget-lines")
async def list_budget_lines(
    project_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> list[BudgetLineResponse]:
    return await _list_budget_lines(db, project_id)


@router.put("/{project_id}/budget-lines")
async def bulk_replace_budget_lines(
    project_id: UUID,
    body: BudgetLineBulkRequest,
    db: DBSession,
    user: CurrentUser,
) -> list[BudgetLineResponse]:
    await db.execute(
        delete(BudgetLineDB).where(BudgetLineDB.project_id == project_id)
    )

    total_days = sum(line.days for line in body.lines)

    for line in body.lines:
        percentage = (
            Decimal(str(line.days)) / Decimal(str(total_days))
            if total_days > 0
            else None
        )
        db.add(BudgetLineDB(
            project_id=project_id,
            functional_area_id=line.functional_area_id,
            days=line.days,
            percentage=percentage,
            details=line.details,
        ))

    await db.commit()
    return await _list_budget_lines(db, project_id)
