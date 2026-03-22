# Capacity FA Detail Drill-Down Design

## Goal

Add a per-user drill-down chart below the existing Capacity Insights overview chart. For a selected functional area, show each user's project vs other time allocation per month, with a count of billable projects reported.

## Navigation & Layout

- Same page: `/capacity/insights` — the detail chart renders below the overview `InsightsChart`
- Always visible on load (not hidden until click). Default state: FA = FE, last 3 months excluding current month
- URL state extends existing params: `start`, `end` (overview) + `fa`, `detail_start`, `detail_end` (drill-down)
- Clicking a bar on the overview chart updates `fa` to the clicked FA and sets `detail_start`/`detail_end` to that single month, then scrolls the detail chart into view
- The detail chart has its own controls: FA dropdown (left) + MonthRangePicker (right)
- Back-link or breadcrumb not needed — it's on the same page

## Backend Endpoint

### `GET /api/capacity/insights/detail`

Query params:
- `fa` (string, required): FA short code — one of `FE`, `BE`, `Design`, `PM`, `Sci`, `Coms`
- `start_date` (string, required): YYYY-MM format
- `end_date` (string, required): YYYY-MM format

Response:
```json
[
  {
    "period": "2026-01",
    "users": [
      {
        "user_id": 42,
        "name": "M. Mendoza",
        "billable_pct": 0.75,
        "billable_project_count": 3
      }
    ]
  }
]
```

**Data semantics:**
- `billable_pct`: float 0.0-1.0. The fraction of the user's reported time allocated to billable projects. Since reports must total 100%, `others = 1 - billable_pct` is computed client-side (same pattern as overview).
- `billable_project_count`: number of distinct billable projects the user reported time to in that period.
- Estimated reports (`estimated=true`) are **included** — this is a capacity view, not a burn calculation. Matches overview behavior.

Validation:
- Same YYYY-MM format validation as overview endpoint
- `start_date` must be <= `end_date`
- Max range: 24 months
- `fa` must be one of the 6 target FA short codes; 422 otherwise

### Service: `get_capacity_fa_detail`

Located in `app/core/services/capacity_insights.py` (same file as overview, per architecture Rule 4 — cross-module analytical JOIN).

Logic:
1. Build a reverse mapping `SHORT_TO_FA_NAME` from `TARGET_FA_MAPPING` (e.g., `"FE" -> "Frontend Developer"`). Resolve the FA short code to `functional_areas.id` by querying the DB for that name
2. Find eligible users: `active=true`, `requires_project_reporting=true`, `functional_area_id` = resolved FA id
3. For each user, for each period in range:
   - Get their report: total percentage and billable percentage (same JOIN as overview: reports -> report_parts -> projects)
   - Exclude on-leave users: if total report percentage = 0 or no report for that period, exclude from that period
   - Count distinct billable projects: `COUNT(DISTINCT project_id) WHERE projects.is_billable = true`
4. Format user name as "F. Lastname" (first initial + dot + space + last name) using `UserDB.first_name` and `UserDB.last_name`. Fallback: if `first_name` is empty/None, use `last_name` only. If `last_name` is empty/None, use `first_name` only. If both empty, use `"Unknown"`
5. Return periods sorted ascending, users within each period sorted alphabetically by name

## Frontend

### Types (`capacity.ts`)

```typescript
export interface UserInsight {
  user_id: number;
  name: string;
  billable_pct: number;
  billable_project_count: number;
}

export interface PeriodUserInsight {
  period: string;
  users: UserInsight[];
}
```

### API client (`capacity.ts`)

Add `getInsightsDetail(fa, startDate, endDate)` returning `PeriodUserInsight[]`.

### Hook

New `useCapacityFADetail(fa, startDate, endDate)` hook with query key `capacity.faDetail(fa, startDate, endDate)`.

### Component: `FADetailChart`

- Grouped vertical stacked bar chart (Recharts `BarChart`)
- X-axis: months. Bars grouped by user within each month
- Each user's bar stacked: project time (solid color) + others (same color, 0.3 opacity)
- Bar color: the FA's color from `FA_COLORS` (same mapping as overview)
- Small number label on top of each bar showing `billable_project_count` (Recharts custom label)
- Hover on a bar: shows user name in grey `bg-muted` tooltip (same pattern as overview)
- Title: "Project time by user"
- Empty state: "No data for the selected period" (same pattern as overview)

### Controls

- FA dropdown: plain `<select>` with the 6 target FAs (FE, BE, Design, PM, Sci, Coms). No colored dots.
- MonthRangePicker: reuse existing `MonthRangePicker` component

### Integration with Overview Chart

The overview `InsightsChart` receives an `onBarClick(fa: string, period: string)` callback prop where `period` is the original `YYYY-MM` string (not the display label).

To support this:
- `transformData` must preserve the original `YYYY-MM` period string in each data point (add a `period` field alongside `month`)
- The `<Bar>` `onClick` handler receives the Recharts payload; extract the FA short code by parsing the `dataKey` (e.g., `"FE_projects"` -> split on `_` -> first segment = `"FE"`)
- Read the `period` field from the data point in the click payload

The `Insights` page wires `onBarClick` to update `fa`, `detail_start`, `detail_end` URL state and scroll to the detail chart via `ref.scrollIntoView({ behavior: 'smooth' })`.

## URL State

The `Insights` page `useUrlState` expands to:

| Param | Default | Description |
|-------|---------|-------------|
| `start` | 6 months ago | Overview start |
| `end` | last month | Overview end |
| `fa` | `FE` | Detail FA selection |
| `detail_start` | 3 months ago | Detail range start |
| `detail_end` | last month | Detail range end |

Defaults for overview and detail are computed once at module load time (same pattern as current `defaultRange()`).

## Router Mounting

The new `fa_detail.py` router is mounted in `app/modules/capacity/router.py` with prefix `/insights/detail`, so the full path is `/api/capacity/insights/detail`.

## Edge Cases

- FA with zero eligible users for a period: that period's `users` array is empty; chart shows empty state if all periods are empty
- User on leave (total report = 0): excluded from that period (not shown, not counted)
- User with 100% non-billable: shown with full "others" bar, `billable_project_count` = 0, label shows "0"
- FA short code not found in DB: endpoint returns empty periods (no users match)
- Single month selected: works fine, shows one group of user bars
- User with missing first/last name: fallback formatting as described in service logic

## Permissions

- Same as overview: any authenticated user (`CurrentUser` dependency)

## Files to Create/Modify

### Backend
- Modify: `app/core/services/capacity_insights.py` — add `SHORT_TO_FA_NAME` reverse mapping and `get_capacity_fa_detail()` function
- Create: `app/modules/capacity/api/fa_detail.py` — new endpoint
- Modify: `app/modules/capacity/router.py` — mount new sub-router with prefix `/insights/detail`
- Create: `backend/tests/modules/capacity/test_capacity_fa_detail.py` — tests

### Frontend
- Modify: `frontend/src/modules/capacity/types/capacity.ts` — add `UserInsight` and `PeriodUserInsight` types
- Modify: `frontend/src/modules/capacity/services/capacity.ts` — add `getInsightsDetail` API method
- Create: `frontend/src/modules/capacity/hooks/useCapacityFADetail.ts` — new hook
- Modify: `frontend/src/core/hooks/queryKeys.ts` — add `capacity.faDetail` key
- Create: `frontend/src/modules/capacity/components/FADetailChart.tsx` — new chart component
- Modify: `frontend/src/modules/capacity/components/InsightsChart.tsx` — add `onBarClick` prop, preserve `period` in chart data
- Modify: `frontend/src/modules/capacity/pages/Insights.tsx` — integrate detail chart, expand URL state, wire scroll behavior
