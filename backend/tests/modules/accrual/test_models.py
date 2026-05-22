"""Model-layer tests for accrual_periods and project_accrual_cells."""

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
        fx_rates={"USD": "1.10", "GBP": "0.85"},
    )
    db_session.add(period)
    await db_session.flush()
    assert period.id is not None
    assert period.created_at is not None


@pytest.mark.asyncio
async def test_cannot_persist_two_open(db_session: AsyncSession) -> None:
    db_session.add(AccrualPeriodDB(start_date=date(2025, 1, 1), status="open", fx_rates={}))
    await db_session.flush()
    db_session.add(AccrualPeriodDB(start_date=date(2026, 1, 1), status="open", fx_rates={}))
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
            fx_rates={},
            closed_at=None,
        )
    )
    with pytest.raises(Exception) as exc_info:
        await db_session.flush()
    msg = str(exc_info.value).lower()
    assert "ck_accrual_periods_closed_status_consistent" in msg or "check" in msg


def test_accrual_period_create_rejects_bad_currency_code() -> None:
    from pydantic import ValidationError

    from app.modules.accrual.schemas import AccrualPeriodCreate

    with pytest.raises(ValidationError, match="currency code"):
        AccrualPeriodCreate(start_date=date(2026, 1, 1), fx_rates={"usd": "1.10"})  # lowercase
    with pytest.raises(ValidationError, match="currency code"):
        AccrualPeriodCreate(start_date=date(2026, 1, 1), fx_rates={"DOLLAR": "1.10"})  # not 3 chars


def test_accrual_period_create_rejects_non_positive_rate() -> None:
    from pydantic import ValidationError

    from app.modules.accrual.schemas import AccrualPeriodCreate

    with pytest.raises(ValidationError, match="must be > 0"):
        AccrualPeriodCreate(start_date=date(2026, 1, 1), fx_rates={"USD": "0"})
    with pytest.raises(ValidationError, match="must be > 0"):
        AccrualPeriodCreate(start_date=date(2026, 1, 1), fx_rates={"USD": "-1.10"})


def test_accrual_period_create_rejects_non_numeric_rate() -> None:
    from pydantic import ValidationError

    from app.modules.accrual.schemas import AccrualPeriodCreate

    with pytest.raises(ValidationError, match="Invalid rate"):
        AccrualPeriodCreate(start_date=date(2026, 1, 1), fx_rates={"USD": "not_a_number"})


def test_accrual_period_create_happy_path() -> None:
    from app.modules.accrual.schemas import AccrualPeriodCreate

    payload = AccrualPeriodCreate(start_date=date(2026, 1, 1), fx_rates={"USD": "1.10"})
    assert payload.start_date == date(2026, 1, 1)
    assert payload.fx_rates == {"USD": "1.10"}


@pytest.mark.asyncio
async def test_persist_live_cell(db_session: AsyncSession) -> None:
    from app.core.models.project import ProjectDB
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB

    project = ProjectDB(name="Test", status="live", currency="USD", budget=Decimal("1200"))
    db_session.add(project)
    await db_session.flush()
    cell = ProjectAccrualCellDB(
        project_id=project.id,
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
    from app.core.models.project import ProjectDB
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB

    project = ProjectDB(name="Test", status="live", currency="USD", budget=Decimal("1200"))
    db_session.add(project)
    await db_session.flush()
    cell = ProjectAccrualCellDB(
        project_id=project.id,
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
    from app.core.models.project import ProjectDB
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB

    project = ProjectDB(name="Test", status="live", currency="USD", budget=Decimal("1200"))
    db_session.add(project)
    await db_session.flush()
    db_session.add(
        ProjectAccrualCellDB(
            project_id=project.id,
            year=2026,
            month=13,
            amount=Decimal("100"),
        )
    )
    with pytest.raises(Exception):
        await db_session.flush()
