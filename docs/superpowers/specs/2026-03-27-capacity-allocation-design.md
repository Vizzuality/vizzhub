# Capacity Allocation Page — Design Spec

## Overview

New page within the capacity module (`/capacity/allocation`) showing team dedication insights. First component: a ranked list of users by average number of billable projects over the last 3 closed reporting periods, with horizontal segmented bars representing project allocation.

Future iteration will add a similar component for active projects ranked by number of people reporting.

## Backend API

### `GET /api/capacity/allocation/users`

No parameters — backend determines the last 3 closed reporting periods automatically.

**Response:**

```json
{
  "periods_used": ["2026-01", "2025-12", "2025-11"],
  "users": [
    {
      "user_id": "uuid",
      "name": "Miguel Mendoza",
      "avg_billable_projects": 2.3,
      "total_distinct_projects": 5,
      "segments": [
        {
          "project_id": "uuid",
          "project_name": "Project Alpha",
          "avg_percentage": 0.45,
          "months_active": ["2026-01", "2025-12"],
          "type": "billable"
        },
        {
          "project_id": "uuid",
          "project_name": "Vacation",
          "avg_percentage": 0.05,
          "months_active": ["2025-12"],
          "type": "absence"
        },
        {
          "project_id": "uuid",
          "project_name": "Internal Tasks",
          "avg_percentage": 0.10,
          "months_active": ["2026-01", "2025-12", "2025-11"],
          "type": "other"
        }
      ]
    }
  ]
}
```

**Business rules:**

- Last 3 reporting periods with status `closed`, ordered descending
- Users filtered: `active=true`, `requires_project_reporting=true`
- Users with no reports in any of the 3 periods are excluded
- `avg_billable_projects`: average count of distinct billable projects per period across the 3 months
- `total_distinct_projects`: total unique billable projects across all 3 months
- `avg_percentage`: mean of the user's percentage for that project across the periods where they reported it
- `months_active`: which of the 3 periods the user reported time to this project
- `type`: derived from `ProjectDB.is_billable` (billable), `ProjectDB.is_absence` (absence), else other
- Users sorted descending by `avg_billable_projects`
- Segments sorted: billable first (descending by `avg_percentage`), then absence, then others
- `periods_used`: the 3 period dates used, for display in the UI

**Implementation location:** `core/services/capacity_insights.py` (new function, following existing pattern of analytical JOINs).

**Endpoint location:** New sub-router `modules/capacity/api/allocation.py`, mounted via `capacity/router.py` with prefix `/allocation`.

## Frontend

### Route & Navigation

- **Route**: `/capacity/allocation`
- **Sidebar**: "Allocation" as second item under Capacity (alongside "Insights")

### Page: `modules/capacity/pages/Allocation.tsx`

Simple page wrapper that renders the `UserAllocationList` component. Shows a header with the periods used: "Based on Jan, Dec, Nov 2025".

### Component: `modules/capacity/components/UserAllocationList.tsx`

Ranked list of users, 10 at a time with "Show more" button.

**Each row layout:**

```
┌──────────────────────────────────────────────────────────┐
│ Miguel Mendoza           avg 2.3 projects · 5 total      │
│ ████████████████████░░░░░░▒▒▒░░░░░░░░░░░░░░░░░░░░░░░░░  │
└──────────────────────────────────────────────────────────┘
```

- **Top line**: Full name (left), stats (right) — "avg X.X projects · Y total"
- **Bottom line**: Horizontal segmented bar
  - Each segment = one project, width proportional to `avg_percentage`
  - Colors from `ITEM_PALETTE`, assigned globally by `project_id` (same project = same color across all users)
  - Opacity by type: billable = 1.0, absence = 0.5, others = 0.3
  - Segment order matches API: billable desc, absence, others

**Tooltip on segment hover:**
- Project name
- Average percentage (formatted as %)
- Months active (e.g., "Jan, Dec 2025")

**Pagination:**
- Shows first 10 users
- "Show more" link/button at bottom loads next 10
- Simple client-side slice with local state counter

### New Files

| File | Purpose |
|------|---------|
| `modules/capacity/pages/Allocation.tsx` | Page component |
| `modules/capacity/components/UserAllocationList.tsx` | Main list component |
| `modules/capacity/hooks/useAllocationUsers.ts` | React Query hook |
| `modules/capacity/types/allocation.ts` | TypeScript types |

### Modified Files

| File | Change |
|------|--------|
| `modules/capacity/services/capacity.ts` | Add `getAllocationUsers()` function |
| `modules/capacity/router.py` (backend) | Mount allocation sub-router |
| `App.tsx` | Add `/capacity/allocation` route |
| `AppSidebar.tsx` | Add "Allocation" menu item |

### Types

```typescript
interface AllocationSegment {
  project_id: string;
  project_name: string;
  avg_percentage: number;
  months_active: string[];
  type: 'billable' | 'absence' | 'other';
}

interface UserAllocation {
  user_id: string;
  name: string;
  avg_billable_projects: number;
  total_distinct_projects: number;
  segments: AllocationSegment[];
}

interface AllocationUsersResponse {
  periods_used: string[];
  users: UserAllocation[];
}
```

## Design Decisions

1. **No parameters on endpoint** — Always uses last 3 closed periods. Simpler API, no date picker needed. Future iteration could add configurability.
2. **Global color assignment by project_id** — Collect all unique project IDs from the response, assign `ITEM_PALETTE` colors in order. Same project gets same color across all user rows.
3. **Client-side pagination** — ~50 users max, single API call. "Show more" increments a counter, slice grows by 10.
4. **Consistent with capacity module** — Same styling, same location in sidebar, same service patterns.
5. **Opacity pattern reused** — Billable/absence/others distinction uses same opacity approach as InsightsChart.
