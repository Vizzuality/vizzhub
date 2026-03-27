# Capacity Insights: Separate Vacation/Absence from Others

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `is_absence` flag to projects and render vacation/absence as a visually distinct segment in capacity insight charts, separate from generic "others".

**Architecture:** Add `is_absence` boolean to `ProjectDB`. Backend capacity queries return `absence_pct` alongside `billable_pct`. Frontend charts render three stacked segments per bar: billable (full opacity), absence (0.5 opacity), others (0.3 opacity). Frontend derives `others = 1 - billable - absence`.

**Tech Stack:** SQLAlchemy + Alembic (migration), FastAPI (backend), React + Recharts (frontend), pytest + vitest (tests)

---

### Task 1: Add `is_absence` column to projects

**Files:**
- Modify: `backend/app/core/models/project.py:73` (after `is_billable`)
- Modify: `backend/app/core/models/project.py:107` (ProjectBase schema)
- Modify: `backend/app/core/models/project.py:169` (ProjectUpdate schema)
- Create: `backend/alembic/versions/033_add_is_absence_to_projects.py`

- [ ] **Step 1: Write migration test (run existing tests first to confirm green)**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/core/test_projects.py -x -q 2>&1 | tail -5 && popd > /dev/null`
Expected: all tests pass

- [ ] **Step 2: Create alembic migration**

```python
"""Add is_absence to projects."""

from alembic import op
import sqlalchemy as sa

revision = "033_add_is_absence"
down_revision = "032_add_mood_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("is_absence", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_check_constraint(
        "ck_projects_not_billable_and_absence",
        "projects",
        "NOT (is_billable AND is_absence)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_projects_not_billable_and_absence", "projects")
    op.drop_column("projects", "is_absence")
```

- [ ] **Step 3: Add `is_absence` to ProjectDB model with check constraint**

In `backend/app/core/models/project.py`, add the check constraint to `__table_args__` and the column:

Add to `__table_args__` tuple (before the closing `)`):
```python
CheckConstraint(
    "NOT (is_billable AND is_absence)",
    name="ck_projects_not_billable_and_absence",
),
```

After line 73 (`is_billable`), add:
```python
is_absence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

- [ ] **Step 4: Add `is_absence` to Pydantic schemas**

In `ProjectBase` (line ~107), after `is_billable: bool = True`:
```python
is_absence: bool = False
```

In `ProjectUpdate` (line ~169), after `is_billable: bool | None = None`:
```python
is_absence: bool | None = None
```

- [ ] **Step 5: Run migration and verify**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && alembic upgrade head && popd > /dev/null`
Expected: migration applies cleanly

- [ ] **Step 6: Run existing project tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/core/test_projects.py -x -q 2>&1 | tail -5 && popd > /dev/null`
Expected: all pass (new column has default, no breaking changes)

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/033_add_is_absence_to_projects.py backend/app/core/models/project.py
git commit -m "feat: add is_absence flag to projects model"
```

---

### Task 2: Update `get_capacity_insights` to return `absence_pct`

**Files:**
- Modify: `backend/app/core/services/capacity_insights.py:311-379` (`report_subq`, `_aggregate_fa_period`)
- Test: `backend/tests/modules/capacity/test_capacity_insights.py`

- [ ] **Step 1: Write failing test — absence separated from others**

In `test_capacity_insights.py`, add an absence project to the `capacity_data` fixture and a new test:

Update `capacity_data` fixture — after the `internal_project` creation (line ~39), add:

```python
absence_project = ProjectDB(name="Vacation / Absence", status="live", is_billable=False, is_absence=True)
db_session.add(absence_project)
```

Update `flush` to include it, then add absence report parts. For `fe1` in Jan: change from 60% billable + 40% internal to 60% billable + 20% internal + 20% absence. Update the existing `ReportPartDB` entries for `fe1_jan`:

```python
# fe1: 60% billable, 20% internal, 20% absence in Jan
ReportPartDB(report_id=report_fe1_jan.id, project_id=billable_project.id, percentage=Decimal("0.6000")),
ReportPartDB(report_id=report_fe1_jan.id, project_id=internal_project.id, percentage=Decimal("0.2000")),
ReportPartDB(report_id=report_fe1_jan.id, project_id=absence_project.id, percentage=Decimal("0.2000")),
```

Keep `fe2` as 80% billable + 20% internal (no absence). Keep `be1` as 100% billable.

Add `"absence_project": absence_project` to the return dict.

Then add a new test:

```python
@pytest.mark.asyncio
async def test_absence_pct_separated_from_others(
    self, db_session: AsyncSession, capacity_data: dict,
):
    from app.core.services.capacity_insights import get_capacity_insights

    result = await get_capacity_insights(
        db=db_session,
        start_date=dt.date(2026, 1, 1),
        end_date=dt.date(2026, 1, 1),
    )
    fa_map = {fa["short"]: fa for fa in result[0]["functional_areas"]}
    # FE: fe1 has 0.2 absence, fe2 has 0 absence → avg 0.1
    assert fa_map["FE"]["absence_pct"] == pytest.approx(0.1, abs=0.01)
    # BE: no absence
    assert fa_map["BE"]["absence_pct"] == pytest.approx(0.0, abs=0.01)
```

Also update `test_billable_pct_averaged_across_users` assertions — billable stays the same (fe1=0.6, fe2=0.8, avg=0.7) since we only changed internal→internal+absence split.

- [ ] **Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/capacity/test_capacity_insights.py::TestGetCapacityInsights::test_absence_pct_separated_from_others -xvs 2>&1 | tail -20 && popd > /dev/null`
Expected: FAIL — `absence_pct` key missing from response dict

- [ ] **Step 3: Implement absence tracking in `get_capacity_insights`**

In `capacity_insights.py`, update the `report_subq` (around line 311) to add an `absence_pct` column:

```python
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
        func.coalesce(func.sum(
            case(
                (ProjectDB.is_absence.is_(True), ReportPartDB.percentage),
                else_=0,
            )
        ), 0).label("absence_pct"),
    )
    .join(ReportPartDB, ReportPartDB.report_id == ReportDB.id)
    .join(ProjectDB, ProjectDB.id == ReportPartDB.project_id)
    .where(ReportPartDB.percentage.isnot(None))
    .group_by(ReportDB.user_id, ReportDB.reporting_period_id)
    .subquery()
)
```

Update the `report_rows` select (around line 331) to also fetch `absence_pct`:

```python
report_rows = await db.execute(
    select(
        report_subq.c.user_id,
        report_subq.c.reporting_period_id,
        report_subq.c.total_pct,
        report_subq.c.billable_pct,
        report_subq.c.absence_pct,
    ).where(report_subq.c.reporting_period_id.in_(period_ids))
)
```

Update `report_lookup` type to `dict[tuple, tuple[float, float, float]]` and unpacking:

```python
report_lookup: dict[tuple, tuple[float, float, float]] = {}
for user_id, period_id, total, billable, absence in report_rows:
    report_lookup[(user_id, period_id)] = (float(total), float(billable), float(absence))
```

Update `_aggregate_fa_period` to compute and return `absence_pct`:

```python
def _aggregate_fa_period(
    users_by_fa: dict[str, list],
    report_lookup: dict[tuple, tuple[float, float, float]],
    period_id: object,
) -> list[dict]:
    """Aggregate billable and absence % per FA for a single period."""
    fas = []
    for short, user_ids in sorted(users_by_fa.items()):
        if not user_ids:
            continue
        active_data = [
            (report_lookup[(uid, period_id)][1], report_lookup[(uid, period_id)][2])
            for uid in user_ids
            if (uid, period_id) in report_lookup and report_lookup[(uid, period_id)][0] > 0
        ]
        if not active_data:
            continue
        avg_billable = sum(b for b, _ in active_data) / len(active_data)
        avg_absence = sum(a for _, a in active_data) / len(active_data)
        fas.append({
            "short": short,
            "billable_pct": round(avg_billable, 4),
            "absence_pct": round(avg_absence, 4),
            "user_count": len(active_data),
        })
    return fas
```

- [ ] **Step 4: Run all capacity insights tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/capacity/test_capacity_insights.py -xvs 2>&1 | tail -30 && popd > /dev/null`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/services/capacity_insights.py backend/tests/modules/capacity/test_capacity_insights.py
git commit -m "feat: return absence_pct in capacity overview insights"
```

---

### Task 3: Update `get_capacity_fa_detail` to return `absence_pct`

**Files:**
- Modify: `backend/app/core/services/capacity_insights.py:64-165` (`get_capacity_fa_detail`)
- Test: `backend/tests/modules/capacity/test_capacity_fa_detail.py`

- [ ] **Step 1: Write failing test**

Update `fa_detail_data` fixture in `test_capacity_fa_detail.py` — add an absence project:

```python
absence = ProjectDB(name="Vacation / Absence", status="live", is_billable=False, is_absence=True)
db_session.add(absence)
```

Add it to flush. Update Alice's report to include absence: change from 40%+30%+30% (billable1+billable2+internal) to 40%+30%+10%+20% (billable1+billable2+internal+absence):

```python
ReportPartDB(report_id=report_alice.id, project_id=billable1.id, percentage=Decimal("0.4000")),
ReportPartDB(report_id=report_alice.id, project_id=billable2.id, percentage=Decimal("0.3000")),
ReportPartDB(report_id=report_alice.id, project_id=internal.id, percentage=Decimal("0.1000")),
ReportPartDB(report_id=report_alice.id, project_id=absence.id, percentage=Decimal("0.2000")),
```

Add `"absence": absence` to the return dict.

Add new test:

```python
@pytest.mark.asyncio
async def test_returns_absence_pct_per_user(
    self, db_session: AsyncSession, fa_detail_data: dict,
):
    from app.core.services.capacity_insights import get_capacity_fa_detail

    result = await get_capacity_fa_detail(
        db=db_session, fa_short="FE",
        start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 1),
    )
    users = {u["name"]: u for u in result[0]["users"]}
    # Alice: 20% absence
    assert users["A. Smith"]["absence_pct"] == pytest.approx(0.2, abs=0.01)
    # Bob: 0% absence (100% internal)
    assert users["B. Jones"]["absence_pct"] == pytest.approx(0.0, abs=0.01)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/capacity/test_capacity_fa_detail.py::TestGetCapacityFADetail::test_returns_absence_pct_per_user -xvs 2>&1 | tail -20 && popd > /dev/null`
Expected: FAIL — `absence_pct` key missing

- [ ] **Step 3: Implement absence tracking in `get_capacity_fa_detail`**

In `capacity_insights.py`, update `get_capacity_fa_detail`'s report query (around line 113) to add `absence_pct`:

```python
report_rows = await db.execute(
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
        func.coalesce(func.sum(
            case(
                (ProjectDB.is_absence.is_(True), ReportPartDB.percentage),
                else_=0,
            )
        ), 0).label("absence_pct"),
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
)
```

Update `report_lookup` type to include absence:

```python
report_lookup: dict[tuple, tuple[float, float, float, int]] = {}
for uid, pid, total, billable, absence, proj_count in report_rows:
    report_lookup[(uid, pid)] = (float(total), float(billable), float(absence), int(proj_count))
```

Update the user dict builder (around line 153) to include `absence_pct`:

```python
users_list.append({
    "user_id": uid,
    "name": _format_user_name(fn, ln, full, em),
    "billable_pct": round(entry[1], 4),
    "absence_pct": round(entry[2], 4),
    "billable_project_count": entry[3],
})
```

- [ ] **Step 4: Run all FA detail tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/capacity/test_capacity_fa_detail.py -xvs 2>&1 | tail -30 && popd > /dev/null`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/services/capacity_insights.py backend/tests/modules/capacity/test_capacity_fa_detail.py
git commit -m "feat: return absence_pct in capacity FA detail"
```

---

### Task 4: Update `get_capacity_user_detail` to return `absence_pct`

**Files:**
- Modify: `backend/app/core/services/capacity_insights.py:187-256` (`get_capacity_user_detail`)
- Test: `backend/tests/modules/capacity/test_capacity_user_detail.py`

- [ ] **Step 1: Write failing test**

Update `user_detail_data` fixture in `test_capacity_user_detail.py` — add absence project:

```python
absence = ProjectDB(name="Vacation / Absence", status="live", is_billable=False, is_absence=True)
db_session.add(absence)
```

Update Alice's report: change from 40%+30%+30% to 40%+30%+10%+20% (billable1+billable2+internal+absence):

```python
ReportPartDB(report_id=report.id, project_id=billable1.id, percentage=Decimal("0.4000")),
ReportPartDB(report_id=report.id, project_id=billable2.id, percentage=Decimal("0.3000")),
ReportPartDB(report_id=report.id, project_id=internal.id, percentage=Decimal("0.1000")),
ReportPartDB(report_id=report.id, project_id=absence.id, percentage=Decimal("0.2000")),
```

Add `"absence": absence` to the return dict.

Add new test:

```python
@pytest.mark.asyncio
async def test_returns_absence_pct_per_period(
    self, db_session: AsyncSession, user_detail_data: dict,
):
    from app.core.services.capacity_insights import get_capacity_user_detail

    user = user_detail_data["user"]
    result = await get_capacity_user_detail(
        db=db_session, user_id=str(user.id),
        start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 1),
    )
    period = result[0]
    assert period["absence_pct"] == pytest.approx(0.2, abs=0.01)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/capacity/test_capacity_user_detail.py::TestGetCapacityUserDetail::test_returns_absence_pct_per_period -xvs 2>&1 | tail -20 && popd > /dev/null`
Expected: FAIL — `absence_pct` key missing

- [ ] **Step 3: Implement absence tracking in `get_capacity_user_detail`**

In `capacity_insights.py`, update `get_capacity_user_detail`'s report query (around line 215) to also fetch `is_absence`:

```python
report_rows = await db.execute(
    select(
        ReportDB.reporting_period_id,
        ProjectDB.id,
        ProjectDB.name,
        ProjectDB.is_billable,
        ProjectDB.is_absence,
        ReportPartDB.percentage,
    )
    .join(ReportPartDB, ReportPartDB.report_id == ReportDB.id)
    .join(ProjectDB, ProjectDB.id == ReportPartDB.project_id)
    .where(
        ReportPartDB.percentage.isnot(None),
        ReportDB.user_id == uid,
        ReportDB.reporting_period_id.in_(period_ids),
    )
)
```

Update the unpacking and period_projects dict:

```python
period_projects: dict[object, list[tuple]] = {}
for pid, proj_id, proj_name, is_billable, is_absence, pct in report_rows:
    period_projects.setdefault(pid, []).append(
        (str(proj_id), proj_name, bool(is_billable), bool(is_absence), float(pct))
    )
```

Update the result builder to compute `absence_pct` per period:

```python
result = []
for period_id, period_date in periods:
    entries = period_projects.get(period_id, [])
    projects = []
    absence_pct = 0.0
    for proj_id, proj_name, is_billable, is_absence, pct in entries:
        if is_absence:
            absence_pct += pct
        elif is_billable and pct > 0:
            projects.append({
                "project_id": proj_id,
                "name": proj_name,
                "percentage": round(pct, 4),
            })
    projects.sort(key=lambda p: p["name"])
    result.append({
        "period": period_date.strftime("%Y-%m"),
        "projects": projects,
        "absence_pct": round(absence_pct, 4),
    })
```

- [ ] **Step 4: Run all user detail tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/capacity/test_capacity_user_detail.py -xvs 2>&1 | tail -30 && popd > /dev/null`
Expected: all pass

- [ ] **Step 5: Run all capacity tests together**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/capacity/ -x -q 2>&1 | tail -10 && popd > /dev/null`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/services/capacity_insights.py backend/tests/modules/capacity/test_capacity_user_detail.py
git commit -m "feat: return absence_pct in capacity user detail"
```

---

### Task 5: Update frontend types and constants

**Files:**
- Modify: `frontend/src/modules/capacity/types/capacity.ts`
- Modify: `frontend/src/modules/capacity/utils/constants.ts`

- [ ] **Step 1: Add `absence_pct` to frontend types**

In `capacity.ts`:

Add `absence_pct` to `FunctionalAreaInsight`:
```typescript
export interface FunctionalAreaInsight {
  short: string;
  billable_pct: number;
  absence_pct: number;
  user_count: number;
}
```

Add `absence_pct` to `UserInsight`:
```typescript
export interface UserInsight {
  user_id: string;
  name: string;
  billable_pct: number;
  absence_pct: number;
  billable_project_count: number;
}
```

Add `absence_pct` to `PeriodProjectInsight`:
```typescript
export interface PeriodProjectInsight {
  period: string;
  projects: ProjectInsight[];
  absence_pct: number;
}
```

- [ ] **Step 2: Add absence color constant**

In `constants.ts`, add:

```typescript
export const ABSENCE_COLOR = '#94a3b8';  // slate-400, neutral grey distinct from others
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/capacity/types/capacity.ts frontend/src/modules/capacity/utils/constants.ts
git commit -m "feat: add absence_pct to capacity types and constants"
```

---

### Task 6: Update InsightsChart to render absence segment

**Files:**
- Modify: `frontend/src/modules/capacity/components/InsightsChart.tsx`

- [ ] **Step 1: Update transformData and replace BAR_TYPES with explicit Bar rendering**

Import `ABSENCE_COLOR` at the top of the file:
```typescript
import { FA_COLORS, FA_ORDER, ABSENCE_COLOR } from '@/modules/capacity/utils/constants';
```

Remove the `BAR_TYPES` constant entirely.

Update `transformData` to compute absence and adjust others:

```typescript
function transformData(data: PeriodInsight[]): ChartDataPoint[] {
  return data.map((period) => {
    const point: ChartDataPoint = {
      month: shortMonth(`${period.period}-01`),
      period: period.period,
    };
    for (const fa of period.functional_areas) {
      point[`${fa.short}_projects`] = Math.round(fa.billable_pct * 100);
      point[`${fa.short}_absence`] = Math.round(fa.absence_pct * 100);
      point[`${fa.short}_others`] = Math.max(0, Math.round((1 - fa.billable_pct - fa.absence_pct) * 100));
    }
    return point;
  });
}
```

Replace the `BAR_TYPES.flatMap` JSX block (around line 101) with explicit per-FA bars. This is needed because absence uses `ABSENCE_COLOR` (neutral grey) instead of the FA color:

```tsx
{activeFAs.flatMap((fa) => [
  <Bar
    key={`${fa}_projects`}
    dataKey={`${fa}_projects`}
    stackId={fa}
    fill={FA_COLORS[fa]}
    fillOpacity={1}
    onMouseEnter={() => setHoveredFA(fa)}
    onMouseLeave={handleLeave}
    onClick={(barData) => {
      if (onBarClick && barData?.payload?.period) {
        onBarClick(fa, String(barData.payload.period));
      }
    }}
  />,
  <Bar
    key={`${fa}_absence`}
    dataKey={`${fa}_absence`}
    stackId={fa}
    fill={ABSENCE_COLOR}
    fillOpacity={0.6}
    onMouseEnter={() => setHoveredFA(fa)}
    onMouseLeave={handleLeave}
    onClick={(barData) => {
      if (onBarClick && barData?.payload?.period) {
        onBarClick(fa, String(barData.payload.period));
      }
    }}
  />,
  <Bar
    key={`${fa}_others`}
    dataKey={`${fa}_others`}
    stackId={fa}
    fill={FA_COLORS[fa]}
    fillOpacity={0.3}
    onMouseEnter={() => setHoveredFA(fa)}
    onMouseLeave={handleLeave}
    onClick={(barData) => {
      if (onBarClick && barData?.payload?.period) {
        onBarClick(fa, String(barData.payload.period));
      }
    }}
  />,
])}
```

- [ ] **Step 2: Add absence legend item**

Add a legend entry after the FA legends (after the `activeFAs.map` block, around line 82):

```tsx
<div className="flex items-center gap-1.5 ml-4 text-muted-foreground">
  <span
    className="inline-block h-3 w-3 rounded-sm"
    style={{ backgroundColor: ABSENCE_COLOR, opacity: 0.6 }}
  />
  <span>Absence</span>
</div>
```

- [ ] **Step 3: Run frontend type check**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npx tsc --noEmit 2>&1 | tail -10 && popd > /dev/null`
Expected: no TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/capacity/components/InsightsChart.tsx
git commit -m "feat: render absence segment in capacity overview chart"
```

---

### Task 7: Update FADetailChart to render absence segment

**Files:**
- Modify: `frontend/src/modules/capacity/components/FADetailChart.tsx`

- [ ] **Step 1: Update transformDetailData**

Update `transformDetailData` to add absence data points:

```typescript
for (const user of period.users) {
  point[`${user.name}_projects`] = Math.round(user.billable_pct * 100);
  point[`${user.name}_absence`] = Math.round(user.absence_pct * 100);
  point[`${user.name}_others`] = Math.max(0, Math.round((1 - user.billable_pct - user.absence_pct) * 100));
  point[`${user.name}_count`] = user.billable_project_count;
}
```

- [ ] **Step 2: Add absence Bar between projects and others**

In the `userNames.flatMap` block (around line 177), add an absence `<Bar>` between the `_projects` bar and the `_others` bar:

```tsx
<Bar
  key={`${name}_absence`}
  dataKey={`${name}_absence`}
  stackId={name}
  fill={ABSENCE_COLOR}
  fillOpacity={0.6}
  onMouseEnter={() => setHoveredUser(name)}
  onMouseLeave={handleLeave}
  onClick={() => {
    if (onUserClick && userIdByName[name]) {
      onUserClick(userIdByName[name]);
    }
  }}
/>,
```

Import `ABSENCE_COLOR` from constants at the top of the file.

- [ ] **Step 3: Add absence to legend**

Add a legend item after the user-color legends (after the `userNames.map` block, around line 157):

```tsx
<div className="flex items-center gap-1.5 text-muted-foreground">
  <span
    className="inline-block h-3 w-3 rounded-sm"
    style={{ backgroundColor: ABSENCE_COLOR, opacity: 0.6 }}
  />
  <span>Absence</span>
</div>
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npx tsc --noEmit 2>&1 | tail -10 && popd > /dev/null`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/capacity/components/FADetailChart.tsx
git commit -m "feat: render absence segment in capacity FA detail chart"
```

---

### Task 8: Update UserDetailChart to render absence segment

**Files:**
- Modify: `frontend/src/modules/capacity/components/UserDetailChart.tsx`

- [ ] **Step 1: Update transformUserDetailData**

Add `ABSENCE_KEY` constant next to `OTHERS_KEY`:

```typescript
const ABSENCE_KEY = '_absence';
const ABSENCE_LABEL = 'Absence';
```

Update the data transform to compute absence and adjust others:

```typescript
const chartData = data.map((period) => {
  const point: ChartDataPoint = { month: shortMonth(`${period.period}-01`) };
  let billableTotal = 0;
  for (const project of period.projects) {
    const pct = Math.round(project.percentage * 100);
    point[project.name] = pct;
    billableTotal += pct;
  }
  const absencePct = Math.round(period.absence_pct * 100);
  point[ABSENCE_KEY] = absencePct;
  point[OTHERS_KEY] = Math.max(0, 100 - billableTotal - absencePct);
  return point;
});
```

- [ ] **Step 2: Add absence Bar and legend**

In the JSX, add the absence `<Bar>` between the project bars and the others bar (around line 236):

```tsx
<Bar
  dataKey={ABSENCE_KEY}
  stackId="user"
  fill={ABSENCE_COLOR}
  fillOpacity={0.6}
  onMouseEnter={() => setHoveredProject(ABSENCE_LABEL)}
  onMouseLeave={handleLeave}
/>
```

Import `ABSENCE_COLOR` from constants.

Update the legend section (around line 199) to add absence before others:

```tsx
<div className="flex items-center gap-1.5">
  <span
    className="inline-block h-3 w-3 rounded-sm"
    style={{ backgroundColor: ABSENCE_COLOR, opacity: 0.6 }}
  />
  <span>{ABSENCE_LABEL}</span>
</div>
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npx tsc --noEmit 2>&1 | tail -10 && popd > /dev/null`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/capacity/components/UserDetailChart.tsx
git commit -m "feat: render absence segment in capacity user detail chart"
```

---

### Task 9: Mark existing "Vacation / Absence" project with `is_absence=true`

**Files:**
- Create: `backend/alembic/versions/033b_mark_absence_project.py`

- [ ] **Step 1: Create data migration**

```python
"""Mark Vacation / Absence project with is_absence flag."""

from alembic import op

revision = "033b_mark_absence_proj"
down_revision = "033_add_is_absence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE projects SET is_absence = true WHERE name = 'Vacation / Absence'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE projects SET is_absence = false WHERE name = 'Vacation / Absence'"
    )
```

- [ ] **Step 2: Run migration**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && alembic upgrade head && popd > /dev/null`
Expected: applies cleanly

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/033b_mark_absence_project.py
git commit -m "data: mark Vacation / Absence project with is_absence flag"
```

---

### Task 10: Final verification

- [ ] **Step 1: Run all backend tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/capacity/ -x -q 2>&1 | tail -10 && popd > /dev/null`
Expected: all pass

- [ ] **Step 2: Run full backend test suite**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest -x -q 2>&1 | tail -10 && popd > /dev/null`
Expected: all pass (no regressions from `is_absence` default)

- [ ] **Step 3: Run frontend type check**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npx tsc --noEmit 2>&1 | tail -10 && popd > /dev/null`
Expected: no errors

- [ ] **Step 4: Run frontend tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npm test -- --run 2>&1 | tail -10 && popd > /dev/null`
Expected: all pass
