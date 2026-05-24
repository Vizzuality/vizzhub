"""Unit tests for period_service."""

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.accrual.models.accrual_period import AccrualPeriodDB
from app.modules.accrual.services import period_service

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(id=DEBUG_USER_ID, email="admin@vizzuality.com", name="Admin")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_create_first_period_no_previous(
    db_session: AsyncSession,
    admin_user: UserDB,
) -> None:
    period = await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=admin_user.id,
    )
    assert period.id is not None
    assert period.status == "open"
    assert period.start_date == date(2026, 1, 1)
    assert period.created_by == admin_user.id

    result = await db_session.execute(
        select(AccrualPeriodDB).where(AccrualPeriodDB.status == "open")
    )
    open_periods = result.scalars().all()
    assert len(open_periods) == 1


@pytest.mark.asyncio
async def test_create_period_rejects_duplicate_start_date(
    db_session: AsyncSession,
    admin_user: UserDB,
) -> None:
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=admin_user.id,
    )
    with pytest.raises(period_service.PeriodConflictError):
        await period_service.create_period(
            db_session,
            start_date=date(2026, 1, 1),
            created_by=admin_user.id,
        )


@pytest.mark.asyncio
async def test_create_second_period_closes_previous(
    db_session: AsyncSession,
    admin_user: UserDB,
) -> None:
    first = await period_service.create_period(
        db_session,
        start_date=date(2025, 1, 1),
        created_by=admin_user.id,
    )
    second = await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=admin_user.id,
    )
    await db_session.refresh(first)
    assert first.status == "closed"
    assert first.closed_at is not None
    assert second.status == "open"


@pytest.mark.asyncio
async def test_get_period_for_month_returns_latest_before(
    db_session: AsyncSession,
    admin_user: UserDB,
) -> None:
    await period_service.create_period(
        db_session,
        start_date=date(2025, 1, 1),
        created_by=admin_user.id,
    )
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=admin_user.id,
    )

    p = await period_service.get_period_for_month(db_session, year=2025, month=6)
    assert p.start_date == date(2025, 1, 1)

    p = await period_service.get_period_for_month(db_session, year=2026, month=3)
    assert p.start_date == date(2026, 1, 1)


@pytest.mark.asyncio
async def test_get_period_for_month_returns_none_before_any_period(
    db_session: AsyncSession,
    admin_user: UserDB,
) -> None:
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=admin_user.id,
    )
    p = await period_service.get_period_for_month(db_session, year=2025, month=12)
    assert p is None


@pytest.mark.asyncio
async def test_close_period_freezes_cells_before_cutoff(db_session: AsyncSession) -> None:
    """Auto-close on rotation freezes all 2025 cells; frozen_eur_amount == amount (EUR)."""
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
    from app.modules.accrual.services import cell_service

    await period_service.create_period(
        db_session,
        start_date=date(2025, 1, 1),
        created_by=None,
    )
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
    await cell_service.redistribute_for_project(db_session, project_id=project.id)

    # Rotating to 2026 should auto-close 2025 with cutoff (2026, 1).
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=None,
    )

    result = await db_session.execute(
        select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == project.id)
    )
    cells = sorted(result.scalars().all(), key=lambda c: (c.year, c.month))
    assert len(cells) == 12
    for cell in cells:
        assert cell.is_frozen is True
        assert cell.frozen_at is not None
        assert cell.frozen_eur_amount == cell.amount


@pytest.mark.asyncio
async def test_freeze_period_cells_idempotent_on_already_closed_period(
    db_session: AsyncSession,
) -> None:
    """When called twice on a closed period, the second call returns 0 (idempotent)."""
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
    from app.modules.accrual.services import cell_service

    # Two periods: 2024 (will close), 2025 (open).
    p_2024 = await period_service.create_period(
        db_session,
        start_date=date(2024, 1, 1),
        created_by=None,
    )
    await period_service.create_period(
        db_session,
        start_date=date(2025, 1, 1),
        created_by=None,
    )

    # Create a project + cells AFTER 2024 was already closed.
    project = ProjectDB(
        name="X",
        code="FRZ",
        status="live",
        currency="USD",
        is_billable=True,
        budget=Decimal("12000"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    # full_range=True: current open period is 2025, so we must bypass the clip
    # to populate historical 2024 cells for a project that ends in 2024-12.
    await cell_service.redistribute_for_project(db_session, project_id=project.id, full_range=True)

    # First freeze: 12 cells freeze.
    n1 = await period_service.freeze_period_cells(db_session, period_id=p_2024.id)
    assert n1 == 12, "all 12 cells in 2024 must freeze"

    # Re-run: nothing more to freeze.
    n2 = await period_service.freeze_period_cells(db_session, period_id=p_2024.id)
    assert n2 == 0, "second call is a no-op"

    # Verify all 2024 cells are now frozen.
    result = await db_session.execute(
        select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == project.id)
    )
    cells = result.scalars().all()
    assert all(c.is_frozen for c in cells)


@pytest.mark.asyncio
async def test_close_period_leaves_future_cells_alone(db_session: AsyncSession) -> None:
    """Cells dated 2026-onwards must NOT freeze when 2025 closes at cutoff 2026-01."""
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
    from app.modules.accrual.services import cell_service

    await period_service.create_period(
        db_session,
        start_date=date(2025, 1, 1),
        created_by=None,
    )
    # Two-year project: spans 2025-2026.
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("2400"),
        start_date=date(2025, 1, 1),
        end_date=date(2026, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    written = await cell_service.redistribute_for_project(db_session, project_id=project.id)
    assert written == 24, "redistribute should populate all 24 months (2025-01 .. 2026-12)"

    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        created_by=None,
    )

    result = await db_session.execute(
        select(ProjectAccrualCellDB)
        .where(ProjectAccrualCellDB.project_id == project.id)
        .order_by(ProjectAccrualCellDB.year, ProjectAccrualCellDB.month)
    )
    cells = result.scalars().all()
    cells_2025 = [c for c in cells if c.year == 2025]
    cells_2026 = [c for c in cells if c.year == 2026]
    assert all(c.is_frozen for c in cells_2025), "2025 cells must freeze"
    assert not any(c.is_frozen for c in cells_2026), "2026 cells must stay live"
