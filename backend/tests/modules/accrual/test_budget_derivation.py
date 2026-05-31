"""Tests for accrual budget derivation (FX conversion + line build)."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accrual.models.accrual_period import AccrualPeriodDB
from app.modules.accrual.services import budget_derivation


@pytest.mark.asyncio
async def test_convert_eur_passthrough(db_session: AsyncSession) -> None:
    result = await budget_derivation.convert_original_budget(
        db_session, original_budget=Decimal("1000"), currency="EUR", start_date=date(2026, 3, 1)
    )
    assert result == Decimal("1000.00")


@pytest.mark.asyncio
async def test_convert_uses_period_rate(db_session: AsyncSession) -> None:
    db_session.add(
        AccrualPeriodDB(start_date=date(2026, 1, 1), status="open", fx_rates={"USD": "1.25"})
    )
    await db_session.flush()
    result = await budget_derivation.convert_original_budget(
        db_session, original_budget=Decimal("1000"), currency="dollar", start_date=date(2026, 6, 1)
    )
    assert result == Decimal("800.00")  # 1000 / 1.25


@pytest.mark.asyncio
async def test_convert_falls_back_to_ecb(db_session: AsyncSession) -> None:
    from app.core.models.exchange_rate import ExchangeRateDB

    db_session.add(AccrualPeriodDB(start_date=date(2026, 1, 1), status="open", fx_rates={}))
    db_session.add(
        ExchangeRateDB(rate_date=date(2026, 1, 15), currency_code="USD", rate=Decimal("1.10"))
    )
    await db_session.flush()
    result = await budget_derivation.convert_original_budget(
        db_session, original_budget=Decimal("1100"), currency="USD", start_date=date(2026, 6, 1)
    )
    assert result == Decimal("1000.00")  # 1100 / 1.10


@pytest.mark.asyncio
async def test_convert_returns_none_when_no_rate(db_session: AsyncSession) -> None:
    result = await budget_derivation.convert_original_budget(
        db_session, original_budget=Decimal("1000"), currency="ZWL", start_date=date(2026, 6, 1)
    )
    assert result is None
