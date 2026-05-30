"""Unit tests for cell_service line-keyed operations."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accrual.models.accrual_cell import AccrualCellDB
from app.modules.accrual.models.accrual_line import AccrualLineDB, LineSource
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB
from app.modules.accrual.services import cell_service, period_service


async def _make_line(
    db: AsyncSession,
    *,
    value_eur: str = "1200",
    window_start: date | None = date(2026, 1, 1),
    window_end: date | None = date(2026, 12, 1),
    project_ids: list | None = None,
) -> AccrualLineDB:
    line = AccrualLineDB(
        name="Line",
        source=LineSource.EXCEL.value,
        value_eur=Decimal(value_eur),
        window_start=window_start,
        window_end=window_end,
    )
    db.add(line)
    await db.flush()
    for pid in project_ids or []:
        db.add(AccrualLineProjectDB(line_id=line.id, project_id=pid))
    await db.flush()
    return line


@pytest.mark.asyncio
async def test_redistribute_for_line_uniform_split(db_session: AsyncSession) -> None:
    """A line with no cells gets value_eur spread evenly across its window."""
    await period_service.create_period(db_session, start_date=date(2026, 1, 1), created_by=None)
    line = await _make_line(db_session, value_eur="1200")
    n = await cell_service.redistribute_for_line(db_session, line_id=line.id)
    assert n == 12
    cells = (
        (await db_session.execute(select(AccrualCellDB).where(AccrualCellDB.line_id == line.id)))
        .scalars()
        .all()
    )
    assert len(cells) == 12
    assert all(c.amount == Decimal("100.00") for c in cells)


@pytest.mark.asyncio
async def test_redistribute_for_line_preserves_overrides(db_session: AsyncSession) -> None:
    """An override is reserved; the remaining value redistributes around it."""
    await period_service.create_period(db_session, start_date=date(2026, 1, 1), created_by=None)
    line = await _make_line(db_session, value_eur="1200")
    await cell_service.redistribute_for_line(db_session, line_id=line.id)
    await cell_service.set_cell_amount_by_line(
        db_session, line_id=line.id, year=2026, month=1, amount=Decimal("300")
    )
    await cell_service.redistribute_for_line(db_session, line_id=line.id)
    cells = {
        c.month: c
        for c in (
            (
                await db_session.execute(
                    select(AccrualCellDB).where(AccrualCellDB.line_id == line.id)
                )
            )
            .scalars()
            .all()
        )
    }
    assert cells[1].amount == Decimal("300.00")
    assert cells[1].is_manual_override is True
    assert cells[2].amount == Decimal("81.82")  # (1200 - 300) / 11


@pytest.mark.asyncio
async def test_redistribute_for_line_no_op_without_window(db_session: AsyncSession) -> None:
    line = await _make_line(db_session, window_start=None, window_end=None)
    n = await cell_service.redistribute_for_line(db_session, line_id=line.id)
    assert n == 0


@pytest.mark.asyncio
async def test_set_cell_amount_by_line_creates_override(db_session: AsyncSession) -> None:
    """Setting an empty month creates the cell as a manual override."""
    line = await _make_line(db_session)
    cell = await cell_service.set_cell_amount_by_line(
        db_session, line_id=line.id, year=2026, month=7, amount=Decimal("123.45")
    )
    assert cell.amount == Decimal("123.45")
    assert cell.is_manual_override is True
    assert cell.is_frozen is False


@pytest.mark.asyncio
async def test_clear_override_by_line_redistributes(db_session: AsyncSession) -> None:
    await period_service.create_period(db_session, start_date=date(2026, 1, 1), created_by=None)
    line = await _make_line(db_session, value_eur="1200")
    await cell_service.redistribute_for_line(db_session, line_id=line.id)
    await cell_service.set_cell_amount_by_line(
        db_session, line_id=line.id, year=2026, month=5, amount=Decimal("300")
    )
    cleared = await cell_service.clear_override_by_line(
        db_session, line_id=line.id, year=2026, month=5
    )
    assert cleared.is_manual_override is False
    assert cleared.amount == Decimal("100.00")


@pytest.mark.asyncio
async def test_bulk_set_cells_by_line_happy_path(db_session: AsyncSession) -> None:
    line = await _make_line(db_session)
    cells = await cell_service.bulk_set_cells_by_line(
        db_session,
        updates=[
            {"line_id": line.id, "year": 2026, "month": 2, "amount": Decimal("150")},
            {"line_id": line.id, "year": 2026, "month": 3, "amount": Decimal("200")},
        ],
    )
    assert len(cells) == 2
    assert {c.month for c in cells} == {2, 3}
    assert all(c.is_manual_override for c in cells)
