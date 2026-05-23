"""AccrualPeriod lifecycle: create, close, lookup."""

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
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
    fx_rates_input: dict[str, str],
    created_by: UUID | None,
) -> AccrualPeriodDB:
    """Create a new accrual period.

    If a previous open period exists, close it first (Task 1.5 wires this in).
    The new period's ``fx_rates`` merges the input with a copy of the previous
    period's rates — currencies not present in the input are copied unchanged.
    """
    open_period = await get_current_period(db)
    if open_period is not None:
        await close_period(db, open_period.id, freeze_cutoff=start_date)

    merged_rates: dict[str, str] = dict(open_period.fx_rates) if open_period else {}
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
    Resolves each cell's EUR amount via rate_resolver and persists frozen_*.
    """
    from app.core.models.project import ProjectDB
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
    from app.modules.accrual.services import rate_resolver

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
            select(ProjectAccrualCellDB, ProjectDB)
            .join(ProjectDB, ProjectDB.id == ProjectAccrualCellDB.project_id)
            .where(
                ProjectAccrualCellDB.is_frozen.is_(False),
                or_(
                    ProjectAccrualCellDB.year < cutoff_y,
                    and_(
                        ProjectAccrualCellDB.year == cutoff_y,
                        ProjectAccrualCellDB.month < cutoff_m,
                    ),
                ),
            )
        )
        now = datetime.now(UTC)
        for cell, project in cells_result.all():
            rate = await rate_resolver.resolve_rate(
                db,
                project=project,
                year=cell.year,
                month=cell.month,
            )
            if rate is None or rate == 0:
                logger.warning(
                    "accrual_cell_freeze_skipped_unresolvable",
                    project_id=str(cell.project_id),
                    year=cell.year,
                    month=cell.month,
                )
                continue
            cell.is_frozen = True
            cell.frozen_at = now
            cell.frozen_rate = rate
            cell.frozen_eur_amount = (cell.amount / rate).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
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


async def validate_currencies_covered(
    db: AsyncSession,
    period: AccrualPeriodDB,
) -> list[str]:
    """Return currencies used by non-archived Projects that lack a rate in the period.

    EUR is always passthrough — never flagged. Projects in status='finished'
    are included (their accruals still need a rate for unfrozen cells, if any).
    """
    from app.core.models.project import ProjectDB

    result = await db.execute(
        select(ProjectDB.currency)
        .distinct()
        .where(ProjectDB.status.in_(["proposal", "live", "finished"]))
    )
    used = {row[0] for row in result.all() if row[0] and row[0].upper() != "EUR"}
    covered = set(period.fx_rates.keys())
    return sorted(used - covered)
