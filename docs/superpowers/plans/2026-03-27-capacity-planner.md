# Capacity Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an editable weekly Gantt-style grid for planning team capacity allocation, replacing the existing Google Sheet.

**Architecture:** New `capacity_plans` table stores per-cell data (project + user + week + percentage). FastAPI endpoints for CRUD + polling. React frontend with TanStack Table for the editable grid, debounced batch saves, and client-side totals calculation.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React, TypeScript, TanStack Table (`@tanstack/react-table`), React Query, shadcn/ui, Tailwind CSS.

**Spec:** `docs/superpowers/specs/2026-03-27-capacity-planner-design.md`

---

## File Map

### Backend — New Files
- `backend/app/modules/capacity/models/__init__.py` — package init
- `backend/app/modules/capacity/models/capacity_plan.py` — `CapacityPlanDB` SQLAlchemy model + Pydantic schemas
- `backend/app/modules/capacity/api/planner.py` — CRUD endpoints (GET, PATCH, DELETE, updated-at)
- `backend/alembic/versions/037_create_capacity_plans.py` — migration
- `backend/tests/modules/capacity/test_planner.py` — API tests

### Backend — Modified Files
- `backend/app/modules/capacity/router.py` — add planner sub-router

### Frontend — New Files
- `frontend/src/modules/capacity/types/planner.ts` — TypeScript interfaces
- `frontend/src/modules/capacity/utils/plannerColors.ts` — percentage-to-color mapping
- `frontend/src/modules/capacity/services/planner.ts` — API client
- `frontend/src/modules/capacity/hooks/usePlannerData.ts` — fetch + polling hook
- `frontend/src/modules/capacity/hooks/usePlannerMutations.ts` — batch save + delete hooks
- `frontend/src/modules/capacity/components/PlannerCell.tsx` — editable cell with color
- `frontend/src/modules/capacity/components/PlannerToolbar.tsx` — toolbar (toggle, FA filter, nav)
- `frontend/src/modules/capacity/components/PlannerAddRow.tsx` — add row selector
- `frontend/src/modules/capacity/components/PlannerSaveIndicator.tsx` — save status
- `frontend/src/modules/capacity/components/PlannerGrid.tsx` — TanStack Table wrapper
- `frontend/src/modules/capacity/pages/Planner.tsx` — page component

### Frontend — Modified Files
- `frontend/src/core/hooks/queryKeys.ts` — add planner keys
- `frontend/src/App.tsx` — add route
- `frontend/src/core/components/layout/AppSidebar.tsx` — add sidebar entry

### Seed Scripts
- `scripts/export_capacity_xlsx_to_json.py` — xlsx → JSON
- `scripts/seed_capacity_planner.py` — JSON → DB

---

## Task 1: Database Model & Migration

**Files:**
- Create: `backend/app/modules/capacity/models/__init__.py`
- Create: `backend/app/modules/capacity/models/capacity_plan.py`
- Create: `backend/alembic/versions/037_create_capacity_plans.py`

- [ ] **Step 1: Create the SQLAlchemy model and Pydantic schemas**

Create `backend/app/modules/capacity/models/__init__.py`:
```python
```

Create `backend/app/modules/capacity/models/capacity_plan.py`:
```python
"""Capacity planning model — stores weekly allocation per project/user."""

from datetime import date, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class CapacityPlanDB(Base):
    __tablename__ = "capacity_plans"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", "week_start", name="uq_capacity_plan_cell"),
        CheckConstraint("percentage >= 1 AND percentage <= 200", name="ck_capacity_plan_pct"),
        CheckConstraint(
            "EXTRACT(ISODOW FROM week_start) = 1",
            name="ck_capacity_plan_monday",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    percentage: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CellUpdate(BaseModel):
    project_id: UUID
    user_id: UUID
    week_start: date
    percentage: int | None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("week_start")
    @classmethod
    def must_be_monday(cls, v: date) -> date:
        if v.isoweekday() != 1:
            raise ValueError("week_start must be a Monday")
        return v

    @field_validator("percentage")
    @classmethod
    def valid_range(cls, v: int | None) -> int | None:
        if v is not None and (v < 0 or v > 200):
            raise ValueError("percentage must be 0-200 or null")
        return v


class BulkCellUpdate(BaseModel):
    updates: list[CellUpdate]
```

- [ ] **Step 2: Create the Alembic migration**

Create `backend/alembic/versions/037_create_capacity_plans.py`:
```python
"""Create capacity_plans table.

Revision ID: 037_capacity_plans
Revises: 036_invoice_postponed_alert
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "037_capacity_plans"
down_revision = "036_invoice_postponed_alert"


def upgrade() -> None:
    op.create_table(
        "capacity_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("percentage", sa.SmallInteger, nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "user_id", "week_start", name="uq_capacity_plan_cell"),
        sa.CheckConstraint("percentage >= 1 AND percentage <= 200", name="ck_capacity_plan_pct"),
        sa.CheckConstraint("EXTRACT(ISODOW FROM week_start) = 1", name="ck_capacity_plan_monday"),
    )
    op.create_index("ix_capacity_plans_project_user", "capacity_plans", ["project_id", "user_id"])
    op.create_index("ix_capacity_plans_week", "capacity_plans", ["week_start"])


def downgrade() -> None:
    op.drop_index("ix_capacity_plans_week")
    op.drop_index("ix_capacity_plans_project_user")
    op.drop_table("capacity_plans")
```

- [ ] **Step 3: Run migration**

Run: `pushd backend > /dev/null && alembic upgrade head && popd > /dev/null`
Expected: migration applies successfully, table exists.

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/capacity/models/ backend/alembic/versions/037_create_capacity_plans.py
git commit -m "feat(capacity): add capacity_plans table and model"
```

---

## Task 2: Backend API Endpoints

**Files:**
- Create: `backend/app/modules/capacity/api/planner.py`
- Modify: `backend/app/modules/capacity/router.py`

- [ ] **Step 1: Write the planner API endpoints**

Create `backend/app/modules/capacity/api/planner.py`:
```python
"""Capacity planner CRUD endpoints."""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.api.deps import CurrentUser, DBSession
from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.core.services.capacity_insights import TARGET_FA_MAPPING
from app.modules.capacity.models.capacity_plan import BulkCellUpdate, CapacityPlanDB

router = APIRouter()


def _fa_short_name(fa_name: str | None) -> str:
    """Map full FA name to short code: 'Frontend Developer' → 'FE'."""
    if not fa_name:
        return ""
    return TARGET_FA_MAPPING.get(fa_name, fa_name)


def _user_name_expr():
    """SQL expression for user display name: first+last > name > email prefix."""
    return func.coalesce(
        func.nullif(
            func.concat_ws(" ", func.nullif(UserDB.first_name, ""), func.nullif(UserDB.last_name, "")),
            "",
        ),
        UserDB.name,
        func.split_part(UserDB.email, "@", 1),
    )


def _mondays_between(start: date, end: date) -> list[str]:
    """Return list of Monday ISO date strings in range [start, end]."""
    from datetime import timedelta

    # Snap start to Monday
    current = start - timedelta(days=start.weekday())
    weeks = []
    while current <= end:
        weeks.append(current.isoformat())
        current += timedelta(weeks=1)
    return weeks


def _parse_date(value: str, name: str) -> date:
    """Parse YYYY-MM-DD string to date."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date format for {name}: {value}")


@router.get("")
async def get_planner(
    db: DBSession,
    user: CurrentUser,
    start: str = Query(description="Start date (YYYY-MM-DD, Monday)"),
    end: str = Query(description="End date (YYYY-MM-DD, Monday)"),
    group_by: str = Query(default="project", description="Group by: project | user"),
) -> dict:
    start_date = _parse_date(start, "start")
    end_date = _parse_date(end, "end")

    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start must be <= end")

    if group_by not in ("project", "user"):
        raise HTTPException(status_code=422, detail="group_by must be 'project' or 'user'")

    weeks = _mondays_between(start_date, end_date)

    stmt = (
        select(
            CapacityPlanDB.project_id,
            ProjectDB.name.label("project_name"),
            CapacityPlanDB.user_id,
            _user_name_expr().label("user_name"),
            FunctionalAreaDB.name.label("functional_area"),
            CapacityPlanDB.week_start,
            CapacityPlanDB.percentage,
        )
        .join(ProjectDB, CapacityPlanDB.project_id == ProjectDB.id)
        .join(UserDB, CapacityPlanDB.user_id == UserDB.id)
        .outerjoin(FunctionalAreaDB, FunctionalAreaDB.id == UserDB.functional_area_id)
        .where(CapacityPlanDB.week_start >= start_date)
        .where(CapacityPlanDB.week_start <= end_date)
        .order_by(ProjectDB.name, UserDB.name, CapacityPlanDB.week_start)
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Build grouped response
    groups_map: dict[str, dict] = {}
    rows_map: dict[str, dict] = {}

    for row in rows:
        if group_by == "project":
            group_key = str(row.project_id)
            group_name = row.project_name
            row_key = f"{row.project_id}:{row.user_id}"
        else:
            group_key = str(row.user_id)
            group_name = row.user_name
            row_key = f"{row.user_id}:{row.project_id}"

        if group_key not in groups_map:
            groups_map[group_key] = {"id": group_key, "name": group_name, "rows": []}

        if row_key not in rows_map:
            row_data = {
                "user_id": str(row.user_id),
                "user_name": row.user_name,
                "functional_area": _fa_short_name(row.functional_area),
                "project_id": str(row.project_id),
                "project_name": row.project_name,
                "cells": {},
            }
            rows_map[row_key] = row_data
            groups_map[group_key]["rows"].append(row_data)

        rows_map[row_key]["cells"][row.week_start.isoformat()] = row.percentage

    return {"groups": list(groups_map.values()), "weeks": weeks}


@router.patch("/cells")
async def update_cells(
    db: DBSession,
    user: CurrentUser,
    body: BulkCellUpdate,
) -> dict:
    if not body.updates:
        return {"updated": 0}

    deletes = []
    upserts = []

    for cell in body.updates:
        if cell.percentage is None or cell.percentage == 0:
            deletes.append(cell)
        else:
            upserts.append(cell)

    deleted_count = 0
    for cell in deletes:
        stmt = delete(CapacityPlanDB).where(
            CapacityPlanDB.project_id == cell.project_id,
            CapacityPlanDB.user_id == cell.user_id,
            CapacityPlanDB.week_start == cell.week_start,
        )
        result = await db.execute(stmt)
        deleted_count += result.rowcount

    upserted_count = 0
    if upserts:
        values = [
            {
                "project_id": cell.project_id,
                "user_id": cell.user_id,
                "week_start": cell.week_start,
                "percentage": cell.percentage,
                "created_by": user.user_id,
                "updated_by": user.user_id,
            }
            for cell in upserts
        ]
        stmt = pg_insert(CapacityPlanDB).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_capacity_plan_cell",
            set_={
                "percentage": stmt.excluded.percentage,
                "updated_by": stmt.excluded.updated_by,
                "updated_at": func.now(),
            },
        )
        await db.execute(stmt)
        upserted_count = len(upserts)

    await db.commit()
    return {"updated": upserted_count + deleted_count}


@router.delete("/rows/{project_id}/{user_id}")
async def delete_row(
    db: DBSession,
    user: CurrentUser,
    project_id: UUID,
    user_id: UUID,
) -> dict:
    stmt = delete(CapacityPlanDB).where(
        CapacityPlanDB.project_id == project_id,
        CapacityPlanDB.user_id == user_id,
    )
    result = await db.execute(stmt)
    await db.commit()
    return {"deleted": result.rowcount}


@router.get("/updated-at")
async def get_updated_at(
    db: DBSession,
    user: CurrentUser,
    start: str = Query(description="Start date (YYYY-MM-DD)"),
    end: str = Query(description="End date (YYYY-MM-DD)"),
) -> dict:
    start_date = _parse_date(start, "start")
    end_date = _parse_date(end, "end")

    stmt = select(func.max(CapacityPlanDB.updated_at)).where(
        CapacityPlanDB.week_start >= start_date,
        CapacityPlanDB.week_start <= end_date,
    )
    result = await db.execute(stmt)
    max_updated = result.scalar_one_or_none()

    return {"updated_at": max_updated.isoformat() if max_updated else None}
```

- [ ] **Step 2: Register planner sub-router**

Modify `backend/app/modules/capacity/router.py` — add after the allocation router include:
```python
from app.modules.capacity.api import planner as planner_router

# Add at the end of the file:
router.include_router(
    planner_router.router, prefix="/planner", tags=["capacity:planner"]
)
```

- [ ] **Step 3: Verify endpoints load**

Run: `pushd backend > /dev/null && python -c "from app.main import app; print('OK')" && popd > /dev/null`
Expected: `OK` (no import errors)

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/capacity/api/planner.py backend/app/modules/capacity/router.py
git commit -m "feat(capacity): add planner CRUD endpoints"
```

---

## Task 3: Backend Tests

**Files:**
- Create: `backend/tests/modules/capacity/test_planner.py`

- [ ] **Step 1: Write planner API tests**

Create `backend/tests/modules/capacity/test_planner.py`:
```python
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
    fa_fe = FunctionalAreaDB(id=uuid4(), name="FE")
    fa_be = FunctionalAreaDB(id=uuid4(), name="BE")
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

    # Create some capacity plan cells
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
        from app.modules.capacity.api.planner import get_planner, _mondays_between

        # Mock the dependencies
        class FakeUser:
            user_id = planner_data["user1"].id

        result = await get_planner(
            db=db_session, user=FakeUser(),
            start="2026-01-05", end="2026-01-19", group_by="project",
        )

        assert "groups" in result
        assert "weeks" in result
        assert len(result["weeks"]) == 3  # Jan 5, 12, 19

        # Alpha project should have 2 users
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

        # Alice has cells in both projects
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
        assert result["deleted"] == 2  # 2 cells for Alice in Alpha


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
```

- [ ] **Step 2: Run tests**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/capacity/test_planner.py -v && popd > /dev/null`
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/modules/capacity/test_planner.py
git commit -m "test(capacity): add planner API tests"
```

---

## Task 4: Frontend Types, Colors & Service

**Files:**
- Create: `frontend/src/modules/capacity/types/planner.ts`
- Create: `frontend/src/modules/capacity/utils/plannerColors.ts`
- Create: `frontend/src/modules/capacity/services/planner.ts`
- Modify: `frontend/src/core/hooks/queryKeys.ts`

- [ ] **Step 1: Create planner types**

Create `frontend/src/modules/capacity/types/planner.ts`:
```typescript
export interface PlannerRow {
  user_id: string;
  user_name: string;
  functional_area: string;
  project_id: string;
  project_name: string;
  cells: Record<string, number>;
}

export interface PlannerGroup {
  id: string;
  name: string;
  rows: PlannerRow[];
}

export interface PlannerResponse {
  groups: PlannerGroup[];
  weeks: string[];
}

export interface CellUpdate {
  project_id: string;
  user_id: string;
  week_start: string;
  percentage: number | null;
}

export interface UpdatedAtResponse {
  updated_at: string | null;
}
```

- [ ] **Step 2: Create color utility**

Create `frontend/src/modules/capacity/utils/plannerColors.ts`:
```typescript
interface ColorRange {
  min: number;
  max: number;
  light: string;
  dark: string;
}

const RANGES: ColorRange[] = [
  { min: 1, max: 20, light: '#D9EAD3', dark: '#2A3B28' },
  { min: 21, max: 40, light: '#FFE599', dark: '#4A3D1A' },
  { min: 41, max: 60, light: '#F9CB9C', dark: '#4A2E1A' },
  { min: 61, max: 80, light: '#F6B26B', dark: '#4A2A10' },
  { min: 81, max: 100, light: '#E06666', dark: '#4A1A1A' },
  { min: 101, max: 200, light: '#8E7CC3', dark: '#2E2450' },
];

export function getPlannerCellColor(
  percentage: number | undefined,
  isDark: boolean,
): string | undefined {
  if (percentage === undefined) return undefined;
  const range = RANGES.find((r) => percentage >= r.min && percentage <= r.max);
  if (!range) return undefined;
  return isDark ? range.dark : range.light;
}
```

- [ ] **Step 3: Create planner API service**

Create `frontend/src/modules/capacity/services/planner.ts`:
```typescript
import api from '@/core/services/client';
import type {
  CellUpdate,
  PlannerResponse,
  UpdatedAtResponse,
} from '@/modules/capacity/types/planner';

export const plannerApi = {
  get: async (
    start: string,
    end: string,
    groupBy: string,
  ): Promise<PlannerResponse> => {
    const response = await api.get<PlannerResponse>('/capacity/planner', {
      params: { start, end, group_by: groupBy },
    });
    return response.data;
  },

  updateCells: async (updates: CellUpdate[]): Promise<{ updated: number }> => {
    const response = await api.patch<{ updated: number }>(
      '/capacity/planner/cells',
      { updates },
    );
    return response.data;
  },

  deleteRow: async (
    projectId: string,
    userId: string,
  ): Promise<{ deleted: number }> => {
    const response = await api.delete<{ deleted: number }>(
      `/capacity/planner/rows/${projectId}/${userId}`,
    );
    return response.data;
  },

  getUpdatedAt: async (
    start: string,
    end: string,
  ): Promise<UpdatedAtResponse> => {
    const response = await api.get<UpdatedAtResponse>(
      '/capacity/planner/updated-at',
      { params: { start, end } },
    );
    return response.data;
  },
};
```

- [ ] **Step 4: Add query keys**

Modify `frontend/src/core/hooks/queryKeys.ts` — add inside the `capacity` object after the existing keys:
```typescript
planner: (start: string, end: string, groupBy: string) =>
  ['capacity', 'planner', start, end, groupBy] as const,
plannerUpdatedAt: (start: string, end: string) =>
  ['capacity', 'planner', 'updated-at', start, end] as const,
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/capacity/types/planner.ts frontend/src/modules/capacity/utils/plannerColors.ts frontend/src/modules/capacity/services/planner.ts frontend/src/core/hooks/queryKeys.ts
git commit -m "feat(capacity): add planner types, colors, service, and query keys"
```

---

## Task 5: Frontend Hooks (Data + Mutations)

**Files:**
- Create: `frontend/src/modules/capacity/hooks/usePlannerData.ts`
- Create: `frontend/src/modules/capacity/hooks/usePlannerMutations.ts`

- [ ] **Step 1: Create the data fetch + polling hook**

Create `frontend/src/modules/capacity/hooks/usePlannerData.ts`:
```typescript
import { useEffect, useRef } from 'react';
import { useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { plannerApi } from '@/modules/capacity/services/planner';
import type { PlannerResponse } from '@/modules/capacity/types/planner';

const POLL_INTERVAL = 20_000;

export function usePlannerData(
  start: string,
  end: string,
  groupBy: string,
  flushPending?: () => Promise<void>,
): UseQueryResult<PlannerResponse> {
  const queryClient = useQueryClient();
  const lastUpdatedAt = useRef<string | null>(null);
  const flushRef = useRef(flushPending);
  flushRef.current = flushPending;

  const query = useQuery({
    queryKey: queryKeys.capacity.planner(start, end, groupBy),
    queryFn: () => plannerApi.get(start, end, groupBy),
  });

  useEffect(() => {
    if (!start || !end) return;

    const interval = setInterval(async () => {
      try {
        const { updated_at } = await plannerApi.getUpdatedAt(start, end);
        if (
          updated_at &&
          lastUpdatedAt.current &&
          updated_at > lastUpdatedAt.current
        ) {
          // Flush pending local changes before refetching
          if (flushRef.current) await flushRef.current();
          queryClient.invalidateQueries({
            queryKey: queryKeys.capacity.planner(start, end, groupBy),
          });
        }
        lastUpdatedAt.current = updated_at;
      } catch {
        // Silently ignore polling errors
      }
    }, POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [start, end, groupBy, queryClient]);

  useEffect(() => {
    if (query.dataUpdatedAt) {
      lastUpdatedAt.current = new Date().toISOString();
    }
  }, [query.dataUpdatedAt]);

  return query;
}
```

- [ ] **Step 2: Create mutations hook with debounced batch save**

Create `frontend/src/modules/capacity/hooks/usePlannerMutations.ts`:
```typescript
import { useCallback, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { plannerApi } from '@/modules/capacity/services/planner';
import type { CellUpdate } from '@/modules/capacity/types/planner';

const DEBOUNCE_MS = 1500;

interface UsePlannerMutationsReturn {
  queueCellUpdate: (update: CellUpdate) => void;
  flushUpdates: () => Promise<void>;
  deleteRow: (projectId: string, userId: string) => Promise<void>;
  isSaving: boolean;
  pendingCount: number;
}

export function usePlannerMutations(
  start: string,
  end: string,
  groupBy: string,
): UsePlannerMutationsReturn {
  const queryClient = useQueryClient();
  const pendingRef = useRef<Map<string, CellUpdate>>(new Map());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cellMutation = useMutation({
    mutationFn: (updates: CellUpdate[]) => plannerApi.updateCells(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.capacity.planner(start, end, groupBy),
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ projectId, userId }: { projectId: string; userId: string }) =>
      plannerApi.deleteRow(projectId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.capacity.planner(start, end, groupBy),
      });
    },
  });

  const flushUpdates = useCallback(async (): Promise<void> => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const updates = Array.from(pendingRef.current.values());
    if (updates.length === 0) return;
    pendingRef.current.clear();
    await cellMutation.mutateAsync(updates);
  }, [cellMutation]);

  const queueCellUpdate = useCallback(
    (update: CellUpdate): void => {
      const key = `${update.project_id}:${update.user_id}:${update.week_start}`;
      pendingRef.current.set(key, update);

      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        flushUpdates();
      }, DEBOUNCE_MS);
    },
    [flushUpdates],
  );

  const deleteRow = useCallback(
    async (projectId: string, userId: string): Promise<void> => {
      await flushUpdates();
      await deleteMutation.mutateAsync({ projectId, userId });
    },
    [flushUpdates, deleteMutation],
  );

  return {
    queueCellUpdate,
    flushUpdates,
    deleteRow,
    isSaving: cellMutation.isPending || deleteMutation.isPending,
    pendingCount: pendingRef.current.size,
  };
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/capacity/hooks/usePlannerData.ts frontend/src/modules/capacity/hooks/usePlannerMutations.ts
git commit -m "feat(capacity): add planner data and mutation hooks"
```

---

## Task 6: Frontend — PlannerCell & PlannerSaveIndicator

**Files:**
- Create: `frontend/src/modules/capacity/components/PlannerCell.tsx`
- Create: `frontend/src/modules/capacity/components/PlannerSaveIndicator.tsx`

- [ ] **Step 1: Create editable cell component**

Create `frontend/src/modules/capacity/components/PlannerCell.tsx`:
```typescript
import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useTheme } from 'next-themes';
import { getPlannerCellColor } from '@/modules/capacity/utils/plannerColors';

interface PlannerCellProps {
  readonly value: number | undefined;
  readonly onChange: (value: number | null) => void;
  readonly isOwnRow: boolean;
}

export function PlannerCell({
  value,
  onChange,
  isOwnRow,
}: PlannerCellProps): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const bgColor = getPlannerCellColor(value, isDark);

  const startEditing = (): void => {
    setDraft(value?.toString() ?? '');
    setEditing(true);
  };

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  const commit = (): void => {
    setEditing(false);
    const num = parseInt(draft, 10);
    if (draft === '' || isNaN(num) || num <= 0) {
      if (value !== undefined) onChange(null);
    } else if (num !== value) {
      onChange(Math.min(num, 200));
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      commit();
    } else if (e.key === 'Escape') {
      setEditing(false);
    }
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        className="w-full h-full border-0 bg-transparent text-center text-xs outline-none"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={handleKeyDown}
        type="number"
        min={0}
        max={200}
      />
    );
  }

  return (
    <div
      className={`flex h-full w-full cursor-pointer items-center justify-center text-xs ${
        !isOwnRow && value !== undefined ? 'ring-1 ring-inset ring-yellow-400/30' : ''
      }`}
      style={{ backgroundColor: bgColor }}
      onClick={startEditing}
      role="gridcell"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') startEditing();
      }}
    >
      {value ?? ''}
    </div>
  );
}
```

- [ ] **Step 2: Create save indicator**

Create `frontend/src/modules/capacity/components/PlannerSaveIndicator.tsx`:
```typescript
import { Check, Loader2 } from 'lucide-react';

interface PlannerSaveIndicatorProps {
  readonly isSaving: boolean;
  readonly pendingCount: number;
}

export function PlannerSaveIndicator({
  isSaving,
  pendingCount,
}: PlannerSaveIndicatorProps): JSX.Element | null {
  if (isSaving) {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        Saving...
      </span>
    );
  }

  if (pendingCount > 0) {
    return (
      <span className="text-xs text-muted-foreground">
        {pendingCount} unsaved
      </span>
    );
  }

  return (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      <Check className="h-3 w-3" />
      Saved
    </span>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/capacity/components/PlannerCell.tsx frontend/src/modules/capacity/components/PlannerSaveIndicator.tsx
git commit -m "feat(capacity): add PlannerCell and PlannerSaveIndicator components"
```

---

## Task 7: Frontend — PlannerToolbar & PlannerAddRow

**Files:**
- Create: `frontend/src/modules/capacity/components/PlannerToolbar.tsx`
- Create: `frontend/src/modules/capacity/components/PlannerAddRow.tsx`

- [ ] **Step 1: Create toolbar component**

Create `frontend/src/modules/capacity/components/PlannerToolbar.tsx`:
```typescript
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { FA_ORDER } from '@/modules/capacity/utils/constants';
import { PlannerSaveIndicator } from '@/modules/capacity/components/PlannerSaveIndicator';

interface PlannerToolbarProps {
  readonly groupBy: string;
  readonly onGroupByChange: (value: string) => void;
  readonly fa: string;
  readonly onFaChange: (value: string) => void;
  readonly onPrev: () => void;
  readonly onNext: () => void;
  readonly isSaving: boolean;
  readonly pendingCount: number;
}

export function PlannerToolbar({
  groupBy,
  onGroupByChange,
  fa,
  onFaChange,
  onPrev,
  onNext,
  isSaving,
  pendingCount,
}: PlannerToolbarProps): JSX.Element {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Capacity Planner</h1>
        <PlannerSaveIndicator isSaving={isSaving} pendingCount={pendingCount} />
      </div>
      <div className="flex items-center gap-2">
        <Select value={fa} onValueChange={onFaChange}>
          <SelectTrigger className="w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All FAs</SelectItem>
            {FA_ORDER.map((f) => (
              <SelectItem key={f} value={f}>{f}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={groupBy} onValueChange={onGroupByChange}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="project">By Project</SelectItem>
            <SelectItem value="user">By Person</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" size="icon" onClick={onPrev}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="icon" onClick={onNext}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create add-row component**

Create `frontend/src/modules/capacity/components/PlannerAddRow.tsx`:
```typescript
import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';

interface SelectOption {
  id: string;
  name: string;
  extra?: string;
}

interface PlannerAddRowProps {
  readonly options: SelectOption[];
  readonly existingIds: Set<string>;
  readonly onSelect: (id: string) => void;
  readonly label: string;
}

export function PlannerAddRow({
  options,
  existingIds,
  onSelect,
  label,
}: PlannerAddRowProps): JSX.Element {
  const [open, setOpen] = useState(false);

  const available = options.filter((o) => !existingIds.has(o.id));

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="h-6 gap-1 text-xs text-muted-foreground">
          <Plus className="h-3 w-3" />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <Command>
          <CommandInput placeholder={`Search ${label.toLowerCase()}...`} />
          <CommandList>
            <CommandEmpty>No results</CommandEmpty>
            {available.map((opt) => (
              <CommandItem
                key={opt.id}
                onSelect={() => {
                  onSelect(opt.id);
                  setOpen(false);
                }}
              >
                <span>{opt.name}</span>
                {opt.extra && (
                  <span className="ml-auto text-xs text-muted-foreground">{opt.extra}</span>
                )}
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/capacity/components/PlannerToolbar.tsx frontend/src/modules/capacity/components/PlannerAddRow.tsx
git commit -m "feat(capacity): add PlannerToolbar and PlannerAddRow components"
```

---

## Task 8: Frontend — PlannerGrid (TanStack Table)

**Files:**
- Create: `frontend/src/modules/capacity/components/PlannerGrid.tsx`

This is the main component. It wires TanStack Table with dynamic week columns, editable cells, group headers, and totals.

- [ ] **Step 1: Install TanStack Table**

Run: `pushd frontend > /dev/null && npm install @tanstack/react-table && popd > /dev/null`

- [ ] **Step 2: Create PlannerGrid component**

Create `frontend/src/modules/capacity/components/PlannerGrid.tsx`:
```typescript
import { useMemo, useCallback } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type RowData,
} from '@tanstack/react-table';
import { Trash2 } from 'lucide-react';
import { useAuth } from '@/core/contexts/AuthContext';
import { PlannerCell } from '@/modules/capacity/components/PlannerCell';
import { PlannerAddRow } from '@/modules/capacity/components/PlannerAddRow';
import type { PlannerGroup, PlannerRow } from '@/modules/capacity/types/planner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/shared/components/ui/alert-dialog';

declare module '@tanstack/react-table' {
  interface TableMeta<TData extends RowData> {
    updateCell: (
      projectId: string,
      userId: string,
      week: string,
      value: number | null,
    ) => void;
    currentUserId: string;
  }
}

interface FlatRow {
  _type: 'header' | 'data' | 'add';
  groupId: string;
  groupName: string;
  user_id?: string;
  user_name?: string;
  functional_area?: string;
  project_id?: string;
  project_name?: string;
  cells: Record<string, number>;
}

interface PlannerGridProps {
  readonly groups: PlannerGroup[];
  readonly weeks: string[];
  readonly groupBy: string;
  readonly fa: string;
  readonly onCellChange: (
    projectId: string,
    userId: string,
    week: string,
    value: number | null,
  ) => void;
  readonly onDeleteRow: (projectId: string, userId: string) => void;
  readonly onAddRow: (groupId: string, targetId: string) => void;
  readonly addRowOptions: { id: string; name: string; extra?: string }[];
}

function getMonthLabel(weekStr: string): string {
  const d = new Date(weekStr + 'T00:00:00');
  return d.toLocaleDateString('en', { month: 'short', year: '2-digit' });
}

function getISOWeekNumber(weekStr: string): number {
  const d = new Date(weekStr + 'T00:00:00');
  const tmp = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  tmp.setUTCDate(tmp.getUTCDate() + 4 - (tmp.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1));
  return Math.ceil(((tmp.getTime() - yearStart.getTime()) / 86_400_000 + 1) / 7);
}

export function PlannerGrid({
  groups,
  weeks,
  groupBy,
  fa,
  onCellChange,
  onDeleteRow,
  onAddRow,
  addRowOptions,
}: PlannerGridProps): JSX.Element {
  const { user: authUser } = useAuth();

  // Filter by FA if set
  const filteredGroups = useMemo(() => {
    if (fa === 'all') return groups;
    return groups
      .map((g) => ({
        ...g,
        rows: g.rows.filter((r) => r.functional_area === fa),
      }))
      .filter((g) => g.rows.length > 0);
  }, [groups, fa]);

  // Flatten groups into rows for the table
  const flatRows = useMemo((): FlatRow[] => {
    const result: FlatRow[] = [];
    for (const group of filteredGroups) {
      result.push({
        _type: 'header',
        groupId: group.id,
        groupName: group.name,
        cells: {},
      });
      for (const row of group.rows) {
        result.push({
          _type: 'data',
          groupId: group.id,
          groupName: group.name,
          user_id: row.user_id,
          user_name: row.user_name,
          functional_area: row.functional_area,
          project_id: row.project_id,
          project_name: row.project_name,
          cells: row.cells,
        });
      }
      result.push({
        _type: 'add',
        groupId: group.id,
        groupName: group.name,
        cells: {},
      });
    }
    return result;
  }, [filteredGroups]);

  // Compute user totals across all groups
  const userTotals = useMemo((): Map<string, Record<string, number>> => {
    const totals = new Map<string, Record<string, number>>();
    for (const group of groups) {
      for (const row of group.rows) {
        if (!totals.has(row.user_id)) totals.set(row.user_id, {});
        const userWeeks = totals.get(row.user_id)!;
        for (const [week, pct] of Object.entries(row.cells)) {
          userWeeks[week] = (userWeeks[week] ?? 0) + pct;
        }
      }
    }
    return totals;
  }, [groups]);

  // Group weeks by month for headers
  const monthGroups = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const w of weeks) {
      const label = getMonthLabel(w);
      if (!map.has(label)) map.set(label, []);
      map.get(label)!.push(w);
    }
    return map;
  }, [weeks]);

  // Existing IDs in each group (for add-row filtering)
  const existingIdsByGroup = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const group of filteredGroups) {
      const ids = new Set<string>();
      for (const row of group.rows) {
        ids.add(groupBy === 'project' ? row.user_id : row.project_id);
      }
      map.set(group.id, ids);
    }
    return map;
  }, [filteredGroups, groupBy]);

  const columns = useMemo((): ColumnDef<FlatRow>[] => {
    const fixed: ColumnDef<FlatRow>[] = [
      {
        id: 'group',
        header: groupBy === 'project' ? 'Project' : 'Person',
        size: 120,
        cell: ({ row: { original } }) => {
          if (original._type === 'header') {
            return <span className="font-semibold">{original.groupName}</span>;
          }
          return null;
        },
      },
      {
        id: 'fa',
        header: 'FA',
        size: 50,
        cell: ({ row: { original } }) => {
          if (original._type === 'data') {
            return <span className="text-xs text-muted-foreground">{original.functional_area}</span>;
          }
          return null;
        },
      },
      {
        id: 'name',
        header: groupBy === 'project' ? 'Name' : 'Project',
        size: 140,
        cell: ({ row: { original }, table }) => {
          if (original._type === 'data') {
            const label = groupBy === 'project' ? original.user_name : original.project_name;
            return (
              <div className="flex items-center justify-between gap-1">
                <span className="truncate text-sm">{label}</span>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <button className="shrink-0 opacity-0 group-hover/row:opacity-100 transition-opacity">
                      <Trash2 className="h-3 w-3 text-muted-foreground hover:text-destructive" />
                    </button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Remove row?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will delete all planned allocations for this combination.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => onDeleteRow(original.project_id!, original.user_id!)}
                      >
                        Remove
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            );
          }
          if (original._type === 'add') {
            return (
              <PlannerAddRow
                options={addRowOptions}
                existingIds={existingIdsByGroup.get(original.groupId) ?? new Set()}
                onSelect={(id) => onAddRow(original.groupId, id)}
                label={groupBy === 'project' ? 'Add person' : 'Add project'}
              />
            );
          }
          return null;
        },
      },
    ];

    const weekCols: ColumnDef<FlatRow>[] = weeks.map((week) => ({
      id: `week_${week}`,
      header: () => <span className="text-xs">W{getISOWeekNumber(week)}</span>,
      size: 42,
      cell: ({ row: { original }, table }) => {
        if (original._type !== 'data') return null;
        const value = original.cells[week];
        const isOwnRow = original.user_id === table.options.meta?.currentUserId;
        return (
          <PlannerCell
            value={value}
            isOwnRow={isOwnRow}
            onChange={(v) =>
              table.options.meta?.updateCell(
                original.project_id!,
                original.user_id!,
                week,
                v,
              )
            }
          />
        );
      },
    }));

    return [...fixed, ...weekCols];
  }, [weeks, groupBy, onDeleteRow, onAddRow, addRowOptions, existingIdsByGroup]);

  const table = useReactTable({
    data: flatRows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    meta: {
      updateCell: onCellChange,
      currentUserId: authUser?.id ?? '',
    },
  });

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full border-collapse">
        {/* Month header row */}
        <thead>
          <tr className="border-b bg-muted/50">
            <th colSpan={3} className="sticky left-0 z-10 bg-muted/50" />
            {Array.from(monthGroups.entries()).map(([month, monthWeeks]) => (
              <th
                key={month}
                colSpan={monthWeeks.length}
                className="border-l px-1 py-1 text-center text-xs font-medium text-muted-foreground"
              >
                {month}
              </th>
            ))}
          </tr>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id} className="border-b bg-muted/30">
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  className={`px-2 py-1 text-left text-xs font-medium ${
                    header.index < 3 ? 'sticky left-0 z-10 bg-muted/30' : ''
                  }`}
                  style={{
                    width: header.getSize(),
                    left: header.index < 3
                      ? header.index === 0 ? 0 : header.index === 1 ? 120 : 170
                      : undefined,
                  }}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const isHeader = row.original._type === 'header';
            const isAdd = row.original._type === 'add';
            return (
              <tr
                key={row.id}
                className={`group/row border-b ${
                  isHeader ? 'bg-muted/20' : isAdd ? '' : 'hover:bg-muted/10'
                }`}
              >
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className={`px-0 py-0 ${
                      cell.column.getIndex() < 3
                        ? 'sticky left-0 z-10 bg-background px-2'
                        : 'border-l'
                    }`}
                    style={{
                      width: cell.column.getSize(),
                      height: isHeader || isAdd ? 28 : 32,
                      left: cell.column.getIndex() < 3
                        ? cell.column.getIndex() === 0 ? 0
                        : cell.column.getIndex() === 1 ? 120 : 170
                        : undefined,
                    }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/capacity/components/PlannerGrid.tsx
git commit -m "feat(capacity): add PlannerGrid with TanStack Table"
```

---

## Task 9: Frontend — Planner Page & Routing

**Files:**
- Create: `frontend/src/modules/capacity/pages/Planner.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/core/components/layout/AppSidebar.tsx`

- [ ] **Step 1: Install TanStack Table (if not already done in Task 8)**

Verify: `pushd frontend > /dev/null && node -e "require('@tanstack/react-table')" && popd > /dev/null`

- [ ] **Step 2: Create Planner page**

Create `frontend/src/modules/capacity/pages/Planner.tsx`:
```typescript
import { useCallback, useMemo, useState } from 'react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useAllProjectSummaries } from '@/core/hooks/useProjects';
import { useReportableUsers } from '@/modules/capacity/hooks/useReportableUsers';
import { usePlannerData } from '@/modules/capacity/hooks/usePlannerData';
import { usePlannerMutations } from '@/modules/capacity/hooks/usePlannerMutations';
import { PlannerToolbar } from '@/modules/capacity/components/PlannerToolbar';
import { PlannerGrid } from '@/modules/capacity/components/PlannerGrid';
import type { PlannerGroup, PlannerRow } from '@/modules/capacity/types/planner';

function defaultStart(): string {
  const d = new Date();
  // Snap to Monday of current week
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(d.setDate(diff));
  return monday.toISOString().slice(0, 10);
}

function addMonths(dateStr: string, months: number): string {
  const d = new Date(dateStr + 'T00:00:00');
  d.setMonth(d.getMonth() + months);
  // Snap to Monday
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  d.setDate(diff);
  return d.toISOString().slice(0, 10);
}

function endFromStart(start: string): string {
  return addMonths(start, 6);
}

const defaultStartDate = defaultStart();
const defaultEndDate = endFromStart(defaultStartDate);

export default function Planner(): JSX.Element {
  const { state, setState } = useUrlState({
    group: { defaultValue: 'project' },
    start: { defaultValue: defaultStartDate },
    end: { defaultValue: defaultEndDate },
    fa: { defaultValue: 'all' },
  });

  const { queueCellUpdate, flushUpdates, deleteRow, isSaving, pendingCount } =
    usePlannerMutations(state.start, state.end, state.group);
  const { data, isLoading, error } = usePlannerData(
    state.start, state.end, state.group, flushUpdates,
  );

  const { data: projects } = useAllProjectSummaries();
  const { data: reportableUsers } = useReportableUsers();

  // Local-only rows not yet persisted (no cells saved yet)
  const [localRows, setLocalRows] = useState<PlannerRow[]>([]);

  const handlePrev = useCallback((): void => {
    flushUpdates();
    const newStart = addMonths(state.start, -1);
    setState({ start: newStart, end: addMonths(newStart, 6) });
  }, [state.start, setState, flushUpdates]);

  const handleNext = useCallback((): void => {
    flushUpdates();
    const newStart = addMonths(state.start, 1);
    setState({ start: newStart, end: addMonths(newStart, 6) });
  }, [state.start, setState, flushUpdates]);

  const handleGroupByChange = useCallback(
    (group: string): void => {
      flushUpdates();
      setState({ group });
    },
    [setState, flushUpdates],
  );

  const handleCellChange = useCallback(
    (projectId: string, userId: string, week: string, value: number | null): void => {
      queueCellUpdate({
        project_id: projectId,
        user_id: userId,
        week_start: week,
        percentage: value,
      });
    },
    [queueCellUpdate],
  );

  const handleDeleteRow = useCallback(
    (projectId: string, userId: string): void => {
      deleteRow(projectId, userId);
    },
    [deleteRow],
  );

  // Merge server data with local phantom rows
  const mergedGroups = useMemo((): PlannerGroup[] => {
    if (!data) return [];
    const groups = data.groups.map((g) => ({ ...g, rows: [...g.rows] }));
    for (const lr of localRows) {
      const groupId = state.group === 'project' ? lr.project_id : lr.user_id;
      const existing = groups.find((g) => g.id === groupId);
      if (existing) {
        existing.rows.push(lr);
      } else {
        groups.push({
          id: groupId,
          name: state.group === 'project' ? lr.project_name : lr.user_name,
          rows: [lr],
        });
      }
    }
    return groups;
  }, [data, localRows, state.group]);

  const handleAddRow = useCallback(
    (groupId: string, targetId: string): void => {
      // Build a phantom row from the selected user/project
      let newRow: PlannerRow;
      if (state.group === 'project') {
        const user = reportableUsers?.find((u) => u.id === targetId);
        if (!user) return;
        newRow = {
          user_id: user.id,
          user_name: user.name,
          functional_area: '',
          project_id: groupId,
          project_name: data?.groups.find((g) => g.id === groupId)?.name ?? '',
          cells: {},
        };
      } else {
        const project = projects?.find((p) => p.id === targetId);
        if (!project) return;
        newRow = {
          user_id: groupId,
          user_name: data?.groups.find((g) => g.id === groupId)?.name ?? '',
          functional_area: '',
          project_id: project.id,
          project_name: project.name,
          cells: {},
        };
      }
      setLocalRows((prev) => [...prev, newRow]);
    },
    [state.group, reportableUsers, projects, data],
  );

  // Clear local rows that now exist in server data
  useMemo(() => {
    if (!data) return;
    setLocalRows((prev) =>
      prev.filter((lr) => {
        const serverGroup = data.groups.find((g) =>
          g.rows.some(
            (r) => r.project_id === lr.project_id && r.user_id === lr.user_id,
          ),
        );
        return !serverGroup;
      }),
    );
  }, [data]);

  const addRowOptions = useMemo(() => {
    if (state.group === 'project' && reportableUsers) {
      return reportableUsers.map((u) => ({ id: u.id, name: u.name }));
    }
    if (state.group === 'user' && projects) {
      return projects.map((p) => ({ id: p.id, name: p.name }));
    }
    return [];
  }, [state.group, reportableUsers, projects]);

  return (
    <div className="space-y-4 p-6">
      <PlannerToolbar
        groupBy={state.group}
        onGroupByChange={handleGroupByChange}
        fa={state.fa}
        onFaChange={(fa) => setState({ fa })}
        onPrev={handlePrev}
        onNext={handleNext}
        isSaving={isSaving}
        pendingCount={pendingCount}
      />

      {isLoading && (
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          Loading...
        </div>
      )}

      {error && (
        <div className="flex h-64 items-center justify-center text-destructive">
          Failed to load planner data
        </div>
      )}

      {data && (
        <PlannerGrid
          groups={mergedGroups}
          weeks={data.weeks}
          groupBy={state.group}
          fa={state.fa}
          onCellChange={handleCellChange}
          onDeleteRow={handleDeleteRow}
          onAddRow={handleAddRow}
          addRowOptions={addRowOptions}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add route to App.tsx**

In `frontend/src/App.tsx`, add the static import near the other capacity imports (the codebase uses static imports, not `lazy()`):
```typescript
import CapacityPlanner from '@/modules/capacity/pages/Planner';
```

Add the route after the existing capacity routes:
```typescript
<Route path="/capacity/planner" element={<CapacityPlanner />} />
```

- [ ] **Step 4: Add sidebar entry**

In `frontend/src/core/components/layout/AppSidebar.tsx`, add to `CAPACITY_TABS`:
```typescript
const CAPACITY_TABS = [
  { to: '/capacity/insights', label: 'Insights' },
  { to: '/capacity/allocation', label: 'Allocation' },
  { to: '/capacity/planner', label: 'Planner' },
] as const;
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/capacity/pages/Planner.tsx frontend/src/App.tsx frontend/src/core/components/layout/AppSidebar.tsx
git commit -m "feat(capacity): add Planner page and routing"
```

---

## Task 10: Seed Scripts

**Files:**
- Create: `scripts/export_capacity_xlsx_to_json.py`
- Create: `scripts/seed_capacity_planner.py`

- [ ] **Step 1: Create xlsx-to-JSON export script**

Create `scripts/export_capacity_xlsx_to_json.py`:
```python
"""Export Capacity management.xlsx 'General view' tab to capacity_seed.json.

Run locally where the xlsx file exists:
    python scripts/export_capacity_xlsx_to_json.py temp/Capacity\ management.xlsx

Outputs: capacity_seed.json in the current directory.
"""

import json
import sys
from datetime import date, timedelta

import openpyxl

# Manual mapping: spreadsheet name → user email.
# Fill in before running. Names not in this dict are skipped with a warning.
NAME_TO_EMAIL: dict[str, str] = {
    # "Clara Linos": "clara@vizzuality.com",
    # "Santiago Ferrer": "santiago@vizzuality.com",
    # Add all team members here
}

DATA_START_ROW = 16
PROJECT_COL = 1
ROLE_COL = 2
NAME_COL = 3
WEEK_START_COL = 4

# Columns 4-11 use "days" format (1-5), columns 12+ use percentage (0-100+)
DAYS_FORMAT_END_COL = 11


def iso_week_to_monday(year: int, week_num: int) -> date:
    """Convert ISO year + week number to the Monday of that week."""
    jan1 = date(year, 1, 1)
    # Find the Monday of ISO week 1
    day_of_week = jan1.isoweekday()
    if day_of_week <= 4:
        iso_week1_monday = jan1 - timedelta(days=day_of_week - 1)
    else:
        iso_week1_monday = jan1 + timedelta(days=8 - day_of_week)
    return iso_week1_monday + timedelta(weeks=week_num - 1)


def main(xlsx_path: str) -> None:
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb["General view"]

    # Read week numbers from row 12 and month names from row 14
    week_info: dict[int, dict] = {}
    current_year = None
    month_to_year: dict[str, int] = {}

    # Read month headers (row 14) to determine year boundaries
    for col in range(WEEK_START_COL, ws.max_column + 1):
        month_name = ws.cell(row=14, column=col).value
        if month_name:
            # Months Nov, Dec → 2025; Jan onwards → 2026 (adjust as needed)
            if month_name in ("November", "December"):
                month_to_year[month_name] = 2025
                current_year = 2025
            else:
                month_to_year[month_name] = 2026
                current_year = 2026

    # Build week_num → Monday mapping
    current_year = 2025  # Start year for first columns
    for col in range(WEEK_START_COL, ws.max_column + 1):
        week_num_val = ws.cell(row=12, column=col).value
        month_val = ws.cell(row=14, column=col).value
        if month_val and month_val in month_to_year:
            current_year = month_to_year[month_val]
        if week_num_val is not None:
            week_num = int(week_num_val)
            # Week 1-2 after week 52 means year rollover
            if week_num < 10 and current_year == 2025:
                current_year = 2026
            monday = iso_week_to_monday(current_year, week_num)
            week_info[col] = {
                "week_num": week_num,
                "monday": monday,
                "is_days_format": col <= DAYS_FORMAT_END_COL,
            }

    # Read data rows
    records: list[dict] = []
    skipped_names: set[str] = set()

    for row in range(DATA_START_ROW, ws.max_row + 1):
        project_name = ws.cell(row=row, column=PROJECT_COL).value
        person_name = ws.cell(row=row, column=NAME_COL).value

        if not person_name:
            continue

        person_name = str(person_name).strip()
        email = NAME_TO_EMAIL.get(person_name)
        if not email:
            skipped_names.add(person_name)
            continue

        project_name = str(project_name).strip() if project_name else None
        if not project_name:
            continue

        for col, info in week_info.items():
            val = ws.cell(row=row, column=col).value
            if val is None or val == "" or str(val).lower() == "x":
                continue

            try:
                num = float(val)
            except (ValueError, TypeError):
                continue

            if num <= 0:
                continue

            # Convert days to percentage if old format
            if info["is_days_format"]:
                percentage = int(num * 20)
            else:
                percentage = int(num)

            if percentage < 1:
                continue

            records.append({
                "project_name": project_name,
                "user_email": email,
                "week_start": info["monday"].isoformat(),
                "percentage": min(percentage, 200),
            })

    # Write output
    output_path = "capacity_seed.json"
    with open(output_path, "w") as f:
        json.dump(records, f, indent=2)

    print(f"Exported {len(records)} records to {output_path}")
    if skipped_names:
        print(f"Skipped names (no email mapping): {sorted(skipped_names)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path-to-xlsx>")
        sys.exit(1)
    main(sys.argv[1])
```

- [ ] **Step 2: Create JSON-to-DB seed script**

Create `scripts/seed_capacity_planner.py`:
```python
"""Seed capacity_plans table from capacity_seed.json.

Run against any environment:
    python scripts/seed_capacity_planner.py [path/to/capacity_seed.json]

Defaults to capacity_seed.json in current directory.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import AsyncSessionLocal
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.capacity.models.capacity_plan import CapacityPlanDB


async def main(json_path: str) -> None:
    with open(json_path) as f:
        records = json.load(f)

    print(f"Loaded {len(records)} records from {json_path}")

    async with AsyncSessionLocal() as db:
        # Build lookup maps
        projects_result = await db.execute(select(ProjectDB.id, ProjectDB.name))
        project_map = {row.name: row.id for row in projects_result.all()}

        users_result = await db.execute(select(UserDB.id, UserDB.email))
        email_map = {row.email: row.id for row in users_result.all()}

        # Get a default user for created_by/updated_by (first user in DB)
        first_user_result = await db.execute(select(UserDB.id).limit(1))
        seed_user_id = first_user_result.scalar_one_or_none()
        if not seed_user_id:
            print("ERROR: No users found in database")
            return

        skipped_projects: set[str] = set()
        skipped_emails: set[str] = set()
        values = []

        for rec in records:
            project_id = project_map.get(rec["project_name"])
            user_id = email_map.get(rec["user_email"])

            if not project_id:
                skipped_projects.add(rec["project_name"])
                continue
            if not user_id:
                skipped_emails.add(rec["user_email"])
                continue

            values.append({
                "project_id": project_id,
                "user_id": user_id,
                "week_start": rec["week_start"],
                "percentage": rec["percentage"],
                "created_by": seed_user_id,
                "updated_by": seed_user_id,
            })

        if values:
            # Batch insert with ON CONFLICT DO NOTHING
            BATCH_SIZE = 500
            inserted = 0
            for i in range(0, len(values), BATCH_SIZE):
                batch = values[i : i + BATCH_SIZE]
                stmt = pg_insert(CapacityPlanDB).values(batch)
                stmt = stmt.on_conflict_do_nothing(constraint="uq_capacity_plan_cell")
                result = await db.execute(stmt)
                inserted += result.rowcount
            await db.commit()
            print(f"Inserted {inserted} records (skipped {len(values) - inserted} duplicates)")
        else:
            print("No valid records to insert")

        if skipped_projects:
            print(f"Skipped projects (not in DB): {sorted(skipped_projects)}")
        if skipped_emails:
            print(f"Skipped emails (not in DB): {sorted(skipped_emails)}")


if __name__ == "__main__":
    json_path = sys.argv[1] if len(sys.argv) > 1 else "capacity_seed.json"
    asyncio.run(main(json_path))
```

- [ ] **Step 3: Commit**

```bash
git add scripts/export_capacity_xlsx_to_json.py scripts/seed_capacity_planner.py
git commit -m "feat(capacity): add planner seed scripts (xlsx→json→db)"
```

---

## Task 11: Integration Test & Polish

- [ ] **Step 1: Run all backend tests**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/capacity/ -v && popd > /dev/null`
Expected: all tests pass.

- [ ] **Step 2: Run all frontend tests**

Run: `pushd frontend > /dev/null && npm test -- --run && popd > /dev/null`
Expected: all tests pass.

- [ ] **Step 3: Start dev server and verify manually**

Run backend: `pushd backend > /dev/null && python run_server.py &`
Run frontend: `pushd frontend > /dev/null && npm run dev &`

Verify:
1. Navigate to `/capacity/planner` — page loads, sidebar shows "Planner" tab
2. Grid shows empty state (no data yet)
3. Run seed to populate: `python scripts/seed_capacity_planner.py`
4. Refresh — data appears in grid with correct colors
5. Click cell → edit → blur → "Saving..." indicator → "Saved"
6. Toggle "By Project" / "By Person" — groups change
7. Use `< >` to navigate timeline
8. FA filter works

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(capacity): capacity planner - integration verified"
```
