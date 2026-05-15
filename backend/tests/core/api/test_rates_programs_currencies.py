"""End-to-end tests for the three small core CRUD endpoints.

Covers `core/api/rates.py`, `core/api/programs.py`, `core/api/currencies.py`
write paths that previously had no integration coverage.
"""

from decimal import Decimal
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.exchange_rate import ExchangeRateDB
from app.core.models.rate import RateDB


@pytest_asyncio.fixture
async def seeded_rate(db_session: AsyncSession) -> RateDB:
    rate = RateDB(code="A", value=Decimal("125"))
    db_session.add(rate)
    await db_session.commit()
    await db_session.refresh(rate)
    return rate


@pytest.mark.asyncio
class TestRatesApi:
    async def test_list_rates(self, client: AsyncClient, seeded_rate: RateDB) -> None:
        resp = await client.get("/api/rates")
        assert resp.status_code == 200
        codes = [r["code"] for r in resp.json()]
        assert "A" in codes

    async def test_create_rate(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/rates",
            json={"code": "B", "value": "100"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["code"] == "B"
        assert Decimal(body["value"]) == Decimal("100")

    async def test_update_rate(self, client: AsyncClient, seeded_rate: RateDB) -> None:
        resp = await client.patch(
            f"/api/rates/{seeded_rate.id}",
            json={"value": "200"},
        )
        assert resp.status_code == 200
        assert Decimal(resp.json()["value"]) == Decimal("200")

    async def test_update_rate_not_found(self, client: AsyncClient) -> None:
        resp = await client.patch(
            "/api/rates/00000000-0000-0000-0000-000000000404",
            json={"value": "1"},
        )
        assert resp.status_code == 404

    async def test_delete_rate(self, client: AsyncClient, seeded_rate: RateDB) -> None:
        resp = await client.delete(f"/api/rates/{seeded_rate.id}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


@pytest.mark.asyncio
class TestProgramsApi:
    async def test_create_and_list(self, client: AsyncClient) -> None:
        resp = await client.post("/api/programs", json={"name": "Climate"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Climate"

        resp = await client.get("/api/programs")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "Climate" in names


@pytest.mark.asyncio
class TestCurrenciesApi:
    async def test_returns_eur_when_empty(self, client: AsyncClient) -> None:
        """EUR is synthetic — no rate row needed."""
        resp = await client.get("/api/currencies")
        assert resp.status_code == 200
        assert "EUR" in resp.json()

    async def test_includes_stored_currency_codes(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        db_session.add(
            ExchangeRateDB(
                rate_date=date.today(),
                currency_code="USD",
                rate=Decimal("1.1"),
            )
        )
        await db_session.commit()

        resp = await client.get("/api/currencies")
        assert resp.status_code == 200
        codes = resp.json()
        assert "USD" in codes
        assert codes[0] == "EUR"
