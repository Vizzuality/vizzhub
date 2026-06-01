"""Unit tests for the accrual dashboard aggregation service.

Recognition frontier mirrors yearly period rotation: months before the open period's
start are recognized via their frozen snapshot; months already elapsed within the open
period are recognized via their live amount; the current month onward is forecast.
"""

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


async def _rotate_to(db: AsyncSession, *years: int) -> None:
    """Open each year's period in order; opening a new one closes (and freezes) the
    prior open period, exactly like production rotation."""
    for y in years:
        await period_service.create_period(db, start_date=date(y, 1, 1), created_by=None)


@pytest.mark.asyncio
async def test_months_always_twelve_and_empty_year_is_zeros(db_session: AsyncSession) -> None:
    summary = await dashboard_service.build_summary(db_session, year=2026, today=date(2026, 6, 1))
    assert [m.month for m in summary.months] == list(range(1, 13))
    assert all(m.amount_eur == 0.0 for m in summary.months)


@pytest.mark.asyncio
async def test_elapsed_month_in_open_period_is_recognized_live(db_session: AsyncSession) -> None:
    # Open 2026 (current open period). A past month within it uses its live amount.
    await _rotate_to(db_session, 2026)
    line = await _line(db_session)
    await _cell(db_session, line, year=2026, month=2, amount="500")
    summary = await dashboard_service.build_summary(db_session, year=2026, today=date(2026, 6, 1))
    feb = next(m for m in summary.months if m.month == 2)
    assert feb.status == "recognized"
    assert feb.amount_eur == 500.0
    assert summary.kpis.recognized_ytd_eur == 500.0


@pytest.mark.asyncio
async def test_future_month_in_open_period_is_forecast(db_session: AsyncSession) -> None:
    await _rotate_to(db_session, 2026)
    line = await _line(db_session)
    await _cell(db_session, line, year=2026, month=11, amount="300")
    summary = await dashboard_service.build_summary(db_session, year=2026, today=date(2026, 6, 1))
    nov = next(m for m in summary.months if m.month == 11)
    assert nov.status == "forecast"
    assert nov.amount_eur == 300.0
    # A forecast month does not count toward recognized YTD.
    assert summary.kpis.recognized_ytd_eur == 0.0


@pytest.mark.asyncio
async def test_closed_prior_year_recognized_via_frozen(db_session: AsyncSession) -> None:
    # Rotate 2025 then 2026: opening 2026 closes 2025 and freezes its cells.
    line = await _line(db_session)
    await _rotate_to(db_session, 2025)
    await _cell(db_session, line, year=2025, month=6, amount="800")
    await _rotate_to(db_session, 2026)

    summary = await dashboard_service.build_summary(db_session, year=2025, today=date(2026, 6, 1))
    jun = next(m for m in summary.months if m.month == 6)
    assert jun.status == "recognized"
    assert jun.amount_eur == 800.0
    assert summary.kpis.recognized_ytd_eur == 800.0


@pytest.mark.asyncio
async def test_closed_month_ignores_live_amount_drift_after_freeze(
    db_session: AsyncSession,
) -> None:
    """A closed month reports its frozen snapshot, not live drift."""
    line = await _line(db_session)
    await _rotate_to(db_session, 2025)
    cell = await _cell(db_session, line, year=2025, month=6, amount="700")
    await _rotate_to(db_session, 2026)  # closes + freezes 2025 at 700

    cell.amount = Decimal("900")  # drift the live amount post-freeze
    await db_session.flush()

    summary = await dashboard_service.build_summary(db_session, year=2025, today=date(2026, 6, 1))
    jun = next(m for m in summary.months if m.month == 6)
    assert jun.amount_eur == 700.0


@pytest.mark.asyncio
async def test_backlog_is_contracted_minus_all_recognized(db_session: AsyncSession) -> None:
    """Backlog must subtract every recognized month across all years, not just the
    open period's start month."""
    line = await _line(db_session, value_eur="1000")
    await _rotate_to(db_session, 2025)
    # Two months in the closed year — both must count toward recognized_to_date.
    await _cell(db_session, line, year=2025, month=3, amount="200")
    await _cell(db_session, line, year=2025, month=9, amount="300")
    await _rotate_to(db_session, 2026)

    summary = await dashboard_service.build_summary(db_session, year=2026, today=date(2026, 6, 1))
    assert summary.kpis.contracted_total_eur == 1000.0
    assert summary.kpis.backlog_eur == 500.0  # 1000 - (200 + 300)


@pytest.mark.asyncio
async def test_manual_pct_and_available_years(db_session: AsyncSession) -> None:
    line = await _line(db_session)
    await _cell(db_session, line, year=2025, month=6, amount="100", is_manual_override=True)
    await _cell(db_session, line, year=2026, month=6, amount="300")
    summary = await dashboard_service.build_summary(db_session, year=2026, today=date(2026, 6, 1))
    assert summary.available_years == [2025, 2026]
    assert summary.kpis.manual_pct == 25.0
