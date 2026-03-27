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
