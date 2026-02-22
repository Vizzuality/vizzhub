# ISO Module: Google Workspace Access Review Collector

**Date**: 2026-02-22
**Status**: Design approved
**Module**: `app/modules/iso/` (first module in modular architecture)

## Purpose

Monthly automated snapshots of privileged access in Google Workspace, with diff engine and human review workflow. Provides audit-ready evidence for ISO 27001:2022 controls A.5.18 (Access rights), A.8.2 (Privileged access rights), and A.8.3 (Information access restriction).

## Scope

### What we automate
1. Capture snapshot: users, groups, group members, admin role assignments
2. Calculate summary with key audit metrics
3. Compare with previous snapshot and generate diff
4. Pre-populate review actions for human review

### What stays manual (human process)
- Justification of changes
- Action decisions (accept, remove, correct, exception)
- Approval and sign-off

### What we exclude (not MVP)
- Nested/transitive group memberships
- Last login / last activity (unreliable via Directory API alone)
- MFA checks (enrolled vs enforced, factor types) — add in future iteration
- Automated approval workflows
- PDF/export generation

---

## Authentication

OAuth with admin account (same pattern as Jira). The admin's domain privileges provide full directory read access without requiring a separate Service Account or Domain-Wide Delegation JSON key.

- **Provider**: `"google_workspace"` in `OAuthTokenDB`
- **Scopes**: `admin.directory.user.readonly`, `admin.directory.group.readonly`, `admin.directory.group.member.readonly`, `admin.directory.rolemanagement.readonly`
- **Flow**: Admin connects from ISO admin UI, consents to scopes, token stored and auto-refreshed
- **Separate from SSO**: Login uses profile scopes only. Directory scopes requested only when admin connects the collector.
- **Domain config**: Stored in admin UI (needed to detect external members)

---

## Data Model

### access_snapshots

| Column | Type | Description |
|---|---|---|
| id | UUID PK | |
| provider | String, NOT NULL | `"google_workspace"` |
| captured_at | DateTime(tz), NOT NULL | When the capture ran |
| captured_by | UUID FK -> users, nullable | Who triggered it (null if cron) |
| data_version | String, NOT NULL, default "1" | Schema version of the JSON in `data` |
| source_metadata | JSONB, NOT NULL, default `{}` | Reproducibility: domain, collector version, scopes, run_mode |
| data | JSONB, NOT NULL | Raw snapshot (users, groups, group_members, role_assignments) |
| summary | JSONB, NOT NULL | Pre-calculated audit metrics |
| created_at | DateTime(tz) | |

### access_reviews

| Column | Type | Description |
|---|---|---|
| id | UUID PK | |
| snapshot_id | UUID FK -> access_snapshots, NOT NULL | Snapshot under review |
| previous_snapshot_id | UUID FK -> access_snapshots, nullable | Comparison baseline (null if first) |
| reviewer_id | UUID FK -> users, NOT NULL | Default: first admin, selectable |
| status | Enum(`draft`, `completed`, `signed`), NOT NULL | |
| scope | String, NOT NULL | e.g. "All users and groups" |
| diff_summary | JSONB, nullable | Auto-calculated changes summary |
| notes | Text, nullable | Reviewer's general observations |
| signed_by | UUID FK -> users, nullable | Who signed the review |
| signed_at | DateTime(tz), nullable | When it was signed |
| created_at | DateTime(tz) | |
| updated_at | DateTime(tz) | |

### access_review_actions

| Column | Type | Description |
|---|---|---|
| id | UUID PK | |
| review_id | UUID FK -> access_reviews, NOT NULL | |
| subject_type | Enum(`user`, `group`), NOT NULL | What the change is about |
| subject_id | String, NOT NULL | Email of user or group |
| subject_label | String, nullable | Display name for reports |
| change_type | Enum, NOT NULL | See change types below |
| previous_value | JSONB, nullable | Structured previous state |
| current_value | JSONB, nullable | Structured current state |
| action_taken | Enum(`accepted`, `removed`, `corrected`, `exception`), nullable | Human decision |
| justification | Text, nullable | Human explanation |
| approved_by | UUID FK -> users, nullable | Who approved this action |
| exception_until | Date, nullable | Temporary exception expiry |
| created_at | DateTime(tz) | |
| updated_at | DateTime(tz) | |

### Change types (stable, minimal set)

| Type | Subject | Description |
|---|---|---|
| `new_user` | user | User exists in current but not previous |
| `removed_user` | user | User exists in previous but not current |
| `role_change` | user | Admin status changed (covers new_admin / admin_removed) |
| `new_external` | group | External member added to a group |
| `group_membership_change` | group | Members added or removed from a group |

---

## Snapshot Data Structure

### data (JSONB)

```json
{
  "users": [
    {
      "id": "google-user-id",
      "email": "maria@empresa.com",
      "name": "Maria Lopez",
      "suspended": false,
      "org_unit_path": "/Engineering"
    }
  ],
  "groups": [
    {
      "id": "google-group-id",
      "email": "devops@empresa.com",
      "name": "DevOps Team"
    }
  ],
  "group_members": {
    "devops@empresa.com": [
      {
        "email": "maria@empresa.com",
        "role": "OWNER",
        "type": "USER"
      },
      {
        "email": "external@vendor.com",
        "role": "MEMBER",
        "type": "USER"
      }
    ]
  },
  "role_assignments": [
    {
      "user_id": "google-user-id",
      "user_email": "maria@empresa.com",
      "role_id": "role-id",
      "role_name": "Super Admin"
    }
  ]
}
```

### summary (JSONB)

```json
{
  "total_users": 45,
  "active_users": 42,
  "suspended_users": 3,
  "total_admins": 4,
  "external_members": 3,
  "total_groups": 12
}
```

### source_metadata (JSONB)

```json
{
  "domain": "empresa.com",
  "collector": "google_workspace",
  "collector_version": "1",
  "scopes": ["admin.directory.user.readonly", "admin.directory.group.readonly", "admin.directory.group.member.readonly", "admin.directory.rolemanagement.readonly"],
  "run_mode": "manual"
}
```

---

## Collector Logic

### APIs used (all read-only, paginated)

| Data | API | Key fields |
|---|---|---|
| Users | `directory.users.list` | primaryEmail, name.fullName, suspended, orgUnitPath |
| Groups | `directory.groups.list` | email, name |
| Group members | `directory.members.list` (per group) | email, role, type |
| Admin roles | `directory.roleAssignments.list` + `directory.roles.list` | assignedTo, roleId, roleName |

### Admin detection

Do NOT rely on `isAdmin` flag. Derive admin status from `roleAssignments`:
- `admin_user_ids = set(assignedTo from roleAssignments)`
- Map to emails using captured users list

---

## Diff Engine

Deterministic comparison between current snapshot (S) and previous snapshot (P).

### Rules

**Users** (by email):
- In S but not P -> `new_user`
- In P but not S -> `removed_user`

**Admins** (derived from role_assignments, by email):
- In S but not P -> `role_change` with `previous_value: {"is_admin": false}`, `current_value: {"is_admin": true}`
- In P but not S -> `role_change` with `previous_value: {"is_admin": true}`, `current_value: {"is_admin": false}`

**Group membership** (per group, by member email):
- Added or removed members -> `group_membership_change` with `current_value: {"added": [...], "removed": [...]}`

**External members** (email domain != configured domain):
- New external member in any group -> `new_external` with `current_value: {"external_added": [...]}`

---

## Automated Flow

### On snapshot capture (manual or cron):

1. Collector fetches data from Google Workspace APIs
2. Build `data` JSON + calculate `summary`
3. Insert `access_snapshots` row
4. Find most recent previous snapshot for same provider
5. Create `access_reviews` in `draft` status, link both snapshots, assign default reviewer (first app admin, selectable)
6. Run diff engine on current vs previous
7. Store `diff_summary` on the review
8. Insert `access_review_actions` pre-populated with detected changes (no justification/action yet)

### Human review:

1. Reviewer opens draft review in UI
2. Sees: snapshot summary, full user/group state, diff table
3. For each detected change: fills justification, selects action, optionally assigns approver
4. Adds general notes
5. Marks as `completed`, then `signed` (sets `signed_by` + `signed_at`)

---

## Execution Modes

- **Manual**: Admin clicks "Capture snapshot" in ISO UI. Runs synchronously or as background job.
- **Cron**: ARQ worker job, monthly (1st of month). Configurable frequency.
- **Both available from MVP**. Cron ensures no month is missed. Manual for on-demand captures.
- **Failure alerts**: If the cron job fails (OAuth token expired, API error, etc.), notify via Slack (reusing existing Slack integration) and log a structured error. The ISO dashboard shows last successful capture date so missing months are visible.

Multiple snapshots per month allowed. Monthly reports use the most recent snapshot within each month.

---

## Module Structure

```
app/modules/iso/
  __init__.py
  router.py                    # Aggregates sub-routers, mounted in main.py
  models/
    __init__.py
    access_snapshot.py         # AccessSnapshotDB
    access_review.py           # AccessReviewDB, AccessReviewActionDB
  services/
    __init__.py
    collectors/
      __init__.py
      google_workspace.py      # GoogleWorkspaceCollector
    diff_engine.py             # Compare two snapshots, generate actions
  api/
    __init__.py
    snapshots.py               # POST capture, GET list/detail
    reviews.py                 # GET list/detail, PATCH update actions, POST sign
    config.py                  # GET/PUT provider config (domain, OAuth status)
  public.py                    # Cross-module interface (future)

src/modules/iso/
  components/                  # UI components
  hooks/                       # Data fetching
  pages/                       # Routes
```

---

## API Endpoints (Backend)

### Snapshots
- `POST /api/iso/snapshots/capture` — Trigger manual capture (provider param)
- `GET /api/iso/snapshots` — List snapshots (paginated, filterable by provider)
- `GET /api/iso/snapshots/{id}` — Snapshot detail with full data

### Reviews
- `GET /api/iso/reviews` — List reviews (paginated, filterable by status)
- `GET /api/iso/reviews/{id}` — Review detail with actions and diff
- `PATCH /api/iso/reviews/{id}` — Update review (notes, reviewer_id)
- `PATCH /api/iso/reviews/{id}/actions/{action_id}` — Update action (justification, action_taken, etc.)
- `POST /api/iso/reviews/{id}/sign` — Sign and close the review

### Config
- `GET /api/iso/config/google-workspace` — OAuth status, configured domain
- `POST /api/iso/config/google-workspace/connect` — Initiate OAuth flow
- `GET /api/iso/config/google-workspace/callback` — OAuth callback
- `DELETE /api/iso/config/google-workspace/disconnect` — Remove token

---

## Dependencies

- `google-api-python-client` — Google Admin SDK
- `google-auth` + `google-auth-oauthlib` — OAuth flow
- Existing: SQLAlchemy, Pydantic, ARQ worker, Redis (optional)

---

## Implementation Subtasks

### Phase 1: Foundation (module scaffold + data model)

- [ ] **1.1** Create `app/modules/iso/` directory structure with `__init__.py` files
- [ ] **1.2** Create `router.py` that aggregates sub-routers
- [ ] **1.3** Mount ISO router in `main.py` under `/api/iso`
- [ ] **1.4** Create SQLAlchemy model `AccessSnapshotDB` (id, provider, captured_at, captured_by, data_version, source_metadata, data, summary, created_at)
- [ ] **1.5** Create SQLAlchemy model `AccessReviewDB` (id, snapshot_id, previous_snapshot_id, reviewer_id, status, scope, diff_summary, notes, signed_by, signed_at, created_at, updated_at)
- [ ] **1.6** Create SQLAlchemy model `AccessReviewActionDB` (id, review_id, subject_type, subject_id, subject_label, change_type, previous_value, current_value, action_taken, justification, approved_by, exception_until, created_at, updated_at)
- [ ] **1.7** Create Pydantic schemas for all models (create, update, response)
- [ ] **1.8** Create and run Alembic migration for the 3 tables
- [ ] **1.9** Add `google-api-python-client`, `google-auth`, `google-auth-oauthlib` to backend dependencies
- [ ] **1.10** Write unit tests for models and schemas

### Phase 2: OAuth for Google Workspace

- [ ] **2.1** Add Google Workspace OAuth config to `app/config.py` (client_id, client_secret, redirect_uri env vars)
- [ ] **2.2** Create `api/config.py` endpoints: GET status, POST connect (initiate OAuth), GET callback, DELETE disconnect
- [ ] **2.3** Implement OAuth flow: generate state, redirect to Google consent with Directory API scopes, exchange code for token
- [ ] **2.4** Store token in `OAuthTokenDB` with provider `"google_workspace"`
- [ ] **2.5** Implement token refresh logic (reuse `OAuthService` pattern from Jira)
- [ ] **2.6** Add domain configuration (stored alongside OAuth config or in a separate ISO config table)
- [ ] **2.7** Write integration tests for OAuth flow (mocked Google responses)

### Phase 3: Google Workspace Collector

- [ ] **3.1** Create `services/collectors/google_workspace.py` with `GoogleWorkspaceCollector` class
- [ ] **3.2** Implement `collect_users()` — paginated `users.list`, extract fields (email, name, suspended, orgUnitPath)
- [ ] **3.3** Implement `collect_groups()` — paginated `groups.list`, extract fields (email, name)
- [ ] **3.4** Implement `collect_group_members()` — for each group, paginated `members.list` (email, role, type)
- [ ] **3.5** Implement `collect_role_assignments()` — paginated `roleAssignments.list` + `roles.list` for name mapping
- [ ] **3.6** Implement `build_snapshot()` — orchestrates all collectors, builds `data` JSON
- [ ] **3.7** Implement `build_summary()` — calculates total_users, active_users, suspended_users, total_admins, external_members, total_groups from snapshot data
- [ ] **3.8** Implement `build_source_metadata()` — domain, collector version, scopes, run_mode
- [ ] **3.9** Write unit tests for collector (mocked Google API responses)

### Phase 4: Snapshot API

- [ ] **4.1** Create `api/snapshots.py` with `POST /capture` endpoint — triggers collector, saves snapshot to DB
- [ ] **4.2** Implement auto-creation of review in `draft` status on snapshot capture (find previous snapshot, assign default reviewer)
- [ ] **4.3** Create `GET /snapshots` endpoint — list with pagination, filter by provider
- [ ] **4.4** Create `GET /snapshots/{id}` endpoint — full detail with data
- [ ] **4.5** Write tests for snapshot endpoints (mocked collector)

### Phase 5: Diff Engine

- [ ] **5.1** Create `services/diff_engine.py` with `compute_diff(current_snapshot, previous_snapshot, domain)` function
- [ ] **5.2** Implement user diff: new_user, removed_user (by email comparison)
- [ ] **5.3** Implement admin diff: role_change (derive admin sets from role_assignments, compare)
- [ ] **5.4** Implement group membership diff: group_membership_change (per group, by member email)
- [ ] **5.5** Implement external member detection: new_external (email domain != configured domain)
- [ ] **5.6** Implement `build_diff_summary()` — counts per change_type for the review
- [ ] **5.7** Implement `create_review_actions()` — pre-populate `AccessReviewActionDB` rows from diff results
- [ ] **5.8** Wire diff engine into snapshot capture flow (after snapshot + review creation)
- [ ] **5.9** Handle first snapshot (no previous): review created with no diff, no actions
- [ ] **5.10** Write unit tests for diff engine (various scenarios: no changes, adds, removals, role changes, externals, first snapshot)

### Phase 6: Review API

- [ ] **6.1** Create `api/reviews.py` with `GET /reviews` endpoint — list with pagination, filter by status
- [ ] **6.2** Create `GET /reviews/{id}` endpoint — review detail with actions and diff summary
- [ ] **6.3** Create `PATCH /reviews/{id}` endpoint — update notes, change reviewer_id
- [ ] **6.4** Create `PATCH /reviews/{id}/actions/{action_id}` endpoint — update action_taken, justification, approved_by, exception_until
- [ ] **6.5** Create `POST /reviews/{id}/sign` endpoint — validate all actions have action_taken, set status=signed, signed_by, signed_at
- [ ] **6.6** Add validation: cannot sign if any action lacks action_taken
- [ ] **6.7** Add validation: cannot modify a signed review
- [ ] **6.8** Write tests for review endpoints (full flow: create via snapshot, update actions, sign)

### Phase 7: Cron Job + Failure Alerts

- [ ] **7.1** Create ARQ task `collect_iso_snapshot` in worker
- [ ] **7.2** Register cron in `WorkerSettings.cron_jobs` (1st of month, configurable)
- [ ] **7.3** Implement error handling: catch OAuth token expiry, API errors, connection failures
- [ ] **7.4** On failure: send Slack notification via existing Slack integration (reuse `send_slack_message`)
- [ ] **7.5** On failure: log structured error with provider, error type, and timestamp
- [ ] **7.6** Write tests for cron task (success + failure scenarios)

### Phase 8: Frontend — ISO Module Shell

- [ ] **8.1** Create `src/modules/iso/` directory structure (components, hooks, pages)
- [ ] **8.2** Add ISO routes to app router (`/iso/...`)
- [ ] **8.3** Add ISO navigation entry (sidebar or top nav)
- [ ] **8.4** Create ISO config page: Google Workspace connection status, connect/disconnect buttons, domain config
- [ ] **8.5** Create hooks for ISO API (queryKeys, useSnapshots, useReviews, useIsoConfig)

### Phase 9: Frontend — Snapshot + Review UI

- [ ] **9.1** Create snapshot list page: table with provider, captured_at, summary stats, link to review
- [ ] **9.2** Create "Capture snapshot" button with loading state
- [ ] **9.3** Create review detail page: header (reviewer, status, dates), snapshot summary card
- [ ] **9.4** Create diff table: list of changes with change_type, subject, previous/current values
- [ ] **9.5** Create action form per change: action_taken selector, justification text, approved_by selector, exception_until date picker
- [ ] **9.6** Create review sign-off flow: validate all actions resolved, confirm dialog, sign button
- [ ] **9.7** Create reviewer selector (dropdown of app admins, default pre-selected)
- [ ] **9.8** Show last successful capture date prominently (for detecting missing months)
- [ ] **9.9** Write frontend tests for key components

### Definition of Done

All subtasks above are complete when:
- [ ] All backend tests pass
- [ ] All frontend tests pass
- [ ] An admin can connect Google Workspace OAuth from the UI
- [ ] A snapshot can be captured manually and via cron
- [ ] Diff engine correctly detects: new users, removed users, role changes, group membership changes, new externals
- [ ] A review is auto-created in draft with pre-populated actions
- [ ] A reviewer can fill justifications, select actions, and sign the review
- [ ] A signed review cannot be modified
- [ ] Failed cron jobs send Slack notification
- [ ] The ISO dashboard shows snapshot history and review status
