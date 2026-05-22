"""Unit tests for period_service."""

from datetime import date
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
