"""HTTP API for AccrualPeriod CRUD (admin-gated)."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission
from app.modules.accrual.models.accrual_period import AccrualPeriodDB
from app.modules.accrual.schemas.accrual_period import (
    AccrualPeriod,
    AccrualPeriodCreate,
)
from app.modules.accrual.services import period_service

logger = structlog.get_logger()
router = APIRouter()

PeriodAdmin = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_PERIOD_MANAGE))]


@router.get("", response_model=list[AccrualPeriod])
async def list_periods(db: DBSession, _: PeriodAdmin) -> list[AccrualPeriodDB]:
    result = await db.execute(select(AccrualPeriodDB).order_by(AccrualPeriodDB.start_date.desc()))
    return list(result.scalars().all())


@router.get("/current", response_model=AccrualPeriod | None)
async def get_current(db: DBSession, _: PeriodAdmin) -> AccrualPeriodDB | None:
    return await period_service.get_current_period(db)


@router.post(
    "",
    response_model=AccrualPeriod,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Duplicate start_date or constraint violation"}},
)
async def create_period(
    payload: AccrualPeriodCreate,
    db: DBSession,
    user: PeriodAdmin,
) -> AccrualPeriodDB:
    try:
        return await period_service.create_period(
            db,
            start_date=payload.start_date,
            created_by=UUID(user.user_id),
        )
    except period_service.PeriodConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
