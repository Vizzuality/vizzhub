"""Tests for capacity FA detail drill-down query."""

import datetime as dt
from decimal import Decimal

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


@pytest_asyncio.fixture
async def fa_detail_data(db_session: AsyncSession) -> dict:
    """Create test data: 1 FA, 2 users, 2 projects, 1 period with reports."""
    fa_fe = FunctionalAreaDB(name="Frontend Developer")
    db_session.add(fa_fe)
    await db_session.flush()

    billable1 = ProjectDB(name="Client A", status="live", is_billable=True)
    billable2 = ProjectDB(name="Client B", status="live", is_billable=True)
    internal = ProjectDB(name="Internal", status="live", is_billable=False)
    absence = ProjectDB(name="Vacation / Absence", status="live", is_billable=False, is_absence=True)
    db_session.add_all([billable1, billable2, internal, absence])
    await db_session.flush()

    user1 = UserDB(
        email="alice@test.com", first_name="Alice", last_name="Smith",
        functional_area_id=fa_fe.id, active=True, requires_project_reporting=True,
    )
    user2 = UserDB(
        email="bob@test.com", first_name="Bob", last_name="Jones",
        functional_area_id=fa_fe.id, active=True, requires_project_reporting=True,
    )
    db_session.add_all([user1, user2])
    await db_session.flush()

    period = ReportingPeriodDB(
        date=dt.date(2026, 1, 1), base_rate=Decimal("175"), status="finished",
    )
    db_session.add(period)
    await db_session.flush()

    # Alice: 40% billable1, 30% billable2, 10% internal, 20% absence = 70% billable, 2 billable projects
    report_alice = ReportDB(user_id=user1.id, reporting_period_id=period.id)
    db_session.add(report_alice)
    await db_session.flush()
    db_session.add_all([
        ReportPartDB(report_id=report_alice.id, project_id=billable1.id, percentage=Decimal("0.4000")),
        ReportPartDB(report_id=report_alice.id, project_id=billable2.id, percentage=Decimal("0.3000")),
        ReportPartDB(report_id=report_alice.id, project_id=internal.id, percentage=Decimal("0.1000")),
        ReportPartDB(report_id=report_alice.id, project_id=absence.id, percentage=Decimal("0.2000")),
    ])

    # Bob: 100% internal = 0% billable, 0 billable projects
    report_bob = ReportDB(user_id=user2.id, reporting_period_id=period.id)
    db_session.add(report_bob)
    await db_session.flush()
    db_session.add(ReportPartDB(
        report_id=report_bob.id, project_id=internal.id, percentage=Decimal("1.0000"),
    ))

    await db_session.commit()

    return {
        "fa_fe": fa_fe, "billable1": billable1, "billable2": billable2,
        "internal": internal, "absence": absence, "user1": user1, "user2": user2, "period": period,
    }


class TestGetCapacityFADetail:
    @pytest.mark.asyncio
    async def test_returns_per_user_data(
        self, db_session: AsyncSession, fa_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_fa_detail

        result = await get_capacity_fa_detail(
            db=db_session, fa_short="FE",
            start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 1),
        )
        assert len(result) == 1
        period = result[0]
        assert period["period"] == "2026-01"
        users = {u["name"]: u for u in period["users"]}
        assert len(users) == 2

        alice = users["A. Smith"]
        assert alice["billable_pct"] == pytest.approx(0.7, abs=0.01)
        assert alice["billable_project_count"] == 2

        bob = users["B. Jones"]
        assert bob["billable_pct"] == pytest.approx(0.0, abs=0.01)
        assert bob["billable_project_count"] == 0

    @pytest.mark.asyncio
    async def test_excludes_on_leave_user(
        self, db_session: AsyncSession, fa_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_fa_detail

        leave_user = UserDB(
            email="leave@test.com", first_name="On", last_name="Leave",
            functional_area_id=fa_detail_data["fa_fe"].id,
            active=True, requires_project_reporting=True,
        )
        db_session.add(leave_user)
        await db_session.flush()
        report = ReportDB(
            user_id=leave_user.id,
            reporting_period_id=fa_detail_data["period"].id,
        )
        db_session.add(report)
        await db_session.flush()
        db_session.add(ReportPartDB(
            report_id=report.id,
            project_id=fa_detail_data["internal"].id,
            percentage=Decimal("0.0000"),
        ))
        await db_session.commit()

        result = await get_capacity_fa_detail(
            db=db_session, fa_short="FE",
            start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 1),
        )
        names = [u["name"] for u in result[0]["users"]]
        assert "O. Leave" not in names
        assert len(names) == 2

    @pytest.mark.asyncio
    async def test_excludes_non_reporting_user(
        self, db_session: AsyncSession, fa_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_fa_detail

        exempt = UserDB(
            email="exempt@test.com", first_name="Not", last_name="Reporting",
            functional_area_id=fa_detail_data["fa_fe"].id,
            active=True, requires_project_reporting=False,
        )
        db_session.add(exempt)
        await db_session.commit()

        result = await get_capacity_fa_detail(
            db=db_session, fa_short="FE",
            start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 1),
        )
        names = [u["name"] for u in result[0]["users"]]
        assert "N. Reporting" not in names

    @pytest.mark.asyncio
    async def test_period_with_no_reports_returns_empty_users(
        self, db_session: AsyncSession, fa_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_fa_detail

        period_feb = ReportingPeriodDB(
            date=dt.date(2026, 2, 1), base_rate=Decimal("175"), status="finished",
        )
        db_session.add(period_feb)
        await db_session.commit()

        result = await get_capacity_fa_detail(
            db=db_session, fa_short="FE",
            start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 2, 1),
        )
        assert len(result) == 2
        assert len(result[0]["users"]) == 2
        assert len(result[1]["users"]) == 0

    @pytest.mark.asyncio
    async def test_unknown_fa_returns_empty(
        self, db_session: AsyncSession, fa_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_fa_detail

        result = await get_capacity_fa_detail(
            db=db_session, fa_short="Sci",
            start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 1),
        )
        assert len(result) == 1
        assert result[0]["users"] == []

    @pytest.mark.asyncio
    async def test_name_formatting_fallback(
        self, db_session: AsyncSession, fa_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_fa_detail

        user_no_last = UserDB(
            email="nolast@test.com", first_name="Solo", last_name=None,
            functional_area_id=fa_detail_data["fa_fe"].id,
            active=True, requires_project_reporting=True,
        )
        db_session.add(user_no_last)
        await db_session.flush()
        report = ReportDB(
            user_id=user_no_last.id,
            reporting_period_id=fa_detail_data["period"].id,
        )
        db_session.add(report)
        await db_session.flush()
        db_session.add(ReportPartDB(
            report_id=report.id,
            project_id=fa_detail_data["billable1"].id,
            percentage=Decimal("1.0000"),
        ))
        await db_session.commit()

        result = await get_capacity_fa_detail(
            db=db_session, fa_short="FE",
            start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 1),
        )
        names = [u["name"] for u in result[0]["users"]]
        assert "Solo" in names

    @pytest.mark.asyncio
    async def test_users_sorted_alphabetically(
        self, db_session: AsyncSession, fa_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_fa_detail

        result = await get_capacity_fa_detail(
            db=db_session, fa_short="FE",
            start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 1),
        )
        names = [u["name"] for u in result[0]["users"]]
        assert names == sorted(names)

    @pytest.mark.asyncio
    async def test_returns_absence_pct_per_user(
        self, db_session: AsyncSession, fa_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_fa_detail

        result = await get_capacity_fa_detail(
            db=db_session, fa_short="FE",
            start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 1),
        )
        users = {u["name"]: u for u in result[0]["users"]}
        assert users["A. Smith"]["absence_pct"] == pytest.approx(0.2, abs=0.01)
        assert users["B. Jones"]["absence_pct"] == pytest.approx(0.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_capacity_fa_detail_exposes_other_pct(
        self, db_session: AsyncSession, fa_detail_data: dict,
    ):
        """Audit #33: each per-user row exposes other_pct alongside billable/absence."""
        from app.core.services.capacity_insights import get_capacity_fa_detail

        result = await get_capacity_fa_detail(
            db=db_session, fa_short="FE",
            start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 1),
        )
        users = {u["name"]: u for u in result[0]["users"]}
        # Alice: 40% A + 30% B + 10% Internal + 20% absence → other = 0.1
        assert users["A. Smith"]["other_pct"] == pytest.approx(0.1, abs=0.01)
        # Bob: 100% internal → other = 1.0
        assert users["B. Jones"]["other_pct"] == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_full_absence_user_excluded_from_fa_detail(
        self, db_session: AsyncSession, fa_detail_data: dict,
    ):
        """Audit #36: a user who reports 100% absence is on effective leave and
        does not appear in the FA detail list."""
        from app.core.services.capacity_insights import get_capacity_fa_detail

        full_pto = UserDB(
            email="pto@test.com", first_name="Full", last_name="PTO",
            functional_area_id=fa_detail_data["fa_fe"].id,
            active=True, requires_project_reporting=True,
        )
        db_session.add(full_pto)
        await db_session.flush()
        report = ReportDB(
            user_id=full_pto.id,
            reporting_period_id=fa_detail_data["period"].id,
        )
        db_session.add(report)
        await db_session.flush()
        db_session.add(ReportPartDB(
            report_id=report.id, project_id=fa_detail_data["absence"].id,
            percentage=Decimal("1.0000"),
        ))
        await db_session.commit()

        result = await get_capacity_fa_detail(
            db=db_session, fa_short="FE",
            start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 1),
        )
        names = [u["name"] for u in result[0]["users"]]
        assert "F. PTO" not in names


class TestCapacityFADetailEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200(
        self, client: AsyncClient, fa_detail_data: dict,
    ):
        resp = await client.get(
            "/api/capacity/insights/detail",
            params={"fa": "FE", "start_date": "2026-01", "end_date": "2026-01"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert len(data[0]["users"]) == 2

    @pytest.mark.asyncio
    async def test_invalid_fa_returns_422(
        self, client: AsyncClient, fa_detail_data: dict,
    ):
        resp = await client.get(
            "/api/capacity/insights/detail",
            params={"fa": "INVALID", "start_date": "2026-01", "end_date": "2026-01"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_date_range_returns_422(
        self, client: AsyncClient, fa_detail_data: dict,
    ):
        resp = await client.get(
            "/api/capacity/insights/detail",
            params={"fa": "FE", "start_date": "2026-03", "end_date": "2026-01"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_fa_returns_400(
        self, client: AsyncClient, fa_detail_data: dict,
    ):
        resp = await client.get(
            "/api/capacity/insights/detail",
            params={"start_date": "2026-01", "end_date": "2026-01"},
        )
        assert resp.status_code == 400
