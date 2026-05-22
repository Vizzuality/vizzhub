"""HTTP API for AccrualPeriod CRUD (admin-gated)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission
from app.core.services.exchange_rate_service import (
    get_available_currencies,
    get_latest_rate,
)
from app.modules.accrual.models.accrual_period import AccrualPeriodDB
from app.modules.accrual.schemas.accrual_period import (
    AccrualPeriod,
    AccrualPeriodCreate,
    AccrualPeriodUpdate,
)
from app.modules.accrual.services import period_service

router = APIRouter()

PeriodAdmin = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_PERIOD_MANAGE))]


@router.get("", response_model=list[AccrualPeriod])
async def list_periods(db: DBSession, _: PeriodAdmin) -> list[AccrualPeriodDB]:
    result = await db.execute(select(AccrualPeriodDB).order_by(AccrualPeriodDB.start_date.desc()))
    return list(result.scalars().all())


@router.get("/current", response_model=AccrualPeriod | None)
async def get_current(db: DBSession, _: PeriodAdmin) -> AccrualPeriodDB | None:
    return await period_service.get_current_period(db)


@router.get("/seed-rates")
async def seed_rates(db: DBSession, _: PeriodAdmin) -> dict[str, str]:
    """Latest ECB rate per available currency, as Decimal strings.

    Used by the PeriodEditor dialog to pre-populate the fx_rates form so the
    admin only has to change the values they want to lock — not type every
    currency from scratch. EUR is skipped (always 1.0 passthrough).
    """
    codes = await get_available_currencies(db)
    result: dict[str, str] = {}
    for code in codes:
        if code == "EUR":
            continue
        rate = await get_latest_rate(db, code)
        if rate is not None:
            result[code] = str(rate[0])
    return result


@router.post("", response_model=AccrualPeriod, status_code=status.HTTP_201_CREATED)
async def create_period(
    payload: AccrualPeriodCreate,
    db: DBSession,
    user: PeriodAdmin,
) -> AccrualPeriodDB:
    try:
        return await period_service.create_period(
            db,
            start_date=payload.start_date,
            fx_rates_input=payload.fx_rates,
            created_by=UUID(user.user_id),
        )
    except period_service.PeriodConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{period_id}", response_model=AccrualPeriod)
async def patch_period(
    period_id: UUID,
    payload: AccrualPeriodUpdate,
    db: DBSession,
    _: PeriodAdmin,
) -> AccrualPeriodDB:
    result = await db.execute(select(AccrualPeriodDB).where(AccrualPeriodDB.id == period_id))
    period = result.scalar_one_or_none()
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    if period.status != "open":
        raise HTTPException(status_code=409, detail="Period is closed")
    if payload.fx_rates is not None:
        period.fx_rates = payload.fx_rates
    await db.flush()
    return period
