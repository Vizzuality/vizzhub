# Capacity Allocation Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/capacity/allocation` page showing a ranked list of users by average billable project count (last 3 finished periods), with segmented horizontal bars.

**Architecture:** New backend endpoint in capacity module (`GET /api/capacity/allocation/users`) with analytical query in `core/services/capacity_insights.py`. Frontend page with list component, client-side pagination (10 at a time), and global project color assignment via `ITEM_PALETTE`.

**Tech Stack:** FastAPI, SQLAlchemy async, React, TypeScript, Recharts (not used for this component — pure CSS bars), React Query, shadcn/ui.

**Spec:** `docs/superpowers/specs/2026-03-27-capacity-allocation-design.md`

---

### Task 1: Backend — Analytical Service Function

**Files:**
- Modify: `backend/app/core/services/capacity_insights.py`
- Create: `backend/tests/modules/capacity/test_allocation_users.py`

- [ ] **Step 1: Write the test fixture**

In `backend/tests/modules/capacity/test_allocation_users.py`:

```python
"""Tests for capacity allocation users endpoint."""

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
    """3 finished periods, 2 users, multiple projects."""
    fa = FunctionalAreaDB(name="Frontend Developer")
    db_session.add(fa)
    await db_session.flush()

    proj_a = ProjectDB(name="Alpha", status="live", is_billable=True)
    proj_b = ProjectDB(name="Beta", status="live", is_billable=True)
    proj_internal = ProjectDB(name="Internal", status="live", is_billable=False)
    proj_absence = ProjectDB(
        name="Vacation", status="live", is_billable=False, is_absence=True,
    )
    db_session.add_all([proj_a, proj_b, proj_internal, proj_absence])
    await db_session.flush()

    user1 = UserDB(
        email="alice@test.com", first_name="Alice", last_name="Smith",
        functional_area_id=fa.id, active=True, requires_project_reporting=True,
    )
    user2 = UserDB(
        email="bob@test.com", first_name="Bob", last_name="Jones",
        functional_area_id=fa.id, active=True, requires_project_reporting=True,
    )
    user_inactive = UserDB(
        email="gone@test.com", first_name="Gone", last_name="User",
        functional_area_id=fa.id, active=False, requires_project_reporting=True,
    )
    user_exempt = UserDB(
        email="exempt@test.com", first_name="No", last_name="Report",
        functional_area_id=fa.id, active=True, requires_project_reporting=False,
    )
    db_session.add_all([user1, user2, user_inactive, user_exempt])
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
    p_active = ReportingPeriodDB(
        date=dt.date(2026, 4, 1), base_rate=Decimal("175"), status="active",
    )
    db_session.add_all([p1, p2, p3, p_active])
    await db_session.flush()

    # user1: Alpha 50%, Internal 30%, Absence 20% in all 3 periods
    # user1: Beta 20% in p2 and p3 only (Alpha drops to 30% those months)
    for period in [p1, p2, p3]:
        report = ReportDB(user_id=user1.id, reporting_period_id=period.id)
        db_session.add(report)
        await db_session.flush()

        alpha_pct = Decimal("0.50") if period == p1 else Decimal("0.30")
        parts = [
            ReportPartDB(
                report_id=report.id, project_id=proj_a.id,
                percentage=alpha_pct, functional_area_id=fa.id,
            ),
            ReportPartDB(
                report_id=report.id, project_id=proj_internal.id,
                percentage=Decimal("0.30"), functional_area_id=fa.id,
            ),
            ReportPartDB(
                report_id=report.id, project_id=proj_absence.id,
                percentage=Decimal("0.20"), functional_area_id=fa.id,
            ),
        ]
        if period != p1:
            parts.append(ReportPartDB(
                report_id=report.id, project_id=proj_b.id,
                percentage=Decimal("0.20"), functional_area_id=fa.id,
            ))
        db_session.add_all(parts)
        await db_session.flush()

    # user2: Alpha 80%, Internal 20% in p1 only (no reports in p2, p3)
    report_u2 = ReportDB(user_id=user2.id, reporting_period_id=p1.id)
    db_session.add(report_u2)
    await db_session.flush()
    db_session.add_all([
        ReportPartDB(
            report_id=report_u2.id, project_id=proj_a.id,
            percentage=Decimal("0.80"), functional_area_id=fa.id,
        ),
        ReportPartDB(
            report_id=report_u2.id, project_id=proj_internal.id,
            percentage=Decimal("0.20"), functional_area_id=fa.id,
        ),
    ])
    await db_session.flush()

    await db_session.commit()

    return {
        "user1": user1, "user2": user2,
        "proj_a": proj_a, "proj_b": proj_b,
        "proj_internal": proj_internal, "proj_absence": proj_absence,
        "periods": [p1, p2, p3], "active_period": p_active,
    }
```

- [ ] **Step 2: Write the failing tests**

Append to the same file:

```python
@pytest.mark.asyncio
async def test_allocation_users_returns_ranked_list(
    client: AsyncClient, allocation_data: dict,
) -> None:
    """Users ranked desc by avg billable projects, correct segments."""
    resp = await client.get("/api/capacity/allocation/users")
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["periods_used"]) == 3
    assert body["periods_used"] == ["2026-03", "2026-02", "2026-01"]

    users = body["users"]
    # user1 has reports in all 3 periods (avg ~1.67 billable proj)
    # user2 has report in 1 period (avg ~0.33 billable proj)
    assert len(users) == 2
    assert users[0]["name"] == "Alice Smith"
    assert users[0]["avg_billable_projects"] == pytest.approx(1.67, abs=0.01)
    assert users[0]["total_distinct_projects"] == 2

    assert users[1]["name"] == "Bob Jones"
    assert users[1]["avg_billable_projects"] == pytest.approx(0.33, abs=0.01)
    assert users[1]["total_distinct_projects"] == 1


@pytest.mark.asyncio
async def test_allocation_users_segments(
    client: AsyncClient, allocation_data: dict,
) -> None:
    """Segments have correct avg_percentage (averaged over ALL periods)."""
    resp = await client.get("/api/capacity/allocation/users")
    user1 = resp.json()["users"][0]
    segments = user1["segments"]

    # Billable segments first, then absence, then other
    billable_segs = [s for s in segments if s["type"] == "billable"]
    absence_segs = [s for s in segments if s["type"] == "absence"]
    other_segs = [s for s in segments if s["type"] == "other"]

    # Alpha: (0.50 + 0.30 + 0.30) / 3 = 0.3667
    alpha = next(s for s in billable_segs if s["project_name"] == "Alpha")
    assert alpha["avg_percentage"] == pytest.approx(0.3667, abs=0.01)
    assert len(alpha["months_active"]) == 3

    # Beta: (0 + 0.20 + 0.20) / 3 = 0.1333
    beta = next(s for s in billable_segs if s["project_name"] == "Beta")
    assert beta["avg_percentage"] == pytest.approx(0.1333, abs=0.01)
    assert len(beta["months_active"]) == 2

    # Absence: (0.20 + 0.20 + 0.20) / 3 = 0.20
    assert len(absence_segs) == 1
    assert absence_segs[0]["avg_percentage"] == pytest.approx(0.20, abs=0.01)

    # Other: (0.30 + 0.30 + 0.30) / 3 = 0.30
    assert len(other_segs) == 1
    assert other_segs[0]["avg_percentage"] == pytest.approx(0.30, abs=0.01)


@pytest.mark.asyncio
async def test_allocation_users_excludes_inactive_and_exempt(
    client: AsyncClient, allocation_data: dict,
) -> None:
    """Inactive users and users without requires_project_reporting are excluded."""
    resp = await client.get("/api/capacity/allocation/users")
    names = [u["name"] for u in resp.json()["users"]]
    assert "Gone User" not in names
    assert "No Report" not in names


@pytest.mark.asyncio
async def test_allocation_users_excludes_active_periods(
    client: AsyncClient, allocation_data: dict,
) -> None:
    """Only finished periods are used, not active ones."""
    resp = await client.get("/api/capacity/allocation/users")
    assert "2026-04" not in resp.json()["periods_used"]


@pytest.mark.asyncio
async def test_allocation_users_empty_when_no_finished_periods(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Returns empty when no finished periods exist."""
    resp = await client.get("/api/capacity/allocation/users")
    assert resp.status_code == 200
    body = resp.json()
    assert body["periods_used"] == []
    assert body["users"] == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/modules/capacity/test_allocation_users.py -v`
Expected: FAIL (404 — endpoint doesn't exist yet)

- [ ] **Step 4: Implement `get_allocation_users` in capacity_insights.py**

Add to `backend/app/core/services/capacity_insights.py`:

```python
def _format_full_name(
    first_name: str | None,
    last_name: str | None,
    full_name: str | None = None,
    email: str | None = None,
) -> str:
    """Format as 'Firstname Lastname' with fallbacks."""
    if first_name and last_name:
        return f"{first_name} {last_name}"
    if first_name:
        return first_name
    if last_name:
        return last_name
    if full_name:
        return full_name
    if email:
        return email.split("@")[0]
    return "Unknown"


async def get_allocation_users(db: AsyncSession) -> dict:
    """User allocation ranked by avg billable project count.

    Uses last 3 finished reporting periods. Returns full user list
    sorted descending by avg_billable_projects.
    """
    # 1. Find last 3 finished periods
    periods_result = await db.execute(
        select(ReportingPeriodDB.id, ReportingPeriodDB.date)
        .where(ReportingPeriodDB.status == "finished")
        .order_by(ReportingPeriodDB.date.desc())
        .limit(3)
    )
    periods = list(periods_result)
    if not periods:
        return {"periods_used": [], "users": []}

    period_ids = [p_id for p_id, _ in periods]
    period_dates = {p_id: p_date for p_id, p_date in periods}
    num_periods = len(periods)

    # 2. Find eligible users
    eligible_result = await db.execute(
        select(
            UserDB.id, UserDB.first_name, UserDB.last_name,
            UserDB.name, UserDB.email,
        )
        .where(
            UserDB.active.is_(True),
            UserDB.requires_project_reporting.is_(True),
        )
    )
    eligible_users = list(eligible_result)
    if not eligible_users:
        return {
            "periods_used": [
                p_date.strftime("%Y-%m") for _, p_date in periods
            ],
            "users": [],
        }

    user_ids = [uid for uid, _, _, _, _ in eligible_users]
    user_info = {
        uid: (fn, ln, full, em)
        for uid, fn, ln, full, em in eligible_users
    }

    # 3. Query all report parts for these users in these periods
    rows = await db.execute(
        select(
            ReportDB.user_id,
            ReportDB.reporting_period_id,
            ReportPartDB.project_id,
            ProjectDB.name.label("project_name"),
            ProjectDB.is_billable,
            ProjectDB.is_absence,
            ReportPartDB.percentage,
        )
        .join(ReportPartDB, ReportPartDB.report_id == ReportDB.id)
        .join(ProjectDB, ProjectDB.id == ReportPartDB.project_id)
        .where(
            ReportPartDB.percentage.isnot(None),
            ReportDB.user_id.in_(user_ids),
            ReportDB.reporting_period_id.in_(period_ids),
        )
    )

    # 4. Build per-user, per-project aggregation
    # {user_id: {project_id: {"name", "is_billable", "is_absence", "pct_sum", "period_ids"}}}
    user_projects: dict[object, dict[object, dict]] = {}
    # {user_id: {period_id: set(billable_project_ids)}}
    user_period_billable: dict[object, dict[object, set]] = {}

    for uid, pid, proj_id, proj_name, is_billable, is_absence, pct in rows:
        up = user_projects.setdefault(uid, {})
        proj_entry = up.setdefault(proj_id, {
            "name": proj_name,
            "is_billable": bool(is_billable),
            "is_absence": bool(is_absence),
            "pct_sum": 0.0,
            "period_ids": set(),
        })
        proj_entry["pct_sum"] += float(pct)
        proj_entry["period_ids"].add(pid)

        if is_billable:
            upb = user_period_billable.setdefault(uid, {})
            upb.setdefault(pid, set()).add(proj_id)

    # 5. Build response
    users_out = []
    for uid in user_ids:
        projects = user_projects.get(uid)
        if not projects:
            continue

        fn, ln, full, em = user_info[uid]

        # avg billable projects per period (count over ALL periods, not just active)
        billable_counts = user_period_billable.get(uid, {})
        total_billable_per_period = sum(
            len(projs) for projs in billable_counts.values()
        )
        avg_billable = round(total_billable_per_period / num_periods, 2)

        # total distinct billable projects
        all_billable_proj_ids: set = set()
        for projs in billable_counts.values():
            all_billable_proj_ids.update(projs)
        total_distinct = len(all_billable_proj_ids)

        # Build segments
        segments = []
        for proj_id, info in projects.items():
            avg_pct = round(info["pct_sum"] / num_periods, 4)
            months = sorted(
                [period_dates[pid].strftime("%Y-%m") for pid in info["period_ids"]],
                reverse=True,
            )
            seg_type = (
                "billable" if info["is_billable"]
                else "absence" if info["is_absence"]
                else "other"
            )
            segments.append({
                "project_id": str(proj_id),
                "project_name": info["name"],
                "avg_percentage": avg_pct,
                "months_active": months,
                "type": seg_type,
            })

        # Sort: billable desc by avg_pct, then absence, then other
        type_order = {"billable": 0, "absence": 1, "other": 2}
        segments.sort(
            key=lambda s: (type_order[s["type"]], -s["avg_percentage"]),
        )

        users_out.append({
            "user_id": str(uid),
            "name": _format_full_name(fn, ln, full, em),
            "avg_billable_projects": avg_billable,
            "total_distinct_projects": total_distinct,
            "segments": segments,
        })

    users_out.sort(key=lambda u: (-u["avg_billable_projects"], u["name"]))

    return {
        "periods_used": [
            p_date.strftime("%Y-%m") for _, p_date in periods
        ],
        "users": users_out,
    }
```

- [ ] **Step 5: Run tests to verify they still fail**

Run: `cd backend && python -m pytest tests/modules/capacity/test_allocation_users.py -v`
Expected: FAIL (404 — endpoint not mounted yet)

- [ ] **Step 6: Commit service function**

```bash
git add backend/app/core/services/capacity_insights.py backend/tests/modules/capacity/test_allocation_users.py
git commit -m "feat(capacity): add get_allocation_users service + tests"
```

---

### Task 2: Backend — API Endpoint & Router

**Files:**
- Create: `backend/app/modules/capacity/api/allocation.py`
- Modify: `backend/app/modules/capacity/router.py`

- [ ] **Step 1: Create the endpoint**

Create `backend/app/modules/capacity/api/allocation.py`:

```python
"""Capacity allocation endpoints."""

from fastapi import APIRouter

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import get_allocation_users

router = APIRouter()


@router.get("/users")
async def allocation_users(
    db: DBSession,
    user: CurrentUser,
) -> dict:
    return await get_allocation_users(db=db)
```

- [ ] **Step 2: Mount in capacity router**

In `backend/app/modules/capacity/router.py`, add import and mount:

```python
from app.modules.capacity.api import allocation as allocation_router

# Add after existing includes:
router.include_router(
    allocation_router.router, prefix="/allocation", tags=["capacity:allocation"]
)
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/modules/capacity/test_allocation_users.py -v`
Expected: ALL PASS

- [ ] **Step 4: Run full capacity test suite for regressions**

Run: `cd backend && python -m pytest tests/modules/capacity/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/capacity/api/allocation.py backend/app/modules/capacity/router.py
git commit -m "feat(capacity): add allocation users endpoint"
```

---

### Task 3: Frontend — Types & Service

**Files:**
- Create: `frontend/src/modules/capacity/types/allocation.ts`
- Modify: `frontend/src/modules/capacity/services/capacity.ts`
- Modify: `frontend/src/core/hooks/queryKeys.ts`

- [ ] **Step 1: Create types**

Create `frontend/src/modules/capacity/types/allocation.ts`:

```typescript
export interface AllocationSegment {
  project_id: string;
  project_name: string;
  avg_percentage: number;
  months_active: string[];
  type: 'billable' | 'absence' | 'other';
}

export interface UserAllocation {
  user_id: string;
  name: string;
  avg_billable_projects: number;
  total_distinct_projects: number;
  segments: AllocationSegment[];
}

export interface AllocationUsersResponse {
  periods_used: string[];
  users: UserAllocation[];
}
```

- [ ] **Step 2: Add service function**

In `frontend/src/modules/capacity/services/capacity.ts`, add import and function:

```typescript
// Add to imports:
import type { AllocationUsersResponse } from '@/modules/capacity/types/allocation';

// Add to capacityApi object:
  getAllocationUsers: async (): Promise<AllocationUsersResponse> => {
    const response = await api.get<AllocationUsersResponse>('/capacity/allocation/users');
    return response.data;
  },
```

- [ ] **Step 3: Add query key**

In `frontend/src/core/hooks/queryKeys.ts`, add to the `capacity` section:

```typescript
    allocationUsers: ['capacity', 'allocation-users'] as const,
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/capacity/types/allocation.ts frontend/src/modules/capacity/services/capacity.ts frontend/src/core/hooks/queryKeys.ts
git commit -m "feat(capacity): add allocation types, service, and query keys"
```

---

### Task 4: Frontend — Hook

**Files:**
- Create: `frontend/src/modules/capacity/hooks/useAllocationUsers.ts`

- [ ] **Step 1: Create the hook**

Create `frontend/src/modules/capacity/hooks/useAllocationUsers.ts`:

```typescript
import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { capacityApi } from '@/modules/capacity/services/capacity';
import type { AllocationUsersResponse } from '@/modules/capacity/types/allocation';

export function useAllocationUsers(): UseQueryResult<AllocationUsersResponse> {
  return useQuery({
    queryKey: queryKeys.capacity.allocationUsers,
    queryFn: () => capacityApi.getAllocationUsers(),
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/capacity/hooks/useAllocationUsers.ts
git commit -m "feat(capacity): add useAllocationUsers hook"
```

---

### Task 5: Frontend — UserAllocationList Component

**Files:**
- Create: `frontend/src/modules/capacity/components/UserAllocationList.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/modules/capacity/components/UserAllocationList.tsx`:

```tsx
import { useMemo, useState } from 'react';
import { ITEM_PALETTE } from '@/modules/capacity/utils/constants';
import type { AllocationSegment, UserAllocation } from '@/modules/capacity/types/allocation';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';

const PAGE_SIZE = 10;

function buildColorMap(users: UserAllocation[]): Map<string, string> {
  const projectIds = new Set<string>();
  for (const user of users) {
    for (const seg of user.segments) {
      projectIds.add(seg.project_id);
    }
  }
  const map = new Map<string, string>();
  let i = 0;
  for (const id of projectIds) {
    map.set(id, ITEM_PALETTE[i % ITEM_PALETTE.length]);
    i++;
  }
  return map;
}

function formatMonths(months: string[]): string {
  return months
    .map((m) => {
      const [year, month] = m.split('-');
      const date = new Date(Number(year), Number(month) - 1);
      return date.toLocaleDateString('en', { month: 'short', year: 'numeric' });
    })
    .join(', ');
}

function opacityForType(type: AllocationSegment['type']): number {
  if (type === 'billable') return 1.0;
  if (type === 'absence') return 0.5;
  return 0.3;
}

interface SegmentBarProps {
  readonly segments: AllocationSegment[];
  readonly colorMap: Map<string, string>;
}

function SegmentBar({ segments, colorMap }: SegmentBarProps): JSX.Element {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-5 w-full overflow-hidden rounded bg-muted/30">
        {segments.map((seg) => {
          const widthPct = seg.avg_percentage * 100;
          if (widthPct < 0.5) return null;
          const color = colorMap.get(seg.project_id) ?? '#6b7280';

          return (
            <Tooltip key={seg.project_id}>
              <TooltipTrigger asChild>
                <div
                  className="h-full min-w-[2px] cursor-default"
                  style={{
                    width: `${widthPct}%`,
                    backgroundColor: color,
                    opacity: opacityForType(seg.type),
                  }}
                />
              </TooltipTrigger>
              <TooltipContent>
                <p className="font-medium">{seg.project_name}</p>
                <p className="text-muted-foreground text-xs">
                  {Math.round(seg.avg_percentage * 100)}%
                </p>
                <p className="text-muted-foreground text-xs">
                  {formatMonths(seg.months_active)}
                </p>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}

interface UserAllocationListProps {
  readonly users: UserAllocation[];
}

export function UserAllocationList({ users }: UserAllocationListProps): JSX.Element {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const colorMap = useMemo(() => buildColorMap(users), [users]);
  const visibleUsers = users.slice(0, visibleCount);
  const hasMore = visibleCount < users.length;

  return (
    <div className="space-y-3">
      {visibleUsers.map((user) => (
        <div key={user.user_id} className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{user.name}</span>
            <span className="text-muted-foreground text-xs">
              avg {user.avg_billable_projects} projects &middot;{' '}
              {user.total_distinct_projects} total
            </span>
          </div>
          <SegmentBar segments={user.segments} colorMap={colorMap} />
        </div>
      ))}

      {hasMore && (
        <button
          type="button"
          onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
          className="text-muted-foreground hover:text-foreground text-sm underline"
        >
          Show more ({users.length - visibleCount} remaining)
        </button>
      )}

      {users.length === 0 && (
        <p className="text-muted-foreground text-sm">No allocation data available.</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/capacity/components/UserAllocationList.tsx
git commit -m "feat(capacity): add UserAllocationList component"
```

---

### Task 6: Frontend — Allocation Page & Routing

**Files:**
- Create: `frontend/src/modules/capacity/pages/Allocation.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/core/components/layout/AppSidebar.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/src/modules/capacity/pages/Allocation.tsx`:

```tsx
import { useAllocationUsers } from '@/modules/capacity/hooks/useAllocationUsers';
import { UserAllocationList } from '@/modules/capacity/components/UserAllocationList';

function formatPeriodsHeader(periods: string[]): string {
  if (periods.length === 0) return '';
  let lastYear = '';
  const parts: string[] = [];
  for (const p of periods) {
    const [year, month] = p.split('-');
    const date = new Date(Number(year), Number(month) - 1);
    const monthName = date.toLocaleDateString('en', { month: 'short' });
    if (year !== lastYear) {
      parts.push(`${monthName} ${year}`);
      lastYear = year;
    } else {
      parts.push(monthName);
    }
  }
  return `Based on ${parts.join(', ')}`;
}

export default function Allocation(): JSX.Element {
  const { data, isLoading, error } = useAllocationUsers();

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Team Allocation</h1>
        {data && data.periods_used.length > 0 && (
          <span className="text-muted-foreground text-sm">
            {formatPeriodsHeader(data.periods_used)}
          </span>
        )}
      </div>

      {isLoading && (
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          Loading...
        </div>
      )}

      {error && (
        <div className="flex h-64 items-center justify-center text-destructive">
          Failed to load allocation data
        </div>
      )}

      {data && <UserAllocationList users={data.users} />}
    </div>
  );
}
```

- [ ] **Step 2: Add route in App.tsx**

In `frontend/src/App.tsx`:

1. Add import at the top (near the CapacityInsights import):
```typescript
import CapacityAllocation from './modules/capacity/pages/Allocation';
```

2. Add route after each `<Route path="/capacity/insights" ...>` line (there are two — one for regular users, one for admin):
```tsx
<Route path="/capacity/allocation" element={<CapacityAllocation />} />
```

- [ ] **Step 3: Add sidebar item**

In `frontend/src/core/components/layout/AppSidebar.tsx`, update `CAPACITY_TABS`:

```typescript
const CAPACITY_TABS = [
  { to: '/capacity/insights', label: 'Insights' },
  { to: '/capacity/allocation', label: 'Allocation' },
] as const;
```

- [ ] **Step 4: Run frontend dev server and verify manually**

Run: `cd frontend && npm run dev`
Verify:
- Sidebar shows "Allocation" under Capacity
- `/capacity/allocation` loads without errors
- Data displays if finished periods exist

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/capacity/pages/Allocation.tsx frontend/src/App.tsx frontend/src/core/components/layout/AppSidebar.tsx
git commit -m "feat(capacity): add allocation page with routing and sidebar"
```

---

### Task 7: Frontend — Tests

**Files:**
- Create: `frontend/src/modules/capacity/components/__tests__/UserAllocationList.test.tsx`

- [ ] **Step 1: Write component tests**

Create `frontend/src/modules/capacity/components/__tests__/UserAllocationList.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { UserAllocationList } from '@/modules/capacity/components/UserAllocationList';
import type { UserAllocation } from '@/modules/capacity/types/allocation';

const MOCK_USERS: UserAllocation[] = [
  {
    user_id: '1',
    name: 'Alice Smith',
    avg_billable_projects: 2.33,
    total_distinct_projects: 4,
    segments: [
      {
        project_id: 'p1',
        project_name: 'Alpha',
        avg_percentage: 0.4,
        months_active: ['2026-03', '2026-02', '2026-01'],
        type: 'billable',
      },
      {
        project_id: 'p2',
        project_name: 'Beta',
        avg_percentage: 0.2,
        months_active: ['2026-03', '2026-02'],
        type: 'billable',
      },
      {
        project_id: 'p3',
        project_name: 'Vacation',
        avg_percentage: 0.1,
        months_active: ['2026-01'],
        type: 'absence',
      },
      {
        project_id: 'p4',
        project_name: 'Internal',
        avg_percentage: 0.3,
        months_active: ['2026-03', '2026-02', '2026-01'],
        type: 'other',
      },
    ],
  },
];

function generateUsers(count: number): UserAllocation[] {
  return Array.from({ length: count }, (_, i) => ({
    user_id: `u${i}`,
    name: `User ${i}`,
    avg_billable_projects: count - i,
    total_distinct_projects: count - i,
    segments: [
      {
        project_id: 'p1',
        project_name: 'Project',
        avg_percentage: 0.5,
        months_active: ['2026-01'],
        type: 'billable' as const,
      },
    ],
  }));
}

describe('UserAllocationList', () => {
  it('renders user name and stats', () => {
    render(<UserAllocationList users={MOCK_USERS} />);
    expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    expect(screen.getByText(/avg 2.33 projects/)).toBeInTheDocument();
    expect(screen.getByText(/4 total/)).toBeInTheDocument();
  });

  it('shows empty message when no users', () => {
    render(<UserAllocationList users={[]} />);
    expect(screen.getByText('No allocation data available.')).toBeInTheDocument();
  });

  it('paginates at 10 users with show more button', () => {
    const users = generateUsers(25);
    render(<UserAllocationList users={users} />);

    expect(screen.getAllByText(/^User \d+$/)).toHaveLength(10);
    const showMore = screen.getByText(/Show more/);
    expect(showMore).toHaveTextContent('15 remaining');

    fireEvent.click(showMore);
    expect(screen.getAllByText(/^User \d+$/)).toHaveLength(20);

    fireEvent.click(screen.getByText(/Show more/));
    expect(screen.getAllByText(/^User \d+$/)).toHaveLength(25);
    expect(screen.queryByText(/Show more/)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests**

Run: `cd frontend && npx vitest run src/modules/capacity/__tests__/Allocation.test.tsx`
Expected: ALL PASS

- [ ] **Step 3: Run full frontend test suite for regressions**

Run: `cd frontend && npm test`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/capacity/components/__tests__/UserAllocationList.test.tsx
git commit -m "test(capacity): add allocation component tests"
```

---

### Task 8: Final Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && python -m pytest tests/modules/capacity/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run full frontend test suite**

Run: `cd frontend && npm test`
Expected: ALL PASS

- [ ] **Step 3: Manual smoke test**

Run both servers and verify:
1. Sidebar shows Allocation under Capacity
2. Page loads with header and period info
3. Users ranked correctly
4. Bars show colored segments with correct opacity
5. Tooltips show project name, %, and months
6. "Show more" button works
7. Same project has same color across different users
