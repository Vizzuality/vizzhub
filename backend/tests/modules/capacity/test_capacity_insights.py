"""Tests for capacity insights analytical query."""

import datetime as dt
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

FA_MAPPING = {
    "Frontend Developer": "FE",
    "Backend Developer": "BE",
    "Designer": "Design",
    "Project Manager": "PM",
    "Scientist": "Sci",
    "Communications": "Coms",
}


@pytest_asyncio.fixture
async def capacity_data(db_session: AsyncSession) -> dict:
    """Create test data: 2 FAs, 2 users, 1 period, reports."""
    fa_fe = FunctionalAreaDB(name="Frontend Developer")
    fa_be = FunctionalAreaDB(name="Backend Developer")
    db_session.add_all([fa_fe, fa_be])
    await db_session.flush()

    billable_project = ProjectDB(name="Client App", status="live", is_billable=True)
    internal_project = ProjectDB(name="Internal Tool", status="live", is_billable=False)
    absence_project = ProjectDB(name="Vacation / Absence", status="live", is_billable=False, is_absence=True)
    db_session.add_all([billable_project, internal_project, absence_project])
    await db_session.flush()

    user_fe1 = UserDB(
        email="fe1@test.com", first_name="Fe", last_name="One",
        functional_area_id=fa_fe.id, active=True, requires_project_reporting=True,
    )
    user_fe2 = UserDB(
        email="fe2@test.com", first_name="Fe", last_name="Two",
        functional_area_id=fa_fe.id, active=True, requires_project_reporting=True,
    )
    user_be1 = UserDB(
        email="be1@test.com", first_name="Be", last_name="One",
        functional_area_id=fa_be.id, active=True, requires_project_reporting=True,
    )
    user_exempt = UserDB(
        email="norpt@test.com", first_name="No", last_name="Report",
        functional_area_id=fa_fe.id, active=True, requires_project_reporting=False,
    )
    db_session.add_all([user_fe1, user_fe2, user_be1, user_exempt])
    await db_session.flush()

    period_jan = ReportingPeriodDB(
        date=dt.date(2026, 1, 1), base_rate=Decimal("175"), status="finished",
    )
    period_feb = ReportingPeriodDB(
        date=dt.date(2026, 2, 1), base_rate=Decimal("175"), status="finished",
    )
    db_session.add_all([period_jan, period_feb])
    await db_session.flush()

    # fe1: 60% billable, 20% internal, 20% absence in Jan
    report_fe1_jan = ReportDB(
        user_id=user_fe1.id, reporting_period_id=period_jan.id,
    )
    db_session.add(report_fe1_jan)
    await db_session.flush()
    db_session.add_all([
        ReportPartDB(
            report_id=report_fe1_jan.id, project_id=billable_project.id,
            percentage=Decimal("0.6000"),
        ),
        ReportPartDB(
            report_id=report_fe1_jan.id, project_id=internal_project.id,
            percentage=Decimal("0.2000"),
        ),
        ReportPartDB(
            report_id=report_fe1_jan.id, project_id=absence_project.id,
            percentage=Decimal("0.2000"),
        ),
    ])

    # fe2: 80% billable, 20% internal in Jan
    report_fe2_jan = ReportDB(
        user_id=user_fe2.id, reporting_period_id=period_jan.id,
    )
    db_session.add(report_fe2_jan)
    await db_session.flush()
    db_session.add_all([
        ReportPartDB(
            report_id=report_fe2_jan.id, project_id=billable_project.id,
            percentage=Decimal("0.8000"),
        ),
        ReportPartDB(
            report_id=report_fe2_jan.id, project_id=internal_project.id,
            percentage=Decimal("0.2000"),
        ),
    ])

    # be1: 100% billable in Jan
    report_be1_jan = ReportDB(
        user_id=user_be1.id, reporting_period_id=period_jan.id,
    )
    db_session.add(report_be1_jan)
    await db_session.flush()
    db_session.add(ReportPartDB(
        report_id=report_be1_jan.id, project_id=billable_project.id,
        percentage=Decimal("1.0000"),
    ))

    await db_session.commit()

    return {
        "fa_fe": fa_fe, "fa_be": fa_be,
        "billable_project": billable_project, "internal_project": internal_project,
        "absence_project": absence_project,
        "user_fe1": user_fe1, "user_fe2": user_fe2, "user_be1": user_be1,
        "period_jan": period_jan, "period_feb": period_feb,
    }


class TestGetCapacityInsights:
    @pytest.mark.asyncio
    async def test_billable_pct_averaged_across_users(
        self, db_session: AsyncSession, capacity_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_insights

        result = await get_capacity_insights(
            db=db_session,
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        assert len(result) == 1
        period = result[0]
        assert period["period"] == "2026-01"

        fa_map = {fa["short"]: fa for fa in period["functional_areas"]}
        # FE: (0.6 + 0.8) / 2 = 0.7
        assert fa_map["FE"]["billable_pct"] == pytest.approx(0.7, abs=0.01)
        assert fa_map["FE"]["user_count"] == 2
        # BE: 1.0 / 1 = 1.0
        assert fa_map["BE"]["billable_pct"] == pytest.approx(1.0, abs=0.01)
        assert fa_map["BE"]["user_count"] == 1

    @pytest.mark.asyncio
    async def test_excludes_non_reporting_users(
        self, db_session: AsyncSession, capacity_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_insights

        result = await get_capacity_insights(
            db=db_session,
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        fa_map = {fa["short"]: fa for fa in result[0]["functional_areas"]}
        # user_exempt has requires_project_reporting=False, excluded
        assert fa_map["FE"]["user_count"] == 2

    @pytest.mark.asyncio
    async def test_users_with_no_report_excluded_from_average(
        self, db_session: AsyncSession, capacity_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_insights

        # Feb has no reports for anyone — all users excluded (on leave)
        result = await get_capacity_insights(
            db=db_session,
            start_date=dt.date(2026, 2, 1),
            end_date=dt.date(2026, 2, 1),
        )
        # No FAs should appear since all users have 0 report total
        assert result[0]["functional_areas"] == []

    @pytest.mark.asyncio
    async def test_on_leave_user_excluded_from_average(
        self, db_session: AsyncSession, capacity_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_insights

        # Add a third FE user who has a report but total = 0 (on leave)
        fa_fe = capacity_data["fa_fe"]
        period_jan = capacity_data["period_jan"]
        user_on_leave = UserDB(
            email="leave@test.com", first_name="On", last_name="Leave",
            functional_area_id=fa_fe.id, active=True, requires_project_reporting=True,
        )
        db_session.add(user_on_leave)
        await db_session.flush()

        # Report with 0% total (all parts have percentage=0)
        report_leave = ReportDB(
            user_id=user_on_leave.id, reporting_period_id=period_jan.id,
        )
        db_session.add(report_leave)
        await db_session.flush()
        db_session.add(ReportPartDB(
            report_id=report_leave.id,
            project_id=capacity_data["billable_project"].id,
            percentage=Decimal("0.0000"),
        ))
        await db_session.commit()

        result = await get_capacity_insights(
            db=db_session,
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        fa_map = {fa["short"]: fa for fa in result[0]["functional_areas"]}
        # On-leave user excluded: still (0.6 + 0.8) / 2 = 0.7, not / 3
        assert fa_map["FE"]["billable_pct"] == pytest.approx(0.7, abs=0.01)
        assert fa_map["FE"]["user_count"] == 2

    @pytest.mark.asyncio
    async def test_only_target_fas_returned(
        self, db_session: AsyncSession, capacity_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_insights

        result = await get_capacity_insights(
            db=db_session,
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        shorts = {fa["short"] for fa in result[0]["functional_areas"]}
        # Only FE and BE have users; other 4 target FAs don't exist in DB
        assert shorts == {"FE", "BE"}

    @pytest.mark.asyncio
    async def test_absence_pct_separated_from_others(
        self, db_session: AsyncSession, capacity_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_insights

        result = await get_capacity_insights(
            db=db_session,
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        fa_map = {fa["short"]: fa for fa in result[0]["functional_areas"]}
        # FE: fe1 has 0.2 absence, fe2 has 0 absence → avg 0.1
        assert fa_map["FE"]["absence_pct"] == pytest.approx(0.1, abs=0.01)
        # BE: no absence
        assert fa_map["BE"]["absence_pct"] == pytest.approx(0.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_multiple_periods(
        self, db_session: AsyncSession, capacity_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_insights

        result = await get_capacity_insights(
            db=db_session,
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 2, 1),
        )
        assert len(result) == 2
        assert result[0]["period"] == "2026-01"
        assert result[1]["period"] == "2026-02"


class TestCapacityInsightsEndpoint:
    @pytest.mark.asyncio
    async def test_get_insights_returns_200(
        self, client: AsyncClient, capacity_data: dict,
    ):
        resp = await client.get(
            "/api/capacity/insights",
            params={"start_date": "2026-01", "end_date": "2026-02"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["period"] == "2026-01"

    @pytest.mark.asyncio
    async def test_invalid_date_range_returns_422(
        self, client: AsyncClient, capacity_data: dict,
    ):
        resp = await client.get(
            "/api/capacity/insights",
            params={"start_date": "2026-03", "end_date": "2026-01"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_range_exceeds_24_months_returns_422(
        self, client: AsyncClient, capacity_data: dict,
    ):
        resp = await client.get(
            "/api/capacity/insights",
            params={"start_date": "2024-01", "end_date": "2026-03"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_exactly_24_months_returns_422(
        self, client: AsyncClient, capacity_data: dict,
    ):
        # 24-month diff = 25 data points, exceeds limit
        resp = await client.get(
            "/api/capacity/insights",
            params={"start_date": "2024-01", "end_date": "2026-01"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_23_month_range_returns_200(
        self, client: AsyncClient, capacity_data: dict,
    ):
        # 23-month diff = 24 data points, within limit
        resp = await client.get(
            "/api/capacity/insights",
            params={"start_date": "2024-02", "end_date": "2026-01"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_params_returns_400(
        self, client: AsyncClient, capacity_data: dict,
    ):
        # FastAPI validation errors return 400 via custom handler in main.py
        resp = await client.get("/api/capacity/insights")
        assert resp.status_code == 400
