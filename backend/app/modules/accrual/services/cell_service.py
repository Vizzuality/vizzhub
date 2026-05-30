"""Cell-level operations for the accrual module.

Cells hang off a line (``line_id``) — the revenue-recognition unit — never a
project. Everything the grid edits goes through the functions below.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accrual.models.accrual_cell import AccrualCellDB, CellSource
from app.modules.accrual.models.accrual_line import AccrualLineDB
from app.modules.accrual.services import period_service

logger = structlog.get_logger()


class CellError(Exception):
    """Base exception for cell-service domain errors."""


class CellFrozenError(CellError):
    """Attempt to mutate a frozen cell."""


def _months_between(start: date, end: date) -> list[tuple[int, int]]:
    """Inclusive (year, month) tuples from start to end, snapped to first-of-month."""
    out: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        out.append((year, month))
        month += 1
        if month == 13:
            month = 1
            year += 1
    return out


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _eligible_target_months(
    by_ym: dict[tuple[int, int], AccrualCellDB],
    months: list[tuple[int, int]],
    *,
    force: bool,
) -> list[tuple[int, int]]:
    """Months that redistribute may write: not frozen, and not override-when-not-force."""
    result: list[tuple[int, int]] = []
    for ym in months:
        cell = by_ym.get(ym)
        if cell and cell.is_frozen:
            continue
        if cell and cell.is_manual_override and not force:
            continue
        result.append(ym)
    return result


def _reserved_amount(
    by_ym: dict[tuple[int, int], AccrualCellDB],
    months_set: set[tuple[int, int]],
    *,
    force: bool,
) -> Decimal:
    """Sum of cell amounts excluded from redistribution (frozen always, overrides unless force).

    Frozen cells are summed across the whole line (out-of-range frozen amounts still
    reduce the value pool); overrides only count when in the visible range.
    """
    frozen = sum((c.amount for c in by_ym.values() if c.is_frozen), Decimal("0"))
    if force:
        return frozen
    overrides = sum(
        (
            c.amount
            for c in by_ym.values()
            if c.is_manual_override and not c.is_frozen and (c.year, c.month) in months_set
        ),
        Decimal("0"),
    )
    return frozen + overrides


async def _get_cell_by_line(
    db: AsyncSession, *, line_id: UUID, year: int, month: int
) -> AccrualCellDB | None:
    """Fetch a single cell by (line_id, year, month), or None."""
    result = await db.execute(
        select(AccrualCellDB).where(
            AccrualCellDB.line_id == line_id,
            AccrualCellDB.year == year,
            AccrualCellDB.month == month,
        )
    )
    return result.scalar_one_or_none()


def _apply_redistribution_to_line(
    db: AsyncSession,
    line_id: UUID,
    target_months: list[tuple[int, int]],
    by_ym: dict[tuple[int, int], AccrualCellDB],
    per_month: Decimal,
    *,
    force: bool,
    source: CellSource,
) -> int:
    """Upsert ``per_month`` into every target cell of a line.

    New cells get ``source``; existing non-override cells get their source
    updated. Manual-override cells that are being force-overwritten also have
    their source reset.
    """
    for ym in target_months:
        existing_cell = by_ym.get(ym)
        if existing_cell is None:
            db.add(
                AccrualCellDB(
                    line_id=line_id,
                    year=ym[0],
                    month=ym[1],
                    amount=per_month,
                    is_manual_override=False,
                    is_frozen=False,
                    source=source.value,
                )
            )
        else:
            existing_cell.amount = per_month
            if force:
                existing_cell.is_manual_override = False
                existing_cell.source = source.value
            elif not existing_cell.is_manual_override:
                existing_cell.source = source.value
    return len(target_months)


async def redistribute_for_line(
    db: AsyncSession,
    *,
    line_id: UUID,
    force: bool = False,
    full_range: bool = False,
    source: CellSource = CellSource.MANUAL,
) -> int:
    """Spread a line's ``value_eur`` uniformly across its window months.

    Pool is the line's declared value; range is its editable window. Frozen cells
    are never touched and their amounts are reserved out of the pool. Manual
    overrides survive (and are reserved) unless ``force``. ``full_range`` skips the
    open-period clip and writes the whole window. Returns the count written.
    """
    line = (
        await db.execute(select(AccrualLineDB).where(AccrualLineDB.id == line_id))
    ).scalar_one_or_none()
    if line is None or line.window_start is None or line.window_end is None:
        return 0

    if full_range:
        range_start = line.window_start
    else:
        period = await period_service.get_current_period(db)
        range_start = max(line.window_start, period.start_date) if period else line.window_start
    if range_start > line.window_end:
        return 0

    months = _months_between(range_start, line.window_end)
    existing = (
        (await db.execute(select(AccrualCellDB).where(AccrualCellDB.line_id == line_id)))
        .scalars()
        .all()
    )
    by_ym: dict[tuple[int, int], AccrualCellDB] = {(c.year, c.month): c for c in existing}

    target_months = _eligible_target_months(by_ym, months, force=force)
    if not target_months:
        return 0

    reserved = _reserved_amount(by_ym, set(months), force=force)
    remaining = max(Decimal(line.value_eur) - reserved, Decimal("0"))
    per_month = _quantize(remaining / Decimal(len(target_months)))

    written = _apply_redistribution_to_line(
        db, line_id, target_months, by_ym, per_month, force=force, source=source
    )
    await db.flush()
    logger.info(
        "accrual_redistribute_line_ran",
        line_id=str(line_id),
        cells_written=written,
        force=force,
    )
    return written


async def set_cell_amount_by_line(
    db: AsyncSession,
    *,
    line_id: UUID,
    year: int,
    month: int,
    amount: Decimal,
    user_id: UUID | None = None,
    source: CellSource = CellSource.MANUAL,
) -> AccrualCellDB:
    """Upsert a line cell to an explicit amount, marking it a manual override.

    Creating a cell on a previously-empty month is the inline-edit "create cell on
    line" path.
    """
    cell = await _get_cell_by_line(db, line_id=line_id, year=year, month=month)
    uid = str(user_id) if user_id else None

    if cell is None:
        cell = AccrualCellDB(
            line_id=line_id,
            year=year,
            month=month,
            amount=_quantize(amount),
            is_manual_override=True,
            source=source.value,
        )
        db.add(cell)
        await db.flush()
        logger.info(
            "accrual_cell_overridden",
            line_id=str(line_id),
            year=year,
            month=month,
            prev_amount="0",
            new_amount=str(cell.amount),
            source=source.value,
            user_id=uid,
        )
        return cell

    if cell.is_frozen:
        logger.warning(
            "accrual_cell_frozen_blocked",
            line_id=str(line_id),
            year=year,
            month=month,
            user_id=uid,
        )
        raise CellFrozenError(f"Cell {year}-{month:02d} is frozen")

    prev = cell.amount
    cell.amount = _quantize(amount)
    cell.is_manual_override = True
    cell.source = source.value
    await db.flush()
    logger.info(
        "accrual_cell_overridden",
        line_id=str(line_id),
        year=year,
        month=month,
        prev_amount=str(prev),
        new_amount=str(cell.amount),
        source=source.value,
        user_id=uid,
    )
    return cell


async def clear_override_by_line(
    db: AsyncSession, *, line_id: UUID, year: int, month: int
) -> AccrualCellDB:
    """Drop a line cell's override flag and redistribute the line's value around it."""
    cell = await _get_cell_by_line(db, line_id=line_id, year=year, month=month)
    if cell is None:
        raise CellError(f"Cell {year}-{month:02d} not found for line {line_id}")
    if cell.is_frozen:
        raise CellFrozenError(f"Cell {year}-{month:02d} is frozen")
    cell.is_manual_override = False
    await db.flush()
    await redistribute_for_line(db, line_id=line_id)
    await db.refresh(cell)
    return cell


async def bulk_set_cells_by_line(
    db: AsyncSession,
    *,
    updates: list[dict],
    user_id: UUID | None = None,
) -> list[AccrualCellDB]:
    """Apply many line-cell overrides atomically via a SAVEPOINT.

    On any exception during the batch, the SAVEPOINT is rolled back so partial
    writes never persist. The outer transaction is not touched — that's the
    caller's responsibility.
    """
    results: list[AccrualCellDB] = []
    savepoint = await db.begin_nested()
    try:
        for update in updates:
            cell = await set_cell_amount_by_line(
                db,
                line_id=update["line_id"],
                year=update["year"],
                month=update["month"],
                amount=update["amount"],
                user_id=user_id,
            )
            results.append(cell)
        await savepoint.commit()
    except Exception:
        await savepoint.rollback()
        raise
    return results
