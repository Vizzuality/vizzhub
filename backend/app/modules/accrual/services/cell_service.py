"""Cell-level operations for the accrual module."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
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


async def _get_cell(
    db: AsyncSession, *, project_id: UUID, year: int, month: int
) -> ProjectAccrualCellDB | None:
    """Fetch a single cell by (project_id, year, month), or None."""
    result = await db.execute(
        select(ProjectAccrualCellDB).where(
            ProjectAccrualCellDB.project_id == project_id,
            ProjectAccrualCellDB.year == year,
            ProjectAccrualCellDB.month == month,
        )
    )
    return result.scalar_one_or_none()


def _eligible_target_months(
    by_ym: dict[tuple[int, int], ProjectAccrualCellDB],
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
    by_ym: dict[tuple[int, int], ProjectAccrualCellDB],
    months_set: set[tuple[int, int]],
    *,
    force: bool,
) -> Decimal:
    """Sum of cell amounts excluded from redistribution (frozen always, overrides unless force).

    Frozen cells are summed across the whole project (out-of-range frozen amounts still
    reduce the budget pool); overrides only count when in the visible range.
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


def _apply_redistribution(
    db: AsyncSession,
    project_id: UUID,
    target_months: list[tuple[int, int]],
    by_ym: dict[tuple[int, int], ProjectAccrualCellDB],
    per_month: Decimal,
    *,
    force: bool,
) -> int:
    """Upsert per_month into every target cell, clearing override flag when force."""
    for ym in target_months:
        existing_cell = by_ym.get(ym)
        if existing_cell is None:
            db.add(
                ProjectAccrualCellDB(
                    project_id=project_id,
                    year=ym[0],
                    month=ym[1],
                    amount=per_month,
                    is_manual_override=False,
                    is_frozen=False,
                )
            )
        else:
            existing_cell.amount = per_month
            if force:
                existing_cell.is_manual_override = False
    return len(target_months)


async def redistribute_for_project(
    db: AsyncSession, *, project_id: UUID, force: bool = False
) -> int:
    """Redistribute the project budget across its mutable months.

    Frozen cells are never touched. Manual overrides survive unless ``force``
    is set. Returns the count of cells written/updated.
    """
    project = (await db.execute(select(ProjectDB).where(ProjectDB.id == project_id))).scalar_one()
    if project.original_budget is None or project.start_date is None or project.end_date is None:
        return 0

    period = await period_service.get_current_period(db)
    range_start = max(project.start_date, period.start_date) if period else project.start_date
    if range_start > project.end_date:
        return 0

    months = _months_between(range_start, project.end_date)
    existing = (
        (
            await db.execute(
                select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == project_id)
            )
        )
        .scalars()
        .all()
    )
    by_ym: dict[tuple[int, int], ProjectAccrualCellDB] = {(c.year, c.month): c for c in existing}

    target_months = _eligible_target_months(by_ym, months, force=force)
    if not target_months:
        return 0

    reserved = _reserved_amount(by_ym, set(months), force=force)
    remaining_budget = max(Decimal(project.original_budget) - reserved, Decimal("0"))
    per_month = _quantize(remaining_budget / Decimal(len(target_months)))

    written = _apply_redistribution(db, project_id, target_months, by_ym, per_month, force=force)
    await db.flush()
    logger.info(
        "accrual_redistribute_ran",
        project_id=str(project_id),
        cells_written=written,
        force=force,
    )
    return written


async def set_cell_amount(
    db: AsyncSession,
    *,
    project_id: UUID,
    year: int,
    month: int,
    amount: Decimal,
    user_id: UUID | None = None,
) -> ProjectAccrualCellDB:
    cell = await _get_cell(db, project_id=project_id, year=year, month=month)
    uid = str(user_id) if user_id else None

    if cell is None:
        cell = ProjectAccrualCellDB(
            project_id=project_id,
            year=year,
            month=month,
            amount=_quantize(amount),
            is_manual_override=True,
        )
        db.add(cell)
        await db.flush()
        logger.info(
            "accrual_cell_overridden",
            project_id=str(project_id),
            year=year,
            month=month,
            prev_amount="0",
            new_amount=str(cell.amount),
            user_id=uid,
        )
        return cell

    if cell.is_frozen:
        logger.warning(
            "accrual_cell_frozen_blocked",
            project_id=str(project_id),
            year=year,
            month=month,
            user_id=uid,
        )
        raise CellFrozenError(f"Cell {year}-{month:02d} is frozen")

    prev = cell.amount
    cell.amount = _quantize(amount)
    cell.is_manual_override = True
    await db.flush()
    logger.info(
        "accrual_cell_overridden",
        project_id=str(project_id),
        year=year,
        month=month,
        prev_amount=str(prev),
        new_amount=str(cell.amount),
        user_id=uid,
    )
    return cell


async def clear_override(
    db: AsyncSession, *, project_id: UUID, year: int, month: int
) -> ProjectAccrualCellDB:
    cell = await _get_cell(db, project_id=project_id, year=year, month=month)
    if cell is None:
        raise CellError(f"Cell {year}-{month:02d} not found for project {project_id}")
    if cell.is_frozen:
        raise CellFrozenError(f"Cell {year}-{month:02d} is frozen")
    cell.is_manual_override = False
    await db.flush()
    await redistribute_for_project(db, project_id=project_id)
    await db.refresh(cell)
    return cell


async def bulk_set_cells(
    db: AsyncSession,
    *,
    updates: list[dict],
    user_id: UUID | None = None,
) -> list[ProjectAccrualCellDB]:
    """Apply many overrides atomically via a SAVEPOINT.

    On any exception during the batch, the SAVEPOINT is rolled back so partial
    writes never persist. The outer transaction is not touched — that's the
    caller's responsibility.
    """
    results: list[ProjectAccrualCellDB] = []
    savepoint = await db.begin_nested()
    try:
        for update in updates:
            cell = await set_cell_amount(
                db,
                project_id=update["project_id"],
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
