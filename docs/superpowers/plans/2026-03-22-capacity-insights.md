# Capacity Insights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Capacity Insights page with a grouped stacked bar chart showing billable vs non-billable time allocation by functional area per month.

**Architecture:** New `capacity` backend module with a single endpoint that calls an analytical query in `core/services/`. Frontend gets a new `capacity` module with Recharts visualization. Sidebar gains a collapsible "Capacity" section visible to all authenticated users.

**Tech Stack:** FastAPI, SQLAlchemy (async), Pydantic, React, Recharts, React Query, TypeScript, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-22-capacity-insights-design.md`

---

## File Structure

### Backend (create)
- `backend/app/core/services/capacity_insights.py` — analytical query joining core + tracker tables
- `backend/app/modules/capacity/__init__.py` — empty module init
- `backend/app/modules/capacity/api/__init__.py` — empty api init
- `backend/app/modules/capacity/api/insights.py` — GET endpoint
- `backend/app/modules/capacity/router.py` — sub-router aggregator
- `backend/app/modules/capacity/public.py` — cross-module interface (empty placeholder)
- `backend/tests/modules/capacity/__init__.py` — empty test init
- `backend/tests/modules/capacity/test_capacity_insights.py` — endpoint + service tests

### Backend (modify)
- `backend/app/main.py` — mount capacity router

### Frontend (create)
- `frontend/src/modules/capacity/types/capacity.ts` — response types
- `frontend/src/modules/capacity/services/capacity.ts` — API client
- `frontend/src/modules/capacity/hooks/useCapacityInsights.ts` — React Query hook
- `frontend/src/modules/capacity/components/InsightsChart.tsx` — Recharts chart
- `frontend/src/modules/capacity/components/MonthRangePicker.tsx` — date controls
- `frontend/src/modules/capacity/pages/Insights.tsx` — page component

### Frontend (modify)
- `frontend/src/core/hooks/queryKeys.ts` — add capacity keys
- `frontend/src/core/components/layout/AppSidebar.tsx` — add Capacity section
- `frontend/src/App.tsx` — add `/capacity/insights` route

---

## Task 1: Backend — Core Service (analytical query)

**Files:**
- Create: `backend/app/core/services/capacity_insights.py`
- Create: `backend/tests/modules/capacity/__init__.py`
- Create: `backend/tests/modules/capacity/test_capacity_insights.py`

- [ ] **Step 1: Create test file with fixtures**

Create `backend/tests/modules/capacity/__init__.py` (empty).

Create `backend/tests/modules/capacity/test_capacity_insights.py`:

```python
"""Tests for capacity insights analytical query."""

import datetime as dt
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
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
    db_session.add_all([billable_project, internal_project])
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
    user_no_report = UserDB(
        email="norpt@test.com", first_name="No", last_name="Report",
        functional_area_id=fa_fe.id, active=True, requires_project_reporting=False,
    )
    db_session.add_all([user_fe1, user_fe2, user_be1, user_no_report])
    await db_session.flush()

    period_jan = ReportingPeriodDB(
        date=dt.date(2026, 1, 1), base_rate=Decimal("175"), status="finished",
    )
    period_feb = ReportingPeriodDB(
        date=dt.date(2026, 2, 1), base_rate=Decimal("175"), status="finished",
    )
    db_session.add_all([period_jan, period_feb])
    await db_session.flush()

    # fe1: 60% billable, 40% internal in Jan
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
            percentage=Decimal("0.4000"),
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
        # user_no_report has requires_project_reporting=False, excluded
        assert fa_map["FE"]["user_count"] == 2

    @pytest.mark.asyncio
    async def test_user_with_no_report_contributes_zero(
        self, db_session: AsyncSession, capacity_data: dict,
    ):
        from app.core.services.capacity_insights import get_capacity_insights

        # Feb has no reports for anyone
        result = await get_capacity_insights(
            db=db_session,
            start_date=dt.date(2026, 2, 1),
            end_date=dt.date(2026, 2, 1),
        )
        fa_map = {fa["short"]: fa for fa in result[0]["functional_areas"]}
        assert fa_map["FE"]["billable_pct"] == 0.0
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/capacity/test_capacity_insights.py -v && popd > /dev/null`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.services.capacity_insights'`

- [ ] **Step 3: Implement the core service**

Create `backend/app/core/services/capacity_insights.py`:

```python
"""Analytical query for capacity insights.

Cross-module JOIN: core tables (users, functional_areas, projects)
+ tracker tables (reports, report_parts, reporting_periods).
Placed in core/services/ per architecture Rule 4.
"""

import logging
from datetime import date

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

logger = logging.getLogger(__name__)

TARGET_FA_MAPPING: dict[str, str] = {
    "Frontend Developer": "FE",
    "Backend Developer": "BE",
    "Designer": "Design",
    "Project Manager": "PM",
    "Scientist": "Sci",
    "Communications": "Coms",
}


async def get_capacity_insights(
    db: AsyncSession,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Compute billable allocation % per target FA per period.

    Returns list of dicts sorted by period ascending, each containing
    'period' (YYYY-MM) and 'functional_areas' list.
    """
    fa_rows = list(await db.execute(
        select(FunctionalAreaDB.id, FunctionalAreaDB.name)
        .where(FunctionalAreaDB.name.in_(TARGET_FA_MAPPING.keys()))
    ))
    fa_id_to_short: dict = {}
    found_names: set[str] = set()
    for fa_id, fa_name in fa_rows:
        fa_id_to_short[fa_id] = TARGET_FA_MAPPING[fa_name]
        found_names.add(fa_name)

    for name in set(TARGET_FA_MAPPING.keys()) - found_names:
        logger.warning("Capacity insights: FA '%s' not found in database", name)

    if not fa_id_to_short:
        return []

    periods_result = await db.execute(
        select(ReportingPeriodDB.id, ReportingPeriodDB.date)
        .where(
            ReportingPeriodDB.date >= start_date,
            ReportingPeriodDB.date <= end_date,
        )
        .order_by(ReportingPeriodDB.date)
    )
    periods = list(periods_result)

    if not periods:
        return []

    eligible_users = await db.execute(
        select(UserDB.id, UserDB.functional_area_id)
        .where(
            UserDB.active.is_(True),
            UserDB.requires_project_reporting.is_(True),
            UserDB.functional_area_id.in_(fa_id_to_short.keys()),
        )
    )
    users_by_fa: dict[str, list] = {}
    for user_id, fa_id in eligible_users:
        short = fa_id_to_short[fa_id]
        users_by_fa.setdefault(short, []).append(user_id)

    billable_sum_subq = (
        select(
            ReportDB.user_id,
            ReportDB.reporting_period_id,
            func.coalesce(func.sum(
                case(
                    (ProjectDB.is_billable.is_(True), ReportPartDB.percentage),
                    else_=0,
                )
            ), 0).label("billable_pct"),
        )
        .join(ReportPartDB, ReportPartDB.report_id == ReportDB.id)
        .join(ProjectDB, ProjectDB.id == ReportPartDB.project_id)
        .where(ReportPartDB.percentage.isnot(None))
        .group_by(ReportDB.user_id, ReportDB.reporting_period_id)
        .subquery()
    )

    period_ids = [p_id for p_id, _ in periods]
    billable_rows = await db.execute(
        select(
            billable_sum_subq.c.user_id,
            billable_sum_subq.c.reporting_period_id,
            billable_sum_subq.c.billable_pct,
        ).where(billable_sum_subq.c.reporting_period_id.in_(period_ids))
    )

    billable_lookup: dict[tuple, float] = {}
    for user_id, period_id, pct in billable_rows:
        billable_lookup[(user_id, period_id)] = float(pct)

    result = []
    for period_id, period_date in periods:
        fas = []
        for short, user_ids in sorted(users_by_fa.items()):
            if not user_ids:
                continue
            total_billable = sum(
                billable_lookup.get((uid, period_id), 0.0)
                for uid in user_ids
            )
            avg_billable = total_billable / len(user_ids)
            fas.append({
                "short": short,
                "billable_pct": round(avg_billable, 4),
                "user_count": len(user_ids),
            })
        result.append({
            "period": period_date.strftime("%Y-%m"),
            "functional_areas": fas,
        })

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/capacity/test_capacity_insights.py -v && popd > /dev/null`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/services/capacity_insights.py backend/tests/modules/capacity/
git commit -m "feat(capacity): add core service for capacity insights query"
```

---

## Task 2: Backend — Module skeleton + endpoint

**Files:**
- Create: `backend/app/modules/capacity/__init__.py`
- Create: `backend/app/modules/capacity/api/__init__.py`
- Create: `backend/app/modules/capacity/api/insights.py`
- Create: `backend/app/modules/capacity/router.py`
- Create: `backend/app/modules/capacity/public.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add endpoint test to existing test file**

Append to `backend/tests/modules/capacity/test_capacity_insights.py`:

```python
from httpx import AsyncClient


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
    async def test_missing_params_returns_422(
        self, client: AsyncClient, capacity_data: dict,
    ):
        resp = await client.get("/api/capacity/insights")
        assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/capacity/test_capacity_insights.py::TestCapacityInsightsEndpoint -v && popd > /dev/null`
Expected: FAIL — 404 (route not mounted yet)

- [ ] **Step 3: Create module skeleton files**

Create `backend/app/modules/capacity/__init__.py` (empty file).

Create `backend/app/modules/capacity/api/__init__.py` (empty file).

Create `backend/app/modules/capacity/public.py`:

```python
"""Cross-module public interface for the capacity module."""
```

Create `backend/app/modules/capacity/api/insights.py`:

```python
"""Capacity insights endpoint."""

import re
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import get_capacity_insights

router = APIRouter()

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_MAX_RANGE_MONTHS = 24


def _parse_month(value: str) -> date:
    """Parse YYYY-MM string to first-of-month date."""
    if not _MONTH_RE.match(value):
        raise HTTPException(status_code=422, detail=f"Invalid date format: {value}")
    year, month = value.split("-")
    return date(int(year), int(month), 1)


@router.get("")
async def capacity_insights(
    db: DBSession,
    user: CurrentUser,
    start_date: str = Query(..., description="Start month (YYYY-MM)"),
    end_date: str = Query(..., description="End month (YYYY-MM)"),
) -> list[dict]:
    start = _parse_month(start_date)
    end = _parse_month(end_date)

    if start > end:
        raise HTTPException(
            status_code=422,
            detail="start_date must be <= end_date",
        )

    month_diff = (end.year - start.year) * 12 + (end.month - start.month)
    if month_diff >= _MAX_RANGE_MONTHS:
        raise HTTPException(
            status_code=422,
            detail=f"Date range must not exceed {_MAX_RANGE_MONTHS} months",
        )

    return await get_capacity_insights(db=db, start_date=start, end_date=end)
```

Create `backend/app/modules/capacity/router.py`:

```python
from fastapi import APIRouter

from app.modules.capacity.api import insights as insights_router

router = APIRouter()
router.include_router(
    insights_router.router, prefix="/insights", tags=["capacity:insights"]
)
```

- [ ] **Step 4: Mount router in main.py**

In `backend/app/main.py`, add the import near the other module router imports:

```python
from app.modules.capacity.router import router as capacity_router
```

And add the mount line after the tracker router mount:

```python
app.include_router(capacity_router, prefix="/api/capacity", tags=["capacity"])
```

- [ ] **Step 5: Run all capacity tests**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/capacity/ -v && popd > /dev/null`
Expected: All 11 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/capacity/ backend/app/main.py backend/tests/modules/capacity/
git commit -m "feat(capacity): add capacity insights endpoint with validation"
```

---

## Task 3: Frontend — Types, service, hook, query keys

**Files:**
- Create: `frontend/src/modules/capacity/types/capacity.ts`
- Create: `frontend/src/modules/capacity/services/capacity.ts`
- Create: `frontend/src/modules/capacity/hooks/useCapacityInsights.ts`
- Modify: `frontend/src/core/hooks/queryKeys.ts`

- [ ] **Step 1: Create types**

Create `frontend/src/modules/capacity/types/capacity.ts`:

```typescript
export interface FunctionalAreaInsight {
  short: string;
  billable_pct: number;
  user_count: number;
}

export interface PeriodInsight {
  period: string;
  functional_areas: FunctionalAreaInsight[];
}
```

- [ ] **Step 2: Create API service**

Create `frontend/src/modules/capacity/services/capacity.ts`:

```typescript
import api from '@/core/services/client';
import type { PeriodInsight } from '@/modules/capacity/types/capacity';

export const capacityApi = {
  getInsights: async (startDate: string, endDate: string): Promise<PeriodInsight[]> => {
    const response = await api.get<PeriodInsight[]>('/capacity/insights', {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  },
};
```

- [ ] **Step 3: Add query keys**

In `frontend/src/core/hooks/queryKeys.ts`, add inside the `queryKeys` object (after the `tracker` key):

```typescript
  capacity: {
    insights: (startDate: string, endDate: string) =>
      ['capacity', 'insights', startDate, endDate] as const,
  },
```

- [ ] **Step 4: Create hook**

Create `frontend/src/modules/capacity/hooks/useCapacityInsights.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { capacityApi } from '@/modules/capacity/services/capacity';

export function useCapacityInsights(startDate: string, endDate: string) {
  return useQuery({
    queryKey: queryKeys.capacity.insights(startDate, endDate),
    queryFn: () => capacityApi.getInsights(startDate, endDate),
    enabled: !!startDate && !!endDate,
  });
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/capacity/ frontend/src/core/hooks/queryKeys.ts
git commit -m "feat(capacity): add frontend types, service, hook for capacity insights"
```

---

## Task 4: Frontend — MonthRangePicker component

**Files:**
- Create: `frontend/src/modules/capacity/components/MonthRangePicker.tsx`

- [ ] **Step 1: Create MonthRangePicker**

Create `frontend/src/modules/capacity/components/MonthRangePicker.tsx`:

```tsx
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';

interface MonthRangePickerProps {
  readonly startDate: string;
  readonly endDate: string;
  readonly onChange: (start: string, end: string) => void;
}

export function MonthRangePicker({
  startDate,
  endDate,
  onChange,
}: MonthRangePickerProps): JSX.Element {
  return (
    <div className="flex items-end gap-4">
      <div className="space-y-1">
        <Label htmlFor="start-month">From</Label>
        <Input
          id="start-month"
          type="month"
          value={startDate}
          onChange={(e) => onChange(e.target.value, endDate)}
          className="w-40"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="end-month">To</Label>
        <Input
          id="end-month"
          type="month"
          value={endDate}
          onChange={(e) => onChange(startDate, e.target.value)}
          className="w-40"
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/capacity/components/MonthRangePicker.tsx
git commit -m "feat(capacity): add MonthRangePicker component"
```

---

## Task 5: Frontend — InsightsChart component

**Files:**
- Create: `frontend/src/modules/capacity/components/InsightsChart.tsx`

- [ ] **Step 1: Create the chart component**

Create `frontend/src/modules/capacity/components/InsightsChart.tsx`:

```tsx
import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts';
import type { PeriodInsight } from '@/modules/capacity/types/capacity';

const FA_COLORS: Record<string, string> = {
  FE: '#3b82f6',
  BE: '#10b981',
  Design: '#f59e0b',
  PM: '#8b5cf6',
  Sci: '#ef4444',
  Coms: '#06b6d4',
};

const FA_ORDER = ['FE', 'BE', 'Design', 'PM', 'Sci', 'Coms'];

interface ChartDataPoint {
  month: string;
  [key: string]: number | string;
}

function formatMonth(period: string): string {
  const [year, month] = period.split('-');
  const date = new Date(Number(year), Number(month) - 1);
  return date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
}

function transformData(data: PeriodInsight[]): ChartDataPoint[] {
  return data.map((period) => {
    const point: ChartDataPoint = { month: formatMonth(period.period) };
    for (const fa of period.functional_areas) {
      point[`${fa.short}_projects`] = Math.round(fa.billable_pct * 100);
      point[`${fa.short}_others`] = Math.round((1 - fa.billable_pct) * 100);
      point[`${fa.short}_users`] = fa.user_count;
    }
    return point;
  });
}

interface InsightsChartProps {
  readonly data: PeriodInsight[];
}

export function InsightsChart({ data }: InsightsChartProps): JSX.Element {
  const chartData = useMemo(() => transformData(data), [data]);

  const activeFAs = useMemo(() => {
    const found = new Set<string>();
    for (const period of data) {
      for (const fa of period.functional_areas) {
        found.add(fa.short);
      }
    }
    return FA_ORDER.filter((fa) => found.has(fa));
  }, [data]);

  if (chartData.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        No data for the selected period
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={450}>
      <BarChart data={chartData} barCategoryGap="15%" barGap={1}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="month" tick={{ fontSize: 12 }} />
        <YAxis
          domain={[0, 100]}
          tickFormatter={(v: number) => `${v}%`}
          tick={{ fontSize: 12 }}
        />
        <RechartsTooltip
          formatter={(value: number, name: string) => {
            const [fa, type] = name.split('_');
            const label = type === 'projects' ? `${fa} Projects` : `${fa} Others`;
            return [`${value}%`, label];
          }}
          labelFormatter={(label: string) => label}
        />
        <Legend
          formatter={(value: string) => {
            const [fa, type] = value.split('_');
            return type === 'projects' ? `${fa} Projects` : `${fa} Others`;
          }}
        />
        {activeFAs.map((fa) => (
          <Bar
            key={`${fa}_projects`}
            dataKey={`${fa}_projects`}
            stackId={fa}
            fill={FA_COLORS[fa]}
            name={`${fa}_projects`}
          />
        ))}
        {activeFAs.map((fa) => (
          <Bar
            key={`${fa}_others`}
            dataKey={`${fa}_others`}
            stackId={fa}
            fill={FA_COLORS[fa]}
            fillOpacity={0.3}
            name={`${fa}_others`}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/capacity/components/InsightsChart.tsx
git commit -m "feat(capacity): add InsightsChart grouped stacked bar component"
```

---

## Task 6: Frontend — Insights page + routing + sidebar

**Files:**
- Create: `frontend/src/modules/capacity/pages/Insights.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/core/components/layout/AppSidebar.tsx`

- [ ] **Step 1: Create Insights page**

Create `frontend/src/modules/capacity/pages/Insights.tsx`:

```tsx
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useCapacityInsights } from '@/modules/capacity/hooks/useCapacityInsights';
import { InsightsChart } from '@/modules/capacity/components/InsightsChart';
import { MonthRangePicker } from '@/modules/capacity/components/MonthRangePicker';

function defaultRange(): { start: string; end: string } {
  const now = new Date();
  const endYear = now.getFullYear();
  const endMonth = now.getMonth() + 1;
  const startDate = new Date(endYear, endMonth - 7, 1);
  const startYear = startDate.getFullYear();
  const startMonth = startDate.getMonth() + 1;
  return {
    start: `${startYear}-${String(startMonth).padStart(2, '0')}`,
    end: `${endYear}-${String(endMonth).padStart(2, '0')}`,
  };
}

const defaults = defaultRange();

export default function Insights(): JSX.Element {
  const { state, setState } = useUrlState({
    start: { defaultValue: defaults.start },
    end: { defaultValue: defaults.end },
  });

  const { data, isLoading, error } = useCapacityInsights(state.start, state.end);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Capacity Insights</h1>
        <MonthRangePicker
          startDate={state.start}
          endDate={state.end}
          onChange={(start, end) => setState({ start, end })}
        />
      </div>

      {isLoading && (
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          Loading...
        </div>
      )}

      {error && (
        <div className="flex h-64 items-center justify-center text-destructive">
          Failed to load capacity data
        </div>
      )}

      {data && <InsightsChart data={data} />}
    </div>
  );
}
```

- [ ] **Step 2: Add route to App.tsx**

In `frontend/src/App.tsx`, add the import at the top with other lazy imports:

```typescript
import CapacityInsights from './modules/capacity/pages/Insights';
```

Add the route in both the bypass-auth and protected route blocks, after the tracker routes and before the admin/ISO routes:

```tsx
<Route path="/capacity/insights" element={<CapacityInsights />} />
```

- [ ] **Step 3: Add sidebar section**

In `frontend/src/core/components/layout/AppSidebar.tsx`:

Add `TrendingUp` to the lucide-react import:

```typescript
import {
  BarChart3,
  ClipboardList,
  FolderKanban,
  Shield,
  Globe,
  SlidersHorizontal,
  Plug,
  Bell,
  Clock,
  Cog,
  Users,
  Moon,
  Sun,
  ChevronRight,
  TrendingUp,
} from 'lucide-react';
```

Add the constant after `ISO_TABS`:

```typescript
const CAPACITY_TABS = [
  { to: '/capacity/insights', label: 'Insights' },
] as const;
```

In the `AppSidebar` function's JSX, add the Capacity collapsible item after the "My Report" `SidebarMenuItem` and before the admin-gated "Global Scores" block. The existing `isActive` fallback (`location.pathname.startsWith(path)`) already handles `/capacity` — no special case needed.

```tsx
              <CollapsibleMenuItem
                icon={TrendingUp}
                label="Capacity"
                isActive={isActive('/capacity')}
                items={CAPACITY_TABS}
              />
```

- [ ] **Step 4: Verify the app compiles**

Run: `pushd frontend > /dev/null && npx tsc --noEmit && popd > /dev/null`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/capacity/pages/Insights.tsx frontend/src/App.tsx frontend/src/core/components/layout/AppSidebar.tsx
git commit -m "feat(capacity): add Insights page, route, and sidebar section"
```

---

## Task 7: Backend — Run full test suite

- [ ] **Step 1: Run all backend tests**

Run: `pushd backend > /dev/null && python -m pytest --tb=short -q && popd > /dev/null`
Expected: All tests pass (existing + 9 new capacity tests)

- [ ] **Step 2: Fix any regressions if needed**

---

## Task 8: Frontend — Run full test suite

- [ ] **Step 1: Run all frontend tests**

Run: `pushd frontend > /dev/null && npx vitest run && popd > /dev/null`
Expected: All tests pass

- [ ] **Step 2: Fix any regressions if needed**
