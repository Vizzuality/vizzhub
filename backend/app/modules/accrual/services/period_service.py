"""AccrualPeriod lifecycle: create, close, lookup."""

from datetime import UTC, date, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accrual.models.accrual_period import AccrualPeriodDB

logger = structlog.get_logger()


class PeriodError(Exception):
    """Base exception for period lifecycle errors."""


class PeriodConflictError(PeriodError):
    """Duplicate start_date or other constraint violation."""


async def create_period(
    db: AsyncSession,
    *,
    start_date: date,
    fx_rates_input: dict[str, str],
    created_by: UUID | None,
) -> AccrualPeriodDB:
    """Create a new accrual period.

    If a previous open period exists, close it first (Task 1.5 wires this in).
    The new period's ``fx_rates`` merges the input with a copy of the previous
    period's rates — currencies not present in the input are copied unchanged.
    """
    open_period = await get_current_period(db)

    closed_previous_id: UUID | None = None
    if open_period is not None:
        await close_period(db, open_period.id)
        closed_previous_id = open_period.id

    merged_rates: dict[str, str] = {}
    if open_period is not None:
        merged_rates.update(dict(open_period.fx_rates))
    merged_rates.update(fx_rates_input)

    new_period = AccrualPeriodDB(
        start_date=start_date,
        status="open",
        fx_rates=merged_rates,
        created_by=created_by,
    )
    db.add(new_period)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise PeriodConflictError(str(exc.orig)) from exc

    logger.info(
        "accrual_period_created",
        period_id=str(new_period.id),
        start_date=str(start_date),
        fx_rates_keys=sorted(merged_rates.keys()),
        closed_previous_id=str(closed_previous_id) if closed_previous_id else None,
    )
    return new_period


async def get_current_period(db: AsyncSession) -> AccrualPeriodDB | None:
    """Return the single open period, or None if none exists."""
    result = await db.execute(select(AccrualPeriodDB).where(AccrualPeriodDB.status == "open"))
    return result.scalar_one_or_none()


async def close_period(db: AsyncSession, period_id: UUID) -> int:
    """Close an open period.

    Marks status='closed' and stamps closed_at. Cell-freezing logic is
    layered on in Slice 2 (Task 2.9). Returns the number of cells frozen
    (currently 0 — no cells table yet).
    """
    result = await db.execute(select(AccrualPeriodDB).where(AccrualPeriodDB.id == period_id))
    period = result.scalar_one()
    if period.status != "open":
        raise PeriodError(f"Period {period_id} is not open (status={period.status})")
    period.status = "closed"
    period.closed_at = datetime.now(UTC)
    await db.flush()
    logger.info(
        "accrual_period_closed",
        period_id=str(period_id),
        frozen_cells_count=0,
    )
    return 0
