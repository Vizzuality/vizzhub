"""Tests for `exchange_rate_service`.

ECB rates are stored as units-per-1-EUR. Conversion direction:
    EUR_amount = original_amount / rate
EUR passthrough: rate = 1.0 so EUR_amount == amount.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.exchange_rate import ExchangeRateDB
from app.core.services.exchange_rate_service import (
    convert_to_eur,
    currency_to_code,
    get_available_currencies,
    get_latest_rate,
)


def test_currency_to_code_normalizes_legacy_label() -> None:
    assert currency_to_code("dollar") == "USD"
    assert currency_to_code("Dollar") == "USD"
    assert currency_to_code("euro") == "EUR"


def test_currency_to_code_uppercases_passthrough() -> None:
    assert currency_to_code("gbp") == "GBP"
    assert currency_to_code("USD") == "USD"


@pytest.mark.asyncio
async def test_convert_to_eur_passthrough(db_session: AsyncSession) -> None:
    """EUR amounts pass through unchanged with no DB lookup."""
    result = await convert_to_eur(db_session, Decimal("100"), "EUR")
    assert result == Decimal("100")


@pytest.mark.asyncio
async def test_convert_to_eur_divides_by_rate(db_session: AsyncSession) -> None:
    """Rate = 1.10 USD per 1 EUR. 110 USD must convert to 100 EUR."""
    db_session.add(
        ExchangeRateDB(
            rate_date=date.today(),
            currency_code="USD",
            rate=Decimal("1.10"),
        )
    )
    await db_session.flush()

    result = await convert_to_eur(db_session, Decimal("110"), "USD")
    assert result is not None
    # 110 / 1.10 == 100
    assert result == Decimal("100")


@pytest.mark.asyncio
async def test_convert_to_eur_normalizes_legacy_label(db_session: AsyncSession) -> None:
    db_session.add(
        ExchangeRateDB(
            rate_date=date.today(),
            currency_code="USD",
            rate=Decimal("2.0"),
        )
    )
    await db_session.flush()

    result = await convert_to_eur(db_session, Decimal("200"), "dollar")
    assert result == Decimal("100")


@pytest.mark.asyncio
async def test_convert_to_eur_returns_none_when_no_rate(db_session: AsyncSession) -> None:
    """No rate stored → None (caller decides how to handle)."""
    result = await convert_to_eur(db_session, Decimal("100"), "XYZ")
    assert result is None


@pytest.mark.asyncio
async def test_get_latest_rate_picks_most_recent_date(db_session: AsyncSession) -> None:
    """When several rates exist, returns the row with the latest rate_date."""
    today = date.today()
    db_session.add_all(
        [
            ExchangeRateDB(
                rate_date=today - timedelta(days=2),
                currency_code="USD",
                rate=Decimal("1.0"),
            ),
            ExchangeRateDB(
                rate_date=today,
                currency_code="USD",
                rate=Decimal("1.25"),
            ),
            ExchangeRateDB(
                rate_date=today - timedelta(days=1),
                currency_code="USD",
                rate=Decimal("1.1"),
            ),
        ]
    )
    await db_session.flush()

    result = await get_latest_rate(db_session, "USD")
    assert result is not None
    rate, rate_date = result
    assert rate == Decimal("1.25")
    assert rate_date == today


@pytest.mark.asyncio
async def test_get_latest_rate_eur_is_synthetic(db_session: AsyncSession) -> None:
    """EUR has no DB row but always returns 1.0."""
    result = await get_latest_rate(db_session, "EUR")
    assert result is not None
    rate, _ = result
    assert rate == Decimal("1.0")


@pytest.mark.asyncio
async def test_convert_to_eur_zero_rate_returns_none(db_session: AsyncSession) -> None:
    """rate=0 must not raise DivisionByZero — return None instead."""
    db_session.add(
        ExchangeRateDB(
            rate_date=date.today(),
            currency_code="USD",
            rate=Decimal("0"),
        )
    )
    await db_session.flush()

    result = await convert_to_eur(db_session, Decimal("100"), "USD")
    assert result is None


@pytest.mark.asyncio
async def test_convert_to_eur_none_code_returns_none(db_session: AsyncSession) -> None:
    """None currency must not raise AttributeError — return None instead."""
    result = await convert_to_eur(db_session, Decimal("100"), None)
    assert result is None


@pytest.mark.asyncio
async def test_convert_to_eur_empty_code_returns_none(db_session: AsyncSession) -> None:
    """Empty-string currency must not silently look up empty code — return None."""
    result = await convert_to_eur(db_session, Decimal("100"), "")
    assert result is None


@pytest.mark.asyncio
async def test_convert_to_eur_at_date_picks_on_or_before_row(db_session: AsyncSession) -> None:
    """Historical lookup picks the latest rate with rate_date <= as_of."""
    db_session.add_all(
        [
            ExchangeRateDB(
                rate_date=date(2024, 1, 15),
                currency_code="USD",
                rate=Decimal("1.10"),
            ),
            ExchangeRateDB(
                rate_date=date(2026, 5, 1),
                currency_code="USD",
                rate=Decimal("1.08"),
            ),
        ]
    )
    await db_session.flush()

    historical = await convert_to_eur(db_session, Decimal("110"), "USD", as_of=date(2024, 6, 1))
    assert historical is not None
    assert historical == Decimal("100")

    latest = await convert_to_eur(db_session, Decimal("108"), "USD")
    assert latest is not None
    assert latest == Decimal("100")


@pytest.mark.asyncio
async def test_get_available_currencies_includes_eur(db_session: AsyncSession) -> None:
    """EUR is added at the head even if no rows for it exist."""
    db_session.add(
        ExchangeRateDB(
            rate_date=date.today(),
            currency_code="USD",
            rate=Decimal("1.1"),
        )
    )
    await db_session.flush()

    codes = await get_available_currencies(db_session)
    assert "EUR" in codes
    assert "USD" in codes
    assert codes[0] == "EUR"
