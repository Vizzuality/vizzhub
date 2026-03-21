# Invoice Postponement Feature

## Overview

Allow users to postpone pending invoices by proposing a new date (max 30 days from last date) with a reason. Each postponement is tracked as a separate record, building a full history. Postponed invoices automatically return to pending when the new date arrives.

## Data Model

### New table: `invoice_postponements`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK, default uuid4 |
| invoice_id | UUID | FK → invoices (CASCADE), NOT NULL |
| postponed_to | date | NOT NULL |
| reason | text | NOT NULL |
| created_by | UUID | FK → users (SET NULL), nullable (for future roles) |
| created_at | timestamptz | server_default now() |

Index: `(invoice_id, created_at DESC)` for fast latest-postponement lookups.

No changes to `InvoiceDB` — `due_date` stays intact as the original issue date.

### Drop legacy `extended_date` column

The existing `extended_date` column on `InvoiceDB` is a legacy field from VizzTracker, semantically replaced by the postponements table. Remove it in the same migration (027):
- Drop column `extended_date` from `invoices` table
- Drop check constraint `ck_invoices_extended_after_due`
- Remove from `InvoiceDB` model, frontend types, and any references

### Effective status logic

Current logic: `scheduled + due_date <= today → pending_to_issue`.

Extended logic (evaluated in order):
1. If stored status is `scheduled` or `pending_to_issue`, and invoice has postponements, and latest `postponed_to > today` → `"postponed"`
2. If stored status is `scheduled` or `pending_to_issue`, and invoice has postponements, and latest `postponed_to <= today` → `"pending_to_issue"`
3. If `status == "scheduled"` and `due_date <= today` → `"pending_to_issue"`
4. Otherwise → stored `status`

The guard on stored status (rule 1-2) ensures that if an invoice has already been transitioned forward to `waiting_for_payment` or `paid`, old postponement records don't override that.

This applies in:
- `_effective_status()` in `invoices.py` (per-project endpoints — needs DB query for postponements)
- The SQL `case()` expression in `admin_invoices.py` (join to subquery)
- The `/totals` endpoint effective status expression (same subquery)

### 30-day hard limit

- Base date = latest `postponed_to` if postponements exist, else `due_date`
- New date must satisfy: `base_date < new_date <= base_date + 30 days`
- Enforced server-side; frontend shows the limit in the UI

## API

### POST `/tracker/projects/{project_id}/invoices/{invoice_id}/postpone`

**Body:**
```json
{
  "postponed_to": "2026-04-15",
  "reason": "Client requested delay"
}
```

**Validations:**
- Invoice exists and belongs to project → 404
- Effective status is `pending_to_issue` → 400 "Only pending invoices can be postponed"
- `reason` is non-empty → 422
- `postponed_to > base_date` → 400 "New date must be after {base_date}"
- `postponed_to <= base_date + 30` → 400 "Cannot postpone more than 30 days from {base_date}"

**Response:** `PostponementResponse` (the created record) + HTTP 201

### GET `/tracker/projects/{project_id}/invoices/{invoice_id}/postponements`

Returns list of all postponements for the invoice, ordered by `created_at DESC`.

**Response:** `list[PostponementResponse]`

### Modified responses

`AdminInvoiceResponse` and per-project invoice responses gain:
- `postpone_count: int` — number of postponements (0 if never postponed)
- `postponed_to: date | null` — latest postponed_to if currently postponed, else null

The `status` field (effective status) can now return `"postponed"`.

### State machine update

```
scheduled ──(due_date passes)──→ pending_to_issue ──→ waiting_for_payment ──→ paid
                                       │       ↑
                                       ↓       │
                                   postponed ──(postponed_to passes)
```

- `pending_to_issue` → `postponed`: via POST /postpone endpoint
- `postponed` → `pending_to_issue`: automatic when `postponed_to <= today`
- `postponed` has no direct manual transition — must wait for date to pass

**ALLOWED_TRANSITIONS update:**
```python
ALLOWED_TRANSITIONS = {
    "scheduled": [],
    "pending_to_issue": ["waiting_for_payment"],
    "postponed": [],  # no manual transitions; auto-returns to pending
    "waiting_for_payment": ["paid"],
    "paid": [],
}
```

The transition endpoint must also reject transitions when effective status is `postponed` (even though stored status may be `scheduled` or `pending_to_issue`).

## Frontend

### Type updates

Add `'postponed'` to `InvoiceStatus` union type in `tracker.ts`. This is used as key type for `STATUS_LABELS`, `STATUS_DOT_COLORS`, `NEXT_STATUS`, and `ALLOWED_TRANSITIONS`.

### Status display

- New `postponed` status in `STATUS_LABELS` ("Postponed") and `STATUS_DOT_COLORS` (`bg-aux-amber` or similar amber/orange)
- Status sort order (integer): pending(0) → postponed(1) → waiting(2) → scheduled(3) → paid(4)
- No transition button from `postponed` — user must wait for date

### Postpone action

- When effective status is `pending_to_issue`, a CalendarClock icon appears next to the status transition button
- Clicking opens an AlertDialog with:
  - Date input (min: base_date + 1, max: base_date + 30)
  - Textarea for reason
  - Shows: "Base date: {date}" and "Limit: {date + 30}"
  - "Postpone" button — uses `e.preventDefault()` on AlertDialogAction to prevent auto-close, calls API, then explicitly closes on success (Radix AlertDialogAction gotcha)

### Postponement history indicator

- If `postpone_count > 0`: small History icon next to status text
- Clicking expands an inline row below the invoice row showing the postponement timeline:
  - Each entry: `postponed_to` date, reason, `created_at` timestamp
  - Ordered newest first
  - Fetched on-demand (lazy load when expanded)
- When collapsed, the listing looks identical to non-postponed invoices (plus the subtle icon)

### Admin invoices page

- `postponed` added to status filter buttons
- Filter SQL logic for `postponed`: join to latest postponement subquery, filter where `lp.postponed_to > today` and stored status in `('scheduled', 'pending_to_issue')`
- When postponed: shows `postponed_to` date instead of `due_date` in the Due column
- KPI cards: 5th card added — **Total Postponed (EUR)**, same EUR-normalized logic as the other totals. Postponed invoices don't count in pending or waiting totals. The `/totals` endpoint returns a new `total_postponed_eur` field.

### InvoicesCard (project detail)

- Same behavior: postpone icon on pending, history expandible, postponed dot color
- Responsive rules follow existing pattern (history row spans all visible columns)

### Admin invoices effective status in SQL

The `case()` expression in admin_invoices needs a subquery to check latest postponement:

```sql
-- Subquery: latest postponed_to per invoice
latest_postponement = (
    SELECT invoice_id, MAX(postponed_to) as postponed_to, COUNT(*) as cnt
    FROM invoice_postponements
    GROUP BY invoice_id
)

-- Effective status with postponement (guard: only for pre-transition statuses)
CASE
  WHEN status IN ('scheduled', 'pending_to_issue')
    AND lp.postponed_to IS NOT NULL AND lp.postponed_to > today THEN 'postponed'
  WHEN status IN ('scheduled', 'pending_to_issue')
    AND lp.postponed_to IS NOT NULL AND lp.postponed_to <= today THEN 'pending_to_issue'
  WHEN status = 'scheduled' AND due_date <= today THEN 'pending_to_issue'
  ELSE status
END
```

The same subquery provides `cnt` as `postpone_count` and `postponed_to` for the response fields.

## Files affected

### Backend (new)
- `app/modules/tracker/models/postponement.py` — PostponementDB model
- `app/modules/tracker/schemas/postponement.py` — Pydantic schemas
- `app/modules/tracker/api/postponements.py` — API endpoints
- `alembic/versions/027_add_invoice_postponements.py`

### Backend (modified)
- `app/modules/tracker/models/invoice.py` — drop `extended_date` column
- `app/modules/tracker/api/invoices.py` — update `_effective_status()`, block transitions when postponed
- `app/modules/tracker/api/admin_invoices.py` — update SQL effective status + filters + totals + `total_postponed_eur`, add response fields, remove `extended_date`
- `app/modules/tracker/schemas/invoice.py` — add `postpone_count`, `postponed_to` to response schemas, update `ALLOWED_TRANSITIONS`, remove `extended_date`
- `app/modules/tracker/router.py` — mount postponements sub-router

### Frontend (modified)
- `src/modules/tracker/types/tracker.ts` — add `'postponed'` to `InvoiceStatus`, add postponement types
- `src/modules/tracker/services/tracker.ts` — add API calls
- `src/core/hooks/queryKeys.ts` — add postponement keys
- `src/modules/tracker/components/invoice-shared.tsx` — postponed status, postpone button, history expandable
- `src/modules/tracker/pages/AdminInvoices.tsx` — filter, sort, display
- `src/modules/tracker/components/InvoicesCard.tsx` — same changes as admin

## Out of scope

- Role-based permissions (future hub-wide change)
- Alert triggers based on postponement (mentioned as future use case)
- Bulk postponement
- Undo/cancel a postponement (once postponed, wait for date or let it expire)
