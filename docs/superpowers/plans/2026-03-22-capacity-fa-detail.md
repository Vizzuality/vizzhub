# Capacity FA Detail Drill-Down Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-user drill-down chart below the existing Capacity Insights overview chart, showing individual user billable allocation for a selected functional area.

**Architecture:** New backend service function `get_capacity_fa_detail()` in the existing `capacity_insights.py` (cross-module analytical JOIN, Rule 4). New endpoint in `capacity/api/fa_detail.py`. Frontend adds `FADetailChart` component below `InsightsChart` on the same page, wired via URL state. Overview chart bars become clickable to set the FA and month.

**Tech Stack:** FastAPI, SQLAlchemy (async), React, TypeScript, Recharts, React Query, Tailwind CSS

---

### Task 1: Backend service — `get_capacity_fa_detail()`

**Files:**
- Modify: `backend/app/core/services/capacity_insights.py`
- Create: `backend/tests/modules/capacity/test_capacity_fa_detail.py`

**Context:** The existing `capacity_insights.py` has `TARGET_FA_MAPPING` (full name -> short code) and `get_capacity_insights()`. We add a reverse mapping and a new function that returns per-user data for a single FA. The existing test file `test_capacity_insights.py` has a `capacity_data` fixture creating 2 FAs (FE, BE), 3 users, 2 periods, and reports. Reuse it.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/modules/capacity/test_capacity_fa_detail.py`:

```python
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
    db_session.add_all([billable1, billable2, internal])
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

    # Alice: 40% billable1, 30% billable2, 30% internal = 70% billable, 2 billable projects
    report_alice = ReportDB(user_id=user1.id, reporting_period_id=period.id)
    db_session.add(report_alice)
    await db_session.flush()
    db_session.add_all([
        ReportPartDB(report_id=report_alice.id, project_id=billable1.id, percentage=Decimal("0.4000")),
        ReportPartDB(report_id=report_alice.id, project_id=billable2.id, percentage=Decimal("0.3000")),
        ReportPartDB(report_id=report_alice.id, project_id=internal.id, percentage=Decimal("0.3000")),
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
        "internal": internal, "user1": user1, "user2": user2, "period": period,
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

        # Add user with 0% total (on leave)
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

        # Add Feb period with no reports
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
        assert len(result[0]["users"]) == 2  # Jan has data
        assert len(result[1]["users"]) == 0  # Feb empty

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

        # User with no last name
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/capacity/test_capacity_fa_detail.py -v && popd`
Expected: FAIL — `get_capacity_fa_detail` does not exist yet.

- [ ] **Step 3: Implement `get_capacity_fa_detail()` and `SHORT_TO_FA_NAME`**

Add to `backend/app/core/services/capacity_insights.py` (after the existing `TARGET_FA_MAPPING`):

```python
SHORT_TO_FA_NAME: dict[str, str] = {v: k for k, v in TARGET_FA_MAPPING.items()}


def _format_user_name(first_name: str | None, last_name: str | None) -> str:
    """Format as 'F. Lastname' with fallbacks."""
    if first_name and last_name:
        return f"{first_name[0]}. {last_name}"
    if last_name:
        return last_name
    if first_name:
        return first_name
    return "Unknown"


async def get_capacity_fa_detail(
    db: AsyncSession,
    fa_short: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Per-user billable allocation for a single FA per period.

    Returns list of dicts sorted by period ascending, each containing
    'period' (YYYY-MM) and 'users' list with per-user breakdown.
    """
    fa_name = SHORT_TO_FA_NAME.get(fa_short)
    if not fa_name:
        return []

    fa_row = (await db.execute(
        select(FunctionalAreaDB.id)
        .where(FunctionalAreaDB.name == fa_name)
    )).scalar_one_or_none()

    if fa_row is None:
        logger.warning("Capacity FA detail: FA '%s' not found in database", fa_name)
        # Still return period shells with empty users
        periods_result = await db.execute(
            select(ReportingPeriodDB.id, ReportingPeriodDB.date)
            .where(
                ReportingPeriodDB.date >= start_date,
                ReportingPeriodDB.date <= end_date,
            )
            .order_by(ReportingPeriodDB.date)
        )
        return [
            {"period": p_date.strftime("%Y-%m"), "users": []}
            for _, p_date in periods_result
        ]

    fa_id = fa_row

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

    eligible_users = list(await db.execute(
        select(UserDB.id, UserDB.first_name, UserDB.last_name)
        .where(
            UserDB.active.is_(True),
            UserDB.requires_project_reporting.is_(True),
            UserDB.functional_area_id == fa_id,
        )
    ))

    if not eligible_users:
        return [
            {"period": p_date.strftime("%Y-%m"), "users": []}
            for _, p_date in periods
        ]

    user_ids = [uid for uid, _, _ in eligible_users]
    user_info = {uid: (fn, ln) for uid, fn, ln in eligible_users}

    period_ids = [p_id for p_id, _ in periods]

    # Per-user report aggregation
    report_subq = (
        select(
            ReportDB.user_id,
            ReportDB.reporting_period_id,
            func.coalesce(func.sum(ReportPartDB.percentage), 0).label("total_pct"),
            func.coalesce(func.sum(
                case(
                    (ProjectDB.is_billable.is_(True), ReportPartDB.percentage),
                    else_=0,
                )
            ), 0).label("billable_pct"),
            func.count(func.distinct(
                case(
                    (ProjectDB.is_billable.is_(True), ReportPartDB.project_id),
                    else_=None,
                )
            )).label("billable_project_count"),
        )
        .join(ReportPartDB, ReportPartDB.report_id == ReportDB.id)
        .join(ProjectDB, ProjectDB.id == ReportPartDB.project_id)
        .where(
            ReportPartDB.percentage.isnot(None),
            ReportDB.user_id.in_(user_ids),
            ReportDB.reporting_period_id.in_(period_ids),
        )
        .group_by(ReportDB.user_id, ReportDB.reporting_period_id)
        .subquery()
    )

    report_rows = await db.execute(
        select(
            report_subq.c.user_id,
            report_subq.c.reporting_period_id,
            report_subq.c.total_pct,
            report_subq.c.billable_pct,
            report_subq.c.billable_project_count,
        )
    )

    # (user_id, period_id) -> (total_pct, billable_pct, billable_project_count)
    report_lookup: dict[tuple, tuple[float, float, int]] = {}
    for uid, pid, total, billable, proj_count in report_rows:
        report_lookup[(uid, pid)] = (float(total), float(billable), int(proj_count))

    result = []
    for period_id, period_date in periods:
        users_list = []
        for uid in user_ids:
            entry = report_lookup.get((uid, period_id))
            if not entry or entry[0] <= 0:
                continue  # on leave or no report
            fn, ln = user_info[uid]
            users_list.append({
                "user_id": uid,
                "name": _format_user_name(fn, ln),
                "billable_pct": round(entry[1], 4),
                "billable_project_count": entry[2],
            })
        users_list.sort(key=lambda u: u["name"])
        result.append({
            "period": period_date.strftime("%Y-%m"),
            "users": users_list,
        })

    return result
```

Note: The `user_id` field is a UUID. The frontend type in Task 4 correctly uses `string` (not `number` as the spec originally had). UUIDs serialize as strings in JSON.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/capacity/test_capacity_fa_detail.py -v && popd`
Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/services/capacity_insights.py backend/tests/modules/capacity/test_capacity_fa_detail.py
git commit -m "feat(capacity): add per-user FA detail service with tests"
```

---

### Task 2: Backend endpoint and router

**Files:**
- Create: `backend/app/modules/capacity/api/_validation.py`
- Modify: `backend/app/modules/capacity/api/insights.py`
- Create: `backend/app/modules/capacity/api/fa_detail.py`
- Modify: `backend/app/modules/capacity/router.py`

**Context:** The existing `insights.py` endpoint uses `_parse_month()`, `_MONTH_RE`, `_MAX_RANGE_MONTHS`, `CurrentUser`, and `DBSession` from deps. To avoid duplicating date validation, first extract the shared helpers to a module-level utility, then create the new endpoint. Mount at prefix `/insights/detail` in router.py so the full path is `/api/capacity/insights/detail`.

- [ ] **Step 1: Extract shared date validation to `capacity/api/_validation.py`**

Create `backend/app/modules/capacity/api/_validation.py`:

```python
"""Shared validation helpers for capacity endpoints."""

import re
from datetime import date

from fastapi import HTTPException

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
MAX_RANGE_MONTHS = 24


def parse_month(value: str) -> date:
    """Parse YYYY-MM string to first-of-month date."""
    if not MONTH_RE.match(value):
        raise HTTPException(status_code=422, detail=f"Invalid date format: {value}")
    year, month = value.split("-")
    return date(int(year), int(month), 1)


def validate_date_range(start: date, end: date) -> None:
    """Validate start <= end and range <= MAX_RANGE_MONTHS."""
    if start > end:
        raise HTTPException(status_code=422, detail="start_date must be <= end_date")
    month_diff = (end.year - start.year) * 12 + (end.month - start.month)
    if month_diff >= MAX_RANGE_MONTHS:
        raise HTTPException(
            status_code=422,
            detail=f"Date range must not exceed {MAX_RANGE_MONTHS} months",
        )
```

- [ ] **Step 2: Refactor `insights.py` to use shared validation**

Update `backend/app/modules/capacity/api/insights.py` to import from `_validation`:

```python
"""Capacity insights endpoint."""

from fastapi import APIRouter, Query

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import get_capacity_insights
from app.modules.capacity.api._validation import parse_month, validate_date_range

router = APIRouter()


@router.get("")
async def capacity_insights(
    db: DBSession,
    user: CurrentUser,
    start_date: str = Query(..., description="Start month (YYYY-MM)"),
    end_date: str = Query(..., description="End month (YYYY-MM)"),
) -> list[dict]:
    start = parse_month(start_date)
    end = parse_month(end_date)
    validate_date_range(start, end)
    return await get_capacity_insights(db=db, start_date=start, end_date=end)
```

- [ ] **Step 3: Create the endpoint file**

Create `backend/app/modules/capacity/api/fa_detail.py`:

```python
"""Capacity FA detail drill-down endpoint."""

from fastapi import APIRouter, HTTPException, Query

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import SHORT_TO_FA_NAME, get_capacity_fa_detail
from app.modules.capacity.api._validation import parse_month, validate_date_range

router = APIRouter()

_VALID_FA_CODES = set(SHORT_TO_FA_NAME.keys())


@router.get("")
async def capacity_fa_detail(
    db: DBSession,
    user: CurrentUser,
    fa: str = Query(..., description="FA short code (FE, BE, Design, PM, Sci, Coms)"),
    start_date: str = Query(..., description="Start month (YYYY-MM)"),
    end_date: str = Query(..., description="End month (YYYY-MM)"),
) -> list[dict]:
    if fa not in _VALID_FA_CODES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid FA code: {fa}. Must be one of {sorted(_VALID_FA_CODES)}",
        )

    start = parse_month(start_date)
    end = parse_month(end_date)
    validate_date_range(start, end)
    return await get_capacity_fa_detail(db=db, fa_short=fa, start_date=start, end_date=end)
```

- [ ] **Step 2: Mount in router.py**

Update `backend/app/modules/capacity/router.py`:

```python
from fastapi import APIRouter

from app.modules.capacity.api import fa_detail as fa_detail_router
from app.modules.capacity.api import insights as insights_router

router = APIRouter()
router.include_router(
    insights_router.router, prefix="/insights", tags=["capacity:insights"]
)
router.include_router(
    fa_detail_router.router, prefix="/insights/detail", tags=["capacity:fa-detail"]
)
```

- [ ] **Step 4: Run endpoint tests**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/capacity/test_capacity_fa_detail.py::TestCapacityFADetailEndpoint -v && popd`
Expected: All 4 endpoint tests PASS.

- [ ] **Step 5: Run full capacity test suite (including existing overview tests)**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/capacity/ -v && popd`
Expected: All tests PASS (overview + detail). This verifies the `insights.py` refactor didn't break anything.

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/capacity/api/_validation.py backend/app/modules/capacity/api/insights.py backend/app/modules/capacity/api/fa_detail.py backend/app/modules/capacity/router.py
git commit -m "feat(capacity): add FA detail endpoint, extract shared date validation"
```

---

### Task 3: Fix MonthRangePicker duplicate ID issue

**Files:**
- Modify: `frontend/src/modules/capacity/components/MonthRangePicker.tsx`

**Context:** The current `MonthRangePicker` uses hardcoded `id="start-month"` and `id="end-month"`. Since both the overview and detail sections will render a `MonthRangePicker`, we need unique IDs. Add an optional `idPrefix` prop.

- [ ] **Step 1: Update MonthRangePicker**

Edit `frontend/src/modules/capacity/components/MonthRangePicker.tsx` to add `idPrefix` prop:

```typescript
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';

interface MonthRangePickerProps {
  readonly startDate: string;
  readonly endDate: string;
  readonly onChange: (start: string, end: string) => void;
  readonly idPrefix?: string;
}

export function MonthRangePicker({
  startDate,
  endDate,
  onChange,
  idPrefix = '',
}: MonthRangePickerProps): JSX.Element {
  const startId = `${idPrefix}start-month`;
  const endId = `${idPrefix}end-month`;

  return (
    <div className="flex items-end gap-4">
      <div className="space-y-1">
        <Label htmlFor={startId}>From</Label>
        <Input
          id={startId}
          type="month"
          value={startDate}
          onChange={(e) => onChange(e.target.value, endDate)}
          className="w-40"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={endId}>To</Label>
        <Input
          id={endId}
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
git commit -m "fix(capacity): add idPrefix to MonthRangePicker to avoid duplicate IDs"
```

---

### Task 4: Frontend types, API client, hook, and query key

**Files:**
- Modify: `frontend/src/modules/capacity/types/capacity.ts`
- Modify: `frontend/src/modules/capacity/services/capacity.ts`
- Create: `frontend/src/modules/capacity/hooks/useCapacityFADetail.ts`
- Modify: `frontend/src/core/hooks/queryKeys.ts`

**Context:** Follow existing patterns from the overview insight. The `user_id` is a UUID (string in JSON). Query key pattern: `capacity.faDetail(fa, startDate, endDate)`.

- [ ] **Step 1: Add types**

Append to `frontend/src/modules/capacity/types/capacity.ts`:

```typescript
export interface UserInsight {
  user_id: string;
  name: string;
  billable_pct: number;
  billable_project_count: number;
}

export interface PeriodUserInsight {
  period: string;
  users: UserInsight[];
}
```

- [ ] **Step 2: Add API method**

Add to `frontend/src/modules/capacity/services/capacity.ts`:

```typescript
import type { PeriodInsight, PeriodUserInsight } from '@/modules/capacity/types/capacity';

// ... existing getInsights ...

export const capacityApi = {
  getInsights: async (startDate: string, endDate: string): Promise<PeriodInsight[]> => {
    const response = await api.get<PeriodInsight[]>('/capacity/insights', {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  },
  getInsightsDetail: async (
    fa: string,
    startDate: string,
    endDate: string,
  ): Promise<PeriodUserInsight[]> => {
    const response = await api.get<PeriodUserInsight[]>('/capacity/insights/detail', {
      params: { fa, start_date: startDate, end_date: endDate },
    });
    return response.data;
  },
};
```

- [ ] **Step 3: Add query key**

Add `faDetail` to the `capacity` section in `frontend/src/core/hooks/queryKeys.ts`:

```typescript
  capacity: {
    insights: (startDate: string, endDate: string) =>
      ['capacity', 'insights', startDate, endDate] as const,
    faDetail: (fa: string, startDate: string, endDate: string) =>
      ['capacity', 'fa-detail', fa, startDate, endDate] as const,
  },
```

- [ ] **Step 4: Create hook**

Create `frontend/src/modules/capacity/hooks/useCapacityFADetail.ts`:

```typescript
import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { capacityApi } from '@/modules/capacity/services/capacity';
import type { PeriodUserInsight } from '@/modules/capacity/types/capacity';

export function useCapacityFADetail(
  fa: string,
  startDate: string,
  endDate: string,
): UseQueryResult<PeriodUserInsight[]> {
  return useQuery({
    queryKey: queryKeys.capacity.faDetail(fa, startDate, endDate),
    queryFn: () => capacityApi.getInsightsDetail(fa, startDate, endDate),
    enabled: !!fa && !!startDate && !!endDate,
  });
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/capacity/types/capacity.ts frontend/src/modules/capacity/services/capacity.ts frontend/src/core/hooks/queryKeys.ts frontend/src/modules/capacity/hooks/useCapacityFADetail.ts
git commit -m "feat(capacity): add FA detail types, API client, hook, and query key"
```

---

### Task 5: FADetailChart component

**Files:**
- Create: `frontend/src/modules/capacity/components/FADetailChart.tsx`

**Context:** Grouped vertical stacked bar chart using Recharts. Same visual pattern as `InsightsChart` but bars are per-user (not per-FA). Uses the FA's color from `FA_COLORS`. Shows `billable_project_count` as a number label on top. Hover shows user name. Has FA dropdown + MonthRangePicker controls.

The `FA_COLORS` and `FA_ORDER` constants are currently defined in `InsightsChart.tsx`. They'll be needed here too. Extract them to a shared location or re-declare. Since they're small, re-declaring is simpler and avoids touching the overview chart in this task.

- [ ] **Step 1: Create FADetailChart component**

Create `frontend/src/modules/capacity/components/FADetailChart.tsx`:

```typescript
import { useCallback, useMemo, useRef, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  CartesianGrid,
  LabelList,
} from 'recharts';
import type { PeriodUserInsight } from '@/modules/capacity/types/capacity';
import { MonthRangePicker } from '@/modules/capacity/components/MonthRangePicker';
import { shortMonth } from '@/shared/constants/dates';

const FA_COLORS: Record<string, string> = {
  FE: '#3b82f6',
  BE: '#10b981',
  Design: '#f59e0b',
  PM: '#8b5cf6',
  Sci: '#ef4444',
  Coms: '#06b6d4',
};

const FA_OPTIONS = ['FE', 'BE', 'Design', 'PM', 'Sci', 'Coms'] as const;

interface ChartDataPoint {
  month: string;
  [key: string]: number | string;
}

function transformDetailData(data: PeriodUserInsight[]): {
  chartData: ChartDataPoint[];
  userNames: string[];
} {
  const userNameSet = new Set<string>();
  for (const period of data) {
    for (const user of period.users) {
      userNameSet.add(user.name);
    }
  }
  const userNames = [...userNameSet].sort();

  const chartData = data.map((period) => {
    const point: ChartDataPoint = { month: shortMonth(`${period.period}-01`) };
    for (const user of period.users) {
      point[`${user.name}_projects`] = Math.round(user.billable_pct * 100);
      point[`${user.name}_others`] = Math.round((1 - user.billable_pct) * 100);
      point[`${user.name}_count`] = user.billable_project_count;
    }
    return point;
  });

  return { chartData, userNames };
}

interface FADetailChartProps {
  readonly data: PeriodUserInsight[];
  readonly fa: string;
  readonly onFAChange: (fa: string) => void;
  readonly startDate: string;
  readonly endDate: string;
  readonly onRangeChange: (start: string, end: string) => void;
}

export function FADetailChart({
  data,
  fa,
  onFAChange,
  startDate,
  endDate,
  onRangeChange,
}: FADetailChartProps): JSX.Element {
  const { chartData, userNames } = useMemo(() => transformDetailData(data), [data]);
  const [hoveredUser, setHoveredUser] = useState<string | null>(null);
  const handleLeave = useCallback(() => setHoveredUser(null), []);

  const color = FA_COLORS[fa] ?? '#6b7280';

  if (chartData.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Project time by user</h2>
          <div className="flex items-center gap-4">
            <select
              value={fa}
              onChange={(e) => onFAChange(e.target.value)}
              className="flex rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {FA_OPTIONS.map((code) => (
                <option key={code} value={code}>{code}</option>
              ))}
            </select>
            <MonthRangePicker
              startDate={startDate}
              endDate={endDate}
              onChange={onRangeChange}
              idPrefix="detail-"
            />
          </div>
        </div>
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          No data for the selected period
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Project time by user</h2>
        <div className="flex items-center gap-4">
          <select
            value={fa}
            onChange={(e) => onFAChange(e.target.value)}
            className="flex rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {FA_OPTIONS.map((code) => (
              <option key={code} value={code}>{code}</option>
            ))}
          </select>
          <MonthRangePicker
            startDate={startDate}
            endDate={endDate}
            onChange={onRangeChange}
            idPrefix="detail-"
          />
        </div>
      </div>

      <div className="relative cursor-pointer">
        {hoveredUser && (
          <div className="pointer-events-none absolute left-1/2 top-2 z-10 -translate-x-1/2 rounded bg-muted px-2 py-1 text-sm text-foreground">
            {hoveredUser}
          </div>
        )}

        <ResponsiveContainer width="100%" height={450}>
          <BarChart data={chartData} barCategoryGap="15%" barGap={1}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(v: number) => `${v}%`}
              tick={{ fontSize: 12 }}
            />
            {userNames.flatMap((name) => [
              <Bar
                key={`${name}_projects`}
                dataKey={`${name}_projects`}
                stackId={name}
                fill={color}
                fillOpacity={1}
                onMouseEnter={() => setHoveredUser(name)}
                onMouseLeave={handleLeave}
              />,
              <Bar
                key={`${name}_others`}
                dataKey={`${name}_others`}
                stackId={name}
                fill={color}
                fillOpacity={0.3}
                onMouseEnter={() => setHoveredUser(name)}
                onMouseLeave={handleLeave}
              >
                <LabelList
                  dataKey={`${name}_count`}
                  position="top"
                  style={{ fontSize: 10, fill: 'currentColor' }}
                />
              </Bar>,
            ])}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/capacity/components/FADetailChart.tsx
git commit -m "feat(capacity): add FADetailChart component"
```

---

### Task 6: Make overview chart bars clickable

**Files:**
- Modify: `frontend/src/modules/capacity/components/InsightsChart.tsx`

**Context:** The overview `InsightsChart` needs an `onBarClick` callback prop. `transformData` must preserve the original `YYYY-MM` period in each data point. The `<Bar>` `onClick` handler extracts the FA short code from the `dataKey` (e.g., `"FE_projects"` -> first segment before `_`) and the `period` from the data point.

Current `InsightsChart.tsx` structure:
- `transformData()` at line 33 converts `period.period` to `shortMonth(...)` as `month`. Need to also store original `period` string.
- `ChartDataPoint` interface at line 28 needs a `period` field.
- `Bar` components at line 106 have `onMouseEnter`/`onMouseLeave`. Add `onClick`.

- [ ] **Step 1: Update InsightsChart**

Modify `frontend/src/modules/capacity/components/InsightsChart.tsx`:

1. Add `onBarClick` to props interface:
```typescript
interface InsightsChartProps {
  readonly data: PeriodInsight[];
  readonly onBarClick?: (fa: string, period: string) => void;
}
```

2. Update `transformData` to preserve `period`:
```typescript
function transformData(data: PeriodInsight[]): ChartDataPoint[] {
  return data.map((period) => {
    const point: ChartDataPoint = {
      month: shortMonth(`${period.period}-01`),
      period: period.period,
    };
    for (const fa of period.functional_areas) {
      point[`${fa.short}_projects`] = Math.round(fa.billable_pct * 100);
      point[`${fa.short}_others`] = Math.round((1 - fa.billable_pct) * 100);
    }
    return point;
  });
}
```

3. Update the component to accept and use `onBarClick`:
```typescript
export function InsightsChart({ data, onBarClick }: InsightsChartProps): JSX.Element {
```

4. Add click handler that parses the FA from `dataKey` and reads `period` from the data point. Add to the `<Bar>` elements:
```typescript
onClick={(barData) => {
  if (onBarClick && barData?.payload?.period) {
    onBarClick(fa, String(barData.payload.period));
  }
}}
```

The full `Bar` rendering becomes:
```typescript
{BAR_TYPES.flatMap(({ suffix, opacity }) =>
  activeFAs.map((fa) => (
    <Bar
      key={`${fa}_${suffix}`}
      dataKey={`${fa}_${suffix}`}
      stackId={fa}
      fill={FA_COLORS[fa]}
      fillOpacity={opacity}
      onMouseEnter={() => setHoveredFA(fa)}
      onMouseLeave={handleLeave}
      onClick={(barData) => {
        if (onBarClick && barData?.payload?.period) {
          onBarClick(fa, String(barData.payload.period));
        }
      }}
    />
  )),
)}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/capacity/components/InsightsChart.tsx
git commit -m "feat(capacity): add onBarClick callback to InsightsChart"
```

---

### Task 7: Integrate detail chart into Insights page

**Files:**
- Modify: `frontend/src/modules/capacity/pages/Insights.tsx`

**Context:** The Insights page currently has `useUrlState` with `start` and `end`. We expand it with `fa`, `detail_start`, `detail_end`. Wire the overview `onBarClick` to update detail state and scroll. Render `FADetailChart` below.

Current `Insights.tsx` has `defaultRange()` computing `start` and `end` at module load time. Add `defaultDetailRange()` for the 3-month detail range.

- [ ] **Step 1: Update Insights page**

Rewrite `frontend/src/modules/capacity/pages/Insights.tsx`:

```typescript
import { useRef } from 'react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useCapacityInsights } from '@/modules/capacity/hooks/useCapacityInsights';
import { useCapacityFADetail } from '@/modules/capacity/hooks/useCapacityFADetail';
import { InsightsChart } from '@/modules/capacity/components/InsightsChart';
import { FADetailChart } from '@/modules/capacity/components/FADetailChart';
import { MonthRangePicker } from '@/modules/capacity/components/MonthRangePicker';

function defaultOverviewRange(): { start: string; end: string } {
  const now = new Date();
  const endDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const startDate = new Date(endDate.getFullYear(), endDate.getMonth() - 5, 1);
  const fmt = (d: Date): string =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  return { start: fmt(startDate), end: fmt(endDate) };
}

function defaultDetailRange(): { detail_start: string; detail_end: string } {
  const now = new Date();
  const endDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const startDate = new Date(endDate.getFullYear(), endDate.getMonth() - 2, 1);
  const fmt = (d: Date): string =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  return { detail_start: fmt(startDate), detail_end: fmt(endDate) };
}

const overviewDefaults = defaultOverviewRange();
const detailDefaults = defaultDetailRange();

export default function Insights(): JSX.Element {
  const { state, setState } = useUrlState({
    start: { defaultValue: overviewDefaults.start },
    end: { defaultValue: overviewDefaults.end },
    fa: { defaultValue: 'FE' },
    detail_start: { defaultValue: detailDefaults.detail_start },
    detail_end: { defaultValue: detailDefaults.detail_end },
  });

  const detailRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, error } = useCapacityInsights(state.start, state.end);
  const {
    data: detailData,
    isLoading: detailLoading,
    error: detailError,
  } = useCapacityFADetail(state.fa, state.detail_start, state.detail_end);

  const handleBarClick = (fa: string, period: string): void => {
    setState({ fa, detail_start: period, detail_end: period });
    detailRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Capacity Insights</h1>
        <MonthRangePicker
          startDate={state.start}
          endDate={state.end}
          onChange={(start, end) => setState({ start, end })}
          idPrefix="overview-"
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

      {data && <InsightsChart data={data} onBarClick={handleBarClick} />}

      <div ref={detailRef}>
        {detailLoading && (
          <div className="flex h-64 items-center justify-center text-muted-foreground">
            Loading...
          </div>
        )}

        {detailError && (
          <div className="flex h-64 items-center justify-center text-destructive">
            Failed to load detail data
          </div>
        )}

        {detailData && (
          <FADetailChart
            data={detailData}
            fa={state.fa}
            onFAChange={(fa) => setState({ fa })}
            startDate={state.detail_start}
            endDate={state.detail_end}
            onRangeChange={(detail_start, detail_end) =>
              setState({ detail_start, detail_end })
            }
          />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run frontend tests**

Run: `pushd frontend > /dev/null && npx vitest run --reporter=verbose && popd`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/capacity/pages/Insights.tsx
git commit -m "feat(capacity): integrate FA detail chart into Insights page"
```

---

### Task 8: Run full test suites and verify

**Files:** None (verification only)

- [ ] **Step 1: Run full backend tests**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/capacity/ -v && popd`
Expected: All capacity tests PASS.

- [ ] **Step 2: Run full frontend tests**

Run: `pushd frontend > /dev/null && npx vitest run --reporter=verbose && popd`
Expected: All tests PASS.

- [ ] **Step 3: Manual smoke test (optional)**

Start dev servers and verify:
1. Navigate to `/capacity/insights`
2. Overview chart loads as before
3. Detail chart loads below with FE selected and last 3 months
4. Click a bar on overview → detail updates FA and month, scrolls down
5. Change FA dropdown → detail chart updates
6. Change detail date range → detail chart updates
