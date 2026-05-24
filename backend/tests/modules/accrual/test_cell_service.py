"""Unit tests for cell_service.redistribute_for_project."""

from datetime import UTC, date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
from app.modules.accrual.services import cell_service, period_service


@pytest.mark.asyncio
async def test_redistribute_brand_new_uniform_split(db_session: AsyncSession) -> None:
    """Greenfield project with no existing cells gets 12 equal cells of 100."""
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=None,
    )
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("1200"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    n = await cell_service.redistribute_for_project(db_session, project_id=project.id)
    assert n == 12
    result = await db_session.execute(
        select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == project.id)
    )
    cells = sorted(result.scalars().all(), key=lambda c: (c.year, c.month))
    assert len(cells) == 12
    assert all(c.amount == Decimal("100.00") for c in cells)
    assert {(c.year, c.month) for c in cells} == {(2026, m) for m in range(1, 13)}


@pytest.mark.asyncio
async def test_redistribute_preserves_overrides(db_session: AsyncSession) -> None:
    """A manual override is honoured and the remaining budget redistributes around it.

    Project: 12 months, budget 1200. After greenfield redistribute, Jan is
    flipped to override=300. A second redistribute pass must keep Jan at 300
    and split (1200 - 300) / 11 = 81.81818... → quantised 81.82 across Feb-Dec.
    """
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=None,
    )
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("1200"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    await cell_service.redistribute_for_project(db_session, project_id=project.id)

    jan_result = await db_session.execute(
        select(ProjectAccrualCellDB).where(
            ProjectAccrualCellDB.project_id == project.id,
            ProjectAccrualCellDB.month == 1,
        )
    )
    jan = jan_result.scalar_one()
    jan.amount = Decimal("300.00")
    jan.is_manual_override = True
    await db_session.flush()

    await cell_service.redistribute_for_project(db_session, project_id=project.id)
    result = await db_session.execute(
        select(ProjectAccrualCellDB)
        .where(ProjectAccrualCellDB.project_id == project.id)
        .order_by(ProjectAccrualCellDB.month)
    )
    cells = result.scalars().all()
    jan_after = next(c for c in cells if c.month == 1)
    feb_after = next(c for c in cells if c.month == 2)
    assert jan_after.amount == Decimal("300.00")
    assert jan_after.is_manual_override is True
    assert feb_after.amount == Decimal("81.82")
    assert feb_after.is_manual_override is False


@pytest.mark.asyncio
async def test_redistribute_no_op_when_budget_missing(db_session: AsyncSession) -> None:
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=None,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    n = await cell_service.redistribute_for_project(db_session, project_id=project.id)
    assert n == 0


@pytest.mark.asyncio
async def test_redistribute_no_op_when_dates_missing(db_session: AsyncSession) -> None:
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("1200"),
    )
    db_session.add(project)
    await db_session.flush()
    n = await cell_service.redistribute_for_project(db_session, project_id=project.id)
    assert n == 0


@pytest.mark.asyncio
async def test_redistribute_force_overrides_manual(db_session: AsyncSession) -> None:
    """force=True clears manual override and rebalances uniformly."""
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=None,
    )
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("1200"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    await cell_service.redistribute_for_project(db_session, project_id=project.id)

    jan_result = await db_session.execute(
        select(ProjectAccrualCellDB).where(
            ProjectAccrualCellDB.project_id == project.id,
            ProjectAccrualCellDB.month == 1,
        )
    )
    jan = jan_result.scalar_one()
    jan.amount = Decimal("999.00")
    jan.is_manual_override = True
    await db_session.flush()

    await cell_service.redistribute_for_project(db_session, project_id=project.id, force=True)
    result = await db_session.execute(
        select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == project.id)
    )
    cells = result.scalars().all()
    assert all(c.amount == Decimal("100.00") for c in cells)
    assert all(c.is_manual_override is False for c in cells)


# --- T2.7: set_cell_amount + clear_override ---


@pytest.mark.asyncio
async def test_set_cell_amount_creates_override(db_session: AsyncSession) -> None:
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=None,
    )
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("1200"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    await cell_service.redistribute_for_project(db_session, project_id=project.id)
    cell = await cell_service.set_cell_amount(
        db_session,
        project_id=project.id,
        year=2026,
        month=5,
        amount=Decimal("250.00"),
    )
    assert cell.amount == Decimal("250.00")
    assert cell.is_manual_override is True


@pytest.mark.asyncio
async def test_set_cell_amount_creates_when_missing(db_session: AsyncSession) -> None:
    """No prior cell at (year, month) → set creates one as override."""
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("1200"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    cell = await cell_service.set_cell_amount(
        db_session,
        project_id=project.id,
        year=2026,
        month=7,
        amount=Decimal("123.45"),
    )
    assert cell.amount == Decimal("123.45")
    assert cell.is_manual_override is True
    assert cell.is_frozen is False


@pytest.mark.asyncio
async def test_set_cell_amount_frozen_raises(db_session: AsyncSession) -> None:
    from datetime import datetime

    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("1200"),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    db_session.add(
        ProjectAccrualCellDB(
            project_id=project.id,
            year=2025,
            month=3,
            amount=Decimal("100"),
            is_frozen=True,
            frozen_at=datetime.now(UTC),
            frozen_eur_amount=Decimal("100"),
        )
    )
    await db_session.flush()
    with pytest.raises(cell_service.CellFrozenError):
        await cell_service.set_cell_amount(
            db_session,
            project_id=project.id,
            year=2025,
            month=3,
            amount=Decimal("999"),
        )


@pytest.mark.asyncio
async def test_clear_override_redistributes(db_session: AsyncSession) -> None:
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=None,
    )
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("1200"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    await cell_service.redistribute_for_project(db_session, project_id=project.id)
    await cell_service.set_cell_amount(
        db_session,
        project_id=project.id,
        year=2026,
        month=5,
        amount=Decimal("300"),
    )
    await cell_service.clear_override(
        db_session,
        project_id=project.id,
        year=2026,
        month=5,
    )
    result = await db_session.execute(
        select(ProjectAccrualCellDB).where(
            ProjectAccrualCellDB.project_id == project.id,
            ProjectAccrualCellDB.month == 5,
        )
    )
    cell = result.scalar_one()
    assert cell.is_manual_override is False
    assert cell.amount == Decimal("100.00")


@pytest.mark.asyncio
async def test_clear_override_frozen_raises(db_session: AsyncSession) -> None:
    from datetime import datetime

    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("1200"),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    db_session.add(
        ProjectAccrualCellDB(
            project_id=project.id,
            year=2025,
            month=3,
            amount=Decimal("100"),
            is_frozen=True,
            frozen_at=datetime.now(UTC),
            frozen_eur_amount=Decimal("100"),
        )
    )
    await db_session.flush()
    with pytest.raises(cell_service.CellFrozenError):
        await cell_service.clear_override(
            db_session,
            project_id=project.id,
            year=2025,
            month=3,
        )


# --- T2.8: bulk_set_cells ---


@pytest.mark.asyncio
async def test_bulk_set_cells_happy_path(db_session: AsyncSession) -> None:
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("1200"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    updates = [
        {"project_id": project.id, "year": 2026, "month": 2, "amount": Decimal("150")},
        {"project_id": project.id, "year": 2026, "month": 3, "amount": Decimal("200")},
    ]
    cells = await cell_service.bulk_set_cells(db_session, updates=updates)
    assert len(cells) == 2
    assert {c.month for c in cells} == {2, 3}
    assert all(c.is_manual_override for c in cells)


@pytest.mark.asyncio
async def test_bulk_set_cells_rollback_on_frozen(db_session: AsyncSession) -> None:
    from datetime import datetime

    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=None,
    )
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("1200"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    await cell_service.redistribute_for_project(db_session, project_id=project.id)

    result = await db_session.execute(
        select(ProjectAccrualCellDB).where(
            ProjectAccrualCellDB.project_id == project.id,
            ProjectAccrualCellDB.month == 5,
        )
    )
    may = result.scalar_one()
    may.is_frozen = True
    may.frozen_at = datetime.now(UTC)
    may.frozen_eur_amount = may.amount
    await db_session.flush()

    updates = [
        {"project_id": project.id, "year": 2026, "month": 2, "amount": Decimal("150")},
        {"project_id": project.id, "year": 2026, "month": 5, "amount": Decimal("999")},  # frozen
    ]
    with pytest.raises(cell_service.CellFrozenError):
        await cell_service.bulk_set_cells(db_session, updates=updates)

    feb_result = await db_session.execute(
        select(ProjectAccrualCellDB).where(
            ProjectAccrualCellDB.project_id == project.id,
            ProjectAccrualCellDB.month == 2,
        )
    )
    feb = feb_result.scalar_one()
    assert feb.amount == Decimal("100.00")
