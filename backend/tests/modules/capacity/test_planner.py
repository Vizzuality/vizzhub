"""Tests for capacity planner endpoints."""

from datetime import date, datetime, timezone
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


class TestGetPlanner:
    @pytest.mark.asyncio
    async def test_returns_grouped_by_project(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_planner

        class FakeUser:
            user_id = planner_data["user1"].id

        result = await get_planner(
            db=db_session, user=FakeUser(),
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

        class FakeUser:
            user_id = planner_data["user1"].id

        result = await get_planner(
            db=db_session, user=FakeUser(),
            start="2026-01-05", end="2026-01-19", group_by="user",
        )

        alice = next(g for g in result["groups"] if "Alice" in g["name"])
        assert len(alice["rows"]) == 2

    @pytest.mark.asyncio
    async def test_sparse_cells(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_planner

        class FakeUser:
            user_id = planner_data["user1"].id

        result = await get_planner(
            db=db_session, user=FakeUser(),
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

        class FakeUser:
            user_id = planner_data["user1"].id

        result = await get_planner(
            db=db_session, user=FakeUser(),
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

        class FakeUser:
            user_id = planner_data["user1"].id

        body = BulkCellUpdate(updates=[{
            "project_id": str(planner_data["project2"].id),
            "user_id": str(planner_data["user2"].id),
            "week_start": "2026-01-05",
            "percentage": 40,
        }])

        result = await update_cells(db=db_session, user=FakeUser(), body=body)
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

        class FakeUser:
            user_id = planner_data["user1"].id

        body = BulkCellUpdate(updates=[{
            "project_id": str(planner_data["project1"].id),
            "user_id": str(planner_data["user1"].id),
            "week_start": "2026-01-05",
            "percentage": 99,
        }])

        result = await update_cells(db=db_session, user=FakeUser(), body=body)
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

        class FakeUser:
            user_id = planner_data["user1"].id

        body = BulkCellUpdate(updates=[{
            "project_id": str(planner_data["project1"].id),
            "user_id": str(planner_data["user1"].id),
            "week_start": "2026-01-05",
            "percentage": None,
        }])

        result = await update_cells(db=db_session, user=FakeUser(), body=body)
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

        class FakeUser:
            user_id = planner_data["user1"].id

        body = BulkCellUpdate(updates=[{
            "project_id": str(planner_data["project1"].id),
            "user_id": str(planner_data["user1"].id),
            "week_start": "2026-01-05",
            "percentage": 0,
        }])

        result = await update_cells(db=db_session, user=FakeUser(), body=body)
        assert result["updated"] == 1


class TestDeleteRow:
    @pytest.mark.asyncio
    async def test_deletes_all_cells_for_combination(self, db_session, planner_data):
        from app.modules.capacity.api.planner import delete_row

        class FakeUser:
            user_id = planner_data["user1"].id

        result = await delete_row(
            db=db_session, user=FakeUser(),
            project_id=planner_data["project1"].id,
            user_id=planner_data["user1"].id,
        )
        assert result["deleted"] == 2


class TestUpdatedAt:
    @pytest.mark.asyncio
    async def test_returns_max_updated_at(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_updated_at

        class FakeUser:
            user_id = planner_data["user1"].id

        result = await get_updated_at(
            db=db_session, user=FakeUser(),
            start="2026-01-05", end="2026-01-19",
        )
        assert result["updated_at"] is not None

    @pytest.mark.asyncio
    async def test_returns_null_for_empty_range(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_updated_at

        class FakeUser:
            user_id = planner_data["user1"].id

        result = await get_updated_at(
            db=db_session, user=FakeUser(),
            start="2030-01-05", end="2030-01-19",
        )
        assert result["updated_at"] is None
