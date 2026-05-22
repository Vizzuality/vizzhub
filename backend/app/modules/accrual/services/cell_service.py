"""Cell-level operations for the accrual module.

Today this module is responsible for redistribute_for_project; T2.7+ add
set_cell_amount, clear_override, and bulk_set_cells.
"""

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


async def redistribute_for_project(
    db: AsyncSession, *, project_id: UUID, force: bool = False
) -> int:
    """Redistribute the project budget across its mutable months.

    Frozen cells are never touched. Manual overrides survive unless ``force``
    is set. Returns the count of cells written/updated.
    """
    project = (await db.execute(select(ProjectDB).where(ProjectDB.id == project_id))).scalar_one()

    if project.budget is None or project.start_date is None or project.end_date is None:
        return 0

    period = await period_service.get_current_period(db)
    range_start = max(project.start_date, period.start_date) if period else project.start_date
    if range_start > project.end_date:
        return 0

    months = _months_between(range_start, project.end_date)
    months_set = set(months)

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

    frozen_total = sum(
        (c.amount for c in by_ym.values() if c.is_frozen),
        Decimal("0"),
    )
    override_total = sum(
        (
            c.amount
            for c in by_ym.values()
            if not force
            and c.is_manual_override
            and not c.is_frozen
            and (c.year, c.month) in months_set
        ),
        Decimal("0"),
    )

    target_months = [
        ym
        for ym in months
        if not (by_ym.get(ym) and by_ym[ym].is_frozen)
        and not (not force and by_ym.get(ym) and by_ym[ym].is_manual_override)
    ]
    if not target_months:
        return 0

    remaining_budget = max(Decimal(project.budget) - frozen_total - override_total, Decimal("0"))
    per_month = _quantize(remaining_budget / Decimal(len(target_months)))

    written = 0
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
        written += 1

    await db.flush()
    logger.info(
        "accrual_redistribute_ran",
        project_id=str(project_id),
        cells_written=written,
        force=force,
    )
    return written
