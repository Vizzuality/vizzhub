"""Model-layer tests for accrual_periods and accrual_cells."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accrual.models.accrual_period import AccrualPeriodDB


@pytest.mark.asyncio
async def test_can_persist_open_period(db_session: AsyncSession) -> None:
    period = AccrualPeriodDB(
        start_date=date(2026, 1, 1),
        status="open",
    )
    db_session.add(period)
    await db_session.flush()
    assert period.id is not None
    assert period.created_at is not None


@pytest.mark.asyncio
async def test_cannot_persist_two_open(db_session: AsyncSession) -> None:
    db_session.add(AccrualPeriodDB(start_date=date(2025, 1, 1), status="open"))
    await db_session.flush()
    db_session.add(AccrualPeriodDB(start_date=date(2026, 1, 1), status="open"))
    with pytest.raises(Exception) as exc_info:
        await db_session.flush()
    msg = str(exc_info.value).lower()
    assert "uq_accrual_periods_one_open" in msg or "unique" in msg


@pytest.mark.asyncio
async def test_closed_period_requires_closed_at(db_session: AsyncSession) -> None:
    db_session.add(
        AccrualPeriodDB(
            start_date=date(2025, 1, 1),
            status="closed",
            closed_at=None,
        )
    )
    with pytest.raises(Exception) as exc_info:
        await db_session.flush()
    msg = str(exc_info.value).lower()
    assert "ck_accrual_periods_closed_status_consistent" in msg or "check" in msg


async def _make_line(db_session: AsyncSession) -> "object":
    from app.modules.accrual.models.accrual_line import AccrualLineDB

    line = AccrualLineDB(name="Test", value_eur=Decimal("1200"))
    db_session.add(line)
    await db_session.flush()
    return line


@pytest.mark.asyncio
async def test_persist_live_cell(db_session: AsyncSession) -> None:
    from app.modules.accrual.models.accrual_cell import AccrualCellDB

    line = await _make_line(db_session)
    cell = AccrualCellDB(
        line_id=line.id,
        year=2026,
        month=3,
        amount=Decimal("100"),
        is_manual_override=False,
        is_frozen=False,
    )
    db_session.add(cell)
    await db_session.flush()
    assert cell.id is not None


@pytest.mark.asyncio
async def test_frozen_cell_requires_three_stamp_fields(db_session: AsyncSession) -> None:
    from app.modules.accrual.models.accrual_cell import AccrualCellDB

    line = await _make_line(db_session)
    cell = AccrualCellDB(
        line_id=line.id,
        year=2025,
        month=6,
        amount=Decimal("100"),
        is_frozen=True,
    )
    db_session.add(cell)
    with pytest.raises(Exception) as exc_info:
        await db_session.flush()
    assert "frozen" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_month_check_rejects_13(db_session: AsyncSession) -> None:
    from app.modules.accrual.models.accrual_cell import AccrualCellDB

    line = await _make_line(db_session)
    db_session.add(
        AccrualCellDB(
            line_id=line.id,
            year=2026,
            month=13,
            amount=Decimal("100"),
        )
    )
    with pytest.raises(Exception):
        await db_session.flush()
