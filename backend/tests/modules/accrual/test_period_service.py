"""Unit tests for period_service."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
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
        fx_rates_input={"USD": "1.10", "GBP": "0.85"},
        created_by=admin_user.id,
    )
    assert period.id is not None
    assert period.status == "open"
    assert period.start_date == date(2026, 1, 1)
    assert period.fx_rates == {"USD": "1.10", "GBP": "0.85"}
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
        fx_rates_input={"USD": "1.10"},
        created_by=admin_user.id,
    )
    with pytest.raises(period_service.PeriodConflictError):
        await period_service.create_period(
            db_session,
            start_date=date(2026, 1, 1),
            fx_rates_input={"USD": "1.10"},
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
        fx_rates_input={"USD": "1.05"},
        created_by=admin_user.id,
    )
    second = await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        fx_rates_input={"USD": "1.10"},
        created_by=admin_user.id,
    )
    await db_session.refresh(first)
    assert first.status == "closed"
    assert first.closed_at is not None
    assert second.status == "open"


@pytest.mark.asyncio
async def test_create_period_copies_unchanged_rates(
    db_session: AsyncSession,
    admin_user: UserDB,
) -> None:
    await period_service.create_period(
        db_session,
        start_date=date(2025, 1, 1),
        fx_rates_input={"USD": "1.05", "GBP": "0.85"},
        created_by=admin_user.id,
    )
    second = await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        fx_rates_input={"USD": "1.10"},  # GBP unchanged → copied
        created_by=admin_user.id,
    )
    assert second.fx_rates == {"USD": "1.10", "GBP": "0.85"}


@pytest.mark.asyncio
async def test_get_period_for_month_returns_latest_before(
    db_session: AsyncSession,
    admin_user: UserDB,
) -> None:
    await period_service.create_period(
        db_session,
        start_date=date(2025, 1, 1),
        fx_rates_input={"USD": "1.05"},
        created_by=admin_user.id,
    )
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        fx_rates_input={"USD": "1.10"},
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
        fx_rates_input={"USD": "1.10"},
        created_by=admin_user.id,
    )
    p = await period_service.get_period_for_month(db_session, year=2025, month=12)
    assert p is None


@pytest.mark.asyncio
async def test_validate_currencies_returns_missing(
    db_session: AsyncSession,
    admin_user: UserDB,
) -> None:
    db_session.add_all(
        [
            ProjectDB(name="A", status="live", currency="USD", budget=Decimal("100")),
            ProjectDB(name="B", status="live", currency="GBP", budget=Decimal("200")),
            ProjectDB(name="C", status="finished", currency="EUR", budget=Decimal("50")),
            ProjectDB(name="D", status="proposal", currency="CHF", budget=Decimal("70")),
        ]
    )
    await db_session.flush()
    period = await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        fx_rates_input={"USD": "1.10"},  # missing GBP, CHF (EUR is passthrough)
        created_by=admin_user.id,
    )
    missing = await period_service.validate_currencies_covered(db_session, period)
    assert set(missing) == {"GBP", "CHF"}


@pytest.mark.asyncio
async def test_close_period_freezes_cells_before_cutoff(db_session: AsyncSession) -> None:
    """Auto-close on rotation freezes all 2025 cells with the 2025 rate."""
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
    from app.modules.accrual.services import cell_service

    await period_service.create_period(
        db_session,
        start_date=date(2025, 1, 1),
        fx_rates_input={"USD": "1.05"},
        created_by=None,
    )
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("1200"),
        original_budget=Decimal("1200"),
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
        fx_rates_input={"USD": "1.10"},
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
        assert cell.frozen_rate == Decimal("1.05")
        expected = (cell.amount / Decimal("1.05")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert cell.frozen_eur_amount == expected


@pytest.mark.asyncio
async def test_close_period_skips_cells_with_unresolvable_rate(
    db_session: AsyncSession,
) -> None:
    """A cell whose currency has no rate anywhere is left live (warned, not crashed)."""
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
    from app.modules.accrual.services import cell_service

    # Period only covers USD, but the project is in JPY with no ECB record either.
    await period_service.create_period(
        db_session,
        start_date=date(2025, 1, 1),
        fx_rates_input={"USD": "1.05"},
        created_by=None,
    )
    project = ProjectDB(
        name="A",
        status="live",
        currency="JPY",
        budget=Decimal("1200"),
        original_budget=Decimal("1200"),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 1),
    )
    db_session.add(project)
    await db_session.flush()
    await cell_service.redistribute_for_project(db_session, project_id=project.id)

    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        fx_rates_input={"USD": "1.10"},
        created_by=None,
    )

    result = await db_session.execute(
        select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == project.id)
    )
    cells = result.scalars().all()
    assert len(cells) == 12
    assert all(c.is_frozen is False for c in cells)


@pytest.mark.asyncio
async def test_close_period_leaves_future_cells_alone(db_session: AsyncSession) -> None:
    """Cells dated 2026-onwards must NOT freeze when 2025 closes at cutoff 2026-01."""
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
    from app.modules.accrual.services import cell_service

    await period_service.create_period(
        db_session,
        start_date=date(2025, 1, 1),
        fx_rates_input={"USD": "1.05"},
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
    await cell_service.redistribute_for_project(db_session, project_id=project.id)

    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        fx_rates_input={"USD": "1.10"},
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
