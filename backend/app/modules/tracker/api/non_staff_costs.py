"""Non-staff cost CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.models.non_staff_cost import NonStaffCostDB
from app.modules.tracker.schemas.non_staff_cost import (
    NonStaffCostCreate,
    NonStaffCostResponse,
    NonStaffCostUpdate,
)
from app.modules.tracker.api.helpers import get_or_404

router = APIRouter()


@router.get("", response_model=list[NonStaffCostResponse])
async def list_non_staff_costs(
    project_id: UUID = Query(...),
    reporting_period_id: UUID | None = Query(default=None),
    db: DBSession = None,
    user: CurrentUser = None,
) -> list[NonStaffCostResponse]:
    stmt = select(NonStaffCostDB).where(
        NonStaffCostDB.project_id == project_id
    )
    if reporting_period_id:
        stmt = stmt.where(
            NonStaffCostDB.reporting_period_id == reporting_period_id
        )
    stmt = stmt.order_by(NonStaffCostDB.created_at)
    result = await db.execute(stmt)
    return [NonStaffCostResponse.model_validate(c) for c in result.scalars().all()]


@router.post("", response_model=NonStaffCostResponse, status_code=201)
async def create_non_staff_cost(
    data: NonStaffCostCreate,
    db: DBSession,
    user: CurrentUser,
) -> NonStaffCostResponse:
    cost = NonStaffCostDB(
        project_id=data.project_id,
        reporting_period_id=data.reporting_period_id,
        cost=data.cost,
        cost_type=data.cost_type,
        details=data.details,
    )
    db.add(cost)
    await db.commit()
    await db.refresh(cost)
    return NonStaffCostResponse.model_validate(cost)


@router.get("/{cost_id}", response_model=NonStaffCostResponse)
async def get_non_staff_cost(
    cost_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> NonStaffCostResponse:
    cost = await get_or_404(NonStaffCostDB, cost_id, db, "Non-staff cost")
    return NonStaffCostResponse.model_validate(cost)


@router.put("/{cost_id}", response_model=NonStaffCostResponse)
async def update_non_staff_cost(
    cost_id: UUID,
    data: NonStaffCostUpdate,
    db: DBSession,
    user: CurrentUser,
) -> NonStaffCostResponse:
    cost = await get_or_404(NonStaffCostDB, cost_id, db, "Non-staff cost")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cost, field, value)

    await db.commit()
    await db.refresh(cost)
    return NonStaffCostResponse.model_validate(cost)


@router.delete("/{cost_id}", status_code=204)
async def delete_non_staff_cost(
    cost_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> None:
    cost = await get_or_404(NonStaffCostDB, cost_id, db, "Non-staff cost")
    await db.delete(cost)
    await db.commit()
