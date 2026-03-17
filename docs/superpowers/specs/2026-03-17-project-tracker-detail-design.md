# Project Tracker Detail — Cost Aggregation & Validation

## Goal

New page at `/tracker/projects/:projectId` showing aggregated project costs (staff + non-staff) with budget comparison. This is the core validation step: confirm vizzhub cost calculations match legacy VizzTracker totals.

## Scope

- Non-staff costs CRUD endpoints
- Project cost summary aggregation endpoint
- Project report parts list endpoint (enriched, filterable by period)
- FE detail page with budget card + reports table
- Validation against legacy DB for multiple projects

## Out of Scope

- Burn chart (Phase 4)
- Time per functional area table (needs budget_lines — Phase 3)
- Progress reports / income tracking (Phase 4)
- Projected costs (estimated reports)

---

## Backend

### 1. Non-Staff Costs CRUD

**Endpoints:**
- `POST /api/tracker/non-staff-costs` — create
- `GET /api/tracker/non-staff-costs?project_id=X&reporting_period_id=Y` — list (project_id required, reporting_period_id optional)
- `GET /api/tracker/non-staff-costs/:id` — detail
- `PUT /api/tracker/non-staff-costs/:id` — update
- `DELETE /api/tracker/non-staff-costs/:id` — delete

**Schemas** (`schemas/non_staff_cost.py`):

```python
class NonStaffCostCreate(BaseModel):
    project_id: UUID
    reporting_period_id: UUID
    cost: Decimal  # >= 0
    cost_type: CostType  # outsource, travel, servers, others
    details: str | None = None

class NonStaffCostUpdate(BaseModel):
    cost: Decimal | None = None
    cost_type: CostType | None = None
    details: str | None = None

class NonStaffCostResponse(BaseModel):
    id: UUID
    project_id: UUID
    reporting_period_id: UUID
    cost: Decimal
    cost_type: CostType
    details: str | None
    created_at: datetime
    updated_at: datetime
```

**API file**: `api/non_staff_costs.py` — standard CRUD pattern matching existing report_parts.py.

**Router**: Add to `tracker/router.py`.

### 2. Project Cost Summary

**Endpoint**: `GET /api/tracker/projects/:projectId/cost-summary`

**API file**: `api/project_costs.py`

**Response schema** (`schemas/project_cost.py`):

```python
class PeriodCostBreakdown(BaseModel):
    period_id: UUID
    date: date
    staff_cost: float
    non_staff_cost: float
    total: float
    parts_count: int

class ProjectCostSummary(BaseModel):
    project_id: UUID
    budget: float | None      # from project_settings, None if no settings or no budget
    contract_rate: float      # from project_settings, falls back to DEFAULT_RATE if no settings
    staff_cost: float         # SUM(report_parts.cost) for this project
    non_staff_cost: float     # SUM(non_staff_costs.cost) for this project
    total_cost: float         # staff + non_staff
    burn_percentage: float | None  # total_cost / budget * 100, None if no budget
    periods: list[PeriodCostBreakdown]  # ordered by date desc
```

**When `TrackerProjectSettingsDB` doesn't exist** for a project: `contract_rate` falls back to `DEFAULT_RATE` (175.00), `budget` is `None`, `burn_percentage` is `None`.

**Service** (`services/aggregation_service.py`):

```python
async def get_project_cost_summary(db: AsyncSession, project_id: UUID) -> ProjectCostSummary:
    # 1. Get project_settings (budget, contract_rate) — fall back to DEFAULT_RATE if not found
    # 2. Staff costs: SUM(report_parts.cost), COUNT(*)
    #    JOIN reports ON report_parts.report_id = reports.id
    #    JOIN reporting_periods ON reports.reporting_period_id = reporting_periods.id
    #    WHERE report_parts.project_id = project_id
    #    AND reports.estimated = false
    #    GROUP BY reports.reporting_period_id, reporting_periods.date
    # 3. Non-staff costs: SUM(non_staff_costs.cost)
    #    JOIN reporting_periods ON non_staff_costs.reporting_period_id = reporting_periods.id
    #    WHERE non_staff_costs.project_id = project_id
    #    GROUP BY non_staff_costs.reporting_period_id, reporting_periods.date
    # 4. Merge period breakdowns (union of period IDs from both queries), compute totals
    # 5. Return ProjectCostSummary
```

Key: exclude estimated reports from staff cost (matches legacy `total_burn` default behavior).

### 3. Project Report Parts List

**Endpoint**: `GET /api/tracker/projects/:projectId/report-parts?period_id=Y`

**API file**: same `api/project_costs.py`

**Response schema**:

```python
class ProjectReportPartResponse(BaseModel):
    id: UUID
    period_date: date
    user_name: str | None
    user_email: str | None
    functional_area: str | None  # JOIN functional_areas to get name
    percentage: float
    days: float | None
    cost: float | None
    estimated: bool  # from parent report
```

**Query**: JOIN report_parts → reports → reporting_periods, JOIN auth_users for name/email, LEFT JOIN functional_areas for area name. Optional filter by period_id. Order by period date DESC, user name ASC.

---

## Frontend

### Route

`/tracker/projects/:projectId` — inside TrackerLayout, accessible from project list.

### Navigation

Add "Tracker" link to project rows in the projects list (or to the project detail page). Exact placement TBD during implementation — follow existing link patterns.

### Page: `ProjectTrackerDetail.tsx`

**Layout:**

```
[Back to projects]     Project Name     [status badge]

┌─────────────────────────────────────────────────┐
│ Budget        Cost to Date     Burn %            │
│ €436,103.00   €437,823.30      100.39%           │
│                                [colored bar]     │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Reports                          [period filter] │
│                                                  │
│ Period  | User  | Func. Area | %  | Days | Cost  │
│ Mar 26  | Alice | Developer  | 10 | 2.0  | 1843  │
│ Mar 26  | Bob   | PM         | 5  | 1.0  | 921   │
│ Feb 26  | Alice | Developer  | 10 | 2.0  | 1843  │
│ ...                                              │
│                                                  │
│ Staff total: €430,000.00                         │
│ Non-staff total: €7,823.30                       │
│ Total: €437,823.30                               │
└─────────────────────────────────────────────────┘
```

**Components:**
- Budget summary card — uses `useProjectCostSummary(projectId)` hook
- Reports table — uses `useProjectReportParts(projectId, periodFilter)` hook
- Period filter — dropdown from the periods in the summary response
- Burn bar: green < 80%, yellow 80-100%, red > 100%

### Types (`types/tracker.ts` — extend)

Add `ProjectCostSummary`, `PeriodCostBreakdown`, `ProjectReportPartResponse`, `NonStaffCost` interfaces.

### Services (`services/tracker.ts` — extend)

Add: `getProjectCostSummary(projectId)`, `getProjectReportParts(projectId, periodId?)`, non-staff costs CRUD methods.

### Hooks

- `useProjectCostSummary(projectId)` — React Query
- `useProjectReportParts(projectId, periodId?)` — React Query
- Non-staff cost mutations (create, update, delete)

---

## Testing

### BE Tests

- `test_non_staff_costs.py` — CRUD tests (create, list with filters, update, delete)
- `test_aggregation.py` — cost summary with:
  - Project with staff costs only
  - Project with staff + non-staff costs
  - Project with no budget (burn_percentage = None)
  - Estimated reports excluded from totals
  - Multiple periods aggregated correctly

### FE Tests

- `ProjectTrackerDetail.test.tsx` — MSW integration tests:
  - Renders budget card with summary data
  - Renders reports table
  - Period filter works
  - Handles project with no data

### Legacy Validation

Manual checkpoint: compare `total_cost` from `/api/tracker/projects/:id/cost-summary` against legacy VizzTracker for 2-3 known projects with imported data.

---

## Dependencies

- Phase 1 complete (report_parts with cost/days exist)
- Imported data in dev DB (legacy data already imported)
- `NonStaffCostDB` model already exists
- `TrackerProjectSettingsDB` model already exists (budget, contract_rate fields)
