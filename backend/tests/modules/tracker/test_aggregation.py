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

    project = ProjectDB(name="Cost Test Project", status="live", budget=Decimal("50000"))
    db_session.add(project)
    await db_session.flush()

    settings = TrackerProjectSettingsDB(
        project_id=project.id,
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
        self,
        client: AsyncClient,
        cost_data: dict,
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
        # Single and batch now share a rounding policy: round(total_cost, 2)
        # before divide, then round burn% to 2dp.
        assert data["burn_percentage"] == 7.82
        assert len(data["periods"]) == 2

    @pytest.mark.asyncio
    async def test_cost_summary_period_breakdown(
        self,
        client: AsyncClient,
        cost_data: dict,
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
        self,
        client: AsyncClient,
        cost_data: dict,
        db_session: AsyncSession,
    ):
        project = cost_data["project"]
        project.budget = None
        await db_session.commit()

        project_id = project.id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/cost-summary",
        )
        data = resp.json()
        assert data["budget"] is None
        assert data["burn_percentage"] is None

    @pytest.mark.asyncio
    async def test_cost_summary_excludes_estimated(
        self,
        client: AsyncClient,
        cost_data: dict,
        db_session: AsyncSession,
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
        self,
        client: AsyncClient,
        cost_data: dict,
        db_session: AsyncSession,
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

    @pytest.mark.asyncio
    async def test_cost_summary_budget_zero_returns_null_burn(
        self,
        client: AsyncClient,
        cost_data: dict,
        db_session: AsyncSession,
    ):
        """budget == 0 returns null burn% (NOT ZeroDivisionError).

        Pins the "null when zero" rule distinct from "null when None"
        so the explicit `budget is None or budget == 0` guard can't be
        accidentally collapsed back to `if budget`.
        """
        project = cost_data["project"]
        project.budget = Decimal("0")
        await db_session.commit()

        resp = await client.get(
            f"/api/tracker/projects/{project.id}/cost-summary",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["budget"] == 0
        # report parts exist (cost > 0) but budget=0 → null, not crash
        assert data["total_cost"] > 0
        assert data["burn_percentage"] is None

    @pytest.mark.asyncio
    async def test_cost_summary_overrun(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Uncapped overrun: cost > budget yields >100% (pin design choice)."""
        rate = RateDB(code="OV", value=Decimal("15365"))
        db_session.add(rate)
        await db_session.flush()

        user = UserDB(
            email="overrun-user@example.com",
            name="Overrun User",
            rate_id=rate.id,
            dedication=Decimal("1.0"),
        )
        db_session.add(user)
        await db_session.flush()

        period = ReportingPeriodDB(
            date=dt.date(2026, 4, 1),
            base_rate=Decimal("175"),
            status="active",
        )
        db_session.add(period)
        await db_session.flush()

        project = ProjectDB(name="Overrun Project", status="live", budget=Decimal("1000"))
        db_session.add(project)
        await db_session.flush()

        report = ReportDB(
            user_id=user.id,
            reporting_period_id=period.id,
            estimated=False,
        )
        db_session.add(report)
        await db_session.flush()

        part = ReportPartDB(
            report_id=report.id,
            project_id=project.id,
            percentage=Decimal("0.50"),
            cost=Decimal("1500.00"),
            days=Decimal("10.0"),
        )
        db_session.add(part)
        await db_session.commit()

        resp = await client.get(
            f"/api/tracker/projects/{project.id}/cost-summary",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost"] == pytest.approx(1500.0)
        # 1500 / 1000 * 100 = 150.0 exactly. Uncapped.
        assert data["burn_percentage"] == 150.0

    @pytest.mark.asyncio
    async def test_cost_summary_zero_cost_positive_budget(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Budget>0 with no report parts → burn% = 0.0, NOT null."""
        project = ProjectDB(name="No-Activity Project", status="live", budget=Decimal("50000"))
        db_session.add(project)
        await db_session.commit()

        resp = await client.get(
            f"/api/tracker/projects/{project.id}/cost-summary",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost"] == pytest.approx(0)
        assert data["burn_percentage"] == 0.0


class TestBatchCosts:
    @pytest.mark.asyncio
    async def test_batch_returns_costs_for_multiple_projects(
        self,
        client: AsyncClient,
        cost_data: dict,
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
        assert costs["burn_percentage"] == 7.82

    @pytest.mark.asyncio
    async def test_batch_empty_project(
        self,
        client: AsyncClient,
        cost_data: dict,
        db_session: AsyncSession,
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
        self,
        client: AsyncClient,
        cost_data: dict,
    ):
        resp = await client.post(
            "/api/tracker/projects/batch-costs",
            json={"project_ids": []},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_batch_and_single_agree_on_burn_percentage(
        self,
        client: AsyncClient,
        cost_data: dict,
    ):
        """Same project, both endpoints → identical burn_percentage to the cent.

        Pins the shared rounding policy in `_compute_burn_percentage` so
        single and batch can't drift apart again.
        """
        project_id = cost_data["project"].id

        single_resp = await client.get(
            f"/api/tracker/projects/{project_id}/cost-summary",
        )
        assert single_resp.status_code == 200
        single_burn = single_resp.json()["burn_percentage"]

        batch_resp = await client.post(
            "/api/tracker/projects/batch-costs",
            json={"project_ids": [str(project_id)]},
        )
        assert batch_resp.status_code == 200
        batch_burn = batch_resp.json()["costs"][str(project_id)]["burn_percentage"]

        assert single_burn == batch_burn


class TestProjectReportParts:
    @pytest.mark.asyncio
    async def test_list_all_parts(
        self,
        client: AsyncClient,
        cost_data: dict,
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
        self,
        client: AsyncClient,
        cost_data: dict,
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


class TestProjectAggregations:
    @pytest.mark.asyncio
    async def test_aggregate_by_functional_area(
        self,
        client: AsyncClient,
        cost_data: dict,
    ):
        project_id = cost_data["project"].id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/aggregations",
            params={"group_by": "functional_area"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["group_by"] == "functional_area"
        assert len(data["rows"]) == 1
        row = data["rows"][0]
        assert row["name"] == "Backend Developer"
        assert row["email"] is None
        assert row["total_days"] == pytest.approx(4.44, rel=1e-2)
        assert row["total_cost"] == pytest.approx(3411.03, rel=1e-4)
        assert len(row["periods"]) == 2
        assert row["periods"][0]["date"] == "2026-02-01"
        assert row["periods"][1]["date"] == "2026-03-01"

    @pytest.mark.asyncio
    async def test_aggregate_by_user(
        self,
        client: AsyncClient,
        cost_data: dict,
    ):
        project_id = cost_data["project"].id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/aggregations",
            params={"group_by": "user"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["group_by"] == "user"
        assert len(data["rows"]) == 1
        row = data["rows"][0]
        assert row["name"] == "Cost User"
        assert row["email"] == "cost-test@example.com"
        assert row["total_days"] == pytest.approx(4.44, rel=1e-2)

    @pytest.mark.asyncio
    async def test_aggregate_invalid_group_by(
        self,
        client: AsyncClient,
        cost_data: dict,
    ):
        project_id = cost_data["project"].id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/aggregations",
            params={"group_by": "invalid"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_aggregate_by_functional_area_user(
        self,
        client: AsyncClient,
        cost_data: dict,
    ):
        project_id = cost_data["project"].id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/aggregations",
            params={"group_by": "functional_area_user"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["group_by"] == "functional_area_user"
        assert len(data["rows"]) == 1

        row = data["rows"][0]
        assert row["name"] == "Backend Developer"
        assert row["total_days"] == pytest.approx(4.44, rel=1e-2)
        assert row["total_cost"] == pytest.approx(3411.03, rel=1e-4)
        assert len(row["periods"]) == 2

        children = row["children"]
        assert len(children) == 1
        assert children[0]["name"] == "Cost User"
        assert children[0]["email"] == "cost-test@example.com"
        assert children[0]["total_days"] == pytest.approx(4.44, rel=1e-2)

    @pytest.mark.asyncio
    async def test_fa_user_multiple_users_same_area(
        self,
        client: AsyncClient,
        cost_data: dict,
        db_session: AsyncSession,
    ):
        user2 = UserDB(
            email="dev2@example.com",
            name="Dev Two",
            rate_id=cost_data["rate"].id,
            dedication=Decimal("1.0"),
        )
        db_session.add(user2)
        await db_session.flush()

        report = ReportDB(
            user_id=user2.id,
            reporting_period_id=cost_data["period1"].id,
            estimated=False,
        )
        db_session.add(report)
        await db_session.flush()

        part = ReportPartDB(
            report_id=report.id,
            project_id=cost_data["project"].id,
            functional_area_id=cost_data["func_area"].id,
            percentage=Decimal("0.30"),
            cost=Decimal("3000.00"),
            days=Decimal("6.0"),
        )
        db_session.add(part)
        await db_session.commit()

        project_id = cost_data["project"].id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/aggregations",
            params={"group_by": "functional_area_user"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["rows"]) == 1

        row = data["rows"][0]
        assert row["name"] == "Backend Developer"
        assert row["total_days"] == pytest.approx(10.44, rel=1e-2)

        children = row["children"]
        assert len(children) == 2
        # Sorted by total_days desc: Dev Two (6.0) > Cost User (4.44)
        assert children[0]["name"] == "Dev Two"
        assert children[0]["total_days"] == pytest.approx(6.0)
        assert children[1]["name"] == "Cost User"
        assert children[1]["total_days"] == pytest.approx(4.44, rel=1e-2)

    @pytest.mark.asyncio
    async def test_fa_user_multiple_areas(
        self,
        client: AsyncClient,
        cost_data: dict,
        db_session: AsyncSession,
    ):
        fa2 = FunctionalAreaDB(name="Frontend Developer")
        db_session.add(fa2)
        await db_session.flush()

        part = ReportPartDB(
            report_id=cost_data["report1"].id,
            project_id=cost_data["project"].id,
            functional_area_id=fa2.id,
            percentage=Decimal("0.15"),
            cost=Decimal("1500.00"),
            days=Decimal("3.0"),
        )
        db_session.add(part)
        await db_session.commit()

        project_id = cost_data["project"].id
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/aggregations",
            params={"group_by": "functional_area_user"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["rows"]) == 2

        names = [r["name"] for r in data["rows"]]
        assert "Backend Developer" in names
        assert "Frontend Developer" in names

        fe_row = next(r for r in data["rows"] if r["name"] == "Frontend Developer")
        assert fe_row["total_days"] == pytest.approx(3.0)
        assert len(fe_row["children"]) == 1
        assert fe_row["children"][0]["name"] == "Cost User"

    @pytest.mark.asyncio
    async def test_aggregate_empty_project(
        self,
        client: AsyncClient,
        cost_data: dict,
        db_session: AsyncSession,
    ):
        empty = ProjectDB(name="Empty", status="live")
        db_session.add(empty)
        await db_session.commit()
        await db_session.refresh(empty)

        resp = await client.get(
            f"/api/tracker/projects/{empty.id}/aggregations",
            params={"group_by": "functional_area"},
        )
        assert resp.status_code == 200
        assert len(resp.json()["rows"]) == 0
