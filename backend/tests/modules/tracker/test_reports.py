"""Tests for report and report_part endpoints."""

import datetime as dt
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.rate import RateDB
from app.core.models.user import UserDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
from app.modules.tracker.models.project_settings import TrackerProjectSettingsDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.core.models.project import ProjectDB


@pytest_asyncio.fixture
async def setup_reporting(db_session: AsyncSession) -> dict:
    """Create test data: period, user with rate, project with settings."""
    rate = RateDB(code="B", value=Decimal("15365"))
    db_session.add(rate)
    await db_session.flush()

    user = UserDB(
        id=DEBUG_USER_ID,
        email="test@example.com",
        name="Test User",
        rate_id=rate.id,
        dedication=Decimal("0.74"),
    )
    db_session.add(user)
    await db_session.flush()

    period = ReportingPeriodDB(
        date=dt.date(2026, 3, 1), base_rate=Decimal("175"), status="active",
    )
    db_session.add(period)
    await db_session.flush()

    project = ProjectDB(name="Test Project", status="live")
    db_session.add(project)
    await db_session.flush()

    settings = TrackerProjectSettingsDB(
        project_id=project.id, contract_rate=Decimal("175"),
    )
    db_session.add(settings)
    await db_session.commit()

    await db_session.refresh(rate)
    await db_session.refresh(user)
    await db_session.refresh(period)
    await db_session.refresh(project)
    await db_session.refresh(settings)

    return {
        "rate": rate,
        "user": user,
        "period": period,
        "project": project,
        "settings": settings,
    }


class TestReportsCRUD:
    @pytest.mark.asyncio
    async def test_create_report(
        self, client: AsyncClient, setup_reporting: dict,
    ):
        resp = await client.post(
            "/api/tracker/reports",
            json={
                "reporting_period_id": str(setup_reporting["period"].id),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["estimated"] is False
        assert data["user_id"] == str(DEBUG_USER_ID)
        assert data["user_name"] == "Test User"

    @pytest.mark.asyncio
    async def test_duplicate_report_returns_409(
        self, client: AsyncClient, setup_reporting: dict,
    ):
        payload = {
            "reporting_period_id": str(setup_reporting["period"].id),
        }
        await client.post("/api/tracker/reports", json=payload)
        resp = await client.post("/api/tracker/reports", json=payload)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_list_reports_by_period(
        self, client: AsyncClient, setup_reporting: dict,
    ):
        await client.post(
            "/api/tracker/reports",
            json={
                "reporting_period_id": str(setup_reporting["period"].id),
            },
        )
        resp = await client.get(
            "/api/tracker/reports",
            params={"reporting_period_id": str(setup_reporting["period"].id)},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_get_report_with_parts(
        self, client: AsyncClient, setup_reporting: dict,
    ):
        create_resp = await client.post(
            "/api/tracker/reports",
            json={
                "reporting_period_id": str(setup_reporting["period"].id),
            },
        )
        report_id = create_resp.json()["id"]
        resp = await client.get(f"/api/tracker/reports/{report_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["parts"] == []
        assert data["user_name"] == "Test User"

    @pytest.mark.asyncio
    async def test_delete_report(
        self, client: AsyncClient, setup_reporting: dict,
    ):
        create_resp = await client.post(
            "/api/tracker/reports",
            json={
                "reporting_period_id": str(setup_reporting["period"].id),
            },
        )
        report_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/tracker/reports/{report_id}")
        assert resp.status_code == 204


class TestReportPartsCRUD:
    @pytest.mark.asyncio
    async def test_create_part_with_cost_calculation(
        self, client: AsyncClient, setup_reporting: dict,
    ):
        report_resp = await client.post(
            "/api/tracker/reports",
            json={
                "reporting_period_id": str(setup_reporting["period"].id),
            },
        )
        report_id = report_resp.json()["id"]

        resp = await client.post(
            "/api/tracker/report-parts",
            json={
                "report_id": report_id,
                "project_id": str(setup_reporting["project"].id),
                "percentage": 0.20,
            },
        )
        assert resp.status_code == 201
        data = resp.json()

        expected_cost = float(
            Decimal("0.20") * Decimal("15365") * Decimal("0.74")
            * (Decimal("175") / Decimal("175"))
        )
        expected_days = float(Decimal("0.20") * Decimal("20") * Decimal("0.74"))

        assert data["cost"] == pytest.approx(expected_cost, rel=1e-4)
        assert data["days"] == pytest.approx(expected_days, rel=1e-4)

    @pytest.mark.asyncio
    async def test_update_part_recalculates_cost(
        self, client: AsyncClient, setup_reporting: dict,
    ):
        report_resp = await client.post(
            "/api/tracker/reports",
            json={
                "reporting_period_id": str(setup_reporting["period"].id),
            },
        )
        report_id = report_resp.json()["id"]

        create_resp = await client.post(
            "/api/tracker/report-parts",
            json={
                "report_id": report_id,
                "project_id": str(setup_reporting["project"].id),
                "percentage": 0.20,
            },
        )
        part_id = create_resp.json()["id"]
        original_cost = create_resp.json()["cost"]

        resp = await client.put(
            f"/api/tracker/report-parts/{part_id}",
            json={"percentage": 0.40},
        )
        assert resp.status_code == 200
        assert resp.json()["cost"] == pytest.approx(original_cost * 2, rel=1e-4)

    @pytest.mark.asyncio
    async def test_list_parts_by_report(
        self, client: AsyncClient, setup_reporting: dict,
    ):
        report_resp = await client.post(
            "/api/tracker/reports",
            json={
                "reporting_period_id": str(setup_reporting["period"].id),
            },
        )
        report_id = report_resp.json()["id"]

        await client.post(
            "/api/tracker/report-parts",
            json={
                "report_id": report_id,
                "project_id": str(setup_reporting["project"].id),
                "percentage": 0.20,
            },
        )

        resp = await client.get(
            "/api/tracker/report-parts",
            params={"report_id": report_id},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_delete_part(
        self, client: AsyncClient, setup_reporting: dict,
    ):
        report_resp = await client.post(
            "/api/tracker/reports",
            json={
                "reporting_period_id": str(setup_reporting["period"].id),
            },
        )
        report_id = report_resp.json()["id"]

        create_resp = await client.post(
            "/api/tracker/report-parts",
            json={
                "report_id": report_id,
                "project_id": str(setup_reporting["project"].id),
                "percentage": 0.20,
            },
        )
        part_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/tracker/report-parts/{part_id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_cost_with_different_contract_rate(
        self, client: AsyncClient, setup_reporting: dict, db_session: AsyncSession,
    ):
        """Contract rate 210 with base 175 → multiplier 1.2."""
        settings = setup_reporting["settings"]
        settings.contract_rate = Decimal("210")
        await db_session.commit()

        report_resp = await client.post(
            "/api/tracker/reports",
            json={
                "reporting_period_id": str(setup_reporting["period"].id),
            },
        )
        report_id = report_resp.json()["id"]

        resp = await client.post(
            "/api/tracker/report-parts",
            json={
                "report_id": report_id,
                "project_id": str(setup_reporting["project"].id),
                "percentage": 0.20,
            },
        )
        assert resp.status_code == 201

        multiplier = 210.0 / 175.0
        base_cost = 0.20 * 15365 * 0.74
        expected_cost = base_cost * multiplier

        assert resp.json()["cost"] == pytest.approx(expected_cost, rel=1e-4)


class TestMoodOnReport:
    """Test mood and feedback_text fields on report update."""

    async def _create_report(self, client: AsyncClient, setup_reporting: dict) -> str:
        resp = await client.post(
            "/api/tracker/reports",
            json={"reporting_period_id": str(setup_reporting["period"].id)},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    @pytest.mark.asyncio
    async def test_update_report_with_mood(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = await self._create_report(client, setup_reporting)
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"estimated": False, "mood": 4},
        )
        assert resp.status_code == 200
        assert resp.json()["mood"] == 4

    @pytest.mark.asyncio
    async def test_update_report_mood_out_of_range(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = await self._create_report(client, setup_reporting)
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"mood": 6},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_report_mood_zero_rejected(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = await self._create_report(client, setup_reporting)
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"mood": 0},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_report_with_feedback_text(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = await self._create_report(client, setup_reporting)
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"estimated": False, "feedback_text": "Great month!"},
        )
        assert resp.status_code == 200
        assert resp.json()["feedback_text"] == "Great month!"

    @pytest.mark.asyncio
    async def test_update_report_mood_null_clears(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = await self._create_report(client, setup_reporting)
        await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"mood": 3},
        )
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"mood": None},
        )
        assert resp.status_code == 200
        assert resp.json()["mood"] is None
