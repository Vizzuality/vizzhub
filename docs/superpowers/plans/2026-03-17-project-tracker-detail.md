# Project Tracker Detail — Cost Aggregation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project tracker detail page showing aggregated staff + non-staff costs, validated against legacy VizzTracker.

**Architecture:** New aggregation service queries report_parts and non_staff_costs, returns per-period breakdowns and totals. Non-staff costs gets standard CRUD. FE page shows budget card + enriched reports table.

**Tech Stack:** FastAPI, SQLAlchemy (async), Pydantic v2, React, TanStack Query, Tailwind/shadcn

**Spec:** `docs/superpowers/specs/2026-03-17-project-tracker-detail-design.md`

---

## File Map

### Backend — Create
| File | Responsibility |
|------|---------------|
| `backend/app/modules/tracker/schemas/non_staff_cost.py` | Pydantic schemas for non-staff costs CRUD |
| `backend/app/modules/tracker/schemas/project_cost.py` | Aggregation response schemas (summary + report parts list) |
| `backend/app/modules/tracker/api/non_staff_costs.py` | Non-staff costs CRUD endpoints |
| `backend/app/modules/tracker/api/project_costs.py` | Cost summary + project report parts endpoints |
| `backend/app/modules/tracker/services/aggregation_service.py` | SQL aggregation queries |
| `backend/tests/modules/tracker/test_non_staff_costs.py` | Non-staff costs CRUD tests |
| `backend/tests/modules/tracker/test_aggregation.py` | Aggregation service + endpoint tests |

### Backend — Modify
| File | Change |
|------|--------|
| `backend/app/modules/tracker/schemas/__init__.py` | Export new schemas |
| `backend/app/modules/tracker/router.py` | Mount non_staff_costs + project_costs routers |

### Frontend — Create
| File | Responsibility |
|------|---------------|
| `frontend/src/modules/tracker/pages/ProjectTrackerDetail.tsx` | Main page: budget card + reports table |
| `frontend/src/modules/tracker/hooks/useProjectCosts.ts` | React Query hooks for cost summary + report parts |
| `frontend/src/modules/tracker/pages/__tests__/ProjectTrackerDetail.test.tsx` | MSW integration tests |

### Frontend — Modify
| File | Change |
|------|--------|
| `frontend/src/modules/tracker/types/tracker.ts` | Add cost summary + non-staff cost interfaces |
| `frontend/src/modules/tracker/services/tracker.ts` | Add cost summary + report parts API methods |
| `frontend/src/core/hooks/queryKeys.ts` | Add tracker.projectCosts key group |
| `frontend/src/App.tsx` | Add route `/tracker/projects/:projectId` |
| `frontend/src/test/msw-handlers.ts` | Add cost summary + report parts handlers |

---

## Chunk 1: Non-Staff Costs CRUD (Backend)

### Task 1: Non-staff cost schemas

**Files:**
- Create: `backend/app/modules/tracker/schemas/non_staff_cost.py`
- Modify: `backend/app/modules/tracker/schemas/__init__.py`

- [ ] **Step 1: Create schemas**

```python
# backend/app/modules/tracker/schemas/non_staff_cost.py
"""Pydantic schemas for non-staff costs."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tracker.models.non_staff_cost import CostType


class NonStaffCostCreate(BaseModel):
    project_id: UUID
    reporting_period_id: UUID
    cost: Decimal = Field(ge=0)
    cost_type: CostType
    details: str | None = None


class NonStaffCostUpdate(BaseModel):
    cost: Decimal | None = Field(default=None, ge=0)
    cost_type: CostType | None = None
    details: str | None = None


class NonStaffCostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    reporting_period_id: UUID
    cost: float
    cost_type: str
    details: str | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: Export from `__init__.py`**

Add to `backend/app/modules/tracker/schemas/__init__.py`:

```python
from app.modules.tracker.schemas.non_staff_cost import (
    NonStaffCostCreate,
    NonStaffCostResponse,
    NonStaffCostUpdate,
)

# Add to __all__:
"NonStaffCostCreate",
"NonStaffCostResponse",
"NonStaffCostUpdate",
```

- [ ] **Step 3: Verify types compile**

Run: `pushd backend > /dev/null && python -c "from app.modules.tracker.schemas.non_staff_cost import *; print('OK')" && popd > /dev/null`

### Task 2: Non-staff costs CRUD tests

**Files:**
- Create: `backend/tests/modules/tracker/test_non_staff_costs.py`

- [ ] **Step 1: Write CRUD tests**

```python
# backend/tests/modules/tracker/test_non_staff_costs.py
"""Tests for non-staff costs CRUD endpoints."""

import datetime as dt
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.tracker.models.non_staff_cost import NonStaffCostDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

from app.core.models.user import UserDB


@pytest_asyncio.fixture
async def setup_non_staff(db_session: AsyncSession) -> dict:
    """Create test data: period, project, user."""
    user = UserDB(id=DEBUG_USER_ID, email="test@example.com", name="Test User")
    db_session.add(user)
    await db_session.flush()

    period = ReportingPeriodDB(
        date=dt.date(2026, 3, 1), base_rate=Decimal("175"), status="active",
    )
    db_session.add(period)
    await db_session.flush()

    project = ProjectDB(name="Test Project", status="live")
    db_session.add(project)
    await db_session.commit()

    await db_session.refresh(period)
    await db_session.refresh(project)

    return {"period": period, "project": project}


class TestNonStaffCostsCRUD:
    @pytest.mark.asyncio
    async def test_create_non_staff_cost(
        self, client: AsyncClient, setup_non_staff: dict,
    ):
        resp = await client.post(
            "/api/tracker/non-staff-costs",
            json={
                "project_id": str(setup_non_staff["project"].id),
                "reporting_period_id": str(setup_non_staff["period"].id),
                "cost": "500.00",
                "cost_type": "travel",
                "details": "Client visit",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["cost"] == 500.0
        assert data["cost_type"] == "travel"
        assert data["details"] == "Client visit"

    @pytest.mark.asyncio
    async def test_list_by_project(
        self, client: AsyncClient, setup_non_staff: dict,
    ):
        project_id = str(setup_non_staff["project"].id)
        period_id = str(setup_non_staff["period"].id)

        await client.post(
            "/api/tracker/non-staff-costs",
            json={
                "project_id": project_id,
                "reporting_period_id": period_id,
                "cost": "100.00",
                "cost_type": "servers",
            },
        )
        await client.post(
            "/api/tracker/non-staff-costs",
            json={
                "project_id": project_id,
                "reporting_period_id": period_id,
                "cost": "200.00",
                "cost_type": "outsource",
            },
        )

        resp = await client.get(
            "/api/tracker/non-staff-costs",
            params={"project_id": project_id},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_list_by_project_and_period(
        self, client: AsyncClient, setup_non_staff: dict,
    ):
        project_id = str(setup_non_staff["project"].id)
        period_id = str(setup_non_staff["period"].id)

        await client.post(
            "/api/tracker/non-staff-costs",
            json={
                "project_id": project_id,
                "reporting_period_id": period_id,
                "cost": "100.00",
                "cost_type": "servers",
            },
        )

        resp = await client.get(
            "/api/tracker/non-staff-costs",
            params={
                "project_id": project_id,
                "reporting_period_id": period_id,
            },
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_list_requires_project_id(
        self, client: AsyncClient, setup_non_staff: dict,
    ):
        resp = await client.get("/api/tracker/non-staff-costs")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_non_staff_cost(
        self, client: AsyncClient, setup_non_staff: dict,
    ):
        create_resp = await client.post(
            "/api/tracker/non-staff-costs",
            json={
                "project_id": str(setup_non_staff["project"].id),
                "reporting_period_id": str(setup_non_staff["period"].id),
                "cost": "500.00",
                "cost_type": "travel",
            },
        )
        cost_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/tracker/non-staff-costs/{cost_id}",
            json={"cost": "750.00", "details": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["cost"] == 750.0
        assert resp.json()["details"] == "Updated"

    @pytest.mark.asyncio
    async def test_delete_non_staff_cost(
        self, client: AsyncClient, setup_non_staff: dict,
    ):
        create_resp = await client.post(
            "/api/tracker/non-staff-costs",
            json={
                "project_id": str(setup_non_staff["project"].id),
                "reporting_period_id": str(setup_non_staff["period"].id),
                "cost": "500.00",
                "cost_type": "travel",
            },
        )
        cost_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/tracker/non-staff-costs/{cost_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/tracker/non-staff-costs/{cost_id}")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to see them fail**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/tracker/test_non_staff_costs.py -v 2>&1 | tail -20 && popd > /dev/null`
Expected: FAIL (endpoints don't exist yet)

### Task 3: Non-staff costs CRUD endpoint

**Files:**
- Create: `backend/app/modules/tracker/api/non_staff_costs.py`
- Modify: `backend/app/modules/tracker/router.py`

- [ ] **Step 1: Create CRUD endpoint**

```python
# backend/app/modules/tracker/api/non_staff_costs.py
"""Non-staff costs CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.models.non_staff_cost import NonStaffCostDB
from app.modules.tracker.schemas.non_staff_cost import (
    NonStaffCostCreate,
    NonStaffCostResponse,
    NonStaffCostUpdate,
)

router = APIRouter()


async def _get_cost_or_404(cost_id: UUID, db: AsyncSession) -> NonStaffCostDB:
    result = await db.execute(
        select(NonStaffCostDB).where(NonStaffCostDB.id == cost_id)
    )
    cost = result.scalar_one_or_none()
    if not cost:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Non-staff cost {cost_id} not found",
        )
    return cost


@router.get("", response_model=list[NonStaffCostResponse])
async def list_non_staff_costs(
    project_id: UUID = Query(...),
    reporting_period_id: UUID | None = Query(default=None),
    db: DBSession = ...,
    user: CurrentUser = ...,
) -> list[NonStaffCostResponse]:
    query = select(NonStaffCostDB).where(
        NonStaffCostDB.project_id == project_id
    )
    if reporting_period_id:
        query = query.where(
            NonStaffCostDB.reporting_period_id == reporting_period_id
        )
    query = query.order_by(NonStaffCostDB.created_at)
    result = await db.execute(query)
    return [NonStaffCostResponse.model_validate(c) for c in result.scalars().all()]


@router.post("", response_model=NonStaffCostResponse, status_code=201)
async def create_non_staff_cost(
    data: NonStaffCostCreate,
    db: DBSession,
    user: CurrentUser,
) -> NonStaffCostResponse:
    cost = NonStaffCostDB(
        project_id=data.project_id,
        reporting_period_id=data.reporting_period_id,
        cost=data.cost,
        cost_type=data.cost_type.value,
        details=data.details,
    )
    db.add(cost)
    await db.commit()
    await db.refresh(cost)
    return NonStaffCostResponse.model_validate(cost)


@router.get("/{cost_id}", response_model=NonStaffCostResponse)
async def get_non_staff_cost(
    cost_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> NonStaffCostResponse:
    cost = await _get_cost_or_404(cost_id, db)
    return NonStaffCostResponse.model_validate(cost)


@router.put("/{cost_id}", response_model=NonStaffCostResponse)
async def update_non_staff_cost(
    cost_id: UUID,
    data: NonStaffCostUpdate,
    db: DBSession,
    user: CurrentUser,
) -> NonStaffCostResponse:
    cost = await _get_cost_or_404(cost_id, db)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "cost_type" and value is not None:
            setattr(cost, field, value.value)
        else:
            setattr(cost, field, value)
    await db.commit()
    await db.refresh(cost)
    return NonStaffCostResponse.model_validate(cost)


@router.delete("/{cost_id}", status_code=204)
async def delete_non_staff_cost(
    cost_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> None:
    cost = await _get_cost_or_404(cost_id, db)
    await db.delete(cost)
    await db.commit()
```

- [ ] **Step 2: Mount router in `tracker/router.py`**

Add to `backend/app/modules/tracker/router.py`:

```python
from app.modules.tracker.api import non_staff_costs as non_staff_costs_router

router.include_router(
    non_staff_costs_router.router,
    prefix="/non-staff-costs",
    tags=["tracker:non-staff-costs"],
)
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/tracker/test_non_staff_costs.py -v 2>&1 | tail -20 && popd > /dev/null`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/tracker/schemas/non_staff_cost.py backend/app/modules/tracker/schemas/__init__.py backend/app/modules/tracker/api/non_staff_costs.py backend/app/modules/tracker/router.py backend/tests/modules/tracker/test_non_staff_costs.py
git commit -m "feat(tracker): add non-staff costs CRUD endpoints"
```

---

## Chunk 2: Cost Aggregation Service + Endpoints (Backend)

### Task 4: Project cost schemas

**Files:**
- Create: `backend/app/modules/tracker/schemas/project_cost.py`

- [ ] **Step 1: Create aggregation response schemas**

```python
# backend/app/modules/tracker/schemas/project_cost.py
"""Schemas for project cost aggregation responses."""

import datetime as dt
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PeriodCostBreakdown(BaseModel):
    period_id: UUID
    date: dt.date
    staff_cost: float
    non_staff_cost: float
    total: float
    parts_count: int


class ProjectCostSummary(BaseModel):
    project_id: UUID
    budget: float | None
    contract_rate: float
    staff_cost: float
    non_staff_cost: float
    total_cost: float
    burn_percentage: float | None
    periods: list[PeriodCostBreakdown]


class ProjectReportPartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    period_date: dt.date
    user_name: str | None
    user_email: str | None
    functional_area: str | None
    percentage: float | None
    days: float | None
    cost: float | None
    estimated: bool
```

- [ ] **Step 2: Verify import**

Run: `pushd backend > /dev/null && python -c "from app.modules.tracker.schemas.project_cost import *; print('OK')" && popd > /dev/null`

### Task 5: Aggregation service

**Files:**
- Create: `backend/app/modules/tracker/services/aggregation_service.py`

- [ ] **Step 1: Create aggregation service**

```python
# backend/app/modules/tracker/services/aggregation_service.py
"""Project cost aggregation queries."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.user import UserDB
from app.modules.tracker.constants import DEFAULT_RATE
from app.modules.tracker.models.non_staff_cost import NonStaffCostDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.modules.tracker.models.project_settings import TrackerProjectSettingsDB
from app.modules.tracker.schemas.project_cost import (
    PeriodCostBreakdown,
    ProjectCostSummary,
    ProjectReportPartResponse,
)


async def get_project_cost_summary(
    db: AsyncSession, project_id: UUID,
) -> ProjectCostSummary:
    """Aggregate staff + non-staff costs for a project across all periods."""
    settings_result = await db.execute(
        select(TrackerProjectSettingsDB).where(
            TrackerProjectSettingsDB.project_id == project_id
        )
    )
    settings = settings_result.scalar_one_or_none()
    budget = float(settings.budget) if settings and settings.budget else None
    contract_rate = float(settings.contract_rate) if settings else float(DEFAULT_RATE)

    # Staff costs by period (exclude estimated reports)
    staff_query = (
        select(
            ReportDB.reporting_period_id,
            ReportingPeriodDB.date,
            func.coalesce(func.sum(ReportPartDB.cost), 0).label("staff_cost"),
            func.count(ReportPartDB.id).label("parts_count"),
        )
        .join(ReportDB, ReportPartDB.report_id == ReportDB.id)
        .join(
            ReportingPeriodDB,
            ReportDB.reporting_period_id == ReportingPeriodDB.id,
        )
        .where(ReportPartDB.project_id == project_id)
        .where(ReportDB.estimated == False)  # noqa: E712
        .group_by(ReportDB.reporting_period_id, ReportingPeriodDB.date)
    )
    staff_result = await db.execute(staff_query)
    staff_rows = {
        row.reporting_period_id: row for row in staff_result.all()
    }

    # Non-staff costs by period
    non_staff_query = (
        select(
            NonStaffCostDB.reporting_period_id,
            ReportingPeriodDB.date,
            func.coalesce(func.sum(NonStaffCostDB.cost), 0).label("non_staff_cost"),
        )
        .join(
            ReportingPeriodDB,
            NonStaffCostDB.reporting_period_id == ReportingPeriodDB.id,
        )
        .where(NonStaffCostDB.project_id == project_id)
        .group_by(NonStaffCostDB.reporting_period_id, ReportingPeriodDB.date)
    )
    non_staff_result = await db.execute(non_staff_query)
    non_staff_rows = {
        row.reporting_period_id: row for row in non_staff_result.all()
    }

    # Merge periods
    all_period_ids = set(staff_rows.keys()) | set(non_staff_rows.keys())
    periods: list[PeriodCostBreakdown] = []
    total_staff = 0.0
    total_non_staff = 0.0

    for pid in all_period_ids:
        s = staff_rows.get(pid)
        ns = non_staff_rows.get(pid)
        staff = float(s.staff_cost) if s else 0.0
        non_staff = float(ns.non_staff_cost) if ns else 0.0
        period_date = s.date if s else ns.date
        parts_count = s.parts_count if s else 0

        total_staff += staff
        total_non_staff += non_staff

        periods.append(PeriodCostBreakdown(
            period_id=pid,
            date=period_date,
            staff_cost=round(staff, 2),
            non_staff_cost=round(non_staff, 2),
            total=round(staff + non_staff, 2),
            parts_count=parts_count,
        ))

    periods.sort(key=lambda p: p.date, reverse=True)

    total_cost = round(total_staff + total_non_staff, 2)
    burn_pct = round(total_cost / budget * 100, 2) if budget else None

    return ProjectCostSummary(
        project_id=project_id,
        budget=budget,
        contract_rate=contract_rate,
        staff_cost=round(total_staff, 2),
        non_staff_cost=round(total_non_staff, 2),
        total_cost=total_cost,
        burn_percentage=burn_pct,
        periods=periods,
    )


async def get_project_report_parts(
    db: AsyncSession,
    project_id: UUID,
    period_id: UUID | None = None,
) -> list[ProjectReportPartResponse]:
    """List enriched report parts for a project, optionally filtered by period."""
    query = (
        select(
            ReportPartDB.id,
            ReportingPeriodDB.date.label("period_date"),
            UserDB.name.label("user_name"),
            UserDB.email.label("user_email"),
            FunctionalAreaDB.name.label("functional_area"),
            ReportPartDB.percentage,
            ReportPartDB.days,
            ReportPartDB.cost,
            ReportDB.estimated,
        )
        .join(ReportDB, ReportPartDB.report_id == ReportDB.id)
        .join(
            ReportingPeriodDB,
            ReportDB.reporting_period_id == ReportingPeriodDB.id,
        )
        .join(UserDB, ReportDB.user_id == UserDB.id)
        .outerjoin(
            FunctionalAreaDB,
            ReportPartDB.functional_area_id == FunctionalAreaDB.id,
        )
        .where(ReportPartDB.project_id == project_id)
        .order_by(ReportingPeriodDB.date.desc(), UserDB.name.asc())
    )

    if period_id:
        query = query.where(ReportDB.reporting_period_id == period_id)

    result = await db.execute(query)
    return [
        ProjectReportPartResponse(
            id=row.id,
            period_date=row.period_date,
            user_name=row.user_name,
            user_email=row.user_email,
            functional_area=row.functional_area,
            percentage=row.percentage,
            days=row.days,
            cost=row.cost,
            estimated=row.estimated,
        )
        for row in result.all()
    ]
```

### Task 6: Aggregation tests

**Files:**
- Create: `backend/tests/modules/tracker/test_aggregation.py`

- [ ] **Step 1: Write aggregation tests**

```python
# backend/tests/modules/tracker/test_aggregation.py
"""Tests for project cost aggregation endpoint."""

import datetime as dt
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.rate import RateDB
from app.core.models.user import UserDB
from app.core.models.functional_area import FunctionalAreaDB
from app.modules.tracker.models.non_staff_cost import NonStaffCostDB
from app.modules.tracker.models.project_settings import TrackerProjectSettingsDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def setup_aggregation(db_session: AsyncSession) -> dict:
    """Full setup: 2 periods, 1 project with settings, 1 user with rate,
    report_parts in each period, non-staff costs in one period."""
    rate = RateDB(code="B", value=Decimal("15365"))
    db_session.add(rate)
    await db_session.flush()

    user = UserDB(
        id=DEBUG_USER_ID, email="test@example.com", name="Test User",
        rate_id=rate.id, dedication=Decimal("0.74"),
    )
    db_session.add(user)
    await db_session.flush()

    period1 = ReportingPeriodDB(
        date=dt.date(2026, 2, 1), base_rate=Decimal("175"), status="finished",
    )
    period2 = ReportingPeriodDB(
        date=dt.date(2026, 3, 1), base_rate=Decimal("175"), status="active",
    )
    db_session.add_all([period1, period2])
    await db_session.flush()

    project = ProjectDB(name="Test Project", status="live")
    db_session.add(project)
    await db_session.flush()

    settings = TrackerProjectSettingsDB(
        project_id=project.id,
        budget=Decimal("50000"),
        contract_rate=Decimal("175"),
    )
    db_session.add(settings)
    await db_session.flush()

    area = FunctionalAreaDB(name="Backend Developer")
    db_session.add(area)
    await db_session.flush()

    # Reports (non-estimated)
    report1 = ReportDB(
        user_id=user.id, reporting_period_id=period1.id, estimated=False,
    )
    report2 = ReportDB(
        user_id=user.id, reporting_period_id=period2.id, estimated=False,
    )
    db_session.add_all([report1, report2])
    await db_session.flush()

    # Report parts — use apply_cost_and_days via API or set cost directly
    part1 = ReportPartDB(
        report_id=report1.id, project_id=project.id,
        functional_area_id=area.id, percentage=Decimal("0.10"),
        cost=Decimal("1137.01"), days=Decimal("1.48"),
    )
    part2 = ReportPartDB(
        report_id=report2.id, project_id=project.id,
        functional_area_id=area.id, percentage=Decimal("0.20"),
        cost=Decimal("2274.02"), days=Decimal("2.96"),
    )
    db_session.add_all([part1, part2])
    await db_session.flush()

    # Non-staff cost in period 1 only
    nsc = NonStaffCostDB(
        project_id=project.id, reporting_period_id=period1.id,
        cost=Decimal("500.00"), cost_type="travel",
        details="Client visit",
    )
    db_session.add(nsc)
    await db_session.commit()

    for obj in [rate, user, period1, period2, project, settings, area,
                report1, report2, part1, part2, nsc]:
        await db_session.refresh(obj)

    return {
        "project": project, "period1": period1, "period2": period2,
        "settings": settings, "part1": part1, "part2": part2,
        "nsc": nsc, "area": area,
    }


class TestProjectCostSummary:
    @pytest.mark.asyncio
    async def test_cost_summary_totals(
        self, client: AsyncClient, setup_aggregation: dict,
    ):
        project_id = str(setup_aggregation["project"].id)
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/cost-summary",
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["budget"] == 50000.0
        assert data["contract_rate"] == 175.0
        assert data["staff_cost"] == 3411.03  # 1137.01 + 2274.02
        assert data["non_staff_cost"] == 500.0
        assert data["total_cost"] == 3911.03
        assert data["burn_percentage"] == pytest.approx(7.82, abs=0.01)
        assert len(data["periods"]) == 2

    @pytest.mark.asyncio
    async def test_cost_summary_period_breakdown(
        self, client: AsyncClient, setup_aggregation: dict,
    ):
        project_id = str(setup_aggregation["project"].id)
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/cost-summary",
        )
        data = resp.json()

        # Periods ordered by date desc: March first, then February
        p_mar = data["periods"][0]
        p_feb = data["periods"][1]

        assert p_mar["date"] == "2026-03-01"
        assert p_mar["staff_cost"] == 2274.02
        assert p_mar["non_staff_cost"] == 0.0
        assert p_mar["parts_count"] == 1

        assert p_feb["date"] == "2026-02-01"
        assert p_feb["staff_cost"] == 1137.01
        assert p_feb["non_staff_cost"] == 500.0
        assert p_feb["parts_count"] == 1

    @pytest.mark.asyncio
    async def test_cost_summary_no_budget(
        self, client: AsyncClient, setup_aggregation: dict, db_session: AsyncSession,
    ):
        """burn_percentage is None when project has no budget."""
        settings = setup_aggregation["settings"]
        settings.budget = None
        await db_session.commit()

        project_id = str(setup_aggregation["project"].id)
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/cost-summary",
        )
        data = resp.json()
        assert data["budget"] is None
        assert data["burn_percentage"] is None
        assert data["total_cost"] > 0

    @pytest.mark.asyncio
    async def test_cost_summary_excludes_estimated(
        self, client: AsyncClient, setup_aggregation: dict, db_session: AsyncSession,
    ):
        """Estimated reports should not count toward staff cost."""
        project = setup_aggregation["project"]
        period = setup_aggregation["period2"]

        user2 = UserDB(email="est@example.com", name="Est User")
        db_session.add(user2)
        await db_session.flush()

        estimated_report = ReportDB(
            user_id=user2.id,
            reporting_period_id=period.id,
            estimated=True,
        )
        db_session.add(estimated_report)
        await db_session.flush()

        est_part = ReportPartDB(
            report_id=estimated_report.id, project_id=project.id,
            percentage=Decimal("0.50"), cost=Decimal("9999.99"),
            days=Decimal("10.0"),
        )
        db_session.add(est_part)
        await db_session.commit()

        resp = await client.get(
            f"/api/tracker/projects/{project.id}/cost-summary",
        )
        data = resp.json()
        # Staff cost should NOT include the 9999.99 from estimated report
        assert data["staff_cost"] == 3411.03

    @pytest.mark.asyncio
    async def test_cost_summary_empty_project(
        self, client: AsyncClient, setup_aggregation: dict, db_session: AsyncSession,
    ):
        """Project with no reports returns zero costs."""
        empty_project = ProjectDB(name="Empty Project", status="live")
        db_session.add(empty_project)
        await db_session.commit()
        await db_session.refresh(empty_project)

        resp = await client.get(
            f"/api/tracker/projects/{empty_project.id}/cost-summary",
        )
        data = resp.json()
        assert data["staff_cost"] == 0.0
        assert data["non_staff_cost"] == 0.0
        assert data["total_cost"] == 0.0
        assert data["periods"] == []
        assert data["budget"] is None


class TestProjectReportParts:
    @pytest.mark.asyncio
    async def test_list_all_parts(
        self, client: AsyncClient, setup_aggregation: dict,
    ):
        project_id = str(setup_aggregation["project"].id)
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/report-parts",
        )
        assert resp.status_code == 200
        parts = resp.json()
        assert len(parts) == 2

        # Ordered by date desc: March part first
        assert parts[0]["period_date"] == "2026-03-01"
        assert parts[0]["user_name"] == "Test User"
        assert parts[0]["functional_area"] == "Backend Developer"
        assert parts[0]["cost"] == 2274.02
        assert parts[0]["estimated"] is False

    @pytest.mark.asyncio
    async def test_filter_by_period(
        self, client: AsyncClient, setup_aggregation: dict,
    ):
        project_id = str(setup_aggregation["project"].id)
        period_id = str(setup_aggregation["period1"].id)
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/report-parts",
            params={"period_id": period_id},
        )
        parts = resp.json()
        assert len(parts) == 1
        assert parts[0]["period_date"] == "2026-02-01"
```

- [ ] **Step 2: Run to see them fail**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/tracker/test_aggregation.py -v 2>&1 | tail -20 && popd > /dev/null`

### Task 7: Project costs API endpoint

**Files:**
- Create: `backend/app/modules/tracker/api/project_costs.py`
- Modify: `backend/app/modules/tracker/router.py`

- [ ] **Step 1: Create endpoint**

```python
# backend/app/modules/tracker/api/project_costs.py
"""Project cost aggregation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.schemas.project_cost import (
    ProjectCostSummary,
    ProjectReportPartResponse,
)
from app.modules.tracker.services.aggregation_service import (
    get_project_cost_summary,
    get_project_report_parts,
)

router = APIRouter()


@router.get("/{project_id}/cost-summary", response_model=ProjectCostSummary)
async def project_cost_summary(
    project_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> ProjectCostSummary:
    return await get_project_cost_summary(db, project_id)


@router.get(
    "/{project_id}/report-parts",
    response_model=list[ProjectReportPartResponse],
)
async def project_report_parts(
    project_id: UUID,
    db: DBSession,
    user: CurrentUser,
    period_id: UUID | None = Query(default=None),
) -> list[ProjectReportPartResponse]:
    return await get_project_report_parts(db, project_id, period_id)
```

- [ ] **Step 2: Mount in router**

Add to `backend/app/modules/tracker/router.py`:

```python
from app.modules.tracker.api import project_costs as project_costs_router

router.include_router(
    project_costs_router.router,
    prefix="/projects",
    tags=["tracker:project-costs"],
)
```

- [ ] **Step 3: Run aggregation tests**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/tracker/test_aggregation.py -v 2>&1 | tail -30 && popd > /dev/null`
Expected: All PASS

- [ ] **Step 4: Run full tracker test suite**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/tracker/ -v 2>&1 | tail -30 && popd > /dev/null`
Expected: All existing + new tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/tracker/schemas/project_cost.py backend/app/modules/tracker/services/aggregation_service.py backend/app/modules/tracker/api/project_costs.py backend/app/modules/tracker/router.py backend/tests/modules/tracker/test_aggregation.py
git commit -m "feat(tracker): add project cost aggregation endpoint and service"
```

---

## Chunk 3: Frontend — Types, Services, Hooks, MSW

### Task 8: Extend FE types and services

**Files:**
- Modify: `frontend/src/modules/tracker/types/tracker.ts`
- Modify: `frontend/src/modules/tracker/services/tracker.ts`
- Modify: `frontend/src/core/hooks/queryKeys.ts`

- [ ] **Step 1: Add types**

Append to `frontend/src/modules/tracker/types/tracker.ts`:

```typescript
export interface PeriodCostBreakdown {
  period_id: string;
  date: string;
  staff_cost: number;
  non_staff_cost: number;
  total: number;
  parts_count: number;
}

export interface ProjectCostSummary {
  project_id: string;
  budget: number | null;
  contract_rate: number;
  staff_cost: number;
  non_staff_cost: number;
  total_cost: number;
  burn_percentage: number | null;
  periods: PeriodCostBreakdown[];
}

export interface ProjectReportPart {
  id: string;
  period_date: string;
  user_name: string | null;
  user_email: string | null;
  functional_area: string | null;
  percentage: number | null;
  days: number | null;
  cost: number | null;
  estimated: boolean;
}

export interface NonStaffCost {
  id: string;
  project_id: string;
  reporting_period_id: string;
  cost: number;
  cost_type: string;
  details: string | null;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: Add service methods**

Append to `trackerApi` in `frontend/src/modules/tracker/services/tracker.ts`:

```typescript
  // Project Costs
  getProjectCostSummary: async (projectId: string): Promise<ProjectCostSummary> => {
    const response = await api.get<ProjectCostSummary>(
      `/tracker/projects/${projectId}/cost-summary`,
    );
    return response.data;
  },

  getProjectReportParts: async (
    projectId: string,
    periodId?: string,
  ): Promise<ProjectReportPart[]> => {
    const response = await api.get<ProjectReportPart[]>(
      `/tracker/projects/${projectId}/report-parts`,
      { params: periodId ? { period_id: periodId } : undefined },
    );
    return response.data;
  },
```

Add the new type imports at the top of the file.

- [ ] **Step 3: Add query keys**

Add to `tracker` section in `frontend/src/core/hooks/queryKeys.ts`:

```typescript
    projectCosts: {
      summary: (projectId: string) =>
        ['tracker', 'project-costs', projectId, 'summary'] as const,
      parts: (projectId: string, periodId?: string) =>
        ['tracker', 'project-costs', projectId, 'parts', periodId] as const,
    },
```

- [ ] **Step 4: Verify TS compiles**

Run: `pushd frontend > /dev/null && npx tsc --noEmit 2>&1 | head -20 && popd > /dev/null`

### Task 9: Project costs hooks

**Files:**
- Create: `frontend/src/modules/tracker/hooks/useProjectCosts.ts`

- [ ] **Step 1: Create hooks**

```typescript
// frontend/src/modules/tracker/hooks/useProjectCosts.ts
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';

export function useProjectCostSummary(projectId: string) {
  return useQuery({
    queryKey: queryKeys.tracker.projectCosts.summary(projectId),
    queryFn: () => trackerApi.getProjectCostSummary(projectId),
    enabled: !!projectId,
  });
}

export function useProjectReportParts(projectId: string, periodId?: string) {
  return useQuery({
    queryKey: queryKeys.tracker.projectCosts.parts(projectId, periodId),
    queryFn: () => trackerApi.getProjectReportParts(projectId, periodId),
    enabled: !!projectId,
  });
}
```

### Task 10: MSW handlers

**Files:**
- Modify: `frontend/src/test/msw-handlers.ts`

- [ ] **Step 1: Add cost summary and report parts fixtures + handlers**

Add fixtures after existing tracker fixtures:

```typescript
const defaultProjectCostSummary = {
  project_id: 'project-1',
  budget: 50000.0,
  contract_rate: 175.0,
  staff_cost: 3411.03,
  non_staff_cost: 500.0,
  total_cost: 3911.03,
  burn_percentage: 7.82,
  periods: [
    {
      period_id: 'period-1',
      date: '2026-03-01',
      staff_cost: 2274.02,
      non_staff_cost: 0.0,
      total: 2274.02,
      parts_count: 1,
    },
    {
      period_id: 'period-2',
      date: '2026-02-01',
      staff_cost: 1137.01,
      non_staff_cost: 500.0,
      total: 1637.01,
      parts_count: 1,
    },
  ],
};

const defaultProjectReportParts = [
  {
    id: 'part-1',
    period_date: '2026-03-01',
    user_name: 'Test User',
    user_email: 'test@example.com',
    functional_area: 'Backend Developer',
    percentage: 0.2,
    days: 2.96,
    cost: 2274.02,
    estimated: false,
  },
  {
    id: 'part-2',
    period_date: '2026-02-01',
    user_name: 'Test User',
    user_email: 'test@example.com',
    functional_area: 'Backend Developer',
    percentage: 0.1,
    days: 1.48,
    cost: 1137.01,
    estimated: false,
  },
];
```

Add handlers:

```typescript
  http.get(`${BASE}/tracker/projects/:projectId/cost-summary`, () => {
    return HttpResponse.json(defaultProjectCostSummary);
  }),
  http.get(`${BASE}/tracker/projects/:projectId/report-parts`, () => {
    return HttpResponse.json(defaultProjectReportParts);
  }),
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/tracker/types/tracker.ts frontend/src/modules/tracker/services/tracker.ts frontend/src/core/hooks/queryKeys.ts frontend/src/modules/tracker/hooks/useProjectCosts.ts frontend/src/test/msw-handlers.ts
git commit -m "feat(tracker): add FE types, services, hooks for project cost summary"
```

---

## Chunk 4: Frontend — Page + Tests + Route

### Task 11: ProjectTrackerDetail page

**Files:**
- Create: `frontend/src/modules/tracker/pages/ProjectTrackerDetail.tsx`

- [ ] **Step 1: Create page component**

```tsx
// frontend/src/modules/tracker/pages/ProjectTrackerDetail.tsx
import { useNavigate, useParams } from 'react-router-dom';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useProject } from '@/core/hooks/useProjects';
import { useProjectCostSummary, useProjectReportParts } from '../hooks/useProjectCosts';
import { formatPeriodDate, SELECT_CLASS } from '../utils/constants';

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
  }).format(value);
}

function burnColor(pct: number): string {
  if (pct > 100) return 'bg-destructive';
  if (pct >= 80) return 'bg-yellow-500';
  return 'bg-primary';
}

export default function ProjectTrackerDetail(): JSX.Element {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [periodFilter, setPeriodFilter] = useUrlState<string>('period', '');

  const { data: project } = useProject(projectId ?? '');
  const { data: summary, isLoading: summaryLoading } = useProjectCostSummary(
    projectId ?? '',
  );
  const { data: parts, isLoading: partsLoading } = useProjectReportParts(
    projectId ?? '',
    periodFilter || undefined,
  );

  if (summaryLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1"
          onClick={() => navigate('/projects')}
        >
          <ArrowLeft className="h-4 w-4" />
          Projects
        </Button>
        <h1 className="text-2xl font-semibold">
          {project?.name ?? 'Project'} — Tracker
        </h1>
      </div>

      {summary && (
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Budget</p>
              <p className="text-2xl font-bold">
                {summary.budget != null
                  ? formatCurrency(summary.budget)
                  : 'Not set'}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Cost to Date</p>
              <p className="text-2xl font-bold">
                {formatCurrency(summary.total_cost)}
              </p>
              <div className="mt-1 text-xs text-muted-foreground">
                Staff: {formatCurrency(summary.staff_cost)} | Non-staff:{' '}
                {formatCurrency(summary.non_staff_cost)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Burn</p>
              <p className="text-2xl font-bold">
                {summary.burn_percentage != null
                  ? `${summary.burn_percentage}%`
                  : '—'}
              </p>
              {summary.burn_percentage != null && (
                <div className="mt-2 h-2 w-full rounded-full bg-muted">
                  <div
                    className={`h-2 rounded-full ${burnColor(summary.burn_percentage)}`}
                    style={{
                      width: `${Math.min(summary.burn_percentage, 100)}%`,
                    }}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Reports</CardTitle>
          {summary && summary.periods.length > 0 && (
            <select
              className={SELECT_CLASS}
              value={periodFilter}
              onChange={(e) => setPeriodFilter(e.target.value)}
            >
              <option value="">All periods</option>
              {summary.periods.map((p) => (
                <option key={p.period_id} value={p.period_id}>
                  {formatPeriodDate(p.date)}
                </option>
              ))}
            </select>
          )}
        </CardHeader>
        <CardContent>
          {partsLoading ? (
            <LoadingSpinner />
          ) : !parts?.length ? (
            <p className="text-sm text-muted-foreground">
              No report data for this project.
            </p>
          ) : (
            <>
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-sm text-muted-foreground">
                    <th className="py-2 px-3">Period</th>
                    <th className="py-2 px-3">User</th>
                    <th className="py-2 px-3">Functional Area</th>
                    <th className="py-2 px-3 text-right">%</th>
                    <th className="py-2 px-3 text-right">Days</th>
                    <th className="py-2 px-3 text-right">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {parts.map((part) => (
                    <tr key={part.id} className="border-b hover:bg-muted/50">
                      <td className="py-2 px-3">
                        {formatPeriodDate(part.period_date)}
                      </td>
                      <td className="py-2 px-3">
                        {part.user_name ?? part.user_email ?? '—'}
                      </td>
                      <td className="py-2 px-3">
                        {part.functional_area ?? '—'}
                      </td>
                      <td className="py-2 px-3 text-right">
                        {part.percentage != null
                          ? `${(part.percentage * 100).toFixed(1)}%`
                          : '—'}
                      </td>
                      <td className="py-2 px-3 text-right">
                        {part.days?.toFixed(2) ?? '—'}
                      </td>
                      <td className="py-2 px-3 text-right">
                        {part.cost != null ? formatCurrency(part.cost) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {summary && (
                <div className="mt-4 flex justify-end gap-6 border-t pt-3 text-sm">
                  <span>
                    Staff: <strong>{formatCurrency(summary.staff_cost)}</strong>
                  </span>
                  <span>
                    Non-staff:{' '}
                    <strong>{formatCurrency(summary.non_staff_cost)}</strong>
                  </span>
                  <span>
                    Total:{' '}
                    <strong>{formatCurrency(summary.total_cost)}</strong>
                  </span>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

**Note:** `useProject` already exists in `@/core/hooks/useProjects` — check that it accepts a project ID and returns project data. If not, the implementer should use the existing projects API to fetch the name.

### Task 12: Route + breadcrumb

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/core/components/layout/PageBreadcrumb.tsx`

- [ ] **Step 1: Add route**

In `frontend/src/App.tsx`, add import at the top:

```tsx
import ProjectTrackerDetail from '@/modules/tracker/pages/ProjectTrackerDetail';
```

Add route in **both** route trees — alongside the existing `/tracker/*` user-facing routes:

1. In BYPASS_AUTH block (line ~77): after `<Route path="/tracker/how-to-report" .../>`, add:
```tsx
<Route path="/tracker/projects/:projectId" element={<ProjectTrackerDetail />} />
```

2. In authenticated block (line ~98): after `<Route path="/tracker/how-to-report" .../>`, add the same route:
```tsx
<Route path="/tracker/projects/:projectId" element={<ProjectTrackerDetail />} />
```

- [ ] **Step 2: Add breadcrumb**

In `frontend/src/core/components/layout/PageBreadcrumb.tsx`, add a case for `/tracker/projects/:id`:

```typescript
// Pattern: /tracker/projects/:id → Tracker > Project Detail
if (pathname.match(/^\/tracker\/projects\/[^/]+$/)) {
  return [
    { label: 'Projects', href: '/projects' },
    { label: 'Tracker Detail' },
  ];
}
```

### Task 13: FE integration tests

**Files:**
- Create: `frontend/src/modules/tracker/pages/__tests__/ProjectTrackerDetail.test.tsx`

- [ ] **Step 1: Write tests**

```tsx
// frontend/src/modules/tracker/pages/__tests__/ProjectTrackerDetail.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { server } from '@/test/setup';
import ProjectTrackerDetail from '../ProjectTrackerDetail';

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

function renderDetail(
  projectId: string = 'project-1',
): ReturnType<typeof render> {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[`/tracker/projects/${projectId}`]}>
        <Routes>
          <Route
            path="/tracker/projects/:projectId"
            element={<ProjectTrackerDetail />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ProjectTrackerDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.resetHandlers();
  });

  it('renders budget card with summary data', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText(/50,000/)).toBeInTheDocument();
    });
    expect(screen.getByText(/3,911.03/)).toBeInTheDocument();
    expect(screen.getByText(/7.82%/)).toBeInTheDocument();
  });

  it('renders reports table with parts', async () => {
    renderDetail();
    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });
    expect(screen.getByText('Backend Developer')).toBeInTheDocument();
    expect(screen.getAllByText(/2,274.02/).length).toBeGreaterThanOrEqual(1);
  });

  it('shows empty state for project with no data', async () => {
    server.use(
      http.get('/api/tracker/projects/:projectId/cost-summary', () => {
        return HttpResponse.json({
          project_id: 'empty',
          budget: null,
          contract_rate: 175.0,
          staff_cost: 0,
          non_staff_cost: 0,
          total_cost: 0,
          burn_percentage: null,
          periods: [],
        });
      }),
      http.get('/api/tracker/projects/:projectId/report-parts', () => {
        return HttpResponse.json([]);
      }),
    );

    renderDetail('empty');
    await waitFor(() => {
      expect(
        screen.getByText(/No report data for this project/),
      ).toBeInTheDocument();
    });
  });

  it('filters by period when selecting from dropdown', async () => {
    const user = userEvent.setup();
    renderDetail();

    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });

    const select = screen.getByRole('combobox') as HTMLSelectElement;
    await user.selectOptions(select, 'period-2');

    // The hook should refetch with period_id filter
    await waitFor(() => {
      expect(select.value).toBe('period-2');
    });
  });
});
```

- [ ] **Step 2: Run FE tests**

Run: `pushd frontend > /dev/null && npx vitest run src/modules/tracker/ --reporter=verbose 2>&1 | tail -30 && popd > /dev/null`
Expected: All tests PASS (existing + new)

- [ ] **Step 3: TS compile check**

Run: `pushd frontend > /dev/null && npx tsc --noEmit 2>&1 | head -20 && popd > /dev/null`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/tracker/pages/ProjectTrackerDetail.tsx frontend/src/modules/tracker/pages/__tests__/ProjectTrackerDetail.test.tsx frontend/src/App.tsx frontend/src/core/components/layout/PageBreadcrumb.tsx
git commit -m "feat(tracker): add project tracker detail page with cost summary"
```

---

## Chunk 5: Legacy Validation (Manual Checkpoint)

### Task 14: Validate against legacy

- [ ] **Step 1: Start backend**

Run: `pushd backend > /dev/null && python run_server.py &`

- [ ] **Step 2: Pick 2-3 projects with imported data and compare**

For each project, call:
```
GET /api/tracker/projects/{project_id}/cost-summary
```

Compare `total_cost` (staff_cost + non_staff_cost) against the legacy VizzTracker's "Cost to date" value. Values should match within rounding tolerance (< €1 difference).

- [ ] **Step 3: Document results**

If values match: validation passes. If discrepancies: investigate whether it's a rounding difference, estimated report inclusion, or data import issue.

- [ ] **Step 4: Run full test suites**

```bash
pushd backend > /dev/null && python -m pytest 2>&1 | tail -5 && popd > /dev/null
pushd frontend > /dev/null && npm test 2>&1 | tail -5 && popd > /dev/null
```

- [ ] **Step 5: Final commit if any fixes needed**
