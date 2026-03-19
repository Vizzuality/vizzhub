# Tracker Detail Enhancements — Design Spec

**Date:** 2026-03-19
**Status:** Approved
**Branch:** `feature/tracker-reports`

## Goal

Enhance the project tracker detail page with two new features:
1. A "Time per Functional Area" table showing days spent per area
2. Reports table grouped by period with merged column and period separators

## Context

The tracker detail page (`/tracker/projects/:projectId`) currently shows:
- 4 KPI cards (Budget, Burn to Date, Forecast Final, Variance)
- 4 charts (Cumulative Burn, Monthly Costs, Burn Trend, Cost Composition)
- A flat reports table with period filter

The legacy VizzTracker had richer detail views including time-per-area breakdowns and period-grouped reports. This spec adds those two features using a generic aggregation endpoint that supports future extensions.

## 1. Backend: Generic Aggregation Endpoint

### Endpoint

`GET /api/tracker/projects/{project_id}/aggregations?group_by=functional_area`

### Parameters

| Param | Type | Required | Values |
|-------|------|----------|--------|
| `group_by` | string (query) | yes | `functional_area`, `user` |

### Response Schema

```python
class AggregationPeriod(BaseModel):
    date: dt.date
    days: float
    cost: float

class AggregationRow(BaseModel):
    name: str              # functional area name or user name
    email: str | None      # only populated for group_by=user
    total_days: float
    total_cost: float
    periods: list[AggregationPeriod]

class AggregationResponse(BaseModel):
    group_by: str
    rows: list[AggregationRow]  # sorted by total_days desc
```

### Query Logic

- Source: `report_parts` joined to `reports` → `reporting_periods`, and to `functional_areas` or `users` depending on `group_by`
- **Must filter by `project_id`:** `.where(ReportPartDB.project_id == project_id)`
- Filters: `.where(ReportDB.estimated.is_(False))`, `.where(ReportPartDB.percentage.isnot(None))`, `.where(ReportPartDB.percentage > 0)` — same null-safe forms as existing aggregation queries
- Group by: name (+ email for users), then sub-group by period date
- Sort: rows by `total_days` descending, periods within each row by date ascending

### Service Location

New function `get_project_aggregations(db, project_id, group_by)` in existing `aggregation_service.py`.

### Files

- **Create:** `backend/app/modules/tracker/schemas/aggregation.py` — imported directly from router, no `__init__.py` change needed
- **Modify:** `backend/app/modules/tracker/services/aggregation_service.py`
- **Modify:** `backend/app/modules/tracker/api/project_costs.py`

### Note on `group_by=user`

The BE supports `group_by=user` from day one but there is no FE consumer yet. This is intentional — it enables the future "Days by People" chart (Phase 2.5 roadmap) without a new endpoint. BE tests cover both values.

## 2. Frontend: Time per Functional Area Table

### Component

`TimeByAreaTable` in `frontend/src/modules/tracker/components/`

### Data Source

New hook `useProjectAggregations(projectId, groupBy)` calling the endpoint above with `group_by=functional_area`.

**Query key:** `tracker.projectCosts.aggregations(projectId, groupBy)` — includes `groupBy` in the key to avoid cache collisions between `functional_area` and `user` queries.

### Behavior

- **Always shows all-time data** — the existing period filter does NOT apply to this table. It only affects the reports table below.
- **Loading state:** Added to the existing top-level loading guard (`summaryLoading || partsLoading || aggregationsLoading`)

### Layout

| Functional Area | Days in Contract | Spent | Remaining |
|---|---|---|---|
| Backend Developer | — | 130.07 | — |
| Frontend Developer | — | 99.79 | — |
| Project Manager | — | 81.76 | — |

- "Days in Contract" and "Remaining" columns show "—" placeholder until budget lines exist (Phase 3)
- Sorted by spent days descending (server-side)
- Footer row with totals for Spent column
- Positioned between BurnDashboard and the period filter/reports table

### Files

- **Create:** `frontend/src/modules/tracker/components/TimeByAreaTable.tsx`
- **Modify:** `frontend/src/modules/tracker/hooks/useProjectCosts.ts` — add `useProjectAggregations`
- **Modify:** `frontend/src/modules/tracker/services/tracker.ts` — add API call
- **Modify:** `frontend/src/modules/tracker/types/tracker.ts` — add types
- **Modify:** `frontend/src/core/hooks/queryKeys.ts` — add key under `tracker.projectCosts`

## 3. Frontend: Reports Table Grouped by Period

### Refactor

Pure FE change to existing `PartsTable` in `ProjectTrackerDetail.tsx`. No new data needed.

### Changes

- Group rows by `period_date`
- First row of each period group shows the period name in a merged cell (`rowSpan`)
- Subsequent rows in the same group leave the Period column empty
- Thick bottom border (`border-b-2`) between period groups, thin border within groups
- Column order unchanged: Period | Person | Role | % | Days | Cost
- Footer unchanged: Staff / Non-staff / Total subtotals
- **Grouping applies always**, even when a period filter is active (in that case there is just one group — this is fine and consistent)

### Files

- **Modify:** `frontend/src/modules/tracker/pages/ProjectTrackerDetail.tsx`

## 4. Page Layout

Order of sections in `ProjectTrackerDetail` (top to bottom):

1. Header (Back button + project name)
2. BurnDashboard — unchanged
3. **TimeByAreaTable** — new (always all-time, not affected by period filter)
4. Period filter dropdown
5. **PartsTable** — refactored with period grouping

## 5. Testing

- **BE:** Tests for `get_project_aggregations()` with both `group_by=functional_area` and `group_by=user` in `test_aggregation.py`
- **FE:** Update `ProjectTrackerDetail.test.tsx` to verify TimeByAreaTable renders

## Decisions

- **Generic endpoint over specific:** `group_by` parameter supports `functional_area` and `user`, enabling future "Days by People" chart without new endpoints
- **Merged column over header rows:** Period grouping uses rowspan in the Period column (option B) to maintain consistent column structure
- **Placeholder columns:** "Days in Contract" and "Remaining" included with "—" values, ready for Phase 3 budget lines
- **`group_by=user` BE-only for now:** Supported in backend and tested, but no FE consumer until "Days by People" feature
