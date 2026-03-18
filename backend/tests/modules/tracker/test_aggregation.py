"""Tests for project cost aggregation endpoints."""

import datetime as dt
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.rate import RateDB
from app.core.models.user import UserDB
from app.modules.tracker.models.non_staff_cost import NonStaffCostDB
from app.modules.tracker.models.project_settings import TrackerProjectSettingsDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

DEBUG_USER_ID = uuid4()


@pytest_asyncio.fixture
async def cost_data(db_session: AsyncSession) -> dict:
    """Create test data for cost aggregation tests."""
    rate = RateDB(code="B", value=Decimal("15365"))
    db_session.add(rate)
    await db_session.flush()

    func_area = FunctionalAreaDB(name="Backend Developer")
    db_session.add(func_area)
    await db_session.flush()

    user = UserDB(
        id=DEBUG_USER_ID,
        email="cost-test@example.com",
        name="Cost User",
        rate_id=rate.id,
        dedication=Decimal("0.74"),
    )
    db_session.add(user)
    await db_session.flush()

    period1 = ReportingPeriodDB(
        date=dt.date(2026, 2, 1),
        base_rate=Decimal("175"),
        status="active",
    )
    period2 = ReportingPeriodDB(
        date=dt.date(2026, 3, 1),
        base_rate=Decimal("175"),
        status="active",
    )
    db_session.add_all([period1, period2])
    await db_session.flush()

    project = ProjectDB(name="Cost Test Project", status="live")
    db_session.add(project)
    await db_session.flush()

    settings = TrackerProjectSettingsDB(
        project_id=project.id,
        budget=Decimal("50000"),
        contract_rate=Decimal("175"),
    )
    db_session.add(settings)
    await db_session.flush()

    report1 = ReportDB(
        user_id=user.id,
        reporting_period_id=period1.id,
        estimated=False,
    )
    report2 = ReportDB(
        user_id=user.id,
        reporting_period_id=period2.id,
        estimated=False,
    )
    db_session.add_all([report1, report2])
    await db_session.flush()

    part1 = ReportPartDB(
        report_id=report1.id,
        project_id=project.id,
        functional_area_id=func_area.id,
        percentage=Decimal("0.10"),
        cost=Decimal("1137.01"),
        days=Decimal("1.48"),
    )
    part2 = ReportPartDB(
        report_id=report2.id,
        project_id=project.id,
        functional_area_id=func_area.id,
        percentage=Decimal("0.20"),
        cost=Decimal("2274.02"),
        days=Decimal("2.96"),
    )
    db_session.add_all([part1, part2])
    await db_session.flush()

    nsc = NonStaffCostDB(
        project_id=project.id,
        reporting_period_id=period1.id,
        cost=Decimal("500.00"),
        cost_type="travel",
        details="Conference trip",
    )
    db_session.add(nsc)
    await db_session.commit()

    return {
        "rate": rate,
        "user": user,
        "func_area": func_area,
        "period1": period1,
        "period2": period2,
        "project": project,
        "settings": settings,
        "report1": report1,
        "report2": report2,
        "part1": part1,
        "part2": part2,
        "nsc": nsc,
    }


class TestCostSummary:
    @pytest.mark.asyncio
    async def test_cost_summary_totals(
        self, client: AsyncClient, cost_data: dict,
    ):
        project_id = cost_data["project"].id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/cost-summary",
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["staff_cost"] == pytest.approx(3411.03, rel=1e-4)
        assert data["non_staff_cost"] == pytest.approx(500.0, rel=1e-4)
        assert data["total_cost"] == pytest.approx(3911.03, rel=1e-4)
        assert data["burn_percentage"] == pytest.approx(7.82206, rel=1e-3)
        assert len(data["periods"]) == 2

    @pytest.mark.asyncio
    async def test_cost_summary_period_breakdown(
        self, client: AsyncClient, cost_data: dict,
    ):
        project_id = cost_data["project"].id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/cost-summary",
        )
        data = resp.json()
        periods = data["periods"]

        # Ordered by date desc: March first, then February
        march = periods[0]
        assert march["date"] == "2026-03-01"
        assert march["staff_cost"] == pytest.approx(2274.02, rel=1e-4)
        assert march["non_staff_cost"] == pytest.approx(0.0)
        assert march["total"] == pytest.approx(2274.02, rel=1e-4)

        feb = periods[1]
        assert feb["date"] == "2026-02-01"
        assert feb["staff_cost"] == pytest.approx(1137.01, rel=1e-4)
        assert feb["non_staff_cost"] == pytest.approx(500.0)
        assert feb["total"] == pytest.approx(1637.01, rel=1e-4)

    @pytest.mark.asyncio
    async def test_cost_summary_no_budget(
        self, client: AsyncClient, cost_data: dict, db_session: AsyncSession,
    ):
        settings = cost_data["settings"]
        settings.budget = None
        await db_session.commit()

        project_id = cost_data["project"].id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/cost-summary",
        )
        data = resp.json()
        assert data["budget"] is None
        assert data["burn_percentage"] is None

    @pytest.mark.asyncio
    async def test_cost_summary_excludes_estimated(
        self, client: AsyncClient, cost_data: dict, db_session: AsyncSession,
    ):
        user2 = UserDB(
            email="estimated@example.com",
            name="Estimated User",
            rate_id=cost_data["rate"].id,
            dedication=Decimal("1.0"),
        )
        db_session.add(user2)
        await db_session.flush()

        estimated_report = ReportDB(
            user_id=user2.id,
            reporting_period_id=cost_data["period1"].id,
            estimated=True,
        )
        db_session.add(estimated_report)
        await db_session.flush()

        estimated_part = ReportPartDB(
            report_id=estimated_report.id,
            project_id=cost_data["project"].id,
            percentage=Decimal("0.50"),
            cost=Decimal("9999.99"),
            days=Decimal("10.0"),
        )
        db_session.add(estimated_part)
        await db_session.commit()

        project_id = cost_data["project"].id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/cost-summary",
        )
        data = resp.json()
        assert data["staff_cost"] == pytest.approx(3411.03, rel=1e-4)

    @pytest.mark.asyncio
    async def test_cost_summary_empty_project(
        self, client: AsyncClient, cost_data: dict, db_session: AsyncSession,
    ):
        empty_project = ProjectDB(name="Empty Project", status="live")
        db_session.add(empty_project)
        await db_session.commit()

        resp = await client.get(
            f"/api/tracker/projects/{empty_project.id}/cost-summary",
        )
        data = resp.json()
        assert data["staff_cost"] == pytest.approx(0)
        assert data["non_staff_cost"] == pytest.approx(0)
        assert data["total_cost"] == pytest.approx(0)
        assert data["burn_percentage"] is None
        assert data["periods"] == []


class TestBatchCosts:
    @pytest.mark.asyncio
    async def test_batch_returns_costs_for_multiple_projects(
        self, client: AsyncClient, cost_data: dict,
    ):
        project_id = str(cost_data["project"].id)
        resp = await client.post(
            "/api/tracker/projects/batch-costs",
            json={"project_ids": [project_id]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert project_id in data["costs"]
        costs = data["costs"][project_id]
        assert costs["staff_cost"] == pytest.approx(3411.03, rel=1e-4)
        assert costs["non_staff_cost"] == pytest.approx(500.0, rel=1e-4)
        assert costs["total_cost"] == pytest.approx(3911.03, rel=1e-4)
        assert costs["budget"] == pytest.approx(50000)
        assert costs["burn_percentage"] == pytest.approx(7.82, abs=0.01)

    @pytest.mark.asyncio
    async def test_batch_empty_project(
        self, client: AsyncClient, cost_data: dict, db_session: AsyncSession,
    ):
        empty = ProjectDB(name="Empty", status="live")
        db_session.add(empty)
        await db_session.commit()
        await db_session.refresh(empty)

        resp = await client.post(
            "/api/tracker/projects/batch-costs",
            json={"project_ids": [str(empty.id)]},
        )
        assert resp.status_code == 200
        data = resp.json()
        costs = data["costs"][str(empty.id)]
        assert costs["total_cost"] == pytest.approx(0)
        assert costs["budget"] is None
        assert costs["burn_percentage"] is None

    @pytest.mark.asyncio
    async def test_batch_empty_request_rejected(
        self, client: AsyncClient, cost_data: dict,
    ):
        resp = await client.post(
            "/api/tracker/projects/batch-costs",
            json={"project_ids": []},
        )
        assert resp.status_code == 400


class TestProjectReportParts:
    @pytest.mark.asyncio
    async def test_list_all_parts(
        self, client: AsyncClient, cost_data: dict,
    ):
        project_id = cost_data["project"].id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/report-parts",
        )
        assert resp.status_code == 200
        parts = resp.json()
        assert len(parts) == 2

        # Ordered by date desc: March part first
        assert parts[0]["period_date"] == "2026-03-01"
        assert parts[0]["user_name"] == "Cost User"
        assert parts[0]["functional_area"] == "Backend Developer"
        assert parts[0]["cost"] == pytest.approx(2274.02, rel=1e-4)

        assert parts[1]["period_date"] == "2026-02-01"
        assert parts[1]["cost"] == pytest.approx(1137.01, rel=1e-4)

    @pytest.mark.asyncio
    async def test_filter_by_period(
        self, client: AsyncClient, cost_data: dict,
    ):
        project_id = cost_data["project"].id
        period_id = cost_data["period1"].id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/report-parts",
            params={"period_id": str(period_id)},
        )
        assert resp.status_code == 200
        parts = resp.json()
        assert len(parts) == 1
        assert parts[0]["period_date"] == "2026-02-01"
        assert parts[0]["cost"] == pytest.approx(1137.01, rel=1e-4)
