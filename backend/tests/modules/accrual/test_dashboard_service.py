"""Unit tests for the accrual dashboard aggregation service."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accrual.models.accrual_cell import AccrualCellDB
from app.modules.accrual.models.accrual_line import AccrualLineDB, LineSource
from app.modules.accrual.services import dashboard_service, period_service


async def _line(db: AsyncSession, value_eur: str = "1200") -> AccrualLineDB:
    line = AccrualLineDB(name="L", source=LineSource.MANUAL.value, value_eur=Decimal(value_eur))
    db.add(line)
    await db.flush()
    return line


async def _cell(
    db: AsyncSession,
    line: AccrualLineDB,
    *,
    year: int,
    month: int,
    amount: str,
    is_manual_override: bool = False,
) -> AccrualCellDB:
    cell = AccrualCellDB(
        line_id=line.id,
        year=year,
        month=month,
        amount=Decimal(amount),
        is_manual_override=is_manual_override,
    )
    db.add(cell)
    await db.flush()
    return cell


@pytest.mark.asyncio
async def test_months_always_twelve_and_empty_year_is_zeros(
    db_session: AsyncSession,
) -> None:
    summary = await dashboard_service.build_summary(db_session, year=2026, today=date(2026, 5, 15))
    assert len(summary.months) == 12
    assert [m.month for m in summary.months] == list(range(1, 13))
    assert all(m.amount_eur == 0.0 for m in summary.months)
    assert all(m.status == "none" for m in summary.months)


@pytest.mark.asyncio
async def test_open_month_uses_live_amount(db_session: AsyncSession) -> None:
    await period_service.create_period(db_session, start_date=date(2026, 3, 1), created_by=None)
    line = await _line(db_session)
    await _cell(db_session, line, year=2026, month=3, amount="500")
    summary = await dashboard_service.build_summary(db_session, year=2026, today=date(2026, 5, 15))
    march = next(m for m in summary.months if m.month == 3)
    assert march.status == "open"
    assert march.amount_eur == 500.0


@pytest.mark.asyncio
async def test_closed_month_uses_frozen_amount_and_counts_as_recognized(
    db_session: AsyncSession,
) -> None:
    await period_service.create_period(db_session, start_date=date(2026, 1, 1), created_by=None)
    line = await _line(db_session)
    await _cell(db_session, line, year=2026, month=1, amount="700")
    period = await period_service.get_period_for_month(db_session, year=2026, month=1)
    await period_service.close_period(db_session, period.id, freeze_cutoff=date(2026, 2, 1))

    summary = await dashboard_service.build_summary(db_session, year=2026, today=date(2026, 5, 15))
    jan = next(m for m in summary.months if m.month == 1)
    assert jan.status == "closed"
    assert jan.amount_eur == 700.0
    assert summary.kpis.recognized_ytd_eur == 700.0


@pytest.mark.asyncio
async def test_closed_month_ignores_live_amount_drift_after_freeze(
    db_session: AsyncSession,
) -> None:
    """A closed month reports the frozen snapshot, not the live amount. Drift the
    live amount post-freeze and confirm the dashboard still reports the frozen value."""
    await period_service.create_period(db_session, start_date=date(2026, 1, 1), created_by=None)
    line = await _line(db_session)
    cell = await _cell(db_session, line, year=2026, month=1, amount="700")
    period = await period_service.get_period_for_month(db_session, year=2026, month=1)
    await period_service.close_period(db_session, period.id, freeze_cutoff=date(2026, 2, 1))

    # Drift the live amount after the freeze; the frozen snapshot stays at 700.
    cell.amount = Decimal("900")
    await db_session.flush()

    summary = await dashboard_service.build_summary(db_session, year=2026, today=date(2026, 5, 15))
    jan = next(m for m in summary.months if m.month == 1)
    assert jan.amount_eur == 700.0
    assert summary.kpis.recognized_ytd_eur == 700.0


@pytest.mark.asyncio
async def test_backlog_is_contracted_minus_recognized_floored_at_zero(
    db_session: AsyncSession,
) -> None:
    await period_service.create_period(db_session, start_date=date(2026, 1, 1), created_by=None)
    line = await _line(db_session, value_eur="1000")
    await _cell(db_session, line, year=2026, month=1, amount="300")
    period = await period_service.get_period_for_month(db_session, year=2026, month=1)
    await period_service.close_period(db_session, period.id, freeze_cutoff=date(2026, 2, 1))

    summary = await dashboard_service.build_summary(db_session, year=2026, today=date(2026, 5, 15))
    assert summary.kpis.contracted_total_eur == 1000.0
    assert summary.kpis.backlog_eur == 700.0


@pytest.mark.asyncio
async def test_manual_pct_and_available_years(db_session: AsyncSession) -> None:
    line = await _line(db_session)
    await _cell(db_session, line, year=2025, month=6, amount="100", is_manual_override=True)
    await _cell(db_session, line, year=2026, month=6, amount="300")
    summary = await dashboard_service.build_summary(db_session, year=2026, today=date(2026, 5, 15))
    assert summary.available_years == [2025, 2026]
    assert summary.kpis.manual_pct == 25.0
