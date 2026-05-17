"""Tests for admin moods aggregation endpoint."""

import datetime as dt
from collections.abc import AsyncGenerator
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.rate import RateDB
from app.core.models.user import UserDB
from app.database import get_db
from app.main import app
from app.modules.tracker.models.anonymous_feedback import AnonymousFeedbackDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

USER_ID_1 = UUID("00000000-0000-0000-0000-000000000001")
USER_ID_2 = UUID("00000000-0000-0000-0000-000000000002")


@pytest_asyncio.fixture
async def non_admin_client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient]:
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
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
        estimated=False,
    )
    report2 = ReportDB(
        user_id=USER_ID_2,
        reporting_period_id=period.id,
        mood=2,
        feedback_text=None,
        estimated=False,
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
        resp = await non_admin_client.get("/api/tracker/moods", params={"month": 3, "year": 2026})
        assert resp.status_code == 403

    async def test_get_moods_empty_month(self, client: AsyncClient, mood_data: None) -> None:
        resp = await client.get("/api/tracker/moods", params={"month": 1, "year": 2025})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reports"] == 0
        assert data["average_mood"] is None

    async def test_get_moods_excludes_estimated_reports(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Estimated reports must not contaminate mood aggregation (per CLAUDE
        tracker rule: estimated=True excludes report from burn-style calcs)."""
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
        # Estimated leftover from prior cycle — must be excluded.
        db_session.add(
            ReportDB(
                user_id=USER_ID_1,
                reporting_period_id=period.id,
                mood=2,
                feedback_text="stale",
                estimated=True,
            )
        )
        # Confirmed report — must be the only one counted.
        db_session.add(
            ReportDB(
                user_id=USER_ID_2,
                reporting_period_id=period.id,
                mood=5,
                feedback_text="real",
                estimated=False,
            )
        )
        await db_session.commit()

        resp = await client.get("/api/tracker/moods", params={"month": 3, "year": 2026})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reports"] == 1
        assert data["total_responses"] == 1
        assert data["average_mood"] == 5.0
        assert data["mood_distribution"] == {"5": 1}
        assert len(data["named_feedback"]) == 1
        assert data["named_feedback"][0]["text"] == "real"


def _last_12_completed_months() -> list[tuple[int, int]]:
    today = dt.date.today()
    d = dt.date(today.year, today.month, 1)
    months: list[tuple[int, int]] = []
    for _ in range(12):
        d = dt.date(d.year - 1, 12, 1) if d.month == 1 else dt.date(d.year, d.month - 1, 1)
        months.append((d.month, d.year))
    months.reverse()
    return months


@pytest.mark.asyncio
class TestMoodsTrendEndpoint:
    async def test_get_moods_trend_excludes_estimated_reports(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Trend must apply the same estimated-exclusion rule as monthly."""
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

        # Use a month inside the trend window (last completed month).
        target_month, target_year = _last_12_completed_months()[-1]
        period = ReportingPeriodDB(
            date=dt.date(target_year, target_month, 1),
            base_rate=Decimal("175"),
            status="active",
        )
        db_session.add(period)
        await db_session.flush()
        db_session.add(
            ReportDB(
                user_id=USER_ID_1,
                reporting_period_id=period.id,
                mood=2,
                feedback_text="stale",
                estimated=True,
            )
        )
        db_session.add(
            ReportDB(
                user_id=USER_ID_2,
                reporting_period_id=period.id,
                mood=5,
                feedback_text="real",
                estimated=False,
            )
        )
        await db_session.commit()

        resp = await client.get("/api/tracker/moods/trend")
        assert resp.status_code == 200
        months = resp.json()["months"]
        bucket = next(m for m in months if m["month"] == target_month and m["year"] == target_year)
        assert bucket["total_reports"] == 1
        assert bucket["total_responses"] == 1
        assert bucket["average_mood"] == 5.0

    async def test_get_moods_trend_returns_12_months(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Trend returns exactly 12 chronological entries; missing months → avg=None."""
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
        db_session.add(user1)
        await db_session.flush()

        # Seed only one month within the window — the rest must come back empty.
        window = _last_12_completed_months()
        seeded_month, seeded_year = window[0]
        period = ReportingPeriodDB(
            date=dt.date(seeded_year, seeded_month, 1),
            base_rate=Decimal("175"),
            status="active",
        )
        db_session.add(period)
        await db_session.flush()
        db_session.add(
            ReportDB(
                user_id=USER_ID_1,
                reporting_period_id=period.id,
                mood=4,
                estimated=False,
            )
        )
        await db_session.commit()

        resp = await client.get("/api/tracker/moods/trend")
        assert resp.status_code == 200
        months = resp.json()["months"]
        assert len(months) == 12
        ordered = [(m["month"], m["year"]) for m in months]
        assert ordered == window
        for entry in months:
            if (entry["month"], entry["year"]) == (seeded_month, seeded_year):
                assert entry["average_mood"] == 4.0
                assert entry["total_responses"] == 1
            else:
                assert entry["average_mood"] is None
                assert entry["total_responses"] == 0
                assert entry["total_reports"] == 0

    async def test_get_moods_trend_excludes_current_month(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Trend = last 12 completed months. Current (in-progress) month is excluded."""
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
        db_session.add(user1)
        await db_session.flush()

        today = dt.date.today()
        period = ReportingPeriodDB(
            date=dt.date(today.year, today.month, 1),
            base_rate=Decimal("175"),
            status="active",
        )
        db_session.add(period)
        await db_session.flush()
        db_session.add(
            ReportDB(
                user_id=USER_ID_1,
                reporting_period_id=period.id,
                mood=3,
                estimated=False,
            )
        )
        await db_session.commit()

        resp = await client.get("/api/tracker/moods/trend")
        assert resp.status_code == 200
        months = resp.json()["months"]
        assert all(not (m["month"] == today.month and m["year"] == today.year) for m in months)

    async def test_get_moods_admin_gate_on_trend(
        self, non_admin_client: AsyncClient, mood_data: None
    ) -> None:
        resp = await non_admin_client.get("/api/tracker/moods/trend")
        assert resp.status_code == 403
