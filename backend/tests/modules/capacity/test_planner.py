"""Tests for capacity planner endpoints."""

from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.capacity.models.capacity_plan import CapacityPlanDB


@pytest_asyncio.fixture
async def planner_data(db_session: AsyncSession):
    """Create test users and projects for planner tests."""
    fa_fe = FunctionalAreaDB(id=uuid4(), name="Frontend Developer")
    fa_be = FunctionalAreaDB(id=uuid4(), name="Backend Developer")
    db_session.add_all([fa_fe, fa_be])
    await db_session.flush()

    user1 = UserDB(
        id=uuid4(), email="alice@test.com", name="Alice Test",
        functional_area_id=fa_fe.id,
    )
    user2 = UserDB(
        id=uuid4(), email="bob@test.com", name="Bob Test",
        functional_area_id=fa_be.id,
    )
    project1 = ProjectDB(id=uuid4(), name="Alpha", status="active")
    project2 = ProjectDB(id=uuid4(), name="Beta", status="active")

    db_session.add_all([user1, user2, project1, project2])
    await db_session.flush()

    cells = [
        CapacityPlanDB(
            project_id=project1.id, user_id=user1.id,
            week_start=date(2026, 1, 5), percentage=50,
            created_by=user1.id, updated_by=user1.id,
        ),
        CapacityPlanDB(
            project_id=project1.id, user_id=user1.id,
            week_start=date(2026, 1, 12), percentage=80,
            created_by=user1.id, updated_by=user1.id,
        ),
        CapacityPlanDB(
            project_id=project2.id, user_id=user1.id,
            week_start=date(2026, 1, 5), percentage=30,
            created_by=user1.id, updated_by=user1.id,
        ),
        CapacityPlanDB(
            project_id=project1.id, user_id=user2.id,
            week_start=date(2026, 1, 5), percentage=60,
            created_by=user2.id, updated_by=user2.id,
        ),
    ]
    db_session.add_all(cells)
    await db_session.flush()

    return {
        "user1": user1, "user2": user2,
        "project1": project1, "project2": project2,
    }


class FakeUser:
    """Minimal auth user stub for direct endpoint calls."""
    def __init__(self, user_id):
        self.user_id = user_id


class TestGetPlanner:
    @pytest.mark.asyncio
    async def test_returns_grouped_by_project(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_planner

        result = await get_planner(
            db=db_session, user=FakeUser(planner_data["user1"].id),
            start="2026-01-05", end="2026-01-19", group_by="project",
        )

        assert "groups" in result
        assert "weeks" in result
        assert len(result["weeks"]) == 3

        alpha = next(g for g in result["groups"] if g["name"] == "Alpha")
        assert len(alpha["rows"]) == 2

    @pytest.mark.asyncio
    async def test_returns_grouped_by_user(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_planner

        result = await get_planner(
            db=db_session, user=FakeUser(planner_data["user1"].id),
            start="2026-01-05", end="2026-01-19", group_by="user",
        )

        alice = next(g for g in result["groups"] if "Alice" in g["name"])
        assert len(alice["rows"]) == 2

    @pytest.mark.asyncio
    async def test_sparse_cells(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_planner

        result = await get_planner(
            db=db_session, user=FakeUser(planner_data["user1"].id),
            start="2026-01-05", end="2026-01-19", group_by="project",
        )

        alpha = next(g for g in result["groups"] if g["name"] == "Alpha")
        alice_row = next(r for r in alpha["rows"] if "Alice" in r["user_name"])
        assert "2026-01-05" in alice_row["cells"]
        assert "2026-01-12" in alice_row["cells"]
        assert "2026-01-19" not in alice_row["cells"]

    @pytest.mark.asyncio
    async def test_returns_comments_per_row(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_planner

        from sqlalchemy import update
        await db_session.execute(
            update(CapacityPlanDB)
            .where(
                CapacityPlanDB.user_id == planner_data["user1"].id,
                CapacityPlanDB.project_id == planner_data["project1"].id,
                CapacityPlanDB.week_start == date(2026, 1, 5),
            )
            .values(comment="Need reviewer")
        )
        await db_session.flush()

        fake_user = FakeUser(planner_data["user1"].id)
        result = await get_planner(
            db_session, fake_user,
            start="2026-01-05", end="2026-01-12",
            group_by="user",
        )

        user1_group = next(g for g in result["groups"] if g["id"] == str(planner_data["user1"].id))
        row = next(r for r in user1_group["rows"] if r["project_id"] == str(planner_data["project1"].id))
        assert row["comments"] == {"2026-01-05": "Need reviewer"}

    @pytest.mark.asyncio
    async def test_rows_without_comments_return_empty_map(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_planner

        fake_user = FakeUser(planner_data["user1"].id)
        result = await get_planner(
            db_session, fake_user,
            start="2026-01-05", end="2026-01-12",
            group_by="user",
        )

        for group in result["groups"]:
            for row in group["rows"]:
                assert row["comments"] == {}

    @pytest.mark.asyncio
    async def test_fa_short_name_mapping(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_planner

        result = await get_planner(
            db=db_session, user=FakeUser(planner_data["user1"].id),
            start="2026-01-05", end="2026-01-19", group_by="project",
        )

        alpha = next(g for g in result["groups"] if g["name"] == "Alpha")
        alice_row = next(r for r in alpha["rows"] if "Alice" in r["user_name"])
        assert alice_row["functional_area"] == "FE"


class TestUpdateCells:
    @pytest.mark.asyncio
    async def test_upsert_new_cell(self, db_session, planner_data):
        from app.modules.capacity.api.planner import update_cells
        from app.modules.capacity.models.capacity_plan import BulkCellUpdate

        body = BulkCellUpdate(updates=[{
            "project_id": str(planner_data["project2"].id),
            "user_id": str(planner_data["user2"].id),
            "week_start": "2026-01-05",
            "percentage": 40,
        }])

        result = await update_cells(
            db=db_session, user=FakeUser(planner_data["user1"].id), body=body,
        )
        assert result["updated"] == 1

        stmt = select(CapacityPlanDB).where(
            CapacityPlanDB.project_id == planner_data["project2"].id,
            CapacityPlanDB.user_id == planner_data["user2"].id,
        )
        rows = (await db_session.execute(stmt)).scalars().all()
        assert len(rows) == 1
        assert rows[0].percentage == 40

    @pytest.mark.asyncio
    async def test_upsert_existing_cell(self, db_session, planner_data):
        from app.modules.capacity.api.planner import update_cells
        from app.modules.capacity.models.capacity_plan import BulkCellUpdate

        body = BulkCellUpdate(updates=[{
            "project_id": str(planner_data["project1"].id),
            "user_id": str(planner_data["user1"].id),
            "week_start": "2026-01-05",
            "percentage": 99,
        }])

        result = await update_cells(
            db=db_session, user=FakeUser(planner_data["user1"].id), body=body,
        )
        assert result["updated"] == 1

        stmt = select(CapacityPlanDB).where(
            CapacityPlanDB.project_id == planner_data["project1"].id,
            CapacityPlanDB.user_id == planner_data["user1"].id,
            CapacityPlanDB.week_start == date(2026, 1, 5),
        )
        row = (await db_session.execute(stmt)).scalar_one()
        assert row.percentage == 99

    @pytest.mark.asyncio
    async def test_delete_cell_with_null(self, db_session, planner_data):
        from app.modules.capacity.api.planner import update_cells
        from app.modules.capacity.models.capacity_plan import BulkCellUpdate

        body = BulkCellUpdate(updates=[{
            "project_id": str(planner_data["project1"].id),
            "user_id": str(planner_data["user1"].id),
            "week_start": "2026-01-05",
            "percentage": None,
        }])

        result = await update_cells(
            db=db_session, user=FakeUser(planner_data["user1"].id), body=body,
        )
        assert result["updated"] == 1

        stmt = select(CapacityPlanDB).where(
            CapacityPlanDB.project_id == planner_data["project1"].id,
            CapacityPlanDB.user_id == planner_data["user1"].id,
            CapacityPlanDB.week_start == date(2026, 1, 5),
        )
        rows = (await db_session.execute(stmt)).scalars().all()
        assert len(rows) == 0

    @pytest.mark.asyncio
    async def test_delete_cell_with_zero(self, db_session, planner_data):
        from app.modules.capacity.api.planner import update_cells
        from app.modules.capacity.models.capacity_plan import BulkCellUpdate

        body = BulkCellUpdate(updates=[{
            "project_id": str(planner_data["project1"].id),
            "user_id": str(planner_data["user1"].id),
            "week_start": "2026-01-05",
            "percentage": 0,
        }])

        result = await update_cells(
            db=db_session, user=FakeUser(planner_data["user1"].id), body=body,
        )
        assert result["updated"] == 1


class TestDeleteRow:
    @pytest.mark.asyncio
    async def test_deletes_all_cells_for_combination(self, db_session, planner_data):
        from app.modules.capacity.api.planner import delete_row

        result = await delete_row(
            db=db_session, user=FakeUser(planner_data["user1"].id),
            project_id=planner_data["project1"].id,
            user_id=planner_data["user1"].id,
        )
        assert result["deleted"] == 2


class TestGetPlannerFiltering:
    @pytest.mark.asyncio
    async def test_excludes_finished_projects(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_planner

        planner_data["project1"].status = "finished"
        await db_session.flush()

        result = await get_planner(
            db=db_session, user=FakeUser(planner_data["user1"].id),
            start="2026-01-05", end="2026-01-19", group_by="project",
        )

        group_names = [g["name"] for g in result["groups"]]
        assert "Alpha" not in group_names

    @pytest.mark.asyncio
    async def test_excludes_inactive_users(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_planner

        planner_data["user2"].active = False
        await db_session.flush()

        result = await get_planner(
            db=db_session, user=FakeUser(planner_data["user1"].id),
            start="2026-01-05", end="2026-01-19", group_by="project",
        )

        alpha = next(g for g in result["groups"] if g["name"] == "Alpha")
        user_names = [r["user_name"] for r in alpha["rows"]]
        assert "Bob Test" not in user_names

    @pytest.mark.asyncio
    async def test_includes_empty_billable_project_groups(self, db_session):
        """Live billable projects with no planner data appear as empty groups."""
        from app.modules.capacity.api.planner import get_planner

        empty_proj = ProjectDB(id=uuid4(), name="Zeta New", status="live", is_billable=True)
        db_session.add(empty_proj)
        await db_session.flush()

        user = UserDB(id=uuid4(), email="solo@test.com", name="Solo")
        db_session.add(user)
        await db_session.flush()

        result = await get_planner(
            db=db_session, user=FakeUser(user.id),
            start="2026-01-05", end="2026-01-19", group_by="project",
        )

        zeta = next((g for g in result["groups"] if g["name"] == "Zeta New"), None)
        assert zeta is not None
        assert len(zeta["rows"]) == 0

    @pytest.mark.asyncio
    async def test_empty_groups_sorted_after_groups_with_data(self, db_session, planner_data):
        """Groups with data come first, empty groups at the end."""
        from app.modules.capacity.api.planner import get_planner

        empty_proj = ProjectDB(id=uuid4(), name="AAA First", status="live", is_billable=True)
        db_session.add(empty_proj)
        await db_session.flush()

        result = await get_planner(
            db=db_session, user=FakeUser(planner_data["user1"].id),
            start="2026-01-05", end="2026-01-19", group_by="project",
        )

        groups = result["groups"]
        has_data = [g for g in groups if len(g["rows"]) > 0]
        empty = [g for g in groups if len(g["rows"]) == 0]
        # All data groups come before empty groups
        data_indices = [groups.index(g) for g in has_data]
        empty_indices = [groups.index(g) for g in empty]
        if data_indices and empty_indices:
            assert max(data_indices) < min(empty_indices)


class TestAbsenceAndOthers:
    @pytest.mark.asyncio
    async def test_absence_excluded_from_project_view(self, db_session, planner_data):
        """Absence project rows don't appear in project view."""
        from app.modules.capacity.api.planner import get_planner

        absence = ProjectDB(id=uuid4(), name="Vacation", status="live", is_absence=True, is_billable=False)
        db_session.add(absence)
        await db_session.flush()

        db_session.add(CapacityPlanDB(
            project_id=absence.id, user_id=planner_data["user1"].id,
            week_start=date(2026, 1, 5), percentage=20,
            created_by=planner_data["user1"].id, updated_by=planner_data["user1"].id,
        ))
        await db_session.flush()

        result = await get_planner(
            db=db_session, user=FakeUser(planner_data["user1"].id),
            start="2026-01-05", end="2026-01-19", group_by="project",
        )

        group_names = [g["name"] for g in result["groups"]]
        assert "Vacation" not in group_names

    @pytest.mark.asyncio
    async def test_absence_injected_in_user_view(self, db_session):
        """Every user group in user view gets a pinned absence row."""
        from app.modules.capacity.api.planner import get_planner

        absence = ProjectDB(id=uuid4(), name="Vacation", status="live", is_absence=True, is_billable=False)
        user = UserDB(id=uuid4(), email="test@t.com", name="Test", requires_project_reporting=True)
        proj = ProjectDB(id=uuid4(), name="Proj", status="live", is_billable=True)
        db_session.add_all([absence, user, proj])
        await db_session.flush()

        db_session.add(CapacityPlanDB(
            project_id=proj.id, user_id=user.id,
            week_start=date(2026, 1, 5), percentage=50,
            created_by=user.id, updated_by=user.id,
        ))
        await db_session.flush()

        result = await get_planner(
            db=db_session, user=FakeUser(user.id),
            start="2026-01-05", end="2026-01-19", group_by="user",
        )

        test_group = next(g for g in result["groups"] if "Test" in g["name"])
        absence_rows = [r for r in test_group["rows"] if r["is_absence"]]
        assert len(absence_rows) == 1
        assert absence_rows[0]["project_name"] == "Vacation"

    @pytest.mark.asyncio
    async def test_non_billable_excluded_from_project_view(self, db_session, planner_data):
        """Non-billable project rows don't appear in project view."""
        from app.modules.capacity.api.planner import get_planner

        internal = ProjectDB(id=uuid4(), name="Internal", status="live", is_billable=False)
        db_session.add(internal)
        await db_session.flush()

        db_session.add(CapacityPlanDB(
            project_id=internal.id, user_id=planner_data["user1"].id,
            week_start=date(2026, 1, 5), percentage=10,
            created_by=planner_data["user1"].id, updated_by=planner_data["user1"].id,
        ))
        await db_session.flush()

        result = await get_planner(
            db=db_session, user=FakeUser(planner_data["user1"].id),
            start="2026-01-05", end="2026-01-19", group_by="project",
        )

        group_names = [g["name"] for g in result["groups"]]
        assert "Internal" not in group_names


class TestWarnings:
    @pytest.mark.asyncio
    async def test_warns_when_allocations_exceed_100(self, db_session):
        """Users whose weekly allocations exceed 100% appear in warnings."""
        from app.modules.capacity.api.planner import get_planner

        user = UserDB(id=uuid4(), email="over@t.com", name="Over")
        p1 = ProjectDB(id=uuid4(), name="P1", status="live", is_billable=True)
        p2 = ProjectDB(id=uuid4(), name="P2", status="live", is_billable=True)
        db_session.add_all([user, p1, p2])
        await db_session.flush()

        db_session.add_all([
            CapacityPlanDB(
                project_id=p1.id, user_id=user.id,
                week_start=date(2026, 1, 5), percentage=60,
                created_by=user.id, updated_by=user.id,
            ),
            CapacityPlanDB(
                project_id=p2.id, user_id=user.id,
                week_start=date(2026, 1, 5), percentage=50,
                created_by=user.id, updated_by=user.id,
            ),
        ])
        await db_session.flush()

        result = await get_planner(
            db=db_session, user=FakeUser(user.id),
            start="2026-01-05", end="2026-01-19", group_by="project",
        )

        assert str(user.id) in result["warnings"]

    @pytest.mark.asyncio
    async def test_no_warning_at_100(self, db_session):
        """Users at exactly 100% don't appear in warnings."""
        from app.modules.capacity.api.planner import get_planner

        user = UserDB(id=uuid4(), email="exact@t.com", name="Exact")
        p1 = ProjectDB(id=uuid4(), name="P1", status="live", is_billable=True)
        p2 = ProjectDB(id=uuid4(), name="P2", status="live", is_billable=True)
        db_session.add_all([user, p1, p2])
        await db_session.flush()

        db_session.add_all([
            CapacityPlanDB(
                project_id=p1.id, user_id=user.id,
                week_start=date(2026, 1, 5), percentage=60,
                created_by=user.id, updated_by=user.id,
            ),
            CapacityPlanDB(
                project_id=p2.id, user_id=user.id,
                week_start=date(2026, 1, 5), percentage=40,
                created_by=user.id, updated_by=user.id,
            ),
        ])
        await db_session.flush()

        result = await get_planner(
            db=db_session, user=FakeUser(user.id),
            start="2026-01-05", end="2026-01-19", group_by="project",
        )

        assert str(user.id) not in result["warnings"]


class TestSuggestions:
    @pytest.mark.asyncio
    async def test_normalizes_to_100(self, db_session):
        """Suggestions sum to ~100% (minus Others if present)."""
        from app.modules.capacity.api.planner import get_planner_suggestions

        user = UserDB(id=uuid4(), email="s@t.com", name="Sugg")
        p1 = ProjectDB(id=uuid4(), name="Alpha", status="active", is_billable=True)
        p2 = ProjectDB(id=uuid4(), name="Beta", status="active", is_billable=True)
        db_session.add_all([user, p1, p2])
        await db_session.flush()

        # 3 Mondays in Jan 2026: 5, 12, 19, 26
        for monday in [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19), date(2026, 1, 26)]:
            db_session.add_all([
                CapacityPlanDB(
                    project_id=p1.id, user_id=user.id,
                    week_start=monday, percentage=60,
                    created_by=user.id, updated_by=user.id,
                ),
                CapacityPlanDB(
                    project_id=p2.id, user_id=user.id,
                    week_start=monday, percentage=40,
                    created_by=user.id, updated_by=user.id,
                ),
            ])
        await db_session.flush()

        result = await get_planner_suggestions(
            db=db_session, user=FakeUser(user.id), month="2026-01-01",
        )

        total = sum(s["percentage"] for s in result["suggestions"])
        assert abs(total - 100.0) < 0.2
        alpha = next(s for s in result["suggestions"] if s["project_name"] == "Alpha")
        assert alpha["percentage"] == 60.0
        assert result["others_percentage"] is None

    @pytest.mark.asyncio
    async def test_others_separated(self, db_session):
        """Operations project appears as others_percentage, not in suggestions."""
        from app.modules.capacity.api.planner import get_planner_suggestions

        user = UserDB(id=uuid4(), email="o@t.com", name="Oth")
        billable = ProjectDB(id=uuid4(), name="Proj", status="active", is_billable=True)
        operations = ProjectDB(id=uuid4(), name="Operations", status="active", is_billable=False)
        db_session.add_all([user, billable, operations])
        await db_session.flush()

        db_session.add_all([
            CapacityPlanDB(
                project_id=billable.id, user_id=user.id,
                week_start=date(2026, 1, 5), percentage=80,
                created_by=user.id, updated_by=user.id,
            ),
            CapacityPlanDB(
                project_id=operations.id, user_id=user.id,
                week_start=date(2026, 1, 5), percentage=20,
                created_by=user.id, updated_by=user.id,
            ),
        ])
        await db_session.flush()

        result = await get_planner_suggestions(
            db=db_session, user=FakeUser(user.id), month="2026-01-01",
        )

        assert result["others_percentage"] == 20.0
        project_names = [s["project_name"] for s in result["suggestions"]]
        assert "Operations" not in project_names
        assert "Proj" in project_names

    @pytest.mark.asyncio
    async def test_absence_included_in_suggestions(self, db_session):
        """Absence projects appear in suggestions with is_absence=True."""
        from app.modules.capacity.api.planner import get_planner_suggestions

        user = UserDB(id=uuid4(), email="a@t.com", name="Abs")
        billable = ProjectDB(id=uuid4(), name="Work", status="active", is_billable=True)
        absence = ProjectDB(id=uuid4(), name="Vacation", status="active", is_absence=True, is_billable=False)
        db_session.add_all([user, billable, absence])
        await db_session.flush()

        db_session.add_all([
            CapacityPlanDB(
                project_id=billable.id, user_id=user.id,
                week_start=date(2026, 1, 5), percentage=80,
                created_by=user.id, updated_by=user.id,
            ),
            CapacityPlanDB(
                project_id=absence.id, user_id=user.id,
                week_start=date(2026, 1, 5), percentage=20,
                created_by=user.id, updated_by=user.id,
            ),
        ])
        await db_session.flush()

        result = await get_planner_suggestions(
            db=db_session, user=FakeUser(user.id), month="2026-01-01",
        )

        vacation = next(s for s in result["suggestions"] if s["project_name"] == "Vacation")
        assert vacation["is_absence"] is True
        assert vacation["percentage"] == 20.0

    @pytest.mark.asyncio
    async def test_empty_planning_returns_empty(self, db_session):
        """No planning data returns empty suggestions."""
        from app.modules.capacity.api.planner import get_planner_suggestions

        user = UserDB(id=uuid4(), email="e@t.com", name="Empty")
        db_session.add(user)
        await db_session.flush()

        result = await get_planner_suggestions(
            db=db_session, user=FakeUser(user.id), month="2026-01-01",
        )

        assert result["suggestions"] == []
        assert result["others_percentage"] is None


class TestUpdatedAt:
    @pytest.mark.asyncio
    async def test_returns_max_updated_at(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_updated_at

        result = await get_updated_at(
            db=db_session, user=FakeUser(planner_data["user1"].id),
            start="2026-01-05", end="2026-01-19",
        )
        assert result["updated_at"] is not None

    @pytest.mark.asyncio
    async def test_returns_null_for_empty_range(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_updated_at

        result = await get_updated_at(
            db=db_session, user=FakeUser(planner_data["user1"].id),
            start="2030-01-05", end="2030-01-19",
        )
        assert result["updated_at"] is None


class TestCellUpdateSchema:
    def test_accepts_comment_within_limit(self):
        from app.modules.capacity.models.capacity_plan import CellUpdate
        from uuid import uuid4
        from datetime import date

        update = CellUpdate(
            project_id=uuid4(),
            user_id=uuid4(),
            week_start=date(2026, 1, 5),
            percentage=50,
            comment="Short note",
        )
        assert update.comment == "Short note"

    def test_rejects_comment_over_500_chars(self):
        from app.modules.capacity.models.capacity_plan import CellUpdate
        from pydantic import ValidationError
        from uuid import uuid4
        from datetime import date
        import pytest

        with pytest.raises(ValidationError):
            CellUpdate(
                project_id=uuid4(),
                user_id=uuid4(),
                week_start=date(2026, 1, 5),
                percentage=50,
                comment="x" * 501,
            )

    def test_comment_defaults_to_none(self):
        from app.modules.capacity.models.capacity_plan import CellUpdate
        from uuid import uuid4
        from datetime import date

        update = CellUpdate(
            project_id=uuid4(),
            user_id=uuid4(),
            week_start=date(2026, 1, 5),
            percentage=50,
        )
        assert update.comment is None


class TestPatchCellsWithComment:
    @pytest.mark.asyncio
    async def test_creates_cell_with_comment(self, db_session, planner_data):
        from app.modules.capacity.api.planner import update_cells
        from app.modules.capacity.models.capacity_plan import BulkCellUpdate, CellUpdate

        u = planner_data["user1"]
        p = planner_data["project2"]
        fake_user = FakeUser(u.id)

        body = BulkCellUpdate(updates=[
            CellUpdate(
                project_id=p.id, user_id=u.id,
                week_start=date(2026, 1, 12),
                percentage=40,
                comment="Blocked on review",
            ),
        ])
        await update_cells(db_session, fake_user, body)

        stmt = select(CapacityPlanDB).where(
            CapacityPlanDB.user_id == u.id,
            CapacityPlanDB.project_id == p.id,
            CapacityPlanDB.week_start == date(2026, 1, 12),
        )
        row = (await db_session.execute(stmt)).scalar_one()
        assert row.percentage == 40
        assert row.comment == "Blocked on review"

    @pytest.mark.asyncio
    async def test_updates_only_comment_on_existing_cell(self, db_session, planner_data):
        from app.modules.capacity.api.planner import update_cells
        from app.modules.capacity.models.capacity_plan import BulkCellUpdate, CellUpdate

        u = planner_data["user1"]
        p = planner_data["project1"]
        fake_user = FakeUser(u.id)

        body = BulkCellUpdate(updates=[
            CellUpdate(
                project_id=p.id, user_id=u.id,
                week_start=date(2026, 1, 5),
                percentage=50,
                comment="Updated note",
            ),
        ])
        await update_cells(db_session, fake_user, body)

        stmt = select(CapacityPlanDB).where(
            CapacityPlanDB.user_id == u.id,
            CapacityPlanDB.project_id == p.id,
            CapacityPlanDB.week_start == date(2026, 1, 5),
        )
        row = (await db_session.execute(stmt)).scalar_one()
        assert row.percentage == 50
        assert row.comment == "Updated note"

    @pytest.mark.asyncio
    async def test_delete_wipes_comment(self, db_session, planner_data):
        from app.modules.capacity.api.planner import update_cells
        from app.modules.capacity.models.capacity_plan import BulkCellUpdate, CellUpdate
        from sqlalchemy import update as sa_update

        u = planner_data["user1"]
        p = planner_data["project1"]
        fake_user = FakeUser(u.id)

        await db_session.execute(
            sa_update(CapacityPlanDB)
            .where(
                CapacityPlanDB.user_id == u.id,
                CapacityPlanDB.project_id == p.id,
                CapacityPlanDB.week_start == date(2026, 1, 5),
            )
            .values(comment="to be gone")
        )
        await db_session.flush()

        body = BulkCellUpdate(updates=[
            CellUpdate(
                project_id=p.id, user_id=u.id,
                week_start=date(2026, 1, 5),
                percentage=None,
                comment="ignored because cell is being deleted",
            ),
        ])
        await update_cells(db_session, fake_user, body)

        stmt = select(CapacityPlanDB).where(
            CapacityPlanDB.user_id == u.id,
            CapacityPlanDB.project_id == p.id,
            CapacityPlanDB.week_start == date(2026, 1, 5),
        )
        assert (await db_session.execute(stmt)).first() is None
