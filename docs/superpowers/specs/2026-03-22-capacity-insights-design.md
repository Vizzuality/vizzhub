# Capacity Insights - Design Spec

## Overview

New "Capacity" section in the sidebar with an "Insights" page showing billable allocation by functional area over time. A grouped vertical stacked bar chart displays how much of each FA's reported time goes to billable projects ("Projects") vs non-billable ("Others").

## Navigation

- New collapsible "Capacity" section in the sidebar, positioned between main navigation and admin section.
- Uses existing `CollapsibleMenuItem` pattern (same as ISO, Notifications, Tracker).
- First sub-item: **Insights** at `/capacity/insights`.
- Visible to **all authenticated users** (no permission gating).
- Icon: `TrendingUp` from lucide-react.

## Page: Capacity Insights (`/capacity/insights`)

### Controls

- Two month/year pickers: **Start** and **End**.
- Default range: last 6 months from current month.
- URL state managed via `useUrlState` (params: `start`, `end` in `YYYY-MM` format).

### Chart: Billable Allocation by Functional Area

**Type**: Grouped vertical stacked bar chart (Recharts `BarChart`).

**Axes**:
- X-axis: months (e.g. "Oct 25", "Nov 25", ...).
- Y-axis: 0-100%.

**Bars**: 6 bars per month, one per functional area:
- FE (Frontend Developer)
- BE (Backend Developer)
- Design (Designer)
- PM (Project Manager)
- Sci (Scientist)
- Coms (Communications)

**Stacking**: Each bar has two segments:
- **Projects** (bottom): average billable % across users in that FA for that month.
- **Others** (top): `1.0 - billable_pct`, filling to 100%.

**Colors**: Each FA gets a distinct color. "Others" rendered as the same color at reduced opacity (e.g. 30%) to visually separate while keeping FA identity.

**Legend**: Shows FA abbreviations with color swatches + Projects/Others distinction.

## Data Flow

### Backend

**New endpoint**: `GET /api/capacity/insights`

Query params:
- `start_date` (string, YYYY-MM, required) — validated as valid YYYY-MM, converted to date
- `end_date` (string, YYYY-MM, required) — must be >= `start_date`, max range: 24 months

**Cross-module data access**: This query joins core tables (`users`, `functional_areas`, `projects`) with tracker tables (`reports`, `report_parts`, `reporting_periods`). Per architecture Rule 4 ("Analytical JOINs allowed in `app/core/services/`"), the query logic lives in `app/core/services/capacity_insights.py`. The capacity module's endpoint calls this core service.

**Grouping dimension**: Group by `users.functional_area_id` (the user's assigned role), NOT by `report_parts.functional_area_id`. We want to know "what percentage of FE developers' time goes to billable projects", regardless of which FA role a specific report_part was filed under.

**Logic** (per reporting period in range, per target FA):

1. Find all users where `functional_area_id` matches the target FA, `active = true`, and `requires_project_reporting = true`. Users with `functional_area_id = NULL` are excluded.
2. For each user, find their report for that period (include all reports regardless of `estimated` status).
3. Sum `report_parts.percentage` where `project.is_billable = true` -> user's billable %.
4. Users with no report in the period contribute 0% billable to the average.
5. Average billable % across all users in the FA.
6. "Others" = `1.0 - avg_billable_pct`.

**Response shape**:
```json
[
  {
    "period": "2026-01",
    "functional_areas": [
      { "short": "FE", "billable_pct": 0.72, "user_count": 5 },
      { "short": "BE", "billable_pct": 0.65, "user_count": 4 },
      { "short": "Design", "billable_pct": 0.80, "user_count": 3 },
      { "short": "PM", "billable_pct": 0.55, "user_count": 4 },
      { "short": "Sci", "billable_pct": 0.40, "user_count": 2 },
      { "short": "Coms", "billable_pct": 0.10, "user_count": 1 }
    ]
  }
]
```

The `short` code and `user_count` are backend-owned. The frontend uses `short` for display and `user_count` for tooltips. The `name` field is omitted since the short-to-name mapping is only needed backend-side for the DB lookup.

**File placement**:
- `app/core/services/capacity_insights.py` - analytical query (cross-module JOINs)
- `app/modules/capacity/__init__.py`
- `app/modules/capacity/api/__init__.py`
- `app/modules/capacity/api/insights.py` - endpoint (calls core service)
- `app/modules/capacity/router.py` - aggregates capacity sub-routers
- `app/modules/capacity/public.py` - cross-module interface (empty for now)

**Router mount**: `main.py` mounts `/capacity` prefix.

### Frontend

**New module**: `src/modules/capacity/`

```
capacity/
  components/
    InsightsChart.tsx       # Recharts grouped stacked bar
    MonthRangePicker.tsx    # Start/end month-year controls
  hooks/
    useCapacityInsights.ts  # React Query hook for the endpoint
  pages/
    Insights.tsx            # Page component
  services/
    capacity.ts             # API client
  types/
    capacity.ts             # Response types
```

**Route**: Added to `App.tsx` at `/capacity/insights`.

**Query key**: Added to `core/hooks/queryKeys.ts`.

### Sidebar Changes

In `AppSidebar.tsx`:
- Add `CAPACITY_TABS` constant: `[{ to: '/capacity/insights', label: 'Insights' }]`.
- Add `CollapsibleMenuItem` with `TrendingUp` icon, label "Capacity", after "My Report" and before "Global Scores" (admin-only). This is the first non-admin `CollapsibleMenuItem` in the sidebar.
- No permission gating — visible to all authenticated users.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| FA with 0 active reporting users in a period | Omit from that month (`user_count` = 0, bar not rendered) |
| FA has users but none submitted reports | Show 0% billable (100% Others); `user_count` reflects total eligible users |
| User with `estimated=true` report | **Include** (allocation intent, not confirmed burn) |
| User with `requires_project_reporting=false` | **Exclude** from calculations |
| User with `functional_area_id = NULL` | **Exclude** — unassigned users don't belong to any FA |
| No reporting periods in selected range | Show empty state message |
| FA name doesn't match exactly in DB | Backend maps FA names to short codes; only the 6 target FAs are returned. Log a warning if a configured FA name is not found. |
| `start_date > end_date` | 422 validation error |
| Range exceeds 24 months | 422 validation error |

## Hard-coded FA Mapping

The 6 target FAs are identified by name from the `functional_areas` table:

| DB Name | Short Code |
|---------|-----------|
| Frontend Developer | FE |
| Backend Developer | BE |
| Designer | Design |
| Project Manager | PM |
| Scientist | Sci |
| Communications | Coms |

This mapping lives in the backend service. FAs not in this list are excluded from the response.
