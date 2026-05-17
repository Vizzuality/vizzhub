"""Tests for capacity user detail drill-down query."""

import datetime as dt
from decimal import Decimal
from uuid import uuid4

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
async def user_detail_data(db_session: AsyncSession) -> dict:
    """Create test data: 1 user, 4 projects (2 billable, 1 internal, 1 absence), 1 period."""
    fa_fe = FunctionalAreaDB(name="Frontend Developer")
    db_session.add(fa_fe)
    await db_session.flush()

    billable1 = ProjectDB(name="Client A", status="live", is_billable=True)
    billable2 = ProjectDB(name="Client B", status="live", is_billable=True)
    internal = ProjectDB(name="Internal", status="live", is_billable=False)
    absence = ProjectDB(
        name="Vacation / Absence", status="live", is_billable=False, is_absence=True
    )
    db_session.add_all([billable1, billable2, internal, absence])
    await db_session.flush()

    user = UserDB(
        email="alice@test.com",
        first_name="Alice",
        last_name="Smith",
        functional_area_id=fa_fe.id,
        active=True,
        requires_project_reporting=True,
    )
    db_session.add(user)
    await db_session.flush()

    period = ReportingPeriodDB(
        date=dt.date(2026, 1, 1),
        base_rate=Decimal("175"),
        status="finished",
    )
    db_session.add(period)
    await db_session.flush()

    # Alice: 40% billable1, 30% billable2, 10% internal, 20% absence
    report = ReportDB(user_id=user.id, reporting_period_id=period.id)
    db_session.add(report)
    await db_session.flush()
    db_session.add_all(
        [
            ReportPartDB(
                report_id=report.id, project_id=billable1.id, percentage=Decimal("0.4000")
            ),
            ReportPartDB(
                report_id=report.id, project_id=billable2.id, percentage=Decimal("0.3000")
            ),
            ReportPartDB(report_id=report.id, project_id=internal.id, percentage=Decimal("0.1000")),
            ReportPartDB(report_id=report.id, project_id=absence.id, percentage=Decimal("0.2000")),
        ]
    )

    await db_session.commit()

    return {
        "user": user,
        "billable1": billable1,
        "billable2": billable2,
        "internal": internal,
        "absence": absence,
        "period": period,
        "fa_fe": fa_fe,
    }


class TestGetCapacityUserDetail:
    @pytest.mark.asyncio
    async def test_returns_per_project_data(
        self,
        db_session: AsyncSession,
        user_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_user_detail

        user = user_detail_data["user"]
        result = await get_capacity_user_detail(
            db=db_session,
            user_id=str(user.id),
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        assert len(result) == 1
        period = result[0]
        assert period["period"] == "2026-01"
        projects = {p["name"]: p for p in period["projects"]}
        # 2 billable + 1 "Other" rollup row for the internal project
        assert {"Client A", "Client B", "Other"}.issubset(projects.keys())
        assert projects["Client A"]["percentage"] == pytest.approx(0.4, abs=0.01)
        assert projects["Client B"]["percentage"] == pytest.approx(0.3, abs=0.01)
        assert projects["Client A"]["type"] == "billable"
        assert projects["Client B"]["type"] == "billable"

    @pytest.mark.asyncio
    async def test_internal_projects_rolled_into_other(
        self,
        db_session: AsyncSession,
        user_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_user_detail

        user = user_detail_data["user"]
        result = await get_capacity_user_detail(
            db=db_session,
            user_id=str(user.id),
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        projects = {p["name"]: p for p in result[0]["projects"]}
        # Internal project is folded into the "Other" pseudo-row, not listed individually
        assert "Internal" not in projects
        assert projects["Other"]["percentage"] == pytest.approx(0.1, abs=0.01)
        assert projects["Other"]["project_id"] == "__other__"
        assert projects["Other"]["type"] == "other"

    @pytest.mark.asyncio
    async def test_projects_sorted_alphabetically(
        self,
        db_session: AsyncSession,
        user_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_user_detail

        user = user_detail_data["user"]
        result = await get_capacity_user_detail(
            db=db_session,
            user_id=str(user.id),
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        # Billable rows sorted alphabetically; "Other" pseudo-row pinned at the end
        billable_names = [p["name"] for p in result[0]["projects"] if p["type"] == "billable"]
        assert billable_names == sorted(billable_names)

    @pytest.mark.asyncio
    async def test_unknown_user_returns_empty(
        self,
        db_session: AsyncSession,
        user_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_user_detail

        # A random UUID does not pass the reportable-user gate → empty list
        result = await get_capacity_user_detail(
            db=db_session,
            user_id=str(uuid4()),
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_absence_and_other_pct_per_period(
        self,
        db_session: AsyncSession,
        user_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_user_detail

        user = user_detail_data["user"]
        result = await get_capacity_user_detail(
            db=db_session,
            user_id=str(user.id),
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        period = result[0]
        assert period["absence_pct"] == pytest.approx(0.2, abs=0.01)
        # 0.1 non-billable non-absence (Internal)
        assert period["other_pct"] == pytest.approx(0.1, abs=0.01)

    @pytest.mark.asyncio
    async def test_user_detail_dedups_same_project_multi_fa(
        self,
        db_session: AsyncSession,
        user_detail_data: dict,
    ):
        """Audit #34: a user reporting the same project under multiple FAs
        collapses to one row with the summed percentage (not two rows)."""
        from app.core.models.functional_area import FunctionalAreaDB
        from app.core.services.capacity_insights import get_capacity_user_detail

        fa_be = FunctionalAreaDB(name="Backend Developer")
        db_session.add(fa_be)
        await db_session.flush()

        # Replace billable1 single-FA row with two FA-split rows summing to 0.7
        from sqlalchemy import delete as sa_delete

        await db_session.execute(
            sa_delete(ReportPartDB).where(
                ReportPartDB.project_id == user_detail_data["billable1"].id,
            )
        )
        await db_session.flush()

        # Re-fetch the existing report
        from sqlalchemy import select as sa_select

        report = (
            await db_session.execute(
                sa_select(ReportDB).where(
                    ReportDB.user_id == user_detail_data["user"].id,
                    ReportDB.reporting_period_id == user_detail_data["period"].id,
                )
            )
        ).scalar_one()
        db_session.add_all(
            [
                ReportPartDB(
                    report_id=report.id,
                    project_id=user_detail_data["billable1"].id,
                    functional_area_id=user_detail_data["fa_fe"].id,
                    percentage=Decimal("0.4000"),
                ),
                ReportPartDB(
                    report_id=report.id,
                    project_id=user_detail_data["billable1"].id,
                    functional_area_id=fa_be.id,
                    percentage=Decimal("0.3000"),
                ),
            ]
        )
        await db_session.commit()

        result = await get_capacity_user_detail(
            db=db_session,
            user_id=str(user_detail_data["user"].id),
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        # One consolidated row for Client A, summed
        client_a_rows = [p for p in result[0]["projects"] if p["name"] == "Client A"]
        assert len(client_a_rows) == 1
        assert client_a_rows[0]["percentage"] == pytest.approx(0.7, abs=0.01)

    @pytest.mark.asyncio
    async def test_user_detail_404s_for_inactive_user(
        self,
        db_session: AsyncSession,
        user_detail_data: dict,
    ):
        """Audit #35: inactive users do not pass the reportable filter
        and the API returns an empty list (effectively 'not found')."""
        from app.core.services.capacity_insights import get_capacity_user_detail

        inactive = UserDB(
            email="inactive@test.com",
            first_name="In",
            last_name="Active",
            functional_area_id=user_detail_data["fa_fe"].id,
            active=False,
            requires_project_reporting=True,
        )
        db_session.add(inactive)
        await db_session.commit()

        result = await get_capacity_user_detail(
            db=db_session,
            user_id=str(inactive.id),
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_user_detail_404s_for_exempt_user(
        self,
        db_session: AsyncSession,
        user_detail_data: dict,
    ):
        """Audit #35: users with requires_project_reporting=False do not
        pass the reportable filter."""
        from app.core.services.capacity_insights import get_capacity_user_detail

        exempt = UserDB(
            email="exempt2@test.com",
            first_name="Exempt",
            last_name="User",
            functional_area_id=user_detail_data["fa_fe"].id,
            active=True,
            requires_project_reporting=False,
        )
        db_session.add(exempt)
        await db_session.commit()

        result = await get_capacity_user_detail(
            db=db_session,
            user_id=str(exempt.id),
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 1, 1),
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_period_returns_no_projects(
        self,
        db_session: AsyncSession,
        user_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_user_detail

        period_feb = ReportingPeriodDB(
            date=dt.date(2026, 2, 1),
            base_rate=Decimal("175"),
            status="finished",
        )
        db_session.add(period_feb)
        await db_session.commit()

        user = user_detail_data["user"]
        result = await get_capacity_user_detail(
            db=db_session,
            user_id=str(user.id),
            start_date=dt.date(2026, 1, 1),
            end_date=dt.date(2026, 2, 1),
        )
        assert len(result) == 2
        # Jan: 2 billable + 1 "Other" pseudo-row = 3 entries
        assert len(result[0]["projects"]) == 3
        # Feb: no reports → no projects
        assert len(result[1]["projects"]) == 0


class TestGetReportableUsers:
    @pytest.mark.asyncio
    async def test_returns_active_reporting_users(
        self,
        db_session: AsyncSession,
        user_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_reportable_users

        result = await get_reportable_users(db_session)
        assert len(result) >= 1
        alice = next((u for u in result if u["name"] == "A. Smith"), None)
        assert alice is not None
        assert alice["id"] == str(user_detail_data["user"].id)

    @pytest.mark.asyncio
    async def test_excludes_inactive_users(
        self,
        db_session: AsyncSession,
        user_detail_data: dict,
    ):
        from app.core.services.capacity_insights import get_reportable_users

        inactive = UserDB(
            email="gone@test.com",
            first_name="Gone",
            last_name="User",
            functional_area_id=user_detail_data["fa_fe"].id,
            active=False,
            requires_project_reporting=True,
        )
        db_session.add(inactive)
        await db_session.commit()

        result = await get_reportable_users(db_session)
        ids = [u["id"] for u in result]
        assert str(inactive.id) not in ids


class TestCapacityUserDetailEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200(
        self,
        client: AsyncClient,
        user_detail_data: dict,
    ):
        user = user_detail_data["user"]
        resp = await client.get(
            "/api/capacity/insights/user-detail",
            params={"user_id": str(user.id), "start_date": "2026-01", "end_date": "2026-01"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        # 2 billable + 1 "Other" pseudo-row
        assert len(data[0]["projects"]) == 3

    @pytest.mark.asyncio
    async def test_invalid_user_id_returns_422(
        self,
        client: AsyncClient,
        user_detail_data: dict,
    ):
        resp = await client.get(
            "/api/capacity/insights/user-detail",
            params={"user_id": "not-a-uuid", "start_date": "2026-01", "end_date": "2026-01"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_date_range_returns_422(
        self,
        client: AsyncClient,
        user_detail_data: dict,
    ):
        user = user_detail_data["user"]
        resp = await client.get(
            "/api/capacity/insights/user-detail",
            params={"user_id": str(user.id), "start_date": "2026-03", "end_date": "2026-01"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_reportable_users_endpoint(
        self,
        client: AsyncClient,
        user_detail_data: dict,
    ):
        resp = await client.get("/api/capacity/insights/user-detail/users")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all("id" in u and "name" in u for u in data)
