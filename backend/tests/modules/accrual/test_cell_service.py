"""Unit tests for cell_service line-keyed operations."""

from datetime import UTC, date
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


@pytest.mark.asyncio
async def test_reconcile_line_window_moves_cells_to_new_window(
    db_session: AsyncSession,
) -> None:
    """Moving a line's window deletes the now-orphaned cells and redistributes
    value_eur across the new window (full range, so a past/closed target year is
    filled too)."""
    await period_service.create_period(db_session, start_date=date(2026, 1, 1), created_by=None)
    line = await _make_line(db_session, value_eur="1200")
    await cell_service.redistribute_for_line(db_session, line_id=line.id)

    line.window_start = date(2024, 1, 1)
    line.window_end = date(2024, 12, 1)
    await db_session.flush()

    orphans = await cell_service.reconcile_line_window(db_session, line_id=line.id)
    assert orphans == 12  # the whole 2026 block was orphaned

    cells = (
        (await db_session.execute(select(AccrualCellDB).where(AccrualCellDB.line_id == line.id)))
        .scalars()
        .all()
    )
    assert {c.year for c in cells} == {2024}
    assert len(cells) == 12
    assert all(c.amount == Decimal("100.00") for c in cells)


@pytest.mark.asyncio
async def test_reconcile_line_window_preserves_in_window_cells(
    db_session: AsyncSession,
) -> None:
    """Shrinking a window keeps the in-window cells (overrides survive) and drops
    only the months that fell outside."""
    await period_service.create_period(db_session, start_date=date(2026, 1, 1), created_by=None)
    line = await _make_line(db_session, value_eur="1200")
    await cell_service.redistribute_for_line(db_session, line_id=line.id)
    await cell_service.set_cell_amount_by_line(
        db_session, line_id=line.id, year=2026, month=1, amount=Decimal("300")
    )

    line.window_end = date(2026, 6, 1)
    await db_session.flush()

    orphans = await cell_service.reconcile_line_window(db_session, line_id=line.id)
    assert orphans == 6  # months 7..12 dropped

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
    assert set(cells) == {1, 2, 3, 4, 5, 6}
    assert cells[1].amount == Decimal("300.00")  # override preserved
    assert cells[1].is_manual_override is True
    assert cells[2].amount == Decimal("180.00")  # (1200 - 300) / 5


@pytest.mark.asyncio
async def test_reconcile_line_window_rejects_frozen_orphan(
    db_session: AsyncSession,
) -> None:
    """A frozen (recognised) cell that would fall outside the new window blocks the
    move — recognised revenue cannot be relocated."""
    from datetime import datetime

    await period_service.create_period(db_session, start_date=date(2026, 1, 1), created_by=None)
    line = await _make_line(db_session, value_eur="1200")
    await cell_service.redistribute_for_line(db_session, line_id=line.id)
    frozen = (
        await db_session.execute(
            select(AccrualCellDB).where(AccrualCellDB.line_id == line.id, AccrualCellDB.month == 3)
        )
    ).scalar_one()
    frozen.is_frozen = True
    frozen.frozen_at = datetime(2026, 4, 1, tzinfo=UTC)
    frozen.frozen_eur_amount = frozen.amount
    await db_session.flush()

    line.window_start = date(2024, 1, 1)
    line.window_end = date(2024, 12, 1)
    await db_session.flush()

    with pytest.raises(cell_service.CellFrozenError):
        await cell_service.reconcile_line_window(db_session, line_id=line.id)


@pytest.mark.asyncio
async def test_set_line_rate_recomputes_value_eur_and_redistributes(
    db_session: AsyncSession,
) -> None:
    line = AccrualLineDB(
        name="L",
        source=LineSource.MANUAL.value,
        value_orig=Decimal("1080"),
        currency="USD",
        value_eur=Decimal("0"),
        window_start=date(2026, 1, 1),
        window_end=date(2026, 3, 31),
    )
    db_session.add(line)
    await db_session.flush()

    result = await cell_service.set_line_rate(db_session, line_id=line.id, rate=Decimal("1.08"))
    await db_session.refresh(line)

    assert result is not None
    assert line.rate == Decimal("1.08")
    assert line.value_eur == Decimal("1000.00")  # 1080 / 1.08
    cells = (
        (await db_session.execute(select(AccrualCellDB).where(AccrualCellDB.line_id == line.id)))
        .scalars()
        .all()
    )
    assert len(cells) == 3
    # redistribute splits uniformly; 1000/3 = 333.33 each → 999.99 total
    assert sum(c.amount for c in cells) == Decimal("999.99")


@pytest.mark.asyncio
async def test_set_line_rate_clear_falls_back_to_period(db_session: AsyncSession) -> None:
    await period_service.create_period(
        db_session, start_date=date(2026, 1, 1), created_by=None, fx_rates={"USD": "1.20"}
    )
    line = AccrualLineDB(
        name="L",
        source=LineSource.MANUAL.value,
        value_orig=Decimal("1200"),
        currency="USD",
        rate=Decimal("1.08"),
        value_eur=Decimal("1111.11"),
        window_start=date(2026, 1, 1),
        window_end=date(2026, 1, 31),
    )
    db_session.add(line)
    await db_session.flush()

    await cell_service.set_line_rate(db_session, line_id=line.id, rate=None)
    await db_session.refresh(line)

    assert line.rate is None
    assert line.value_eur == Decimal("1000.00")  # 1200 / 1.20 (period)


@pytest.mark.asyncio
async def test_set_line_rate_noop_for_eur_line(db_session: AsyncSession) -> None:
    line = AccrualLineDB(
        name="L",
        source=LineSource.MANUAL.value,
        value_orig=Decimal("500"),
        currency="EUR",
        value_eur=Decimal("500"),
        window_start=date(2026, 1, 1),
        window_end=date(2026, 1, 31),
    )
    db_session.add(line)
    await db_session.flush()

    result = await cell_service.set_line_rate(db_session, line_id=line.id, rate=Decimal("1.08"))
    await db_session.refresh(line)
    assert result is None
    assert line.rate is None
    assert line.value_eur == Decimal("500")


@pytest.mark.asyncio
async def test_set_line_rate_reconstructs_value_orig_when_missing(
    db_session: AsyncSession,
) -> None:
    """A line imported in EUR (no value_orig) gets its foreign amount reconstructed
    from the period rate, then the override recomputes value_eur. Clearing restores
    the original EUR figure."""
    await period_service.create_period(
        db_session, start_date=date(2026, 1, 1), created_by=None, fx_rates={"USD": "1.20"}
    )
    line = AccrualLineDB(
        name="L",
        source=LineSource.MANUAL.value,
        value_orig=None,
        currency="USD",
        value_eur=Decimal("900"),
        window_start=date(2026, 1, 1),
        window_end=date(2026, 1, 31),
    )
    db_session.add(line)
    await db_session.flush()

    result = await cell_service.set_line_rate(db_session, line_id=line.id, rate=Decimal("1.08"))
    await db_session.refresh(line)
    assert result is not None
    assert line.value_orig == Decimal("1080.00")  # 900 × 1.20 (period), persisted
    assert line.rate == Decimal("1.08")
    assert line.value_eur == Decimal("1000.00")  # 1080 / 1.08

    # Clearing the override falls back to the period rate and restores the EUR.
    await cell_service.set_line_rate(db_session, line_id=line.id, rate=None)
    await db_session.refresh(line)
    assert line.rate is None
    assert line.value_eur == Decimal("900.00")  # 1080 / 1.20


@pytest.mark.asyncio
async def test_set_line_rate_noop_without_value_orig_or_period(db_session: AsyncSession) -> None:
    """No value_orig and no resolvable period/ECB rate → nothing to reconstruct from."""
    line = AccrualLineDB(
        name="L",
        source=LineSource.MANUAL.value,
        value_orig=None,
        currency="USD",
        value_eur=Decimal("900"),
        window_start=date(2026, 1, 1),
        window_end=date(2026, 1, 31),
    )
    db_session.add(line)
    await db_session.flush()
    result = await cell_service.set_line_rate(db_session, line_id=line.id, rate=Decimal("1.08"))
    await db_session.refresh(line)
    assert result is None
    assert line.value_orig is None
    assert line.value_eur == Decimal("900")


@pytest.mark.asyncio
async def test_set_line_rate_clear_noop_without_window_start(db_session: AsyncSession) -> None:
    line = AccrualLineDB(
        name="L",
        source=LineSource.MANUAL.value,
        value_orig=Decimal("1200"),
        currency="USD",
        rate=Decimal("1.08"),
        value_eur=Decimal("1111.11"),
        window_start=None,
        window_end=None,
    )
    db_session.add(line)
    await db_session.flush()
    result = await cell_service.set_line_rate(db_session, line_id=line.id, rate=None)
    await db_session.refresh(line)
    assert result is None
    assert line.rate == Decimal("1.08")  # unchanged
    assert line.value_eur == Decimal("1111.11")  # untouched
