"""Tests for admin moods aggregation endpoint."""

from collections.abc import AsyncGenerator
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.database import get_db
from app.main import app
from app.core.models.rate import RateDB
from app.core.models.user import UserDB
from app.modules.tracker.models.anonymous_feedback import AnonymousFeedbackDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

import datetime as dt

USER_ID_1 = UUID("00000000-0000-0000-0000-000000000001")
USER_ID_2 = UUID("00000000-0000-0000-0000-000000000002")


@pytest_asyncio.fixture
async def non_admin_client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_get_current_user() -> TokenData:
        return TokenData(
            user_id=str(USER_ID_1),
            email="user@example.com",
            roles=["user"],
            permissions=["tracker:view", "tracker:manage_own_reports"],
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def mood_data(db_session: AsyncSession) -> None:
    rate = RateDB(code="B", value=Decimal("15365"))
    db_session.add(rate)
    await db_session.flush()

    user1 = UserDB(
        id=USER_ID_1,
        email="alice@example.com",
        first_name="Alice",
        last_name="Smith",
        rate_id=rate.id,
    )
    user2 = UserDB(
        id=USER_ID_2,
        email="bob@example.com",
        first_name="Bob",
        last_name="Jones",
        rate_id=rate.id,
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.flush()

    period = ReportingPeriodDB(
        date=dt.date(2026, 3, 1),
        base_rate=Decimal("175"),
        status="active",
    )
    db_session.add(period)
    await db_session.flush()

    report1 = ReportDB(
        user_id=USER_ID_1,
        reporting_period_id=period.id,
        mood=4,
        feedback_text="Great month",
    )
    report2 = ReportDB(
        user_id=USER_ID_2,
        reporting_period_id=period.id,
        mood=2,
        feedback_text=None,
    )
    db_session.add(report1)
    db_session.add(report2)
    await db_session.flush()

    anon = AnonymousFeedbackDB(month=3, year=2026, text="Anonymous note")
    db_session.add(anon)
    await db_session.commit()


@pytest.mark.asyncio
class TestMoodsEndpoint:
    async def test_get_moods_returns_distribution(
        self, client: AsyncClient, mood_data: None
    ) -> None:
        resp = await client.get("/api/tracker/moods", params={"month": 3, "year": 2026})
        assert resp.status_code == 200
        data = resp.json()
        # mood_distribution keys are strings in JSON
        assert data["mood_distribution"]["4"] == 1
        assert data["mood_distribution"]["2"] == 1
        assert data["total_responses"] == 2
        assert data["average_mood"] == 3.0

    async def test_get_moods_includes_anonymous_feedback(
        self, client: AsyncClient, mood_data: None
    ) -> None:
        resp = await client.get("/api/tracker/moods", params={"month": 3, "year": 2026})
        anon = resp.json()["anonymous_feedback"]
        assert any(item["text"] == "Anonymous note" for item in anon)

    async def test_get_moods_includes_named_feedback(
        self, client: AsyncClient, mood_data: None
    ) -> None:
        resp = await client.get("/api/tracker/moods", params={"month": 3, "year": 2026})
        named = resp.json()["named_feedback"]
        assert len(named) == 2

    async def test_get_moods_requires_admin(
        self, non_admin_client: AsyncClient, mood_data: None
    ) -> None:
        resp = await non_admin_client.get(
            "/api/tracker/moods", params={"month": 3, "year": 2026}
        )
        assert resp.status_code == 403

    async def test_get_moods_empty_month(
        self, client: AsyncClient, mood_data: None
    ) -> None:
        resp = await client.get("/api/tracker/moods", params={"month": 1, "year": 2025})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reports"] == 0
        assert data["average_mood"] is None
