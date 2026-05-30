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
from app.core.services.exchange_rate_service import get_latest_rate
from app.modules.accrual.models.accrual_period import AccrualPeriodDB
from app.modules.accrual.schemas.accrual_period import (
    AccrualPeriod,
    AccrualPeriodCreate,
    AccrualPeriodUpdate,
)
from app.modules.accrual.services import period_service

logger = structlog.get_logger()
router = APIRouter()

PeriodAdmin = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_PERIOD_MANAGE))]


async def _build_response(db, period: AccrualPeriodDB) -> AccrualPeriod:
    """Enrich a period with the ECB USD/EUR rate effective at its start_date."""
    rate_pair = await get_latest_rate(db, "USD", as_of=period.start_date)
    response = AccrualPeriod.model_validate(period)
    if rate_pair is not None:
        response.usd_rate = rate_pair[0]
    return response


@router.get("", response_model=list[AccrualPeriod])
async def list_periods(db: DBSession, _: PeriodAdmin) -> list[AccrualPeriod]:
    result = await db.execute(select(AccrualPeriodDB).order_by(AccrualPeriodDB.start_date.desc()))
    periods = list(result.scalars().all())
    return [await _build_response(db, p) for p in periods]


@router.get("/current", response_model=AccrualPeriod | None)
async def get_current(db: DBSession, _: PeriodAdmin) -> AccrualPeriod | None:
    period = await period_service.get_current_period(db)
    return await _build_response(db, period) if period else None


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
) -> AccrualPeriod:
    try:
        period = await period_service.create_period(
            db,
            start_date=payload.start_date,
            created_by=UUID(user.user_id),
            fx_rates=payload.fx_rates,
        )
    except period_service.PeriodConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await _build_response(db, period)


@router.patch(
    "/{period_id}",
    response_model=AccrualPeriod,
    responses={404: {"description": "Period not found"}},
)
async def update_period(
    period_id: UUID,
    payload: AccrualPeriodUpdate,
    db: DBSession,
    _: PeriodAdmin,
) -> AccrualPeriod:
    """Replace a period's CEO fx_rates. Does not touch the period's frozen cells."""
    try:
        period = await period_service.update_fx_rates(db, period_id, payload.fx_rates)
    except period_service.PeriodError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await _build_response(db, period)
