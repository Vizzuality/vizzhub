"""Unit tests for rate_resolver.

Resolution order:
1. project.locked_fx_rate (per-project override).
2. project.currency == EUR → Decimal('1').
3. Period for (year, month) has the currency → period rate.
4. ECB latest rate for currency on/before first-of-month.
5. None.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.accrual.services import period_service, rate_resolver


@pytest.mark.asyncio
async def test_locked_fx_rate_overrides_period(db_session: AsyncSession) -> None:
    project = ProjectDB(
        name="A",
        status="live",
        currency="USD",
        budget=Decimal("100"),
        locked_fx_rate=Decimal("1.20"),
    )
    db_session.add(project)
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        fx_rates_input={"USD": "1.10"},
        created_by=None,
    )
    await db_session.flush()
    rate = await rate_resolver.resolve_rate(db_session, project=project, year=2026, month=3)
    assert rate == Decimal("1.20")


@pytest.mark.asyncio
async def test_eur_currency_returns_one(db_session: AsyncSession) -> None:
    project = ProjectDB(name="A", status="live", currency="EUR", budget=Decimal("100"))
    db_session.add(project)
    await db_session.flush()
    rate = await rate_resolver.resolve_rate(db_session, project=project, year=2026, month=3)
    assert rate == Decimal("1")


@pytest.mark.asyncio
async def test_legacy_euro_label_returns_one(db_session: AsyncSession) -> None:
    """Legacy 'euro' (lowercase, pre-ISO) must normalise to EUR."""
    project = ProjectDB(name="A", status="live", currency="euro", budget=Decimal("100"))
    db_session.add(project)
    await db_session.flush()
    rate = await rate_resolver.resolve_rate(db_session, project=project, year=2026, month=3)
    assert rate == Decimal("1")


@pytest.mark.asyncio
async def test_legacy_dollar_label_uses_period_usd(db_session: AsyncSession) -> None:
    """Legacy 'dollar' (lowercase, pre-ISO) must map to USD and hit period rate."""
    project = ProjectDB(name="A", status="live", currency="dollar", budget=Decimal("100"))
    db_session.add(project)
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        fx_rates_input={"USD": "1.10"},
        created_by=None,
    )
    await db_session.flush()
    rate = await rate_resolver.resolve_rate(db_session, project=project, year=2026, month=3)
    assert rate == Decimal("1.10")


@pytest.mark.asyncio
async def test_uses_period_rate(db_session: AsyncSession) -> None:
    project = ProjectDB(name="A", status="live", currency="USD", budget=Decimal("100"))
    db_session.add(project)
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        fx_rates_input={"USD": "1.10"},
        created_by=None,
    )
    await db_session.flush()
    rate = await rate_resolver.resolve_rate(db_session, project=project, year=2026, month=3)
    assert rate == Decimal("1.10")


@pytest.mark.asyncio
async def test_fallback_to_ecb_when_period_missing_currency(db_session: AsyncSession) -> None:
    from app.core.models.exchange_rate import ExchangeRateDB

    project = ProjectDB(name="A", status="live", currency="CHF", budget=Decimal("100"))
    db_session.add(project)
    db_session.add(
        ExchangeRateDB(
            rate_date=date(2026, 2, 1),
            currency_code="CHF",
            rate=Decimal("0.95"),
        )
    )
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        fx_rates_input={"USD": "1.10"},
        created_by=None,
    )
    await db_session.flush()
    rate = await rate_resolver.resolve_rate(db_session, project=project, year=2026, month=3)
    assert rate == Decimal("0.95")


@pytest.mark.asyncio
async def test_returns_none_when_no_resolution(db_session: AsyncSession) -> None:
    project = ProjectDB(name="A", status="live", currency="JPY", budget=Decimal("100"))
    db_session.add(project)
    await period_service.create_period(
        db_session,
        start_date=date(2026, 1, 1),
        fx_rates_input={"USD": "1.10"},
        created_by=None,
    )
    await db_session.flush()
    rate = await rate_resolver.resolve_rate(db_session, project=project, year=2026, month=3)
    assert rate is None


@pytest.mark.asyncio
async def test_locked_override_wins_even_without_period(db_session: AsyncSession) -> None:
    project = ProjectDB(
        name="A",
        status="live",
        currency="JPY",
        budget=Decimal("100"),
        locked_fx_rate=Decimal("160.5"),
    )
    db_session.add(project)
    await db_session.flush()
    rate = await rate_resolver.resolve_rate(db_session, project=project, year=2026, month=3)
    assert rate == Decimal("160.5")
