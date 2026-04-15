# Planner Cell Comments — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional comments to Capacity Planner cells, surfaced in by-person view with a hover icon for editing and a per-week expand action that displays every comment inline as a 4-column overlay.

**Architecture:** Extend `capacity_plans` with a nullable `comment` column. Reuse the existing cell PATCH pipeline (`queueCellUpdate` → debounced flush). In the frontend, add a `MessageSquare` hover icon to `PlannerCell` that opens a Radix Popover, add an expand icon to the week header when any visible row has a comment, and render overlays within rows so they inherit row-top positioning automatically. Only one week expanded at a time.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic (backend). React + TypeScript + Vite + TanStack Table + Radix UI + React Query (frontend). Tests via pytest-asyncio and vitest.

**Spec:** `docs/superpowers/specs/2026-04-15-planner-comments-design.md`

---

## File Structure

**Backend**
- Create: `backend/alembic/versions/054_planner_comment.py` — migration adding nullable `comment` column.
- Modify: `backend/app/modules/capacity/models/capacity_plan.py` — add `comment` mapped column and `comment` field on `CellUpdate` with length validator.
- Modify: `backend/app/modules/capacity/api/planner.py` — extend `_build_row_data` to include a `comments` dict, populate it in `_process_rows`, and include `comment` in the PATCH upsert payload.
- Modify: `backend/tests/modules/capacity/test_planner.py` — add tests for comment roundtrip, delete semantics, length validation.

**Frontend**
- Modify: `frontend/src/modules/capacity/types/planner.ts` — add `comments` to `PlannerRow`, `comment` to `CellUpdate`.
- Modify: `frontend/src/modules/capacity/hooks/usePlannerMutations.ts` — optimistic update must also touch `comments`.
- Create: `frontend/src/modules/capacity/components/PlannerCommentPopover.tsx` — popover with textarea, counter, Save, Delete.
- Modify: `frontend/src/modules/capacity/components/PlannerCell.tsx` — integrate the popover and hover icon; accept `comment`, `onCommentChange`, and `canComment` props.
- Modify: `frontend/src/modules/capacity/components/PlannerGrid.tsx` — week-header expand icon, expanded-state, overlay rendering; wire new cell props.
- Modify: `frontend/src/modules/capacity/pages/Planner.tsx` — pipe comment updates through the existing `queueCellUpdate` pathway.
- Create: `frontend/src/modules/capacity/components/__tests__/PlannerCommentPopover.test.tsx` — popover interactions.
- Create: `frontend/src/modules/capacity/components/__tests__/PlannerCell.test.tsx` — hover icon visibility rules.

---

## Task 1: Alembic migration

**Files:**
- Create: `backend/alembic/versions/054_planner_comment.py`

- [ ] **Step 1: Create migration file**

```python
"""Add comment column to capacity_plans.

Revision ID: 054_planner_cmt
Revises: 053_iso_notes
"""

from alembic import op

revision = "054_planner_cmt"
down_revision = "053_iso_notes"


def upgrade() -> None:
    op.execute("ALTER TABLE capacity_plans ADD COLUMN IF NOT EXISTS comment TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE capacity_plans DROP COLUMN IF EXISTS comment")
```

- [ ] **Step 2: Apply migration locally**

Run: `cd backend && alembic upgrade head`
Expected: `054_planner_cmt` applied. Verify with `alembic current`.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/054_planner_comment.py
git commit -m "feat(planner): add comment column migration"
```

---

## Task 2: SQLAlchemy model and Pydantic schema

**Files:**
- Modify: `backend/app/modules/capacity/models/capacity_plan.py`

- [ ] **Step 1: Write the failing test**

Add in `backend/tests/modules/capacity/test_planner.py` inside a new class at the end:

```python
class TestCellUpdateSchema:
    def test_accepts_comment_within_limit(self):
        from app.modules.capacity.models.capacity_plan import CellUpdate
        from uuid import uuid4
        from datetime import date

        update = CellUpdate(
            project_id=uuid4(),
            user_id=uuid4(),
            week_start=date(2026, 1, 5),
            percentage=50,
            comment="Short note",
        )
        assert update.comment == "Short note"

    def test_rejects_comment_over_500_chars(self):
        from app.modules.capacity.models.capacity_plan import CellUpdate
        from pydantic import ValidationError
        from uuid import uuid4
        from datetime import date
        import pytest

        with pytest.raises(ValidationError):
            CellUpdate(
                project_id=uuid4(),
                user_id=uuid4(),
                week_start=date(2026, 1, 5),
                percentage=50,
                comment="x" * 501,
            )

    def test_comment_defaults_to_none(self):
        from app.modules.capacity.models.capacity_plan import CellUpdate
        from uuid import uuid4
        from datetime import date

        update = CellUpdate(
            project_id=uuid4(),
            user_id=uuid4(),
            week_start=date(2026, 1, 5),
            percentage=50,
        )
        assert update.comment is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/modules/capacity/test_planner.py::TestCellUpdateSchema -v`
Expected: FAIL — `comment` not a recognised field.

- [ ] **Step 3: Update model and schema**

In `backend/app/modules/capacity/models/capacity_plan.py`:

Add import:
```python
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, SmallInteger, Text, UniqueConstraint
```

Add mapped column after `percentage`:
```python
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Extend `CellUpdate`:
```python
class CellUpdate(BaseModel):
    project_id: UUID
    user_id: UUID
    week_start: date
    percentage: int | None
    comment: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("week_start")
    @classmethod
    def must_be_monday(cls, v: date) -> date:
        if v.isoweekday() != 1:
            raise ValueError("week_start must be a Monday")
        return v

    @field_validator("percentage")
    @classmethod
    def valid_range(cls, v: int | None) -> int | None:
        if v is not None and (v < 0 or v > 200):
            raise ValueError("percentage must be 0-200 or null")
        return v

    @field_validator("comment")
    @classmethod
    def comment_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 500:
            raise ValueError("comment must be 500 chars or fewer")
        return v
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/modules/capacity/test_planner.py::TestCellUpdateSchema -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/capacity/models/capacity_plan.py backend/tests/modules/capacity/test_planner.py
git commit -m "feat(planner): add comment field to CapacityPlan model"
```

---

## Task 3: GET endpoint returns `comments` map

**Files:**
- Modify: `backend/app/modules/capacity/api/planner.py`
- Modify: `backend/tests/modules/capacity/test_planner.py`

- [ ] **Step 1: Write the failing test**

Add to `TestGetPlanner` in `test_planner.py`:

```python
    @pytest.mark.asyncio
    async def test_returns_comments_per_row(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_planner

        # Attach a comment to user1/project1/2026-01-05
        from sqlalchemy import update
        await db_session.execute(
            update(CapacityPlanDB)
            .where(
                CapacityPlanDB.user_id == planner_data["user1"].id,
                CapacityPlanDB.project_id == planner_data["project1"].id,
                CapacityPlanDB.week_start == date(2026, 1, 5),
            )
            .values(comment="Need reviewer")
        )
        await db_session.flush()

        fake_user = FakeUser(planner_data["user1"].id)
        result = await get_planner(
            db_session, fake_user,
            start="2026-01-05", end="2026-01-12",
            group_by="user",
        )

        user1_group = next(g for g in result["groups"] if g["id"] == str(planner_data["user1"].id))
        row = next(r for r in user1_group["rows"] if r["project_id"] == str(planner_data["project1"].id))
        assert row["comments"] == {"2026-01-05": "Need reviewer"}

    @pytest.mark.asyncio
    async def test_rows_without_comments_return_empty_map(self, db_session, planner_data):
        from app.modules.capacity.api.planner import get_planner

        fake_user = FakeUser(planner_data["user1"].id)
        result = await get_planner(
            db_session, fake_user,
            start="2026-01-05", end="2026-01-12",
            group_by="user",
        )

        for group in result["groups"]:
            for row in group["rows"]:
                assert row["comments"] == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/modules/capacity/test_planner.py::TestGetPlanner::test_returns_comments_per_row tests/modules/capacity/test_planner.py::TestGetPlanner::test_rows_without_comments_return_empty_map -v`
Expected: FAIL — `comments` key missing from row dict.

- [ ] **Step 3: Extend row builder and row processor**

In `backend/app/modules/capacity/api/planner.py`:

Replace `_build_row_data`:
```python
def _build_row_data(row) -> dict:
    """Build a single row dict from a query result row."""
    return {
        "user_id": str(row.user_id),
        "user_name": row.user_name,
        "functional_area": _fa_short_name(row.functional_area),
        "project_id": str(row.project_id),
        "project_name": row.project_name,
        "is_absence": row.is_absence,
        "is_other": not row.is_absence and not row.is_billable,
        "cells": {},
        "comments": {},
    }
```

In `_process_rows`, after `rows_map[row_key]["cells"][row.week_start.isoformat()] = row.percentage`, add:

```python
        if row.comment:
            rows_map[row_key]["comments"][row.week_start.isoformat()] = row.comment
```

In the main SQL `select` inside `get_planner`, add `CapacityPlanDB.comment` alongside the existing columns:

```python
    stmt = (
        select(
            CapacityPlanDB.project_id,
            ProjectDB.name.label("project_name"),
            ProjectDB.is_absence,
            ProjectDB.is_billable,
            CapacityPlanDB.user_id,
            _user_name_expr().label("user_name"),
            FunctionalAreaDB.name.label("functional_area"),
            CapacityPlanDB.week_start,
            CapacityPlanDB.percentage,
            CapacityPlanDB.comment,
        )
        # ...rest unchanged...
    )
```

Also update `_inject_pinned_rows` and `_inject_empty_groups` to include `"comments": {}` in every injected row dict so the response shape is uniform. In `_inject_pinned_rows`, update the appended dict:

```python
                group["rows"].append({
                    "user_id": user_key,
                    "user_name": group["name"],
                    "functional_area": "",
                    "project_id": pp_id,
                    "project_name": pp.name,
                    "is_absence": pp.is_absence,
                    "is_other": not pp.is_absence,
                    "cells": {},
                    "comments": {},
                })
```

(`_inject_empty_groups` builds empty groups without rows, so no row dict to update there.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/modules/capacity/test_planner.py::TestGetPlanner -v`
Expected: PASS (all tests in class, including new ones).

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/capacity/api/planner.py backend/tests/modules/capacity/test_planner.py
git commit -m "feat(planner): return comments map in GET response"
```

---

## Task 4: PATCH endpoint writes comment

**Files:**
- Modify: `backend/app/modules/capacity/api/planner.py`
- Modify: `backend/tests/modules/capacity/test_planner.py`

- [ ] **Step 1: Write the failing test**

Add a new class at the end of `test_planner.py`:

```python
class TestPatchCellsWithComment:
    @pytest.mark.asyncio
    async def test_creates_cell_with_comment(self, db_session, planner_data):
        from app.modules.capacity.api.planner import update_cells
        from app.modules.capacity.models.capacity_plan import BulkCellUpdate, CellUpdate

        u = planner_data["user1"]
        p = planner_data["project2"]
        fake_user = FakeUser(u.id)

        body = BulkCellUpdate(updates=[
            CellUpdate(
                project_id=p.id, user_id=u.id,
                week_start=date(2026, 1, 12),
                percentage=40,
                comment="Blocked on review",
            ),
        ])
        await update_cells(db_session, fake_user, body)

        stmt = select(CapacityPlanDB).where(
            CapacityPlanDB.user_id == u.id,
            CapacityPlanDB.project_id == p.id,
            CapacityPlanDB.week_start == date(2026, 1, 12),
        )
        row = (await db_session.execute(stmt)).scalar_one()
        assert row.percentage == 40
        assert row.comment == "Blocked on review"

    @pytest.mark.asyncio
    async def test_updates_only_comment_on_existing_cell(self, db_session, planner_data):
        from app.modules.capacity.api.planner import update_cells
        from app.modules.capacity.models.capacity_plan import BulkCellUpdate, CellUpdate

        u = planner_data["user1"]
        p = planner_data["project1"]
        fake_user = FakeUser(u.id)

        body = BulkCellUpdate(updates=[
            CellUpdate(
                project_id=p.id, user_id=u.id,
                week_start=date(2026, 1, 5),
                percentage=50,  # unchanged
                comment="Updated note",
            ),
        ])
        await update_cells(db_session, fake_user, body)

        stmt = select(CapacityPlanDB).where(
            CapacityPlanDB.user_id == u.id,
            CapacityPlanDB.project_id == p.id,
            CapacityPlanDB.week_start == date(2026, 1, 5),
        )
        row = (await db_session.execute(stmt)).scalar_one()
        assert row.percentage == 50
        assert row.comment == "Updated note"

    @pytest.mark.asyncio
    async def test_delete_wipes_comment(self, db_session, planner_data):
        from app.modules.capacity.api.planner import update_cells
        from app.modules.capacity.models.capacity_plan import BulkCellUpdate, CellUpdate
        from sqlalchemy import update as sa_update

        u = planner_data["user1"]
        p = planner_data["project1"]
        fake_user = FakeUser(u.id)

        # Seed a comment
        await db_session.execute(
            sa_update(CapacityPlanDB)
            .where(
                CapacityPlanDB.user_id == u.id,
                CapacityPlanDB.project_id == p.id,
                CapacityPlanDB.week_start == date(2026, 1, 5),
            )
            .values(comment="to be gone")
        )
        await db_session.flush()

        # percentage=None triggers delete branch
        body = BulkCellUpdate(updates=[
            CellUpdate(
                project_id=p.id, user_id=u.id,
                week_start=date(2026, 1, 5),
                percentage=None,
                comment="ignored because cell is being deleted",
            ),
        ])
        await update_cells(db_session, fake_user, body)

        stmt = select(CapacityPlanDB).where(
            CapacityPlanDB.user_id == u.id,
            CapacityPlanDB.project_id == p.id,
            CapacityPlanDB.week_start == date(2026, 1, 5),
        )
        assert (await db_session.execute(stmt)).first() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/modules/capacity/test_planner.py::TestPatchCellsWithComment -v`
Expected: FAIL — upsert does not write `comment` yet.

- [ ] **Step 3: Include comment in upsert**

In `backend/app/modules/capacity/api/planner.py`, inside `update_cells`, modify the `values` list and the `on_conflict_do_update.set_`:

```python
    upserted_count = 0
    if upserts:
        values = [
            {
                "project_id": cell.project_id,
                "user_id": cell.user_id,
                "week_start": cell.week_start,
                "percentage": cell.percentage,
                "comment": cell.comment,
                "created_by": user.user_id,
                "updated_by": user.user_id,
            }
            for cell in upserts
        ]
        stmt = pg_insert(CapacityPlanDB).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_capacity_plan_cell",
            set_={
                "percentage": stmt.excluded.percentage,
                "comment": stmt.excluded.comment,
                "updated_by": stmt.excluded.updated_by,
                "updated_at": func.now(),
            },
        )
        await db.execute(stmt)
        upserted_count = len(upserts)
```

The delete branch is unchanged — `tuple_.in_()` already wipes the full row.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/modules/capacity/test_planner.py -v`
Expected: PASS (all planner tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/capacity/api/planner.py backend/tests/modules/capacity/test_planner.py
git commit -m "feat(planner): persist comment in PATCH upsert"
```

---

## Task 5: Frontend types

**Files:**
- Modify: `frontend/src/modules/capacity/types/planner.ts`

- [ ] **Step 1: Edit types**

Replace the relevant exports with:

```ts
export interface PlannerRow {
  user_id: string;
  user_name: string;
  functional_area: string;
  project_id: string;
  project_name: string;
  is_absence?: boolean;
  is_other?: boolean;
  cells: Record<string, number>;
  comments: Record<string, string>;
}

// ...PlannerGroup, PlannerResponse unchanged...

export interface CellUpdate {
  project_id: string;
  user_id: string;
  week_start: string;
  percentage: number | null;
  comment?: string | null;
}
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend && npx tsc -b`
Expected: PASS (the added `comments` field is optional at existing call sites that only read `cells`; existing code does not yet touch `comments`).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/capacity/types/planner.ts
git commit -m "feat(planner): add comments to types"
```

---

## Task 6: Optimistic cache update for comments

**Files:**
- Modify: `frontend/src/modules/capacity/hooks/usePlannerMutations.ts`

- [ ] **Step 1: Edit `updateRowCells`**

Replace the function with:

```ts
function updateRowCells(row: PlannerRow, update: CellUpdate): PlannerRow {
  if (row.project_id !== update.project_id || row.user_id !== update.user_id) return row;
  const cells = { ...row.cells };
  const comments = { ...row.comments };
  if (update.percentage === null) {
    delete cells[update.week_start];
    delete comments[update.week_start];
  } else {
    cells[update.week_start] = update.percentage;
    if (update.comment === null) {
      delete comments[update.week_start];
    } else if (update.comment !== undefined) {
      comments[update.week_start] = update.comment;
    }
  }
  return { ...row, cells, comments };
}
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend && npx tsc -b`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/capacity/hooks/usePlannerMutations.ts
git commit -m "feat(planner): optimistic comment updates"
```

---

## Task 7: `PlannerCommentPopover` component

**Files:**
- Create: `frontend/src/modules/capacity/components/PlannerCommentPopover.tsx`
- Create: `frontend/src/modules/capacity/components/__tests__/PlannerCommentPopover.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/modules/capacity/components/__tests__/PlannerCommentPopover.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PlannerCommentPopover } from '@/modules/capacity/components/PlannerCommentPopover';

function renderOpen(props: Partial<React.ComponentProps<typeof PlannerCommentPopover>> = {}) {
  const onSave = vi.fn();
  const onDelete = vi.fn();
  const onOpenChange = vi.fn();
  render(
    <PlannerCommentPopover
      open
      onOpenChange={onOpenChange}
      comment={props.comment}
      onSave={onSave}
      onDelete={onDelete}
      anchor={<button>anchor</button>}
    />,
  );
  return { onSave, onDelete, onOpenChange };
}

describe('PlannerCommentPopover', () => {
  it('shows Delete only when editing an existing comment', () => {
    renderOpen({ comment: 'Existing' });
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
  });

  it('hides Delete when creating a new comment', () => {
    renderOpen({ comment: undefined });
    expect(screen.queryByRole('button', { name: /delete/i })).toBeNull();
  });

  it('calls onSave with trimmed text', () => {
    const { onSave } = renderOpen();
    const ta = screen.getByRole('textbox');
    fireEvent.change(ta, { target: { value: '  hello  ' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith('hello');
  });

  it('ignores save when text is empty after trim', () => {
    const { onSave, onOpenChange } = renderOpen();
    const ta = screen.getByRole('textbox');
    fireEvent.change(ta, { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    expect(onSave).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('enforces 500 char max in the textarea', () => {
    renderOpen();
    const ta = screen.getByRole('textbox') as HTMLTextAreaElement;
    expect(ta.maxLength).toBe(500);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/modules/capacity/components/__tests__/PlannerCommentPopover.test.tsx`
Expected: FAIL — component does not exist.

- [ ] **Step 3: Create the component**

```tsx
// frontend/src/modules/capacity/components/PlannerCommentPopover.tsx
import { useEffect, useState, type ReactNode } from 'react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import { Button } from '@/shared/components/ui/button';

const MAX_LEN = 500;

interface PlannerCommentPopoverProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly comment?: string;
  readonly onSave: (text: string) => void;
  readonly onDelete?: () => void;
  readonly anchor: ReactNode;
}

export function PlannerCommentPopover({
  open,
  onOpenChange,
  comment,
  onSave,
  onDelete,
  anchor,
}: PlannerCommentPopoverProps): JSX.Element {
  const [draft, setDraft] = useState(comment ?? '');

  useEffect(() => {
    if (open) setDraft(comment ?? '');
  }, [open, comment]);

  const commitSave = (): void => {
    const trimmed = draft.trim();
    if (!trimmed) {
      onOpenChange(false);
      return;
    }
    onSave(trimmed);
    onOpenChange(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      commitSave();
    }
  };

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>{anchor}</PopoverTrigger>
      <PopoverContent className="w-72 p-3" align="start" sideOffset={4}>
        <textarea
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          maxLength={MAX_LEN}
          placeholder="Add a note…"
          className="h-24 w-full resize-none rounded border bg-background p-2 text-sm outline-none focus:ring-1 focus:ring-primary"
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {draft.length} / {MAX_LEN}
          </span>
          <div className="flex gap-2">
            {comment !== undefined && onDelete && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  onDelete();
                  onOpenChange(false);
                }}
              >
                Delete
              </Button>
            )}
            <Button size="sm" onClick={commitSave}>Save</Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/modules/capacity/components/__tests__/PlannerCommentPopover.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/capacity/components/PlannerCommentPopover.tsx frontend/src/modules/capacity/components/__tests__/PlannerCommentPopover.test.tsx
git commit -m "feat(planner): add PlannerCommentPopover component"
```

---

## Task 8: Hover icon + popover in `PlannerCell`

**Files:**
- Modify: `frontend/src/modules/capacity/components/PlannerCell.tsx`
- Create: `frontend/src/modules/capacity/components/__tests__/PlannerCell.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/modules/capacity/components/__tests__/PlannerCell.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PlannerCell } from '@/modules/capacity/components/PlannerCell';

describe('PlannerCell (comments)', () => {
  it('renders the comment icon when comment exists and canComment is true', () => {
    render(
      <PlannerCell
        value={50}
        isOwnRow
        canComment
        comment="hello"
        onChange={() => {}}
        onCommentChange={() => {}}
      />,
    );
    expect(screen.getByRole('button', { name: /comment/i })).toBeInTheDocument();
  });

  it('does not render the comment icon when canComment is false', () => {
    render(
      <PlannerCell
        value={50}
        isOwnRow
        canComment={false}
        comment="hello"
        onChange={() => {}}
        onCommentChange={() => {}}
      />,
    );
    expect(screen.queryByRole('button', { name: /comment/i })).toBeNull();
  });

  it('does not render the comment icon when the cell has no value', () => {
    render(
      <PlannerCell
        value={undefined}
        isOwnRow
        canComment
        onChange={() => {}}
        onCommentChange={() => {}}
      />,
    );
    expect(screen.queryByRole('button', { name: /comment/i })).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/modules/capacity/components/__tests__/PlannerCell.test.tsx`
Expected: FAIL — `canComment`/`comment`/`onCommentChange` props not declared.

- [ ] **Step 3: Extend `PlannerCell`**

Read the full current file first — the component renders a single `<button>` and tracks `editing`/`draft`/`inputRef` state. Do **not** rewrite internals; only **wrap** the existing return and **append** the comment UI.

Add imports at the top of `PlannerCell.tsx`:
```tsx
import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { MessageSquare } from 'lucide-react';
import { PlannerCommentPopover } from '@/modules/capacity/components/PlannerCommentPopover';
```
(Merge with existing `useEffect/useRef/useState` import if duplicated.)

Extend the props interface:
```tsx
interface PlannerCellProps {
  readonly value: number | undefined;
  readonly onChange: (value: number | null) => void;
  readonly isOwnRow: boolean;
  readonly selected?: boolean;
  readonly absence?: boolean;
  readonly canComment?: boolean;
  readonly comment?: string;
  readonly onCommentChange?: (value: string | null) => void;
  readonly onMouseDown?: (e: React.MouseEvent) => void;
  readonly onMouseEnter?: () => void;
}
```

Destructure the new props in the component signature (add `canComment`, `comment`, `onCommentChange`).

Add these derived values near the top of the component body:
```tsx
  const [popoverOpen, setPopoverOpen] = useState(false);
  const showIcon = Boolean(canComment && value !== undefined && onCommentChange);
  const hasComment = comment !== undefined && comment !== '';
```

Wrap the existing return in a `<div className="relative h-full w-full">…</div>` and append the popover + anchor after the existing `<button>`:

```tsx
  return (
    <div className="relative h-full w-full">
      {/* KEEP the existing <button>…</button> exactly as it is today */}
      {showIcon && (
        <PlannerCommentPopover
          open={popoverOpen}
          onOpenChange={setPopoverOpen}
          comment={hasComment ? comment : undefined}
          onSave={(text) => onCommentChange?.(text)}
          onDelete={hasComment ? () => onCommentChange?.(null) : undefined}
          anchor={
            <button
              type="button"
              aria-label={hasComment ? 'Edit comment' : 'Add comment'}
              onClick={(e) => { e.stopPropagation(); setPopoverOpen((v) => !v); }}
              onMouseDown={(e) => e.stopPropagation()}
              className={`absolute right-0.5 top-0.5 rounded p-0.5 transition-opacity ${
                hasComment
                  ? 'opacity-100 text-primary'
                  : 'opacity-0 hover:opacity-100 group-hover/cell:opacity-100 text-muted-foreground'
              }`}
            >
              <MessageSquare className="h-2.5 w-2.5" />
            </button>
          }
        />
      )}
    </div>
  );
```

The `onMouseDown={(e) => e.stopPropagation()}` on the anchor prevents the icon click from triggering drag-select on the parent cell.

The `group-hover/cell` class requires the parent `<td>` to declare `group/cell`. That is added in Task 9 Step 5.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/modules/capacity/components/__tests__/PlannerCell.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/capacity/components/PlannerCell.tsx frontend/src/modules/capacity/components/__tests__/PlannerCell.test.tsx
git commit -m "feat(planner): add comment icon and popover to PlannerCell"
```

---

## Task 9: Wire comments in `PlannerGrid` + overlay

**Files:**
- Modify: `frontend/src/modules/capacity/components/PlannerGrid.tsx`

- [ ] **Step 1: Add `onCommentChange` prop to `PlannerGridProps`**

Keep `onCellChange` signature stable. Add a separate prop for comments:

Add to the `PlannerGridProps` interface:

```ts
  readonly onCommentChange?: (
    projectId: string,
    userId: string,
    week: string,
    comment: string | null,
  ) => void;
```

- [ ] **Step 2: Extend `FlatRow` and flattening**

Replace `FlatRow`'s `cells` line and update the flattening pass to carry comments:

```ts
interface FlatRow {
  _type: 'header' | 'data' | 'add';
  groupId: string;
  groupName: string;
  hasWarning?: boolean;
  user_id?: string;
  user_name?: string;
  functional_area?: string;
  project_id?: string;
  project_name?: string;
  is_absence?: boolean;
  is_other?: boolean;
  cells: Record<string, number>;
  comments?: Record<string, string>;
}
```

In the `flatRows` useMemo, when pushing a `_type: 'data'` row, include:

```ts
          comments: row.comments ?? {},
```

- [ ] **Step 3: Week-header expand icon and state**

Inside the `PlannerGrid` component, after `currentWeekKey`, add:

```ts
  const [expandedWeek, setExpandedWeek] = useState<string | null>(null);

  const weeksWithComments = useMemo(() => {
    const set = new Set<string>();
    if (groupBy !== 'user') return set;
    for (const row of flatRows) {
      if (row._type !== 'data' || !row.comments) continue;
      for (const [week, text] of Object.entries(row.comments)) {
        if (text) set.add(week);
      }
    }
    return set;
  }, [flatRows, groupBy]);

  // Auto-collapse if the expanded week no longer has any visible comments
  useEffect(() => {
    if (expandedWeek && !weeksWithComments.has(expandedWeek)) {
      setExpandedWeek(null);
    }
  }, [expandedWeek, weeksWithComments]);
```

In the `columns` useMemo, replace the week column header render with a header that reads the key and includes the expand icon:

```ts
    const weekCols: ColumnDef<FlatRow>[] = weeks.map((week) => {
      const weekLabel = `W${getISOWeekNumber(week)}`;
      return {
        id: `week_${week}`,
        header: () => (
          <div className="flex items-center gap-1">
            <span>{weekLabel}</span>
            {weeksWithComments.has(week) && (
              <button
                type="button"
                aria-label={`Toggle comments for ${weekLabel}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setExpandedWeek((prev) => (prev === week ? null : week));
                }}
                className={`rounded p-0.5 ${expandedWeek === week ? 'text-primary' : 'text-muted-foreground hover:text-primary'}`}
              >
                <MessageSquare className="h-3 w-3" />
              </button>
            )}
          </div>
        ),
        size: 42,
        cell: () => null,
      };
    });
```

Add the import at the top:
```ts
import { AlertTriangle, MessageSquare, Trash2 } from 'lucide-react';
```

(Replace the existing `import { AlertTriangle, Trash2 } from 'lucide-react';`.)

Then in `useReactTable`'s columns dependency list, add `weeksWithComments` and `expandedWeek`.

- [ ] **Step 4: Grid-level Esc handler adds collapse**

In `handleGridKeyDown`, inside the existing Escape branch, also reset `expandedWeek`:

```ts
      if (e.key === 'Escape') {
        selection.clearSelection();
        setExpandedWeek(null);
        return;
      }
```

- [ ] **Step 5: Pass comment props + overlay to data-row cells**

Wire `canComment`, `comment`, and `onCommentChange` to `<PlannerCell>`. Find the block rendering `<PlannerCell>` inside the data-row mapping and replace it with:

```tsx
                      {isWeekCol && orig._type === 'data' && coord ? (
                        <PlannerCell
                          value={orig.cells[coord.week]}
                          isOwnRow={orig.user_id === authUser?.id}
                          selected={isSelected}
                          absence={orig.is_absence}
                          canComment={groupBy === 'user' && !orig.is_absence && !orig.is_other}
                          comment={orig.comments?.[coord.week]}
                          onCommentChange={(text) =>
                            onCommentChange?.(coord.projectId, coord.userId, coord.week, text)
                          }
                          onChange={(v) =>
                            onCellChange(
                              coord.projectId,
                              coord.userId,
                              coord.week,
                              v,
                            )
                          }
                          onMouseDown={(e) => {
                            selection.handleCellMouseDown(coord, e.shiftKey);
                          }}
                          onMouseEnter={() => {
                            selection.handleCellMouseEnter(coord);
                          }}
                        />
                      ) : (
                        flexRender(cell.column.columnDef.cell, cell.getContext())
                      )}
```

Also add the class `group/cell` to the data-row week `<td>`:

Update the data-row td className where it currently is:
```tsx
                      className={`group/cell px-0 py-0 ${
                        colIdx < 2
                          ? 'sticky left-0 z-10 bg-background px-2'
                          : 'border-l'
                      }`}
```

- [ ] **Step 6: Render overlay inside the row**

Find the `<tr>` for data rows (same `row.getVisibleCells().map(...)` wrapper). Make the `<tr>` `relative` and append the overlay AFTER the cell loop, still inside the `<tr>`:

Change:
```tsx
            return (
              <tr key={row.id} className="group/row border-b hover:bg-muted/10">
                {row.getVisibleCells().map((cell) => { /* …existing… */ })}
              </tr>
            );
```
To:
```tsx
            const commentForExpanded = expandedWeek && orig.comments
              ? orig.comments[expandedWeek]
              : undefined;
            const commentLeft = expandedWeek
              ? 250 + (weeks.indexOf(expandedWeek)) * 42 + 42 // 250 = left sticky cols width, +42 = span past the cell itself
              : 0;
            return (
              <tr key={row.id} className="group/row relative border-b hover:bg-muted/10">
                {row.getVisibleCells().map((cell) => { /* …existing… */ })}
                {commentForExpanded && (
                  <td
                    aria-hidden
                    className="pointer-events-none absolute top-0 flex h-full items-center rounded-sm border px-2 text-xs"
                    style={{
                      left: commentLeft,
                      width: 4 * 42,
                      backgroundColor: isDark
                        ? 'rgba(251,191,36,0.22)'
                        : 'rgba(251,191,36,0.18)',
                      borderColor: '#d97706',
                      zIndex: 15,
                    }}
                    title={commentForExpanded}
                  >
                    <span className="truncate">{commentForExpanded}</span>
                  </td>
                )}
              </tr>
            );
```

**Note on positioning:** 250 is the combined width of the two sticky columns (FA 50px + Name 200px). Each week column is 42px wide. `weeks.indexOf(expandedWeek) * 42` offsets to the start of the commented cell; `+ 42` pushes the overlay to start right of that cell. Width spans 4 columns.

- [ ] **Step 7: Run typecheck + all capacity tests**

Run: `cd frontend && npx tsc -b && npx vitest run src/modules/capacity`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/modules/capacity/components/PlannerGrid.tsx
git commit -m "feat(planner): expand week to view all comments"
```

---

## Task 10: Wire comment callback from `Planner.tsx`

**Files:**
- Modify: `frontend/src/modules/capacity/pages/Planner.tsx`

- [ ] **Step 1: Add `handleCommentChange`**

In `Planner.tsx`, near `handleCellChange`, add:

```tsx
  const handleCommentChange = useCallback(
    (projectId: string, userId: string, week: string, comment: string | null): void => {
      // Look up current percentage for this cell — comment is only allowed when cell has a value
      const row = data?.groups
        .flatMap((g) => g.rows)
        .find((r) => r.project_id === projectId && r.user_id === userId);
      const percentage = row?.cells[week];
      if (percentage === undefined) return;
      queueCellUpdate({
        project_id: projectId,
        user_id: userId,
        week_start: week,
        percentage,
        comment,
      });
    },
    [data, queueCellUpdate],
  );
```

Add `onCommentChange={handleCommentChange}` to the `<PlannerGrid>` JSX.

- [ ] **Step 2: Run typecheck**

Run: `cd frontend && npx tsc -b`
Expected: PASS.

- [ ] **Step 3: Full capacity test run**

Run: `cd frontend && npx vitest run src/modules/capacity`
Expected: PASS.

- [ ] **Step 4: Manual smoke test (required)**

Start dev server, load `/capacity/planner?group=user`:
- Hover a valued cell → comment icon appears top-right.
- Click icon → popover opens with textarea.
- Type a note, Cmd/Ctrl+Enter → popover closes, icon stays visible (solid color).
- Reload page → comment persists.
- Click the icon next to `Wxx` in the header → overlays appear on rows with a comment for that week.
- Esc → overlays collapse.
- Switch to `group=project` → icon and header expand are hidden; underlying data still present.
- Set cell value to 0 / blank → row deleted, comment gone.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/capacity/pages/Planner.tsx
git commit -m "feat(planner): wire comment mutations"
```

---

## Task 11: Regression sweep

**Files:** none (verification only).

- [ ] **Step 1: Backend full suite**

Run: `cd backend && pytest tests/modules/capacity -v`
Expected: PASS (all existing tests + new ones).

- [ ] **Step 2: Frontend full suite**

Run: `cd frontend && npx vitest run`
Expected: PASS.

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: PASS.

---

## Rollback

If the UI is withdrawn, the migration is safe to roll back: `alembic downgrade 053_iso_notes` drops the nullable column. No data loss outside of the comments themselves.
