# Invoice Postponement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to postpone pending invoices with a new date (max 30 days) and reason, tracking full history in a separate table.

**Architecture:** New `invoice_postponements` table with FK to invoices. Effective status logic extended to detect postponed state. Legacy `extended_date` column removed. New KPI card for postponed total.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React, React Query, Tailwind, shadcn/ui

**Spec:** `docs/superpowers/specs/2026-03-21-invoice-postponement-design.md`

---

## Chunk 1: Backend Model, Migration, and Drop Legacy

### Task 1: PostponementDB model

**Files:**
- Create: `backend/app/modules/tracker/models/postponement.py`

- [ ] **Step 1: Create the model file**

```python
"""Invoice postponement history."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class InvoicePostponementDB(Base):
    """One row per postponement action on an invoice."""

    __tablename__ = "invoice_postponements"
    __table_args__ = (
        Index("ix_invoice_postponements_invoice_created", "invoice_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    invoice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    postponed_to: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 2: Verify import works**

Run: `pushd backend > /dev/null && python -c "from app.modules.tracker.models.postponement import InvoicePostponementDB; print('OK')" && popd > /dev/null`

### Task 2: Pydantic schemas for postponements

**Files:**
- Create: `backend/app/modules/tracker/schemas/postponement.py`

- [ ] **Step 1: Create schemas file**

```python
"""Postponement request/response schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PostponeRequest(BaseModel):
    postponed_to: date
    reason: str = Field(..., min_length=1)


class PostponementResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    postponed_to: date
    reason: str
    created_by: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

### Task 3: Alembic migration 027

**Files:**
- Create: `backend/alembic/versions/027_add_invoice_postponements.py`
- Modify: `backend/app/modules/tracker/models/invoice.py`

- [ ] **Step 1: Create migration**

```python
"""Add invoice_postponements table and drop legacy extended_date.

Revision ID: 027_add_invoice_postponements
Revises: 026_add_exchange_rates
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027_add_invoice_postponements"
down_revision: str = "026_add_exchange_rates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoice_postponements",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("postponed_to", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_invoice_postponements_invoice_created",
        "invoice_postponements",
        ["invoice_id", "created_at"],
    )

    # Drop legacy extended_date
    op.drop_constraint("ck_invoices_extended_after_due", "invoices", type_="check")
    op.drop_column("invoices", "extended_date")


def downgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("extended_date", sa.Date(), nullable=True),
    )
    op.create_check_constraint(
        "ck_invoices_extended_after_due",
        "invoices",
        "extended_date IS NULL OR due_date IS NULL OR extended_date >= due_date",
    )
    op.drop_index(
        "ix_invoice_postponements_invoice_created",
        table_name="invoice_postponements",
    )
    op.drop_table("invoice_postponements")
```

- [ ] **Step 2: Remove `extended_date` from InvoiceDB model**

In `backend/app/modules/tracker/models/invoice.py`, remove:
- The `extended_date` mapped column (line 44)
- The check constraint `ck_invoices_extended_after_due` (lines 24-27)

The model should have these `__table_args__`:
```python
__table_args__ = (
    CheckConstraint("amount >= 0", name="ck_invoices_amount_positive"),
    CheckConstraint(
        "status IN ('scheduled', 'pending_to_issue', 'waiting_for_payment', 'paid')",
        name="ck_invoices_status_valid",
    ),
)
```

- [ ] **Step 3: Run migration locally**

Run: `pushd backend > /dev/null && alembic upgrade head && popd > /dev/null`

- [ ] **Step 4: Verify migration**

Run: `pushd backend > /dev/null && python -c "from app.database import sync_engine; from sqlalchemy import inspect; i = inspect(sync_engine); print([c['name'] for c in i.get_columns('invoice_postponements')]); print('extended_date' not in [c['name'] for c in i.get_columns('invoices')])" && popd > /dev/null`

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/tracker/models/postponement.py backend/app/modules/tracker/schemas/postponement.py backend/alembic/versions/027_add_invoice_postponements.py backend/app/modules/tracker/models/invoice.py
git commit -m "feat: add invoice_postponements table, drop legacy extended_date"
```

---

## Chunk 2: Backend API — Postpone Endpoint and Effective Status

### Task 4: Update `_effective_status` and transition logic

**Files:**
- Modify: `backend/app/modules/tracker/api/invoices.py`
- Modify: `backend/app/modules/tracker/schemas/invoice.py`

- [ ] **Step 1: Update ALLOWED_TRANSITIONS in schemas**

In `backend/app/modules/tracker/schemas/invoice.py`, update:

```python
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "scheduled": [],
    "pending_to_issue": ["waiting_for_payment"],
    "postponed": [],
    "waiting_for_payment": ["paid", "pending_to_issue"],
    "paid": ["waiting_for_payment"],
}
```

Also remove `extended_date` from `InvoiceCreate`, `InvoiceUpdate`, and `InvoiceResponse` if present.

- [ ] **Step 2: Update `_effective_status` in invoices.py**

Replace the current `_effective_status` function. The new version needs the DB session to check postponements:

```python
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.tracker.models.postponement import InvoicePostponementDB


async def _effective_status(inv: InvoiceDB, db: AsyncSession) -> str:
    """Compute effective status considering postponements and date auto-promotion."""
    if inv.status in ("scheduled", "pending_to_issue"):
        result = await db.execute(
            select(InvoicePostponementDB.postponed_to)
            .where(InvoicePostponementDB.invoice_id == inv.id)
            .order_by(InvoicePostponementDB.created_at.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        if latest is not None:
            if latest > date.today():
                return "postponed"
            return "pending_to_issue"

    if inv.status == "scheduled" and inv.due_date <= date.today():
        return "pending_to_issue"
    return inv.status
```

- [ ] **Step 3: Update `_to_response` to use async effective status**

```python
async def _to_response(inv: InvoiceDB, db: AsyncSession) -> dict:
    eff = await _effective_status(inv, db)
    return {
        "id": inv.id,
        "project_id": inv.project_id,
        "code": inv.code,
        "amount": float(inv.amount),
        "due_date": inv.due_date,
        "invoiced_on": inv.invoiced_on,
        "milestone": inv.milestone,
        "observations": inv.observations,
        "status": eff,
        "created_at": inv.created_at,
        "updated_at": inv.updated_at,
    }
```

- [ ] **Step 4: Update all endpoint handlers to use async `_to_response` and `_effective_status`**

Every endpoint that calls `_effective_status` or `_to_response` now needs `await` and `db` parameter. Update:
- `list_invoices`: `[await _to_response(inv, db) for inv in invoices]`
- `create_invoice`: `return await _to_response(inv, db)`
- `update_invoice`: `return await _to_response(inv, db)`
- `transition_invoice`: use `await _effective_status(inv, db)` for validation, then `return await _to_response(inv, db)`

- [ ] **Step 5: Block transitions when effective status is `postponed`**

In the `transition_invoice` endpoint, after computing effective status, add check:
```python
eff_status = await _effective_status(inv, db)
if eff_status == "postponed":
    raise HTTPException(status_code=400, detail="Cannot transition a postponed invoice")
```

- [ ] **Step 6: Run existing tests to verify nothing is broken**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/tracker/test_invoices.py -v 2>&1 | tail -20 && popd > /dev/null`

Fix any failures caused by the `extended_date` removal or the async `_effective_status` signature change.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/tracker/api/invoices.py backend/app/modules/tracker/schemas/invoice.py
git commit -m "feat: async effective status with postponement support"
```

### Task 5: Postpone and history endpoints

**Files:**
- Create: `backend/app/modules/tracker/api/postponements.py`
- Modify: `backend/app/modules/tracker/router.py`

- [ ] **Step 1: Create postponements API**

```python
"""Invoice postponement endpoints."""

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.postponement import InvoicePostponementDB
from app.modules.tracker.schemas.postponement import PostponeRequest, PostponementResponse
from app.modules.tracker.api.invoices import _effective_status

router = APIRouter()

MAX_POSTPONE_DAYS = 30


@router.post(
    "/{project_id}/invoices/{invoice_id}/postpone",
    status_code=status.HTTP_201_CREATED,
)
async def postpone_invoice(
    project_id: UUID,
    invoice_id: UUID,
    body: PostponeRequest,
    db: DBSession,
    user: CurrentUser,
) -> PostponementResponse:
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    eff = await _effective_status(inv, db)
    if eff != "pending_to_issue":
        raise HTTPException(status_code=400, detail="Only pending invoices can be postponed")

    # Determine base date
    result = await db.execute(
        select(InvoicePostponementDB.postponed_to)
        .where(InvoicePostponementDB.invoice_id == invoice_id)
        .order_by(InvoicePostponementDB.created_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    base_date = latest if latest is not None else inv.due_date

    if body.postponed_to <= base_date:
        raise HTTPException(
            status_code=400,
            detail=f"New date must be after {base_date}",
        )
    if body.postponed_to > base_date + timedelta(days=MAX_POSTPONE_DAYS):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot postpone more than {MAX_POSTPONE_DAYS} days from {base_date}",
        )

    postponement = InvoicePostponementDB(
        invoice_id=invoice_id,
        postponed_to=body.postponed_to,
        reason=body.reason,
        created_by=user.user_id,
    )
    db.add(postponement)
    await db.commit()
    await db.refresh(postponement)
    return PostponementResponse.model_validate(postponement)


@router.get("/{project_id}/invoices/{invoice_id}/postponements")
async def list_postponements(
    project_id: UUID,
    invoice_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> list[PostponementResponse]:
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    result = await db.execute(
        select(InvoicePostponementDB)
        .where(InvoicePostponementDB.invoice_id == invoice_id)
        .order_by(InvoicePostponementDB.created_at.desc())
    )
    return [PostponementResponse.model_validate(r) for r in result.scalars().all()]
```

- [ ] **Step 2: Mount in router.py**

Add to `backend/app/modules/tracker/router.py`:

```python
from app.modules.tracker.api import postponements as postponements_router

router.include_router(
    postponements_router.router,
    prefix=_PROJECTS_PREFIX,
    tags=["tracker:postponements"],
)
```

- [ ] **Step 3: Run server and test manually**

Run: `pushd backend > /dev/null && python -c "from app.modules.tracker.api.postponements import router; print('Router OK')" && popd > /dev/null`

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/tracker/api/postponements.py backend/app/modules/tracker/router.py
git commit -m "feat: postpone and history endpoints"
```

### Task 6: Write backend tests for postponement

**Files:**
- Create: `backend/tests/modules/tracker/test_postponements.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for invoice postponement feature."""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient


@pytest.fixture
async def setup_invoice(async_client: AsyncClient, setup_user_project):
    """Create a pending invoice for testing postponement."""
    user, project = setup_user_project
    yesterday = date.today() - timedelta(days=1)
    resp = await async_client.post(
        f"/api/tracker/projects/{project.id}/invoices",
        json={
            "amount": 1000,
            "due_date": str(yesterday),
            "milestone": "Test milestone",
        },
    )
    assert resp.status_code == 201
    inv = resp.json()
    assert inv["status"] == "pending_to_issue"
    return user, project, inv


class TestPostponeInvoice:
    async def test_postpone_pending_invoice(self, async_client, setup_invoice):
        _, project, inv = setup_invoice
        new_date = date.today() + timedelta(days=10)
        resp = await async_client.post(
            f"/api/tracker/projects/{project.id}/invoices/{inv['id']}/postpone",
            json={"postponed_to": str(new_date), "reason": "Client delay"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["postponed_to"] == str(new_date)
        assert data["reason"] == "Client delay"

    async def test_effective_status_becomes_postponed(self, async_client, setup_invoice):
        _, project, inv = setup_invoice
        new_date = date.today() + timedelta(days=10)
        await async_client.post(
            f"/api/tracker/projects/{project.id}/invoices/{inv['id']}/postpone",
            json={"postponed_to": str(new_date), "reason": "Delay"},
        )
        resp = await async_client.get(
            f"/api/tracker/projects/{project.id}/invoices"
        )
        found = [i for i in resp.json() if i["id"] == inv["id"]][0]
        assert found["status"] == "postponed"

    async def test_cannot_postpone_non_pending(self, async_client, setup_user_project):
        _, project = setup_user_project
        future = date.today() + timedelta(days=30)
        resp = await async_client.post(
            f"/api/tracker/projects/{project.id}/invoices",
            json={"amount": 500, "due_date": str(future), "milestone": "Future"},
        )
        inv = resp.json()
        assert inv["status"] == "scheduled"
        resp = await async_client.post(
            f"/api/tracker/projects/{project.id}/invoices/{inv['id']}/postpone",
            json={"postponed_to": str(future + timedelta(days=5)), "reason": "Test"},
        )
        assert resp.status_code == 400

    async def test_30_day_hard_limit(self, async_client, setup_invoice):
        _, project, inv = setup_invoice
        too_far = date.today() + timedelta(days=60)
        resp = await async_client.post(
            f"/api/tracker/projects/{project.id}/invoices/{inv['id']}/postpone",
            json={"postponed_to": str(too_far), "reason": "Too far"},
        )
        assert resp.status_code == 400
        assert "30 days" in resp.json()["detail"]

    async def test_new_date_must_be_after_base(self, async_client, setup_invoice):
        _, project, inv = setup_invoice
        past = date.today() - timedelta(days=5)
        resp = await async_client.post(
            f"/api/tracker/projects/{project.id}/invoices/{inv['id']}/postpone",
            json={"postponed_to": str(past), "reason": "Past date"},
        )
        assert resp.status_code == 400

    async def test_serial_postponement_uses_last_date_as_base(self, async_client, setup_invoice):
        _, project, inv = setup_invoice
        first_date = date.today() + timedelta(days=10)
        await async_client.post(
            f"/api/tracker/projects/{project.id}/invoices/{inv['id']}/postpone",
            json={"postponed_to": str(first_date), "reason": "First"},
        )
        # Second postponement: base is now first_date, not due_date
        second_date = first_date + timedelta(days=15)
        resp = await async_client.post(
            f"/api/tracker/projects/{project.id}/invoices/{inv['id']}/postpone",
            json={"postponed_to": str(second_date), "reason": "Second"},
        )
        assert resp.status_code == 201

    async def test_cannot_transition_while_postponed(self, async_client, setup_invoice):
        _, project, inv = setup_invoice
        new_date = date.today() + timedelta(days=10)
        await async_client.post(
            f"/api/tracker/projects/{project.id}/invoices/{inv['id']}/postpone",
            json={"postponed_to": str(new_date), "reason": "Delay"},
        )
        resp = await async_client.post(
            f"/api/tracker/projects/{project.id}/invoices/{inv['id']}/transition",
            json={"status": "waiting_for_payment"},
        )
        assert resp.status_code == 400

    async def test_list_postponements(self, async_client, setup_invoice):
        _, project, inv = setup_invoice
        for i in range(3):
            d = date.today() + timedelta(days=5 + i * 5)
            await async_client.post(
                f"/api/tracker/projects/{project.id}/invoices/{inv['id']}/postpone",
                json={"postponed_to": str(d), "reason": f"Reason {i+1}"},
            )
        resp = await async_client.get(
            f"/api/tracker/projects/{project.id}/invoices/{inv['id']}/postponements"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["reason"] == "Reason 3"  # newest first

    async def test_reason_required(self, async_client, setup_invoice):
        _, project, inv = setup_invoice
        resp = await async_client.post(
            f"/api/tracker/projects/{project.id}/invoices/{inv['id']}/postpone",
            json={"postponed_to": str(date.today() + timedelta(days=5)), "reason": ""},
        )
        assert resp.status_code == 422
```

- [ ] **Step 2: Run tests**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/tracker/test_postponements.py -v 2>&1 | tail -30 && popd > /dev/null`

- [ ] **Step 3: Fix any failures and re-run**

- [ ] **Step 4: Commit**

```bash
git add tests/modules/tracker/test_postponements.py
git commit -m "test: postponement endpoint tests"
```

---

## Chunk 3: Admin Invoices — SQL Effective Status, Response Fields, KPI, Filters

### Task 7: Update admin invoices backend

**Files:**
- Modify: `backend/app/modules/tracker/api/admin_invoices.py`

- [ ] **Step 1: Add postponement subquery and update effective status SQL**

At the top of `list_all_invoices` and `get_invoice_totals`, add the postponement subquery:

```python
from app.modules.tracker.models.postponement import InvoicePostponementDB

# Subquery: latest postponed_to + count per invoice
latest_pp = (
    select(
        InvoicePostponementDB.invoice_id,
        func.max(InvoicePostponementDB.postponed_to).label("postponed_to"),
        func.count().label("postpone_count"),
    )
    .group_by(InvoicePostponementDB.invoice_id)
    .subquery()
)
```

Update the `effective_status` case expression in both endpoints:

```python
effective_status = case(
    (
        InvoiceDB.status.in_(["scheduled", "pending_to_issue"])
        & (latest_pp.c.postponed_to.isnot(None))
        & (latest_pp.c.postponed_to > today),
        literal("postponed"),
    ),
    (
        InvoiceDB.status.in_(["scheduled", "pending_to_issue"])
        & (latest_pp.c.postponed_to.isnot(None))
        & (latest_pp.c.postponed_to <= today),
        literal("pending_to_issue"),
    ),
    (
        (InvoiceDB.status == "scheduled") & (InvoiceDB.due_date <= today),
        literal("pending_to_issue"),
    ),
    else_=InvoiceDB.status,
)
```

Add `.outerjoin(latest_pp, latest_pp.c.invoice_id == InvoiceDB.id)` to the base query.

- [ ] **Step 2: Add `postpone_count` and `postponed_to` to AdminInvoiceResponse**

```python
class AdminInvoiceResponse(BaseModel):
    id: UUID
    project_id: UUID
    project_name: str
    code: str | None
    amount: float
    currency: str
    due_date: dt.date
    invoiced_on: dt.date | None
    milestone: str
    observations: str | None
    status: str
    postpone_count: int
    postponed_to: dt.date | None
```

Remove `extended_date` from the response. Update the items list comprehension to include the new fields from the subquery.

- [ ] **Step 3: Add `postponed` filter logic in `_apply_filters`**

```python
elif status == "postponed":
    stmt = stmt.where(
        InvoiceDB.status.in_(["scheduled", "pending_to_issue"])
        & (latest_pp.c.postponed_to.isnot(None))
        & (latest_pp.c.postponed_to > today)
    )
```

Note: `_apply_filters` will need the `latest_pp` subquery passed as parameter, or the join must be applied before filtering.

- [ ] **Step 4: Update status sort order**

```python
status_order = case(
    {
        "pending_to_issue": 0,
        "postponed": 1,
        "waiting_for_payment": 2,
        "scheduled": 3,
        "paid": 4,
    },
    value=effective_status,
    else_=5,
)
```

- [ ] **Step 5: Add `total_postponed_eur` to totals endpoint**

In `InvoiceTotalsResponse`, add:
```python
total_postponed_eur: float
```

In `get_invoice_totals`, add to the loop:
```python
if eff_status == "postponed":
    total_postponed += eur_amount
```

And return it in the response.

- [ ] **Step 6: Run full backend test suite**

Run: `pushd backend > /dev/null && python -m pytest tests/modules/tracker/ -v 2>&1 | tail -30 && popd > /dev/null`

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/tracker/api/admin_invoices.py
git commit -m "feat: admin invoices with postponement status, filters, KPI"
```

---

## Chunk 4: Frontend — Types, Service, Status Display

### Task 8: Frontend types and service

**Files:**
- Modify: `frontend/src/modules/tracker/types/tracker.ts`
- Modify: `frontend/src/modules/tracker/services/tracker.ts`
- Modify: `frontend/src/core/hooks/queryKeys.ts`

- [ ] **Step 1: Update InvoiceStatus type**

```typescript
export type InvoiceStatus = 'scheduled' | 'pending_to_issue' | 'postponed' | 'waiting_for_payment' | 'paid';
```

- [ ] **Step 2: Remove `extended_date` from Invoice and AdminInvoice interfaces**

Remove `extended_date: string | null;` from both. Add:
```typescript
  postpone_count: number;
  postponed_to: string | null;
```

- [ ] **Step 3: Add PostponementResponse type and update InvoiceTotals**

```typescript
export interface Postponement {
  id: string;
  invoice_id: string;
  postponed_to: string;
  reason: string;
  created_by: string | null;
  created_at: string;
}

export interface InvoiceTotals {
  total_pending_eur: number;
  total_waiting_eur: number;
  total_postponed_eur: number;
  total_current_year_eur: number;
  usd_eur_rate: number | null;
  rate_date: string | null;
}
```

- [ ] **Step 4: Add service methods**

In `tracker.ts`:
```typescript
  postponeInvoice: async (projectId: string, invoiceId: string, data: { postponed_to: string; reason: string }): Promise<Postponement> => {
    const { data: result } = await api.post<Postponement>(
      `/tracker/projects/${projectId}/invoices/${invoiceId}/postpone`,
      data,
    );
    return result;
  },

  listPostponements: async (projectId: string, invoiceId: string): Promise<Postponement[]> => {
    const { data } = await api.get<Postponement[]>(
      `/tracker/projects/${projectId}/invoices/${invoiceId}/postponements`,
    );
    return data;
  },
```

- [ ] **Step 5: Add query keys**

In `queryKeys.ts` under `tracker.invoices`:
```typescript
postponements: (projectId: string, invoiceId: string) =>
  ['tracker', 'invoices', projectId, invoiceId, 'postponements'] as const,
```

- [ ] **Step 6: TypeScript check**

Run: `pushd frontend > /dev/null && npx tsc --noEmit 2>&1 | tail -10 && popd > /dev/null`

Fix all type errors (there will be errors from removed `extended_date`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/modules/tracker/types/tracker.ts frontend/src/modules/tracker/services/tracker.ts frontend/src/core/hooks/queryKeys.ts
git commit -m "feat: frontend types, service, keys for postponement"
```

### Task 9: Update invoice-shared.tsx — status display, postpone button, history

**Files:**
- Modify: `frontend/src/modules/tracker/components/invoice-shared.tsx`

- [ ] **Step 1: Add `postponed` to status maps**

```typescript
export const STATUS_LABELS: Record<InvoiceStatus, string> = {
  scheduled: 'Scheduled',
  pending_to_issue: 'Pending',
  postponed: 'Postponed',
  waiting_for_payment: 'Waiting',
  paid: 'Paid',
};

export const STATUS_DOT_COLORS: Record<InvoiceStatus, string> = {
  scheduled: 'bg-muted-foreground',
  pending_to_issue: 'bg-aux-yellow',
  postponed: 'bg-orange-400',
  waiting_for_payment: 'bg-aux-red',
  paid: 'bg-aux-neon-grass',
};

const NEXT_STATUS: Record<InvoiceStatus, InvoiceStatus | null> = {
  scheduled: null,
  pending_to_issue: 'waiting_for_payment',
  postponed: null,
  waiting_for_payment: 'paid',
  paid: null,
};

const NEXT_LABELS: Record<InvoiceStatus, string> = {
  scheduled: '',
  pending_to_issue: 'Mark waiting',
  postponed: '',
  waiting_for_payment: 'Mark paid',
  paid: '',
};

export const ALLOWED_TRANSITIONS: Record<InvoiceStatus, InvoiceStatus[]> = {
  scheduled: [],
  pending_to_issue: ['waiting_for_payment'],
  postponed: [],
  waiting_for_payment: ['paid', 'pending_to_issue'],
  paid: ['waiting_for_payment'],
};
```

- [ ] **Step 2: Add PostponeButton component**

A CalendarClock icon that opens an AlertDialog with date + reason fields. Uses `e.preventDefault()` on AlertDialogAction for async submit. Only shown when `status === 'pending_to_issue'`.

```typescript
import { CalendarClock, History } from 'lucide-react';
import { Textarea } from '@/shared/components/ui/textarea';

// Add PostponeButton component — shows CalendarClock icon, opens dialog
// on submit: calls trackerApi.postponeInvoice, invalidates queries
```

Implementation: AlertDialog with date input (min/max from due_date/postponed_to + 30), textarea for reason, submit button with `e.preventDefault()` pattern.

- [ ] **Step 3: Add PostponementHistory component**

Inline expandable row showing postponement history. Lazy-loaded on expand via `useQuery` with `enabled: expanded`.

```typescript
// PostponementHistory: shows list of postponements when expanded
// Each row: date, reason, created_at
// Fetched on-demand
```

- [ ] **Step 4: Export new components for use in AdminInvoices and InvoicesCard**

- [ ] **Step 5: TypeScript check and run frontend tests**

Run: `pushd frontend > /dev/null && npx tsc --noEmit 2>&1 | grep -v "ProjectTrackerDetail" && npx vitest run 2>&1 | tail -10 && popd > /dev/null`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/modules/tracker/components/invoice-shared.tsx
git commit -m "feat: postponed status display, postpone button, history component"
```

---

## Chunk 5: Frontend — Admin Invoices and InvoicesCard Integration

### Task 10: Update AdminInvoices page

**Files:**
- Modify: `frontend/src/modules/tracker/pages/AdminInvoices.tsx`

- [ ] **Step 1: Add `Postponed` to status filter buttons**

Add `{ value: 'postponed', label: 'Postponed' }` to the filter array.

- [ ] **Step 2: Add 5th KPI card for Total Postponed**

Update `KpiCards` to include `total_postponed_eur`:
```typescript
const cards = [
  { label: 'Pending', value: totals?.total_pending_eur },
  { label: 'Postponed', value: totals?.total_postponed_eur },
  { label: 'Waiting', value: totals?.total_waiting_eur },
  { label: 'Year Total', value: totals?.total_current_year_eur },
];
```

Update grid: `grid-cols-2 md:grid-cols-5` (5 cards + rate card → use `md:grid-cols-3 lg:grid-cols-5` for responsive).

- [ ] **Step 3: Update InvoiceRow to show postpone button and history**

- Add `PostponeButton` next to StatusCell when `status === 'pending_to_issue'`
- Add History icon when `postpone_count > 0`
- Show `postponed_to` date instead of `due_date` when status is `postponed`
- Add expandable history row below the invoice row

- [ ] **Step 4: Invalidate totals query on postpone success**

When a postpone succeeds, invalidate both the invoice list and totals queries.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/tracker/pages/AdminInvoices.tsx
git commit -m "feat: admin invoices postponed filter, KPI card, inline history"
```

### Task 11: Update InvoicesCard (project detail)

**Files:**
- Modify: `frontend/src/modules/tracker/components/InvoicesCard.tsx`

- [ ] **Step 1: Add postpone button and history to InvoiceRow**

Same pattern as AdminInvoices: PostponeButton on pending, History icon on postponed, expandable history row.

- [ ] **Step 2: Remove `extended_date` references if any**

- [ ] **Step 3: TypeScript check and run all frontend tests**

Run: `pushd frontend > /dev/null && npx tsc --noEmit 2>&1 | grep -v "ProjectTrackerDetail" && npx vitest run 2>&1 | tail -10 && popd > /dev/null`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/tracker/components/InvoicesCard.tsx
git commit -m "feat: project detail invoices with postpone support"
```

### Task 12: Final verification

- [ ] **Step 1: Run full backend test suite**

Run: `pushd backend > /dev/null && python -m pytest -q 2>&1 | tail -10 && popd > /dev/null`
Expected: All tests pass.

- [ ] **Step 2: Run full frontend test suite**

Run: `pushd frontend > /dev/null && npx vitest run 2>&1 | tail -10 && popd > /dev/null`
Expected: All tests pass.

- [ ] **Step 3: TypeScript check**

Run: `pushd frontend > /dev/null && npx tsc --noEmit 2>&1 | grep -c error && popd > /dev/null`
Expected: 0 errors (except pre-existing ProjectTrackerDetail).

- [ ] **Step 4: Final commit if any fixes**

```bash
git add -A && git commit -m "fix: address test failures from postponement feature"
```
