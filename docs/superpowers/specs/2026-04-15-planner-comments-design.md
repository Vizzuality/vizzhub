# Capacity Planner — Cell Comments — Design

**Date:** 2026-04-15
**Module:** `capacity` (planner)
**Goal:** Let users attach a short comment to a planner cell. In the by-person view, the week header flags weeks that have comments and an "expand" action lets users read all comments for that week inline, without leaving the grid.

## Requirements

- A planner cell (`project × user × week`) can have an optional comment (max 500 chars).
- Comments are tied to a valued cell: no percentage → no comment. Clearing the percentage removes the comment.
- The feature — reading, adding, and editing comments — is surfaced only in the by-person view (`groupBy === 'user'`). In by-project the column is hidden from the UI but data is preserved.
- Any authenticated user can add/edit/delete a comment on any cell (same permissions as editing the percentage).
- Week header shows an icon when at least one visible row has a comment for that week.
- Clicking the icon expands that week: each row with a comment for that week displays the text in an overlay extending 4 columns to the right of the commented cell.
- Only one week can be expanded at a time.

## Backend

### Database

Add one nullable column to `capacity_plans`:

| Column    | Type        | Notes                    |
| --------- | ----------- | ------------------------ |
| `comment` | TEXT NULL   | Free text, max 500 chars |

No other schema changes. The existing `percentage` check constraint (`1..200`) and `uq_capacity_plan_cell` unique constraint remain.

Migration: `054_planner_comment.py` — single `op.add_column`.

### Models / Schemas

`app/modules/capacity/models/capacity_plan.py`:

```python
class CapacityPlanDB(Base):
    # ...existing columns...
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class CellUpdate(BaseModel):
    project_id: UUID
    user_id: UUID
    week_start: date
    percentage: int | None
    comment: str | None = None

    @field_validator("comment")
    @classmethod
    def comment_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 500:
            raise ValueError("comment must be 500 chars or fewer")
        return v
```

### API

**`GET /capacity/planner`** — extend each row with a parallel `comments` map keyed by week (ISO Monday string), mirroring the existing `cells` map:

```json
{
  "user_id": "…",
  "project_id": "…",
  "cells":    { "2026-04-13": 50, "2026-04-20": 80 },
  "comments": { "2026-04-13": "Pending review by PM" }
}
```

Rows with no comments for any visible week simply have `comments: {}`. This preserves the current integer-valued `cells` structure so existing render paths remain untouched.

**`PATCH /capacity/planner/cells`** — accept an optional `comment` per update. Upsert branch writes `comment` alongside `percentage`. Delete branch (percentage null or 0) wipes the row entirely, including any comment.

If a client sends `{ percentage: 50, comment: "…" }` for an existing row whose percentage is already 50, the upsert still runs and the comment updates. The unique constraint on `(project, user, week)` keeps behavior correct.

No new endpoints.

## Frontend

### Types

`src/modules/capacity/types/planner.ts`:

```ts
export interface PlannerRow {
  // ...existing fields...
  cells: Record<string, number>;
  comments: Record<string, string>;  // new
}

export interface CellUpdate {
  project_id: string;
  user_id: string;
  week_start: string;
  percentage: number | null;
  comment: string | null;  // new
}
```

### Cell UI — adding / editing a comment

Only rendered when `groupBy === 'user'`.

- `PlannerCell` receives two new props: `comment?: string` and `onCommentChange(value: string | null)`.
- A 10px `MessageSquare` icon sits at the top-right corner of the cell:
  - Always visible with accent color when `comment` is set.
  - Hidden (opacity-0 → hover:opacity-100) when the cell has a percentage but no comment.
  - Never rendered when the cell has no percentage (matches the "no value → no comment" rule).
- Clicking the icon opens a Radix Popover anchored to the cell. Popover contents:
  - `<textarea>` autofocused, `maxLength={500}`, placeholder "Add a note…".
  - Footer: `{draft.length} / 500` counter, **Save** button, **Delete** button (only when an existing comment is being edited).
  - Shortcuts: `Cmd/Ctrl+Enter` = Save, `Esc` = Cancel and close.
- Save path calls `queueCellUpdate({ project_id, user_id, week_start, percentage: currentValue, comment: draft })`. Reuses the existing debounced flush pipeline.
- Delete path calls the same with `comment: null`.
- The popover never triggers a percentage edit: the double-click-to-edit-value and drag-to-select mechanics are unchanged.

### Week header — expand indicator

- In by-person view, for each week compute `hasAnyComment = filteredGroups` contains at least one row whose `comments[weekKey]` is non-empty.
- The existing week header cell (`W15`, `W16`, …) gets a small `MessageSquare` icon next to the label when `hasAnyComment` is true. Icon is clickable.
- Click toggles an `expandedWeek` local state in `PlannerGrid`:
  - Null → clicked week key (expand it).
  - Same key → null (collapse).
  - Different key → replace (only one expanded at a time).
- `Esc` key at the grid level also collapses.
- State does not persist to the URL (ephemeral, per-session).

### Expanded overlay

When `expandedWeek === weekKey`, for each data row where `comments[weekKey]` is a non-empty string, render an absolutely-positioned overlay inside the scrollable container:

- Anchored to the commented cell's horizontal position (`left = weekColumnOffset`).
- Width = `4 × WEEK_COLUMN_WIDTH` (168px with current 42px columns).
- Height = row height (32px).
- Vertical position matches the row's top offset.
- Content: `<div>` with `truncate` + `title={comment}` for the tooltip of full text.
- Style: amber-ish tint (light: `rgba(251,191,36,0.18)`, dark: `rgba(251,191,36,0.22)`), 1px amber border, rounded corners, padding-x 8px, z-index 15 (above `<td>`, below sticky headers at 20).

Rendering approach: overlays are absolutely positioned within the scrollable `containerRef`. Since row heights vary (group headers 28px, data rows 32px, add rows 28px) and we already have sticky headers, the cleanest path is to render each overlay as a child of the row's `<tr>` (via a portal-less absolutely positioned `<div>` inside the data row's first cell with `position: relative` on the row) rather than trying to compute top offsets. This means the overlay inherits the row's top automatically; we only need to compute `left = weekColumnOffset` from the header cell's `offsetLeft`. One overlay per (row, expandedWeek) pair with non-empty comment.

### Empty state

If `expandedWeek` is set but no visible row has a comment for that week (e.g. a filter change removed them), the icon disappears and we auto-collapse.

## Scope exclusions

- No comment history, audit log, or author metadata on the comment itself (the row already tracks `created_by`/`updated_by`).
- No markdown or rich text.
- No mention/notification features.
- No comment on `is_absence` / `is_other` pinned rows — those rows are not user-editable in any other way either.

## Testing

### Backend
- Unit test: `PATCH /capacity/planner/cells` with comment only (percentage unchanged) updates the row.
- Unit test: comment is stripped when the row is deleted via percentage=0/null.
- Unit test: comment longer than 500 chars → 422.
- Unit test: `GET /capacity/planner` returns `comments` map, empty when none set.

### Frontend
- `PlannerCell`: hover icon visibility depends on comment existence and `groupBy`.
- `PlannerCell`: save path calls `onCommentChange` with trimmed text.
- `PlannerGrid`: week header icon renders only when any visible row has a comment for that week in by-person view.
- `PlannerGrid`: overlay appears for rows with comments when a week is expanded; `Esc` collapses.

## Migration & rollout

- Single DDL (add nullable column), zero downtime.
- No backfill.
- Frontend ships the UI guarded by `groupBy === 'user'`; by-project view is unaffected.
