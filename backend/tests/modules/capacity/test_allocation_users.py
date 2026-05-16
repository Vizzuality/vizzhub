"""Tests for allocation users analytical query."""

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
async def allocation_data(db_session: AsyncSession) -> dict:
    """Create test data for allocation users tests.

    1 FA (Frontend Developer), 4 projects (Alpha billable, Beta billable,
    Internal non-billable, Vacation absence), 4 users (alice active+reporting,
    bob active+reporting, gone inactive, exempt non-reporting),
    4 periods (3 finished: Jan/Feb/Mar 2026, 1 active: Apr 2026).

    Reports:
      Alice: Alpha 50%+Internal 30%+Absence 20% in p1;
             Alpha 30%+Beta 20%+Internal 30%+Absence 20% in p2 and p3
      Bob:   Alpha 80%+Internal 20% in p1 only
    """
    fa_fe = FunctionalAreaDB(name="Frontend Developer")
    db_session.add(fa_fe)
    await db_session.flush()

    alpha = ProjectDB(name="Alpha", status="live", is_billable=True)
    beta = ProjectDB(name="Beta", status="live", is_billable=True)
    internal = ProjectDB(name="Internal", status="live", is_billable=False)
    vacation = ProjectDB(
        name="Vacation", status="live", is_billable=False, is_absence=True,
    )
    db_session.add_all([alpha, beta, internal, vacation])
    await db_session.flush()

    alice = UserDB(
        email="alice@test.com", first_name="Alice", last_name="Smith",
        functional_area_id=fa_fe.id, active=True,
        requires_project_reporting=True,
    )
    bob = UserDB(
        email="bob@test.com", first_name="Bob", last_name="Jones",
        functional_area_id=fa_fe.id, active=True,
        requires_project_reporting=True,
    )
    gone = UserDB(
        email="gone@test.com", first_name="Gone", last_name="User",
        functional_area_id=fa_fe.id, active=False,
        requires_project_reporting=True,
    )
    exempt = UserDB(
        email="exempt@test.com", first_name="No", last_name="Report",
        functional_area_id=fa_fe.id, active=True,
        requires_project_reporting=False,
    )
    db_session.add_all([alice, bob, gone, exempt])
    await db_session.flush()

    p1 = ReportingPeriodDB(
        date=dt.date(2026, 1, 1), base_rate=Decimal("175"), status="finished",
    )
    p2 = ReportingPeriodDB(
        date=dt.date(2026, 2, 1), base_rate=Decimal("175"), status="finished",
    )
    p3 = ReportingPeriodDB(
        date=dt.date(2026, 3, 1), base_rate=Decimal("175"), status="finished",
    )
    p4 = ReportingPeriodDB(
        date=dt.date(2026, 4, 1), base_rate=Decimal("175"), status="active",
    )
    db_session.add_all([p1, p2, p3, p4])
    await db_session.flush()

    # Alice p1: Alpha 50% + Internal 30% + Vacation 20%
    r_alice_p1 = ReportDB(user_id=alice.id, reporting_period_id=p1.id)
    db_session.add(r_alice_p1)
    await db_session.flush()
    db_session.add_all([
        ReportPartDB(
            report_id=r_alice_p1.id, project_id=alpha.id,
            percentage=Decimal("0.5000"),
        ),
        ReportPartDB(
            report_id=r_alice_p1.id, project_id=internal.id,
            percentage=Decimal("0.3000"),
        ),
        ReportPartDB(
            report_id=r_alice_p1.id, project_id=vacation.id,
            percentage=Decimal("0.2000"),
        ),
    ])

    # Alice p2: Alpha 30% + Beta 20% + Internal 30% + Vacation 20%
    r_alice_p2 = ReportDB(user_id=alice.id, reporting_period_id=p2.id)
    db_session.add(r_alice_p2)
    await db_session.flush()
    db_session.add_all([
        ReportPartDB(
            report_id=r_alice_p2.id, project_id=alpha.id,
            percentage=Decimal("0.3000"),
        ),
        ReportPartDB(
            report_id=r_alice_p2.id, project_id=beta.id,
            percentage=Decimal("0.2000"),
        ),
        ReportPartDB(
            report_id=r_alice_p2.id, project_id=internal.id,
            percentage=Decimal("0.3000"),
        ),
        ReportPartDB(
            report_id=r_alice_p2.id, project_id=vacation.id,
            percentage=Decimal("0.2000"),
        ),
    ])

    # Alice p3: same as p2
    r_alice_p3 = ReportDB(user_id=alice.id, reporting_period_id=p3.id)
    db_session.add(r_alice_p3)
    await db_session.flush()
    db_session.add_all([
        ReportPartDB(
            report_id=r_alice_p3.id, project_id=alpha.id,
            percentage=Decimal("0.3000"),
        ),
        ReportPartDB(
            report_id=r_alice_p3.id, project_id=beta.id,
            percentage=Decimal("0.2000"),
        ),
        ReportPartDB(
            report_id=r_alice_p3.id, project_id=internal.id,
            percentage=Decimal("0.3000"),
        ),
        ReportPartDB(
            report_id=r_alice_p3.id, project_id=vacation.id,
            percentage=Decimal("0.2000"),
        ),
    ])

    # Bob p1: Alpha 80% + Internal 20%
    r_bob_p1 = ReportDB(user_id=bob.id, reporting_period_id=p1.id)
    db_session.add(r_bob_p1)
    await db_session.flush()
    db_session.add_all([
        ReportPartDB(
            report_id=r_bob_p1.id, project_id=alpha.id,
            percentage=Decimal("0.8000"),
        ),
        ReportPartDB(
            report_id=r_bob_p1.id, project_id=internal.id,
            percentage=Decimal("0.2000"),
        ),
    ])

    await db_session.commit()

    return {
        "fa_fe": fa_fe,
        "alpha": alpha, "beta": beta, "internal": internal, "vacation": vacation,
        "alice": alice, "bob": bob, "gone": gone, "exempt": exempt,
        "p1": p1, "p2": p2, "p3": p3, "p4": p4,
    }


class TestGetAllocationUsers:
    @pytest.mark.asyncio
    async def test_allocation_users_returns_ranked_list(
        self, db_session: AsyncSession, allocation_data: dict,
    ):
        from app.core.services.capacity_insights import get_allocation_users

        result = await get_allocation_users(db=db_session)

        assert "periods_used" in result
        assert "users" in result
        # 3 finished periods, descending order
        assert len(result["periods_used"]) == 3
        assert result["periods_used"] == ["2026-03", "2026-02", "2026-01"]

        users = result["users"]
        assert len(users) == 2

        # Alice: billable in all 3 periods → avg = (1+2+2)/3 ≈ 1.6667
        # Bob: billable in 1 period → avg = (1+0+0)/3 ≈ 0.3333
        # Alice first (higher avg_billable_projects)
        assert users[0]["name"] == "Alice Smith"
        assert users[0]["avg_billable_projects"] == pytest.approx(1.6667, abs=0.01)
        assert users[0]["total_distinct_projects"] == 2

        assert users[1]["name"] == "Bob Jones"
        assert users[1]["avg_billable_projects"] == pytest.approx(0.3333, abs=0.01)
        assert users[1]["total_distinct_projects"] == 1

    @pytest.mark.asyncio
    async def test_allocation_users_segments(
        self, db_session: AsyncSession, allocation_data: dict,
    ):
        from app.core.services.capacity_insights import get_allocation_users

        result = await get_allocation_users(db=db_session)
        alice = result["users"][0]
        segments = {s["project_name"]: s for s in alice["segments"]}

        # Alpha: (0.50+0.30+0.30)/3 = 0.3667
        assert segments["Alpha"]["avg_percentage"] == pytest.approx(0.3667, abs=0.01)
        assert isinstance(segments["Alpha"]["months_active"], list)
        assert len(segments["Alpha"]["months_active"]) == 3
        assert segments["Alpha"]["months_active"] == ["2026-03", "2026-02", "2026-01"]

        # Beta: (0+0.20+0.20)/3 = 0.1333
        assert segments["Beta"]["avg_percentage"] == pytest.approx(0.1333, abs=0.01)
        assert isinstance(segments["Beta"]["months_active"], list)
        assert len(segments["Beta"]["months_active"]) == 2
        assert segments["Beta"]["months_active"] == ["2026-03", "2026-02"]

        # Absence grouped: (0.20+0.20+0.20)/3 = 0.20
        assert segments["Absence"]["avg_percentage"] == pytest.approx(0.20, abs=0.01)
        assert segments["Absence"]["type"] == "absence"
        assert segments["Absence"]["project_id"] == "__absence__"

        # Other grouped: (0.30+0.30+0.30)/3 = 0.30
        assert segments["Other"]["avg_percentage"] == pytest.approx(0.30, abs=0.01)
        assert segments["Other"]["type"] == "other"
        assert segments["Other"]["project_id"] == "__other__"

    @pytest.mark.asyncio
    async def test_allocation_users_excludes_inactive_and_exempt(
        self, db_session: AsyncSession, allocation_data: dict,
    ):
        from app.core.services.capacity_insights import get_allocation_users

        result = await get_allocation_users(db=db_session)
        names = [u["name"] for u in result["users"]]
        assert "Gone User" not in names
        assert "No Report" not in names

    @pytest.mark.asyncio
    async def test_allocation_users_default_excludes_active_periods(
        self, db_session: AsyncSession, allocation_data: dict,
    ):
        from app.core.services.capacity_insights import get_allocation_users

        result = await get_allocation_users(db=db_session)
        assert "2026-04" not in result["periods_used"]

    @pytest.mark.asyncio
    async def test_allocation_users_date_range_includes_active_periods(
        self, db_session: AsyncSession, allocation_data: dict,
    ):
        """When user explicitly selects a date range, active periods are included."""
        from app.core.services.capacity_insights import get_allocation_users

        result = await get_allocation_users(
            db=db_session,
            start_date=dt.date(2026, 4, 1),
            end_date=dt.date(2026, 4, 1),
        )
        assert "2026-04" in result["periods_used"]

    @pytest.mark.asyncio
    async def test_allocation_users_empty_when_no_finished_periods(
        self, db_session: AsyncSession,
    ):
        from app.core.services.capacity_insights import get_allocation_users

        # No fixture data → no finished periods at all
        result = await get_allocation_users(db=db_session)
        assert result["periods_used"] == []
        assert result["users"] == []

    @pytest.mark.asyncio
    async def test_allocation_users_includes_functional_area(
        self, db_session: AsyncSession, allocation_data: dict,
    ):
        from app.core.services.capacity_insights import get_allocation_users

        result = await get_allocation_users(db=db_session)
        alice = next(u for u in result["users"] if u["name"] == "Alice Smith")
        # "Frontend Developer" maps to "FE" via TARGET_FA_MAPPING
        assert alice["functional_area"] == "FE"


class TestGetAllocationProjects:
    @pytest.mark.asyncio
    async def test_allocation_projects_returns_ranked_list(
        self, db_session: AsyncSession, allocation_data: dict,
    ):
        from app.core.services.capacity_insights import get_allocation_projects

        result = await get_allocation_projects(db=db_session)

        assert "periods_used" in result
        assert "projects" in result

        projects = result["projects"]
        # Only billable+live projects: Alpha and Beta
        assert len(projects) == 2

        # Alpha: 2 users in p1, 1 in p2, 1 in p3 → avg = (2+1+1)/3 ≈ 1.33
        # Beta: 0 in p1, 1 in p2, 1 in p3 → avg = (0+1+1)/3 ≈ 0.67
        # Alpha ranks first (higher avg_people)
        assert projects[0]["name"] == "Alpha"
        assert projects[0]["avg_people"] == pytest.approx(1.33, abs=0.01)
        assert projects[0]["total_distinct_people"] == 2

        assert projects[1]["name"] == "Beta"
        assert projects[1]["avg_people"] == pytest.approx(0.67, abs=0.01)
        assert projects[1]["total_distinct_people"] == 1

    @pytest.mark.asyncio
    async def test_allocation_projects_segments(
        self, db_session: AsyncSession, allocation_data: dict,
    ):
        from app.core.services.capacity_insights import get_allocation_projects

        result = await get_allocation_projects(db=db_session)
        alpha = next(p for p in result["projects"] if p["name"] == "Alpha")
        segments = {s["user_name"]: s for s in alpha["segments"]}

        # Alice on Alpha: (0.50+0.30+0.30)/3 = 0.3667
        assert "Alice Smith" in segments
        assert segments["Alice Smith"]["avg_percentage"] == pytest.approx(0.3667, abs=0.01)
        assert isinstance(segments["Alice Smith"]["months_active"], list)
        assert len(segments["Alice Smith"]["months_active"]) == 3

        # Bob on Alpha: (0.80+0+0)/3 = 0.2667
        assert "Bob Jones" in segments
        assert segments["Bob Jones"]["avg_percentage"] == pytest.approx(0.2667, abs=0.01)
        assert len(segments["Bob Jones"]["months_active"]) == 1

    @pytest.mark.asyncio
    async def test_allocation_projects_excludes_non_billable(
        self, db_session: AsyncSession, allocation_data: dict,
    ):
        from app.core.services.capacity_insights import get_allocation_projects

        result = await get_allocation_projects(db=db_session)
        project_names = [p["name"] for p in result["projects"]]
        assert "Internal" not in project_names
        assert "Vacation" not in project_names

    @pytest.mark.asyncio
    async def test_allocation_projects_excludes_inactive_users(
        self, db_session: AsyncSession, allocation_data: dict,
    ):
        """Audit #35: an inactive user with billable reports must not appear in
        any project's segment list."""
        from app.core.services.capacity_insights import get_allocation_projects

        # Move all of Alice's report parts to "Gone User" (inactive)
        gone = allocation_data["gone"]
        # Re-target alice's reports to the inactive user
        from sqlalchemy import update as sa_update
        await db_session.execute(
            sa_update(ReportDB)
            .where(ReportDB.user_id == allocation_data["alice"].id)
            .values(user_id=gone.id)
        )
        await db_session.commit()

        result = await get_allocation_projects(db=db_session)
        alpha = next((p for p in result["projects"] if p["name"] == "Alpha"), None)
        assert alpha is not None
        seg_names = [s["user_name"] for s in alpha["segments"]]
        assert "Gone User" not in seg_names

    @pytest.mark.asyncio
    async def test_allocation_projects_excludes_exempt_users(
        self, db_session: AsyncSession, allocation_data: dict,
    ):
        """Audit #35: users with requires_project_reporting=False must not appear in segments."""
        from app.core.services.capacity_insights import get_allocation_projects

        exempt = allocation_data["exempt"]
        from sqlalchemy import update as sa_update
        await db_session.execute(
            sa_update(ReportDB)
            .where(ReportDB.user_id == allocation_data["bob"].id)
            .values(user_id=exempt.id)
        )
        await db_session.commit()

        result = await get_allocation_projects(db=db_session)
        alpha = next((p for p in result["projects"] if p["name"] == "Alpha"), None)
        if alpha is not None:
            seg_names = [s["user_name"] for s in alpha["segments"]]
            assert "No Report" not in seg_names
