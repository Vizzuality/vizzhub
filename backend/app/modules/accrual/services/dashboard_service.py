"""Read-only aggregation for the accrual dashboard. Intra-module reads only.

Recognition frontier: periods rotate yearly and a period closes when the next one
opens, so "recognized" is everything before the open period's start (those cells are
frozen) PLUS any month that has already elapsed within the still-open period (actuals
not yet frozen). Everything from the current month onward is forecast. The single
cutoff `max(open_period_start, current_month)` captures both halves.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accrual.models.accrual_cell import AccrualCellDB
from app.modules.accrual.models.accrual_line import AccrualLineDB
from app.modules.accrual.models.accrual_period import AccrualPeriodDB
from app.modules.accrual.schemas.accrual_dashboard import (
    DashboardKpis,
    DashboardMonth,
    DashboardSummary,
)

_ZERO = Decimal("0")
YearMonth = tuple[int, int]


def _to_float(value: Decimal | None) -> float:
    return float(value) if value is not None else 0.0


async def _open_boundary(db: AsyncSession) -> YearMonth | None:
    """(year, month) where the current open period starts. None if no open period."""
    row = (
        await db.execute(
            select(AccrualPeriodDB.start_date)
            .where(AccrualPeriodDB.status == "open")
            .order_by(AccrualPeriodDB.start_date.desc())
            .limit(1)
        )
    ).first()
    return (row[0].year, row[0].month) if row else None


async def _amount_by_ym(db: AsyncSession) -> dict[YearMonth, Decimal]:
    """(year, month) -> summed EUR. Frozen snapshot when present (closed periods),
    else the live amount (open/forecast cells)."""
    amount = func.coalesce(AccrualCellDB.frozen_eur_amount, AccrualCellDB.amount)
    rows = (
        await db.execute(
            select(
                AccrualCellDB.year,
                AccrualCellDB.month,
                func.coalesce(func.sum(amount), _ZERO),
            ).group_by(AccrualCellDB.year, AccrualCellDB.month)
        )
    ).all()
    return {(y, m): total for y, m, total in rows}


def _recognized_cutoff(boundary: YearMonth | None, today: date) -> YearMonth:
    """Months strictly before this (year, month) are recognized. Takes the later of
    the open-period start and the current month so a year closed early (open period in
    the future) still counts its frozen months as recognized."""
    current = (today.year, today.month)
    return max(boundary, current) if boundary else current


async def _available_years(db: AsyncSession) -> list[int]:
    rows = (
        await db.execute(select(AccrualCellDB.year).distinct().order_by(AccrualCellDB.year))
    ).all()
    return [r[0] for r in rows]


async def _contracted_total(db: AsyncSession) -> Decimal:
    return (
        await db.execute(select(func.coalesce(func.sum(AccrualLineDB.value_eur), _ZERO)))
    ).scalar_one()


def _quarter_months(today: date) -> set[int]:
    start = ((today.month - 1) // 3) * 3 + 1
    return {start, start + 1, start + 2}


def _build_kpis(
    amount_by_ym: dict[YearMonth, Decimal],
    *,
    year: int,
    cutoff: YearMonth,
    quarter_months: set[int],
    contracted: Decimal,
    year_plan: Decimal,
) -> DashboardKpis:
    recognized_ytd = _ZERO
    recognized_quarter = _ZERO
    recognized_to_date = _ZERO
    for (yy, mm), amount in amount_by_ym.items():
        if (yy, mm) >= cutoff:  # current month or later → forecast
            continue
        recognized_to_date += amount
        if yy == year:
            recognized_ytd += amount
            if mm in quarter_months:
                recognized_quarter += amount

    backlog = contracted - recognized_to_date
    if backlog < _ZERO:
        backlog = _ZERO

    # Share of the selected year's planned recognition (all 12 months) already
    # recognized — the burn-up curve's endpoint expressed as a single figure.
    plan_recognized_pct = float(recognized_ytd / year_plan * 100) if year_plan != _ZERO else 0.0

    return DashboardKpis(
        recognized_ytd_eur=_to_float(recognized_ytd),
        recognized_quarter_eur=_to_float(recognized_quarter),
        contracted_total_eur=_to_float(contracted),
        backlog_eur=_to_float(backlog),
        plan_recognized_pct=plan_recognized_pct,
    )


async def build_summary(db: AsyncSession, *, year: int, today: date) -> DashboardSummary:
    cutoff = _recognized_cutoff(await _open_boundary(db), today)
    amount_by_ym = await _amount_by_ym(db)

    months = [
        DashboardMonth(
            month=month,
            amount_eur=_to_float(amount_by_ym.get((year, month), _ZERO)),
            status="recognized" if (year, month) < cutoff else "forecast",
        )
        for month in range(1, 13)
    ]
    year_plan = sum((amount_by_ym.get((year, m), _ZERO) for m in range(1, 13)), _ZERO)

    kpis = _build_kpis(
        amount_by_ym,
        year=year,
        cutoff=cutoff,
        quarter_months=_quarter_months(today),
        contracted=await _contracted_total(db),
        year_plan=year_plan,
    )
    return DashboardSummary(
        year=year,
        available_years=await _available_years(db),
        months=months,
        kpis=kpis,
    )
