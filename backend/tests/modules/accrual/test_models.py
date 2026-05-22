"""Model-layer tests for accrual_periods."""

from datetime import date

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
