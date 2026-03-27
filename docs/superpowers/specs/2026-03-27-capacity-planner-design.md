# Capacity Planner Design

Replaces the "Capacity management" Google Sheet with an editable weekly Gantt-style grid inside vizzhub. Users plan future project allocation per person per week, with color-coded cells by dedication percentage.

## Data Model

### Table: `capacity_plans`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| project_id | UUID | FK → projects.id, NOT NULL |
| user_id | UUID | FK → users.id, NOT NULL |
| week_start | DATE | NOT NULL (Monday of ISO week) |
| percentage | SMALLINT | NOT NULL, CHECK 1-200 |
| created_by | UUID | FK → users.id, NOT NULL |
| updated_by | UUID | FK → users.id, NOT NULL |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | DEFAULT now() |

**UNIQUE** constraint on `(project_id, user_id, week_start)`.

Empty cells are not stored — absence of a row means no allocation. Rows in the grid are derived from the distinct `(project_id, user_id)` combinations that exist within the visible date range. Adding a grid row creates the first cell for that combination; deleting a grid row removes all cells for that combination.

The user's `functional_area` is read from the `users` table — not duplicated here.

## API Endpoints

All under `/api/capacity/planner`. Any authenticated user can read and write.

### Read

**`GET /api/capacity/planner`**

Query params: `start` (DATE), `end` (DATE), `group_by` (`project` | `user`).

Response:

```json
{
  "groups": [
    {
      "id": "project-or-user-uuid",
      "name": "FIP",
      "rows": [
        {
          "user_id": "uuid",
          "user_name": "Clara Linos",
          "functional_area": "PM",
          "project_id": "uuid",
          "project_name": "FIP",
          "cells": {
            "2026-01-05": 20,
            "2026-01-12": 20
          }
        }
      ]
    }
  ],
  "weeks": ["2026-01-05", "2026-01-12", "..."]
}
```

`cells` is a sparse dict — only weeks with a value. `weeks` is the full list of Mondays in the range.

When `group_by=project`: groups are projects, rows are users within each project.
When `group_by=user`: groups are users, rows are projects within each user.

### Write

**`DELETE /api/capacity/planner/rows/{project_id}/{user_id}`**

Deletes all cells for that project/user combination.

**`PATCH /api/capacity/planner/cells`**

Body:

```json
{
  "updates": [
    { "project_id": "uuid", "user_id": "uuid", "week_start": "2026-01-05", "percentage": 50 },
    { "project_id": "uuid", "user_id": "uuid", "week_start": "2026-01-12", "percentage": null }
  ]
}
```

`percentage: null` deletes the cell. `percentage: 0` is also treated as a delete (not stored). Bulk endpoint to support debounced batch saves.

Adding a row is a frontend-local action — no API call. The row persists to the database when the first cell is edited via this PATCH endpoint.

### Polling

**`GET /api/capacity/planner/updated-at`**

Query params: `start`, `end`. Returns `{ "updated_at": "2026-01-05T12:00:00Z" }` — the `MAX(updated_at)` of cells in the range. Called every 15-30 seconds by the frontend. If the timestamp is newer than the last known value, triggers a full refetch.

### Permissions

No per-row permission checks. Any authenticated user can edit any cell. If a user edits another user's data, the frontend shows a warning ("You are editing another user's data") but does not block.

## Frontend

### Grid Layout

```
+----------------------------------------------------------+
| Capacity Planner                   [By Project v] < >    |
+--------+----+---------+----------------------------------+
|        |    |         |  January          | February     |
| Project| FA | Name    | W1  W2  W3  W4   | W5  W6  W7   |
+--------+----+---------+----+----+----+----+----+----+----+
| FIP    |    |         |    |    |    |    |    |    |    |
|        | PM | Clara   | 20 | 20 | 20 | 20 | 20 | 20 | 20|
|        | FE | Clement | 30 | 30 | 50 | 50 | 80 | 80 | 80|
|        |    |  + Add  |    |    |    |    |    |    |    |
+--------+----+---------+----+----+----+----+----+----+----+
```

### TanStack Table Setup

- 3 pinned-left columns: Project, FA, Name
- Dynamic columns: one per week in the visible range (max ~26 weeks = 6 months)
- Column groups: weeks grouped under their month (TanStack header groups)
- `defaultColumn` with editable cell renderer (input + onBlur + `table.meta.updateData`)

### Interactions

- **Click cell** → becomes input, Enter/Tab/blur saves
- **Arrow keys** → navigate between cells
- **`< >`** → shifts the 6-month window by one month (recalculates start/end, refetch)
- **Toggle** "By Project" / "By Person" switches grouping
- **"+ Add"** at the end of each group → selector to add a row (user selector in project view, project selector in user view)
- **"x"** to delete a row (with confirmation dialog)

### Color Scheme

Colors derived from cell percentage value. Light mode uses the spreadsheet colors directly. Dark mode uses the same hues with reduced lightness (oklch, ~30% darker) for readability on dark backgrounds.

| Range | Light | Dark | Description |
|-------|-------|------|-------------|
| empty | transparent | transparent | No allocation |
| 1-20% | `#D9EAD3` | `#2A3B28` | Green |
| 21-40% | `#FFE599` | `#4A3D1A` | Yellow |
| 41-60% | `#F9CB9C` | `#4A2E1A` | Light orange |
| 61-80% | `#F6B26B` | `#4A2A10` | Orange |
| 81-100% | `#E06666` | `#4A1A1A` | Red |
| >100% | `#8E7CC3` | `#2E2450` | Purple (overallocation) |

### Totals Row

Calculated **client-side** for instant feedback during editing.

- **By Project view**: a summary row at the bottom of each project group shows the total headcount (sum of all user percentages) per week for that project. For per-user cross-project totals (overallocation detection), a collapsible "User Totals" section at the bottom of the page lists each user with their total dedication per week, color-coded with purple for >100%.
- **By Person view**: the group header for each user shows their total dedication per week (sum of all project rows). Color-coded — purple when >100%.

Totals use the same color scheme — purple (>100%) signals overallocation.

### Save Strategy

- **Optimistic updates**: cell reflects change immediately
- **Debounced batch**: changes accumulate in a local buffer, flushed to server via `PATCH /cells` after 1.5s of inactivity or on navigation/view change
- **Failure handling**: revert affected cells + error toast
- **Save indicator**: subtle "Saving..." / "Saved" in the toolbar (Google Docs style)

### Concurrency

- **Last-write-wins** — no locking
- **Polling**: `GET /planner/updated-at` every 15-30 seconds. If timestamp is newer, flush any pending local changes first, then refetch
- Changes from other users become visible within 30 seconds without manual reload

### URL State

All view state in URL via `useUrlState`:

- `group` — `project` | `user`
- `start` — first visible Monday (DATE)
- `end` — last visible Monday (DATE)
- `fa` — functional area filter (optional, client-side only)

### Query Keys

Add to `queryKeys.ts`:

```typescript
capacity: {
  // ... existing
  planner: (start: string, end: string, groupBy: string) =>
    ['capacity', 'planner', start, end, groupBy] as const,
  plannerUpdatedAt: (start: string, end: string) =>
    ['capacity', 'planner', 'updated-at', start, end] as const,
}
```

FA filtering is client-side — the API returns all data for the date range, and the frontend filters by `functional_area` when `fa` is set. The dataset is small enough (~36 users × ~26 weeks) that server-side filtering is unnecessary.

## File Structure

### Backend

```
app/modules/capacity/
├── api/
│   ├── planner.py              # CRUD endpoints + updated-at
│   └── ... (existing)
├── models/
│   └── capacity_plan.py        # CapacityPlanDB (SQLAlchemy)
├── router.py                   # add planner sub-router
└── public.py                   # export model if needed cross-module
```

The `models/` directory is new for this module (capacity was previously read-only analytical views). This is the first writable state owned by the capacity module.

New alembic migration for `capacity_plans` table.

### Frontend

```
src/modules/capacity/
├── components/
│   ├── PlannerGrid.tsx         # TanStack Table wrapper
│   ├── PlannerCell.tsx         # Editable cell with color
│   ├── PlannerToolbar.tsx      # Toggle, FA filter, < > nav
│   ├── PlannerAddRow.tsx       # Selector to add row
│   ├── PlannerSaveIndicator.tsx # Saving.../Saved
│   └── ... (existing)
├── hooks/
│   ├── usePlannerData.ts       # Fetch + refetch + polling
│   ├── usePlannerMutations.ts  # PATCH cells, DELETE rows, buffer/flush
│   └── ... (existing)
├── pages/
│   ├── Planner.tsx             # Page component
│   └── ... (existing)
├── types/
│   ├── planner.ts              # Types
│   └── ... (existing)
└── utils/
    ├── plannerColors.ts        # percentage → color (light/dark)
    └── ... (existing)
```

### Routing

New sidebar entry under Capacity. Route: `/capacity/planner`.

## Seed

Two-step process to separate xlsx parsing from DB insertion.

### Step 1: `scripts/export_capacity_xlsx_to_json.py`

Runs locally where the xlsx exists. Reads "General view" tab:

- Iterates rows from row 16: Project (col 1), Role (col 2), Name (col 3)
- Week columns start at col 4, week numbers in row 12, months in row 14
- Converts ISO week number + year → `week_start` (Monday date)
- Old format (Nov-Dec, cols 4-11): values are days (1-5), converted to percentage: `days × 20`
- New format (Jan+, cols 12+): values are already percentages
- Values "x" are skipped (no allocation)
- Matches names to user emails (manual mapping dict in script)

Outputs `capacity_seed.json`:

```json
[
  {
    "project_name": "FIP",
    "user_email": "clara@vizzuality.com",
    "week_start": "2026-01-05",
    "percentage": 20
  }
]
```

### Step 2: `scripts/seed_capacity_planner.py`

Runs against any DB (local or prod). Reads `capacity_seed.json`:

- Resolves `project_name` → `project_id` and `user_email` → `user_id` from DB
- Logs warnings for unresolved names (e.g., "Freelancer")
- Bulk insert with `ON CONFLICT DO NOTHING`
- Portable via SSM (text file, like playbook seed)
