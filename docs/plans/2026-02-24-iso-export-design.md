# ISO Access Review Excel Export — Design

## Context

ISO 27001 audits are annual. Auditors need a self-contained XLSX document covering the full year's access reviews. The export must reflect everything currently visible in the frontend: snapshot totals, review details, diff summary, actions, users, groups, group members, and admins.

## Decisions

- **One file per export request.** Endpoint accepts a date range; all snapshots in range are included as tabs. Single-snapshot export is just a range of one.
- **Full migration to modular architecture.** Move existing scorecard export into `app/modules/scorecard/`, shared helpers into `app/core/services/`, ISO export into `app/modules/iso/`.
- **Frontend entry points:** both snapshots list page (date range picker) and snapshot detail page (single export button).

## XLSX Structure

### Summary tab

One row per snapshot in the date range:

| Snapshot Date | Provider | Total Users | Total Admins | Total Groups | External Members | Review Status | Reviewer | Signed By | Signed Date |
|---|---|---|---|---|---|---|---|---|---|

### Per-snapshot tabs (named `Review YYYY-MM-DD`)

Each tab contains the following sections, separated by blank rows:

**ISO Header block (rows 1-12):**

| Field | Source |
|---|---|
| Organization | `source_metadata.domain` |
| Provider | `snapshot.provider` |
| Snapshot Date | `snapshot.captured_at` |
| Review Scope | `review.scope` |
| Reviewer | User email from `review.reviewer_id` |
| Status | `review.status` |
| Signed By | User email from `review.signed_by` |
| Signed Date | `review.signed_at` |
| Notes | `review.notes` |
| Export Date | Current timestamp |

**Diff Summary table** (if review has `diff_summary`):

| Change Type | Count |
|---|---|
| New Users | N |
| Removed Users | N |
| Role Changes | N |
| New External | N |
| Group Changes | N |

**Actions table** (if review has actions):

| Subject | Type | Change Type | Details | Action Taken | Justification | Exception Until |
|---|---|---|---|---|---|---|

**Users table:**

| Name | Email | Status | Org Unit |
|---|---|---|---|

**Groups table:**

| Name | Email | Members |
|---|---|---|

**Group Members table:**

| Group Email | Member Email | Role | Type |
|---|---|---|---|

**Admins table:**

| Email | Role Name |
|---|---|

## Architecture — Modular Migration

### Shared helpers → `app/core/services/export_helpers.py`

Move from `app/services/export_helpers.py`. Contains:
- Fill/font/border constants (GREEN_FILL, HEADER_FILL, THIN_BORDER, etc.)
- `apply_header_style`, `apply_row_style`, `apply_score_traffic_light`, `apply_indicator_traffic_light`
- `set_column_widths`, `freeze_panes`, `format_month_header`
- `create_methodology_sheet` (scorecard-specific but lives here since it uses shared constants)
- `save_to_bytes` (extracted from ExportService as standalone function)

### Scorecard export → `app/modules/scorecard/`

```
app/modules/scorecard/
├── __init__.py
├── router.py                        # new: aggregates sub-routers
├── services/
│   ├── __init__.py
│   ├── export_service.py            # moved from app/services/export_service.py
│   └── export_definitions.py        # moved from app/services/export_definitions.py
└── api/
    ├── __init__.py
    └── exports.py                   # moved from app/api/exports.py
```

Update `app/main.py` to mount scorecard module router. Keep existing URL prefix (`/exports/...`) via the module router for backward compatibility.

### ISO export → `app/modules/iso/`

```
app/modules/iso/
├── services/
│   └── export_service.py            # new: IsoExportService
└── api/
    └── exports.py                   # new: export endpoints
```

Wire into existing `app/modules/iso/router.py`.

## Backend API

```
GET /iso/exports/snapshots?from=2025-01-01&to=2025-12-31
GET /iso/exports/snapshots/{snapshot_id}
```

Both return XLSX binary (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`). Admin-only. Rate-limited (10/min).

Filename: `iso_access_review_{from}_{to}.xlsx` or `iso_access_review_{snapshot_date}.xlsx`.

### `IsoExportService`

```python
class IsoExportService:
    async def export_snapshots(
        self, db: AsyncSession, snapshot_ids: list[UUID]
    ) -> BytesIO:
        """Generate XLSX with Summary tab + one tab per snapshot."""

    def _write_summary_sheet(self, ws, snapshots_with_reviews): ...
    def _write_snapshot_tab(self, wb, snapshot, review, actions): ...
    def _write_iso_header(self, ws, snapshot, review): ...
    def _write_diff_summary(self, ws, diff_summary): ...
    def _write_actions_table(self, ws, actions): ...
    def _write_users_table(self, ws, users): ...
    def _write_groups_table(self, ws, groups, group_members): ...
    def _write_group_members_table(self, ws, group_members): ...
    def _write_admins_table(self, ws, role_assignments): ...
```

## Frontend

### API layer — `frontend/src/services/api/iso.ts`

Add methods:
```typescript
exportSnapshots(from: string, to: string): Promise<Blob>
exportSnapshot(id: string): Promise<Blob>
```

### Hook — `frontend/src/hooks/useIsoExport.ts`

Reuse the `downloadBlob` pattern from `useExport.ts`. Extract `downloadBlob` to a shared util if not already.

### UI

**Snapshots list page (`ISOSnapshots.tsx`):**
- Year selector (dropdown or date inputs) + "Export" button in the header area

**Snapshot detail page (`ISOSnapshotDetail.tsx`):**
- "Export" button in the header next to the status badge

## Testing

**Backend:**
- `backend/tests/test_iso_exports.py` — endpoint tests (date range, single snapshot, empty range, admin-only)
- `backend/tests/test_iso_export_service.py` — unit tests for sheet generation (header fields, table contents, tab naming)

**Frontend:**
- Test export buttons render and trigger API calls
- Test hook state management (isExporting, error)

## Migration verification

After moving scorecard files:
- `cd backend && pytest tests/test_exports.py -v` — existing export tests still pass
- `cd backend && pytest` — full suite passes
- `cd frontend && npm test -- --run` — all frontend tests pass
