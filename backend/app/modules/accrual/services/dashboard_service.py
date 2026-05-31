"""Read-only aggregation for the accrual dashboard. Intra-module reads only."""

from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, select
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


def _to_float(value: Decimal | None) -> float:
    return float(value) if value is not None else 0.0


async def _period_status_by_ym(db: AsyncSession) -> dict[tuple[int, int], str]:
    """Map (year, month) -> period status. One period == one month."""
    rows = (await db.execute(select(AccrualPeriodDB.start_date, AccrualPeriodDB.status))).all()
    return {(sd.year, sd.month): status for sd, status in rows}


async def _amounts_by_ym(
    db: AsyncSession,
) -> dict[tuple[int, int], tuple[Decimal, Decimal]]:
    """Map (year, month) -> (live_sum, frozen_sum). frozen_sum falls back to live
    when frozen_eur_amount is NULL."""
    frozen_expr = func.coalesce(AccrualCellDB.frozen_eur_amount, AccrualCellDB.amount)
    rows = (
        await db.execute(
            select(
                AccrualCellDB.year,
                AccrualCellDB.month,
                func.coalesce(func.sum(AccrualCellDB.amount), _ZERO),
                func.coalesce(func.sum(frozen_expr), _ZERO),
            ).group_by(AccrualCellDB.year, AccrualCellDB.month)
        )
    ).all()
    return {(y, m): (live, frozen) for y, m, live, frozen in rows}


def _amount_for_status(status: str, live: Decimal, frozen: Decimal) -> Decimal:
    return frozen if status == "closed" else live


async def build_summary(db: AsyncSession, *, year: int, today: date) -> DashboardSummary:
    status_by_ym = await _period_status_by_ym(db)
    amounts_by_ym = await _amounts_by_ym(db)

    months: list[DashboardMonth] = []
    for month in range(1, 13):
        status = status_by_ym.get((year, month), "none")
        live, frozen = amounts_by_ym.get((year, month), (_ZERO, _ZERO))
        amount = _amount_for_status(status, live, frozen)
        months.append(DashboardMonth(month=month, amount_eur=_to_float(amount), status=status))

    kpis = await _build_kpis(
        db,
        year=year,
        today=today,
        status_by_ym=status_by_ym,
        amounts_by_ym=amounts_by_ym,
    )
    available_years = await _available_years(db)
    return DashboardSummary(year=year, available_years=available_years, months=months, kpis=kpis)


async def _available_years(db: AsyncSession) -> list[int]:
    rows = (
        await db.execute(select(AccrualCellDB.year).distinct().order_by(AccrualCellDB.year))
    ).all()
    return [r[0] for r in rows]


async def _build_kpis(
    db: AsyncSession,
    *,
    year: int,
    today: date,
    status_by_ym: dict[tuple[int, int], str],
    amounts_by_ym: dict[tuple[int, int], tuple[Decimal, Decimal]],
) -> DashboardKpis:
    quarter_months = _quarter_months(today)

    recognized_ytd = _ZERO
    recognized_quarter = _ZERO
    for month in range(1, 13):
        if status_by_ym.get((year, month)) != "closed":
            continue
        _, frozen = amounts_by_ym.get((year, month), (_ZERO, _ZERO))
        recognized_ytd += frozen
        if month in quarter_months:
            recognized_quarter += frozen

    recognized_to_date = _ZERO
    for (yy, mm), (_, frozen) in amounts_by_ym.items():
        if status_by_ym.get((yy, mm)) == "closed":
            recognized_to_date += frozen

    contracted = (
        await db.execute(select(func.coalesce(func.sum(AccrualLineDB.value_eur), _ZERO)))
    ).scalar_one()
    backlog = contracted - recognized_to_date
    if backlog < _ZERO:
        backlog = _ZERO

    manual_pct = await _manual_pct(db)

    return DashboardKpis(
        recognized_ytd_eur=_to_float(recognized_ytd),
        recognized_quarter_eur=_to_float(recognized_quarter),
        contracted_total_eur=_to_float(contracted),
        backlog_eur=_to_float(backlog),
        manual_pct=manual_pct,
    )


def _quarter_months(today: date) -> set[int]:
    start = ((today.month - 1) // 3) * 3 + 1
    return {start, start + 1, start + 2}


async def _manual_pct(db: AsyncSession) -> float:
    total = (
        await db.execute(select(func.coalesce(func.sum(AccrualCellDB.amount), _ZERO)))
    ).scalar_one()
    if total == _ZERO:
        return 0.0
    manual = (
        await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (AccrualCellDB.is_manual_override, AccrualCellDB.amount),
                            else_=_ZERO,
                        )
                    ),
                    _ZERO,
                )
            )
        )
    ).scalar_one()
    return float(manual / total * 100)
