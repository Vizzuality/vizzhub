# Projects UI Design

## Context

With 394 projects now in the database (391 imported from VizzTracker + 3 existing), the platform needs a central Projects view independent of scorecard. Not all projects have scorecard data, and tracker data is coming. Projects is a core entity that all modules reference.

## Data Model Changes

### Status enum migration

Replace `in_progress`/`finished` with `proposal`/`live`/`finished`:

| Old value | New value | UI label |
|-----------|-----------|----------|
| (new default) | `proposal` | Proposal |
| `in_progress` | `live` | Live |
| `finished` | `finished` | Finished |

- Alembic migration updates existing rows: `in_progress` → `live`
- Default on create: `proposal`
- `code` field: required on create via Pydantic validation (`str = Field(..., min_length=1)`), but DB column stays nullable for legacy data with NULL codes

## Routes

| Route | Access | Purpose |
|-------|--------|---------|
| `/projects` | All users | Project listing with filters, sort, search |
| `/projects/new` | Admin only (403 otherwise) | Create project form |
| `/projects/:id/edit` | Admin only (403 otherwise) | Edit project form |
| `/` | All users | Redirects to `/projects` |

Existing scorecard routes (`/scorecard`, `/scorecard/:id`) remain unchanged for now. Long-term, the scorecard list at `/scorecard` will focus only on scored projects and link to `/projects` for management. The create form in scorecard will be removed once `/projects/new` is live.

## Sidebar

Add "Projects" as first item, visible to all users:

1. **Projects** (new, all users)
2. Scorecard
3. Global Scores (admin)
4. ISO (admin)
5. Administration (admin)

## Projects Index (`/projects`)

### Filters & Search

Same pattern as current scorecard list:
- **Search**: by name and code, debounce 300ms
- **Status filter**: All | Proposal | Live | Finished (toggle buttons)
- **Date range**: start date from/to
- **Clear filters** button when active

### Sort

- Name (default asc)
- Created (default desc)
- Status

All server-side.

### Views

List and Grid toggle (persisted to localStorage — accepted exception to URL-as-source-of-truth rule, consistent with existing scorecard behavior).

### Pagination

Server-side, page_size=45, same pattern.

### Project Card

Each card displays:
- **Name**
- **Status badge**: Proposal (yellow), Live (blue), Finished (green)
- **Code**
- **Is Billable** indicator
- **Program name** (if belongs to one — resolved via JOIN in the list endpoint, returned as `program_name` in the response)
- **Jira project key** (if set)
- **GitHub repository** (if set)
- **Date range** (if set)
- **Score** (from scorecard, if has data)
- **Burn %** (from tracker, if has data)
- **Action links**: Scorecard | Tracker (future) | Edit (admin only)

### Create Button

Visible only for admins. Navigates to `/projects/new`.

## Project Form (`/projects/new` and `/projects/:id/edit`)

Same component, two modes (create vs edit).

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Name | text input | Yes | |
| Code | text input | Yes | Company-wide manual ID |
| Status | select | Yes | Proposal / Live / Finished |
| Is Billable | checkbox/toggle | Yes | Default: true |
| Currency | select | No | Dollar / Euro |
| Program | select | No | From `GET /api/programs` (lightweight list) |
| Jira Project Key | text input | No | e.g., "PROJ" |
| GitHub Repository | text input | No | Validates `owner/repo` format |
| Slack Channel | combobox | No | Disabled if Slack not configured |
| Start Date | date input | No | |
| End Date | date input | No | Must be >= start date |
| Notes | textarea | No | |
| Summary | textarea | No | |

### Actions

- **Save / Create** (primary button)
- **Cancel** (navigates back to `/projects`)
- **Delete** (edit only, admin only, with confirmation dialog)
- **Mark as Finished / Reopen** (status shortcuts, edit only)

### Permissions

- Admin only. Non-admin navigating to these routes sees 403 page.

## Backend

### API prefix migration

The current project endpoints live at `/api/scorecards` (mounted in `main.py`). This spec introduces `/api/projects` as a new router in `app/core/api/projects.py`. The old `/api/scorecards` prefix stays for now (scorecard frontend uses it). Migration path:
1. Create new `/api/projects` router with all project CRUD operations
2. Scorecard frontend gradually migrates to `/api/projects`
3. Once migrated, deprecate `/api/scorecards` project endpoints

### New endpoints (`/api/projects`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/projects` | CurrentUser | List projects (paginated, filtered, sorted) |
| POST | `/api/projects` | AdminUser | Create project |
| GET | `/api/projects/:id` | CurrentUser | Get project detail |
| PUT | `/api/projects/:id` | AdminUser | Update project (full replace, all fields) |
| DELETE | `/api/projects/:id` | AdminUser | Delete project |

Same query params for list: `page`, `page_size`, `search`, `status`, `sort`, `order`, `from`, `to`.

**Important**: The new endpoints must persist ALL project fields (name, code, program_id, is_billable, currency, notes, summary, jira_project_key, github_repo, start_date, end_date, status, finished_at, slack_channel_id). The existing `/api/scorecards` handlers only persist 6 fields — the new router must not repeat this bug.

**Permission changes**: New endpoints use `AdminUser` for write operations. Existing `/api/scorecards` endpoints remain unchanged to avoid breaking scorecard UI.

### Programs endpoint

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/programs` | CurrentUser | List all programs (lightweight: id + name) |

Simple endpoint to populate the Program dropdown in the project form. No CRUD for programs via API (managed by import script).

### Batch burn endpoint

`POST /api/tracker/burn/batch` — accepts list of project IDs, returns burn percentage per project. Same pattern as `POST /api/scores/batch` in scorecard. Cached like scorecard scores.

**Note**: This requires scaffolding the tracker module's API layer (router.py, a minimal service). Only the burn batch endpoint is needed now; full tracker CRUD comes later.

### List response schema

The list endpoint returns `program_name` (resolved via LEFT JOIN to programs table) alongside `program_id`, so the frontend doesn't need a separate lookup.

### Status filter validation

The backend `list_projects` filter must accept the new enum values (`proposal`, `live`, `finished`) instead of the old (`in_progress`, `finished`).

### Delete cascade

On project deletion, the following related records must be cleaned up:
- `metrics` (no CASCADE FK — must delete manually, same as current behavior)
- `scores` (CASCADE)
- `tracker_project_settings` (CASCADE)
- `budget_lines` (CASCADE)
- `invoices` (CASCADE)
- `non_staff_costs` (CASCADE)
- `report_parts` (RESTRICT — cannot delete project with time data)
- `progress_reports` (RESTRICT — cannot delete project with progress data)
- `links` with project_id (CASCADE)

If report_parts or progress_reports exist, deletion must be blocked with a clear error message.

### Frontend type updates

The `Project` type at `src/core/types/project.ts` must be extended with: `code`, `program_id`, `program_name`, `is_billable`, `currency`, `notes`, `summary`. The `ProjectStatus` enum must be updated to `proposal`/`live`/`finished`.

### Status migration

Alembic migration:
1. `UPDATE projects SET status = 'live' WHERE status = 'in_progress'`
2. Update `ProjectStatus` enum in Python code
3. Update scorecard frontend status filters to accept new values
4. Update default status from `in_progress` to `proposal`

## Future step (separate task)

Move Budget & Schedule (EVM: budget_total, cost_to_date, percent_completed, percent_planned) and Milestones from scorecard edit to `/projects/:id/edit`. These belong naturally to the project/tracker domain, not scorecard metrics. Done last to minimize disruption.

## Dependencies

- Core schema (T1.1) — already done, fields exist in DB
- Tracker module schema (T1.2) — already done, tracker_project_settings exists
- Data import (T1.3) — already done, projects have data

## Implementation order

1. Backend: status migration (Alembic) + `ProjectStatus` enum update
2. Backend: new `/api/projects` endpoints + `/api/programs` endpoint
3. Frontend: update `Project` type + `ProjectStatus` enum
4. Frontend: sidebar + routes + Projects index page
5. Frontend: Project form (create/edit) with 403 for non-admin
6. Update scorecard frontend to use new status values in filters
7. Backend: batch burn endpoint (minimal tracker API scaffolding)
8. Frontend: integrate burn % in project cards
9. (Future) Move budget/milestones from scorecard to projects edit
