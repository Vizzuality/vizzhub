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
from app.modules.tracker.models.report_part import ReportPartDB
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
        assert data["estimated"] is True
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


class TestConfirmValidation:
    """Confirm (estimated=false) requires parts totaling 100%."""

    async def _create_report_with_full_allocation(
        self, client: AsyncClient, setup_reporting: dict,
    ) -> str:
        resp = await client.post(
            "/api/tracker/reports",
            json={"reporting_period_id": str(setup_reporting["period"].id), "estimated": True},
        )
        assert resp.status_code == 201
        report_id = resp.json()["id"]
        await client.post(
            "/api/tracker/report-parts",
            json={
                "report_id": report_id,
                "project_id": str(setup_reporting["project"].id),
                "percentage": 1.0,
            },
        )
        return report_id

    @pytest.mark.asyncio
    async def test_confirm_rejected_when_not_100_percent(
        self, client: AsyncClient, setup_reporting: dict
    ):
        resp = await client.post(
            "/api/tracker/reports",
            json={"reporting_period_id": str(setup_reporting["period"].id), "estimated": True},
        )
        report_id = resp.json()["id"]
        await client.post(
            "/api/tracker/report-parts",
            json={
                "report_id": report_id,
                "project_id": str(setup_reporting["project"].id),
                "percentage": 0.5,
            },
        )
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"estimated": False},
        )
        assert resp.status_code == 400
        assert "100%" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_confirm_rejected_when_no_parts(
        self, client: AsyncClient, setup_reporting: dict
    ):
        resp = await client.post(
            "/api/tracker/reports",
            json={"reporting_period_id": str(setup_reporting["period"].id), "estimated": True},
        )
        report_id = resp.json()["id"]
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"estimated": False},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_confirm_accepted_when_100_percent(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = await self._create_report_with_full_allocation(client, setup_reporting)
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"estimated": False},
        )
        assert resp.status_code == 200
        assert resp.json()["estimated"] is False

    @pytest.mark.asyncio
    async def test_reopen_does_not_require_100_percent(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = await self._create_report_with_full_allocation(client, setup_reporting)
        await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"estimated": False},
        )
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"estimated": True},
        )
        assert resp.status_code == 200
        assert resp.json()["estimated"] is True


class TestMoodOnReport:
    """Test mood and feedback_text fields on report update."""

    async def _create_confirmed_report(
        self, client: AsyncClient, setup_reporting: dict
    ) -> str:
        resp = await client.post(
            "/api/tracker/reports",
            json={"reporting_period_id": str(setup_reporting["period"].id), "estimated": True},
        )
        assert resp.status_code == 201
        report_id = resp.json()["id"]
        await client.post(
            "/api/tracker/report-parts",
            json={
                "report_id": report_id,
                "project_id": str(setup_reporting["project"].id),
                "percentage": 1.0,
            },
        )
        await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"estimated": False},
        )
        return report_id

    @pytest.mark.asyncio
    async def test_update_report_with_mood(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = await self._create_confirmed_report(client, setup_reporting)
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"mood": 4},
        )
        assert resp.status_code == 200
        assert resp.json()["mood"] == 4

    @pytest.mark.asyncio
    async def test_update_report_mood_out_of_range(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = await self._create_confirmed_report(client, setup_reporting)
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"mood": 6},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_report_mood_zero_rejected(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = await self._create_confirmed_report(client, setup_reporting)
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"mood": 0},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_report_with_feedback_text(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = await self._create_confirmed_report(client, setup_reporting)
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"feedback_text": "Great month!"},
        )
        assert resp.status_code == 200
        assert resp.json()["feedback_text"] == "Great month!"

    @pytest.mark.asyncio
    async def test_update_report_mood_null_clears(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = await self._create_confirmed_report(client, setup_reporting)
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


class TestPrepopulateParts:
    """Creating a report copies parts from the previous period, with filters."""

    async def _seed_prev_report_with_parts(
        self,
        db_session: AsyncSession,
        setup_reporting: dict,
        prev_parts: list[tuple[ProjectDB, Decimal | None]],
    ) -> ReportingPeriodDB:
        """Create a previous period + report owned by setup_reporting['user']
        with the given (project, percentage) parts. Returns the new active period."""
        prev_period = ReportingPeriodDB(
            date=dt.date(2026, 2, 1), base_rate=Decimal("175"), status="closed",
        )
        db_session.add(prev_period)
        await db_session.flush()

        prev_report = ReportDB(
            user_id=setup_reporting["user"].id,
            reporting_period_id=prev_period.id,
            estimated=False,
        )
        db_session.add(prev_report)
        await db_session.flush()

        for project, pct in prev_parts:
            db_session.add(ReportPartDB(
                report_id=prev_report.id,
                project_id=project.id,
                percentage=pct,
            ))
        await db_session.commit()

        # Move the active period to one strictly after prev_period.
        active = setup_reporting["period"]
        active.date = dt.date(2026, 3, 1)
        await db_session.commit()
        return active

    @pytest.mark.asyncio
    async def test_skips_finished_projects(
        self,
        client: AsyncClient,
        setup_reporting: dict,
        db_session: AsyncSession,
    ):
        live = setup_reporting["project"]
        finished = ProjectDB(name="Old", status="finished")
        db_session.add(finished)
        await db_session.flush()

        active = await self._seed_prev_report_with_parts(
            db_session, setup_reporting,
            [(live, Decimal("0.6")), (finished, Decimal("0.4"))],
        )

        resp = await client.post(
            "/api/tracker/reports",
            json={"reporting_period_id": str(active.id)},
        )
        assert resp.status_code == 201
        report_id = resp.json()["id"]

        detail = await client.get(f"/api/tracker/reports/{report_id}")
        project_ids = {p["project_id"] for p in detail.json()["parts"]}
        assert str(live.id) in project_ids
        assert str(finished.id) not in project_ids

    @pytest.mark.asyncio
    async def test_skips_zero_or_null_percentage_parts(
        self,
        client: AsyncClient,
        setup_reporting: dict,
        db_session: AsyncSession,
    ):
        live = setup_reporting["project"]
        zero_project = ProjectDB(name="ZeroPct", status="live")
        null_project = ProjectDB(name="NullPct", status="live")
        db_session.add_all([zero_project, null_project])
        await db_session.flush()

        active = await self._seed_prev_report_with_parts(
            db_session, setup_reporting,
            [
                (live, Decimal("1.0")),
                (zero_project, Decimal("0")),
                (null_project, None),
            ],
        )

        resp = await client.post(
            "/api/tracker/reports",
            json={"reporting_period_id": str(active.id)},
        )
        assert resp.status_code == 201
        report_id = resp.json()["id"]

        detail = await client.get(f"/api/tracker/reports/{report_id}")
        project_ids = {p["project_id"] for p in detail.json()["parts"]}
        assert str(live.id) in project_ids
        assert str(zero_project.id) not in project_ids
        assert str(null_project.id) not in project_ids
