"""AccrualPeriod lifecycle: create, close, lookup.

Cells are EUR-only, so periods don't carry FX rates. A period is just an
open/closed lifecycle marker that freezes cells once it closes.
"""

from datetime import UTC, date, datetime
from uuid import UUID

import structlog
from sqlalchemy import and_, or_, select
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
    created_by: UUID | None,
) -> AccrualPeriodDB:
    """Create a new accrual period.

    If a previous open period exists, close it first — the existing period's
    cells with year/month before ``start_date`` get frozen.
    """
    open_period = await get_current_period(db)
    if open_period is not None:
        await close_period(db, open_period.id, freeze_cutoff=start_date)

    new_period = AccrualPeriodDB(
        start_date=start_date,
        status="open",
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
        closed_previous_id=str(open_period.id) if open_period else None,
    )
    return new_period


async def get_current_period(db: AsyncSession) -> AccrualPeriodDB | None:
    """Return the single open period, or None if none exists."""
    result = await db.execute(select(AccrualPeriodDB).where(AccrualPeriodDB.status == "open"))
    return result.scalar_one_or_none()


async def freeze_period_cells(
    db: AsyncSession,
    *,
    period_id: UUID,
    cutoff: date | None = None,
) -> int:
    """Freeze unfrozen cells in the period's range. Idempotent.

    Cutoff defaults to the start_date of the NEXT period (chronologically after
    the one identified by period_id). When the given period is the latest/open
    one, cutoff is None → nothing freezes. Already-frozen cells are skipped.
    Since cells are EUR already, freezing just stamps frozen_at and copies
    amount → frozen_eur_amount.
    """
    from app.modules.accrual.models.accrual_cell import AccrualCellDB

    period = await db.get(AccrualPeriodDB, period_id)
    if period is None:
        raise PeriodError(f"Period {period_id} not found")

    effective_cutoff = cutoff
    if effective_cutoff is None:
        next_result = await db.execute(
            select(AccrualPeriodDB)
            .where(AccrualPeriodDB.start_date > period.start_date)
            .order_by(AccrualPeriodDB.start_date.asc())
            .limit(1)
        )
        next_period = next_result.scalar_one_or_none()
        if next_period is not None:
            effective_cutoff = next_period.start_date

    frozen_count = 0
    if effective_cutoff is not None:
        cutoff_y, cutoff_m = effective_cutoff.year, effective_cutoff.month
        cells_result = await db.execute(
            select(AccrualCellDB).where(
                AccrualCellDB.is_frozen.is_(False),
                or_(
                    AccrualCellDB.year < cutoff_y,
                    and_(
                        AccrualCellDB.year == cutoff_y,
                        AccrualCellDB.month < cutoff_m,
                    ),
                ),
            )
        )
        now = datetime.now(UTC)
        for cell in cells_result.scalars().all():
            cell.is_frozen = True
            cell.frozen_at = now
            cell.frozen_eur_amount = cell.amount
            frozen_count += 1

    if frozen_count:
        await db.flush()
    logger.info(
        "accrual_period_cells_frozen",
        period_id=str(period_id),
        frozen_cells_count=frozen_count,
        freeze_cutoff=effective_cutoff.isoformat() if effective_cutoff else None,
    )
    return frozen_count


async def close_period(
    db: AsyncSession,
    period_id: UUID,
    *,
    freeze_cutoff: date | None = None,
) -> int:
    """Flip status to closed, stamp closed_at, then freeze cells before cutoff.

    Called from two places:
    - ``create_period`` (period rotation): passes the new period's start_date
      as ``freeze_cutoff``.
    - Standalone admin "close period" (no successor yet): omits the cutoff;
      freeze_period_cells then looks up the next period if one exists, otherwise
      freezes nothing.

    Returns the number of cells frozen.
    """
    period = await db.get(AccrualPeriodDB, period_id)
    if period is None:
        raise PeriodError(f"Period {period_id} not found")
    if period.status != "open":
        raise PeriodError(f"Period {period_id} is not open (status={period.status})")

    period.status = "closed"
    period.closed_at = datetime.now(UTC)
    await db.flush()

    frozen_count = await freeze_period_cells(db, period_id=period_id, cutoff=freeze_cutoff)
    logger.info(
        "accrual_period_closed",
        period_id=str(period_id),
        frozen_cells_count=frozen_count,
        freeze_cutoff=freeze_cutoff.isoformat() if freeze_cutoff else None,
    )
    return frozen_count


async def get_period_for_month(
    db: AsyncSession,
    *,
    year: int,
    month: int,
) -> AccrualPeriodDB | None:
    """Return the period covering (year, month).

    A period covers ``[start_date, next_period.start_date)``. Looks up the
    latest period whose start_date <= the first day of the given month.
    Returns None if no period starts on or before that month.
    """
    first_of_month = date(year, month, 1)
    result = await db.execute(
        select(AccrualPeriodDB)
        .where(AccrualPeriodDB.start_date <= first_of_month)
        .order_by(AccrualPeriodDB.start_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
