# Tracker Data Migration Design

## Context

Migration from legacy VizzTracker (Rails/Heroku) to the tracker module in vizzhub.
The goal is to reproduce the exact data model and import all production data with full integrity.
The import must be reproducible — it will run in production without affecting existing tables.

- Legacy DB: `vizz_trackr_development` (local, refreshed from Heroku prod 2026-03-14)
- Legacy schema: `docs/legacy/schema.rb`
- Legacy models: `docs/legacy/models.md`
- Legacy codebase: `/Volumes/Work/Dev/Vizz Tracker/vizz_trackr/`

## Key Architectural Decisions

### D1: Contract → Project flattening

Legacy VizzTracker has a `project → contract` hierarchy where `contract` carries all budget/time data and `project` is just a grouping. In vizzhub, `project` is the central work unit (scores, metrics, Jira, GitHub).

**Decision**: Flatten. Each legacy `contract` becomes a vizzhub `project`. Legacy `projects` with multiple contracts become `programs` (new grouping entity).

- 391 legacy contracts → 391 vizzhub projects
- 68 legacy projects (2+ contracts) → 68 programs
- 95 legacy projects (1 contract) → project inherits name, no program
- 3 legacy projects (0 contracts) → ignored

### D2: Users — vizzhub is source of truth

Legacy users have Devise auth fields, team assignments, and job roles. Vizzhub uses Google SSO.

**Decision**: vizzhub `users` table is source of truth for identity. Legacy users are matched by email. Auth fields (Devise) and `admin` flag are deprecated. New fields added to core `users`.

### D3: Teams deprecated

Legacy teams (6 records: K, Rosling, Operations, BD, Outsource, Executive) are organizational groupings that are no longer used.

**Decision**: Not migrated. No `teams` table.

### D4: Roles → Functional Areas

Legacy `roles` are job roles (Backend Developer, Designer, etc.), not auth roles. To avoid confusion with vizzhub auth roles (admin/user), renamed to `functional_areas`.

**Decision**: New `functional_areas` table in core. 9 legacy roles migrated.

### D5: Percentages as decimals 0-1

Vizzhub scorecard stores percentages as `Numeric` decimals 0.0000-1.0000. Legacy VizzTracker uses the same convention for `dedication` (0.74 = 74%) but uses literal percentages in other places (progress_reports.percentage = 75.0 means 75%).

**Decision**: All percentages stored as decimals 0-1 in vizzhub. Legacy fields that use 0-100 scale must be divided by 100 during import.

### D6: Float → Numeric for financial fields

Legacy uses `float` for all money fields. This causes precision issues.

**Decision**: All financial fields use `Numeric(12,2)` in vizzhub.

### D8: Preserve legacy `created_at`

All legacy tables (except `invoices`) have `created_at` / `updated_at`. We preserve `created_at` from legacy data for historical traceability. `updated_at` is set to import time.

### D7: Bigint → UUID primary keys

Legacy uses bigint autoincrement PKs. Vizzhub uses UUID.

**Decision**: All new tables use UUID PKs. Migration script maintains a mapping table (`legacy_id bigint → new_id UUID`) per entity for FK resolution.

---

## Table Migration Plan

### Legend

| Symbol | Meaning |
|--------|---------|
| CORE | Table lives in `app/core/models/` |
| TRACKER | Table lives in `app/modules/tracker/models/` |
| EXTEND | Existing vizzhub table, add fields |
| NEW | New table |
| DEPRECATED | Not migrated |

---

### 1. `users` — CORE / EXTEND

Source of truth: vizzhub. Legacy users matched by email.

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `id` (bigint) | — | — | Mapping table only |
| `email` | `email` | varchar(255), unique | Match key |
| `name` | `name` | varchar(255) | **NEW field** in core users |
| `team_id` | — | — | DEPRECATED |
| `role_id` | `functional_area_id` | UUID, FK | **NEW field**, FK to `functional_areas` |
| `rate_id` | `rate_id` | UUID, FK | **NEW field**, FK to `rates` |
| `dedication` | `dedication` | Numeric(3,2) | **NEW field**, 0-1 scale. Legacy already uses 0-1. |
| `active` | `active` | bool, default true | **NEW field**, soft delete |
| `admin` | — | — | DEPRECATED (vizzhub has own role system) |
| `encrypted_password` | — | — | DEPRECATED (Google SSO) |
| `reset_password_token` | — | — | DEPRECATED |
| `reset_password_sent_at` | — | — | DEPRECATED |
| `remember_created_at` | — | — | DEPRECATED |

**Import rules**:
- For each legacy user, find vizzhub user by email
- If exists: update `name`, `functional_area_id`, `rate_id`, `dedication`, `active`
- If not exists: create new user with legacy data (they'll complete profile on first Google SSO login)
- FK resolution: `role_id` → lookup in `functional_areas` mapping; `rate_id` → lookup in `rates` mapping

---

### 2. `functional_areas` (legacy: `roles`) — CORE / NEW

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `id` (bigint) | `id` | UUID | New PK |
| `name` | `name` | varchar(255), unique | Direct copy |

**9 records**: Backend Developer, Designer, Frontend Developer, Project Manager, Scientist, User Research, Operations, Business Development, Communications

**Import rules**: Insert all 9. Create mapping table `legacy_roles_id → functional_areas.id`.

---

### 3. `rates` — CORE / NEW

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `id` (bigint) | `id` | UUID | New PK |
| `code` | `code` | varchar(50), unique | Direct copy |
| `value` (float) | `value` | Numeric(12,2) | Float → Numeric |

**4 records**: A=11853, B=15365, C=21072, D=24876.67

**Import rules**: Insert all 4. Create mapping table `legacy_rates_id → rates.id`.

---

### 4. `programs` (legacy: `projects` with 2+ contracts) — CORE / NEW

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `id` (bigint) | `id` | UUID | New PK |
| `name` | `name` | varchar(255), unique | Direct copy |

**Import rules**:
- Only create programs for legacy projects that have 2+ contracts (68 records)
- Legacy projects with 1 contract: no program created (project inherits directly)
- Legacy projects with 0 contracts: ignored
- Create mapping table `legacy_projects_id → programs.id` (only for multi-contract projects)

---

### 5. `projects` (legacy: `contracts`) — CORE / EXTEND

Existing vizzhub `projects` table extended with new fields.

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `contracts.id` (bigint) | `id` | UUID | New PK |
| `contracts.name` | `name` | varchar(255) | Direct copy |
| `contracts.code` | `code` | varchar(100) | **NEW field** — company-wide manual ID |
| `contracts.project_id` | `program_id` | UUID, FK nullable | **NEW field** — FK to `programs`. Set only for multi-contract legacy projects |
| `projects.is_billable` | `is_billable` | bool, default true | **NEW field** — inherited from legacy parent project |
| `contracts.budget` (float) | — | — | Lives in tracker module (see budget_lines / tracker tables) |
| `contracts.start_date` | `start_date` | date | Already exists in vizzhub |
| `contracts.end_date` | `end_date` | date | Already exists in vizzhub |
| `contracts.aasm_state` | — | — | Mapped to vizzhub `status`: proposal/live → "in_progress", finished → "finished" |
| `contracts.contract_rate` | — | — | TRACKER module field (see below) |
| (from invoices) `currency` | `currency` | varchar(20), default "dollar" | **NEW field** — moved from invoices to project level. Enum: euro, dollar |
| `contracts.alias` | — | — | DEPRECATED — not migrated |
| `contracts.notes` | `notes` | text | **NEW field** in core projects |
| `contracts.summary` | `summary` | text | **NEW field** in core projects |
| Existing: `jira_project_key` | `jira_project_key` | varchar(50) | Unchanged. Multiple projects can share the same Jira key. |
| Existing: `github_repo` | `github_repo` | varchar(255) | Unchanged. Multiple projects can share the same repo. |
| Existing: `slack_channel_id` | `slack_channel_id` | varchar(50) | Unchanged |
| Existing: `status` | `status` | varchar(20) | Unchanged |
| Existing: `finished_at` | `finished_at` | date | Unchanged |

**Import rules**:
- Each legacy contract → new vizzhub project
- `name`: use contract name directly (verified: no duplicates in legacy contracts)
- `program_id`: set if legacy project had 2+ contracts; null otherwise
- `is_billable`: inherited from legacy parent project
- `start_date`, `end_date`: direct copy from contract
- `status`: map from `aasm_state` (proposal/live → "in_progress", finished → "finished")
- Existing vizzhub projects (3): keep as-is, do not overwrite
- Create mapping table `legacy_contracts_id → projects.id`

**Fields deferred to tracker module**: `budget`, `contract_rate` — these are tracker-specific operational data, handled in `tracker_project_settings` below.

---

### 6. `reporting_periods` — TRACKER / NEW

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `id` (bigint) | `id` | UUID | New PK |
| `date` | `date` | date, unique | Direct copy |
| `base_rate` (float) | `base_rate` | Numeric(12,2), default 175.0 | Float → Numeric |
| `aasm_state` | `status` | varchar(20) | Rename field. Enum: unstarted, active, finished |

**90 records** (monthly, from ~2018 to present).

**Import rules**: Insert all. Create mapping table `legacy_reporting_periods_id → reporting_periods.id`.

---

### 7. `budget_lines` — TRACKER / NEW

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `id` (bigint) | `id` | UUID | New PK |
| `contract_id` | `project_id` | UUID, FK | Resolved via contracts mapping |
| `role_id` | `functional_area_id` | UUID, FK nullable | Resolved via roles mapping |
| `days` (int) | `days` | integer | Direct copy |
| `adjusted_days` (float) | `adjusted_days` | Numeric(8,2) | Float → Numeric |
| `percentage` (float) | `percentage` | Numeric(5,4) | **Convert: /100 → 0-1 scale** |
| `details` | `details` | varchar(255) | Direct copy |

**946 records**.

**Import rules**: Insert all. Resolve FKs via mapping tables.

---

### 8. `invoices` — TRACKER / NEW

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `id` (bigint) | `id` | UUID | New PK |
| `contract_id` | `project_id` | UUID, FK | Resolved via contracts mapping |
| `code` | `code` | varchar(100) | Direct copy |
| `amount` (float) | `amount` | Numeric(12,2) | Float → Numeric |
| `currency` | — | — | Moved to core `projects`. Invoices inherit from project. Legacy contract_id=672 has mixed currencies (data error, resolve manually). |
| `due_date` | `due_date` | date | Direct copy |
| `extended_date` | `extended_date` | date | Direct copy |
| `invoiced_on` | `invoiced_on` | date | Direct copy |
| `milestone` | `milestone` | text | Direct copy |
| `observations` | `observations` | text | Direct copy |
| `aasm_state` | `status` | varchar(30) | Rename. Enum: scheduled, pending_to_issue, waiting_for_payment, paid |

**519 records**.

**Import rules**: Insert all. Resolve `contract_id` → `project_id` via mapping.

---

### 9. `non_staff_costs` — TRACKER / NEW

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `id` (bigint) | `id` | UUID | New PK |
| `contract_id` | `project_id` | UUID, FK | Resolved via contracts mapping |
| `reporting_period_id` | `reporting_period_id` | UUID, FK | Resolved via mapping |
| `cost` (float) | `cost` | Numeric(12,2) | Float → Numeric |
| `cost_type` | `cost_type` | varchar(50) | Enum: outsource, travel, servers, others |
| `details` | `details` | varchar(255) | Direct copy |

**408 records**.

**Import rules**: Insert all. Resolve FKs via mapping tables.

---

### 10. `reports` — TRACKER / NEW

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `id` (bigint) | `id` | UUID | New PK |
| `user_id` | `user_id` | UUID, FK | Resolved via users mapping (by email) |
| `team_id` | — | — | DEPRECATED |
| `reporting_period_id` | `reporting_period_id` | UUID, FK | Resolved via mapping |
| `estimated` | `estimated` | bool, default false | Direct copy |

**4,290 records**.

**Import rules**: Insert all. Resolve FKs via mapping tables. Drop `team_id`.

---

### 11. `report_parts` — TRACKER / NEW

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `id` (bigint) | `id` | UUID | New PK |
| `report_id` | `report_id` | UUID, FK | Resolved via reports mapping |
| `contract_id` | `project_id` | UUID, FK | Resolved via contracts mapping |
| `role_id` | `functional_area_id` | UUID, FK nullable | Resolved via roles mapping |
| `percentage` (float) | `percentage` | Numeric(5,4) | **Convert: /100 → 0-1 scale** |
| `days` (float) | `days` | Numeric(8,4) | Float → Numeric |
| `cost` (float) | `cost` | Numeric(12,2) | Float → Numeric |

**24,793 records** (largest table).

**Unique constraint**: (`project_id`, `report_id`, `functional_area_id`)

**Import rules**: Insert all. Resolve FKs via mapping tables. Convert percentage /100.

---

### 12. `progress_reports` — TRACKER / NEW

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `id` (bigint) | `id` | UUID | New PK |
| `reporting_period_id` | `reporting_period_id` | UUID, FK | Resolved via mapping |
| `contract_id` | `project_id` | UUID, FK | Resolved via contracts mapping |
| `percentage` (float) | `percentage` | Numeric(5,4) | **Convert: /100 → 0-1 scale** |
| `delta` (float) | `delta` | Numeric(5,4) | **Convert: /100 → 0-1 scale** |

**808 records**.

**Unique constraint**: (`reporting_period_id`, `project_id`)

**Import rules**: Insert all. Resolve FKs via mapping tables. Convert percentage and delta /100.

---

### 13. `links` (legacy: `project_links`) — CORE / NEW

Generic links table. Can attach to a program OR a project (dual nullable FK, exactly one must be set).

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `id` (bigint) | `id` | UUID | New PK |
| `project_id` | `program_id` | UUID, FK nullable | Legacy projects → programs. For single-contract projects → `project_id` instead |
| — | `project_id` | UUID, FK nullable | For links attached directly to a project |
| `title` | `title` | varchar(255) | Direct copy |
| `url` | `url` | varchar(500) | Direct copy |
| `link_type` | `link_type` | varchar(50) | Enum: code, project-management, app-environments, design |

**Check constraint**: exactly one of (`program_id`, `project_id`) must be non-null.

**416 records**.

**Import rules**:
- Legacy project with 2+ contracts (→ program): `links.program_id` = mapped program ID
- Legacy project with 1 contract (no program): `links.project_id` = mapped project ID
- Legacy project with 0 contracts: ignored (same as projects)

---

### Tables NOT migrated

| Legacy table | Reason |
|---|---|
| `teams` | Deprecated (D3) |
| `ar_internal_metadata` | Rails internal |
| `schema_migrations` | Rails internal |

### Views NOT migrated (will be recreated as queries/services)

| Legacy view | Reason |
|---|---|
| `full_reports` | Denormalized JOIN — recreate as query in tracker services |
| `monthly_incomes` | Calculated view — recreate as query in tracker services |

---

## Tracker-specific project fields

These legacy `contracts` fields are operational data specific to tracker. They will live in a tracker-owned table, not in core `projects`.

**Table: `tracker_project_settings`** (TRACKER / NEW)

| Legacy field | Vizzhub field | Type | Notes |
|---|---|---|---|
| `contracts.budget` (float) | `budget` | Numeric(12,2) | Total contract budget |
| `contracts.contract_rate` (float) | `contract_rate` | Numeric(12,2), default 175.0 | Rate for this project |
| — | `project_id` | UUID, FK unique | 1:1 with projects |

---

## Import execution order

Dependencies determine insertion order:

```
1. functional_areas    (no deps)
2. rates               (no deps)
3. programs            (no deps)
4. users               (deps: functional_areas, rates)
5. projects            (deps: programs)
6. tracker_project_settings (deps: projects)
7. reporting_periods   (no deps, but logically after projects)
8. budget_lines        (deps: projects, functional_areas)
9. invoices            (deps: projects)
10. non_staff_costs    (deps: projects, reporting_periods)
11. progress_reports   (deps: reporting_periods, projects)
12. reports            (deps: users, reporting_periods)
13. report_parts       (deps: reports, projects, functional_areas)
14. links              (deps: projects, programs)
```

## Mapping tables

The import script creates temporary mapping tables for FK resolution:

```sql
CREATE TEMP TABLE _map_functional_areas (legacy_id bigint, new_id uuid);
CREATE TEMP TABLE _map_rates (legacy_id bigint, new_id uuid);
CREATE TEMP TABLE _map_programs (legacy_id bigint, new_id uuid);
CREATE TEMP TABLE _map_users (legacy_id bigint, new_id uuid);
CREATE TEMP TABLE _map_projects (legacy_id bigint, new_id uuid);  -- legacy contracts.id → projects.id
CREATE TEMP TABLE _map_reporting_periods (legacy_id bigint, new_id uuid);
CREATE TEMP TABLE _map_reports (legacy_id bigint, new_id uuid);
```

## Data verification (from 2026-03-14 dump)

Percentage scale verified across all tables:
- `budget_lines.percentage`: 0.8–100 → **0-100 scale, convert /100**
- `report_parts.percentage`: 0–100 → **0-100 scale, convert /100**
- `progress_reports.percentage`: 0–100 → **0-100 scale, convert /100**
- `progress_reports.delta`: -75–100 → **0-100 scale, convert /100** (3 negative deltas exist — historical corrections)
- `users.dedication`: 0.5–1.0 → **already 0-1 scale, no conversion**

Float precision issues confirmed (e.g. `report_parts.cost = 526.8000000000001`). Numeric migration necessary.

Nullability notes:
- `budget_lines.role_id`: null in 33/946 ("Flexible time" lines)
- `budget_lines.adjusted_days`: null in 870/946 (rarely used)
- `report_parts.role_id`: null in 473/24793
- `reports.team_id`: null in 1657/4290 (deprecated, not migrated)
- `non_staff_costs.cost_type`: no "servers" in production data (only outsource=365, travel=27, others=16)
- `invoices.aasm_state`: no "pending_to_issue" in production data (paid=469, waiting_for_payment=9, scheduled=41)

## Validation checks (post-import)

- [ ] Row counts match per table (legacy → vizzhub)
- [ ] Financial totals match: SUM(budget), SUM(cost), SUM(amount)
- [ ] All FKs resolve (no orphans)
- [ ] No duplicate unique constraints violated
- [ ] Percentages in 0-1 range (not 0-100)
- [ ] All legacy users matched by email or created
- [ ] Programs have correct child project count
- [ ] Progress report monotonicity preserved (3 known exceptions with negative delta allowed)

---

## Index strategy

Read-heavy workload. Indexes designed for analytical queries: cost/time aggregation per project, per period, per functional area, and cross-project statistics.

### FK indexes (standard, on all FK columns)

Every FK column gets a btree index. These are the baseline.

### Composite indexes for analytical queries

```sql
-- report_parts (25k rows, center of all cost/time queries)
-- "Cost and time for a project, broken down by period"
-- Covers: burn rate, budget vs actual, project cost over time
CREATE INDEX idx_report_parts_project_area
  ON report_parts (project_id, functional_area_id);
-- Supports: distribution of cost/time by functional area for a project

-- reports (4k rows, pivot between users, periods, and report_parts)
-- "All reports for a user in a period" / "All reports in a period"
CREATE UNIQUE INDEX idx_reports_user_period
  ON reports (user_id, reporting_period_id);
-- Note: business rule says one report per user per period — enforce as unique

-- "Join report_parts → reports efficiently when filtering by period"
CREATE INDEX idx_reports_period_id
  ON reports (reporting_period_id)
  INCLUDE (user_id);
-- Covers the JOIN from report_parts and avoids table lookup for user_id

-- invoices
-- "Pending invoices for a project" / "Invoice status dashboard"
CREATE INDEX idx_invoices_project_status
  ON invoices (project_id, status);

-- non_staff_costs
-- "Non-staff costs for a project in a period"
CREATE INDEX idx_non_staff_costs_project_period
  ON non_staff_costs (project_id, reporting_period_id);

-- budget_lines
-- "Budget breakdown by functional area for a project"
CREATE INDEX idx_budget_lines_project_area
  ON budget_lines (project_id, functional_area_id);

-- progress_reports — UNIQUE(reporting_period_id, project_id) already covers queries
-- Add reverse for "all progress for a project over time"
CREATE INDEX idx_progress_reports_project_period
  ON progress_reports (project_id, reporting_period_id);

-- reports: partial index for burn calculations (exclude estimated reports)
CREATE INDEX idx_reports_period_not_estimated
  ON reports (reporting_period_id)
  WHERE estimated = false;

-- projects
-- "Filter by program, status, billable"
CREATE INDEX idx_projects_program_id ON projects (program_id) WHERE program_id IS NOT NULL;
CREATE INDEX idx_projects_status ON projects (status);
CREATE INDEX idx_projects_billable ON projects (is_billable);

-- links
CREATE INDEX idx_links_program_id ON links (program_id) WHERE program_id IS NOT NULL;
CREATE INDEX idx_links_project_id ON links (project_id) WHERE project_id IS NOT NULL;
```

### Query patterns these indexes support

| Query | Primary index used |
|---|---|
| Total cost for a project (all periods) | `report_parts(project_id)` FK + `reports(reporting_period_id)` |
| Cost for a project in one period | `reports(reporting_period_id) INCLUDE(user_id)` → `report_parts(report_id)` FK |
| Cost breakdown by functional area | `report_parts(project_id, functional_area_id)` |
| Budget by functional area | `budget_lines(project_id, functional_area_id)` |
| Budget vs actual for a project | `tracker_project_settings(project_id)` + report_parts aggregation |
| Progress history for a project | `progress_reports(project_id, reporting_period_id)` |
| All projects in a period with costs | `reports(reporting_period_id)` → `report_parts(report_id)` |
| Pending invoices | `invoices(project_id, status)` |
| Non-staff costs per project per period | `non_staff_costs(project_id, reporting_period_id)` |
| User time report for a period | `reports(user_id, reporting_period_id)` UNIQUE |
| Cross-project statistics per period | `reports(reporting_period_id)` → aggregate report_parts |
| Burn rate (excluding estimates) | `reports(reporting_period_id) WHERE NOT estimated` partial index |
| Filter projects by program/status/billable | `projects(program_id)`, `projects(status)`, `projects(is_billable)` |

---

## Constraints

### Unique constraints

| Table | Columns | Notes |
|---|---|---|
| `functional_areas` | `(name)` | From legacy roles |
| `rates` | `(code)` | |
| `programs` | `(name)` | |
| `reporting_periods` | `(date)` | One per month |
| `reporting_periods` | `(status) WHERE status = 'active'` | Partial unique — only one active period at a time |
| `progress_reports` | `(reporting_period_id, project_id)` | One progress entry per project per period |
| `report_parts` | `(project_id, report_id, functional_area_id)` | One entry per project+report+area |
| `reports` | `(user_id, reporting_period_id)` | One report per user per period (not enforced in legacy, enforced now). 1 legacy duplicate: report 2470 (user 23, period 23) is empty — discard during import. |
| `links` | — | No unique constraint needed |

### NOT NULL constraints (beyond timestamps and PKs)

| Table | NOT NULL columns |
|---|---|
| `budget_lines` | `project_id` |
| `non_staff_costs` | `project_id`, `reporting_period_id`, `cost`, `cost_type` |
| `progress_reports` | `reporting_period_id`, `project_id`, `percentage` |
| `report_parts` | `report_id`, `project_id` |
| `reports` | `user_id`, `reporting_period_id` |
| `invoices` | `project_id`, `due_date`, `milestone`, `amount` |
| `links` | — (one of program_id/project_id enforced by CHECK) |
| `tracker_project_settings` | `project_id` |

### CHECK constraints

```sql
-- invoices
CHECK (amount >= 0)
CHECK (currency IN ('euro', 'dollar'))
CHECK (extended_date IS NULL OR due_date IS NULL OR extended_date > due_date)

-- projects (existing table, new constraint)
CHECK (end_date IS NULL OR start_date IS NULL OR end_date > start_date)

-- non_staff_costs
CHECK (cost_type IN ('outsource', 'travel', 'servers', 'others'))
CHECK (cost >= 0)

-- progress_reports
CHECK (percentage >= 0 AND percentage <= 1)
CHECK (delta >= -1 AND delta <= 1)

-- report_parts
CHECK (percentage IS NULL OR (percentage >= 0 AND percentage <= 1))
CHECK (cost IS NULL OR cost >= 0)
CHECK (days IS NULL OR days >= 0)

-- budget_lines
CHECK (percentage IS NULL OR (percentage >= 0 AND percentage <= 1))
CHECK (days IS NULL OR days >= 0)

-- links
CHECK (
  (program_id IS NOT NULL AND project_id IS NULL)
  OR (program_id IS NULL AND project_id IS NOT NULL)
)

-- reporting_periods
CHECK (status IN ('unstarted', 'active', 'finished'))

-- invoices
CHECK (status IN ('scheduled', 'pending_to_issue', 'waiting_for_payment', 'paid'))
```

### FK ondelete behavior

| Table | FK | ondelete | Reason |
|---|---|---|---|
| `budget_lines.project_id` | → projects | CASCADE | Budget lines belong to project |
| `budget_lines.functional_area_id` | → functional_areas | SET NULL | Preserve line if area deleted |
| `invoices.project_id` | → projects | CASCADE | Invoices belong to project |
| `non_staff_costs.project_id` | → projects | CASCADE | Costs belong to project |
| `non_staff_costs.reporting_period_id` | → reporting_periods | CASCADE | Costs belong to period |
| `progress_reports.project_id` | → projects | RESTRICT | Don't delete project with progress data |
| `progress_reports.reporting_period_id` | → reporting_periods | CASCADE | |
| `report_parts.report_id` | → reports | CASCADE | Parts belong to report |
| `report_parts.project_id` | → projects | RESTRICT | Don't delete project with time data (legacy behavior) |
| `report_parts.functional_area_id` | → functional_areas | SET NULL | Preserve part if area deleted |
| `reports.user_id` | → users | RESTRICT | Don't delete user with reports (soft delete instead) |
| `reports.reporting_period_id` | → reporting_periods | CASCADE | |
| `tracker_project_settings.project_id` | → projects | CASCADE | Settings belong to project |
| `links.program_id` | → programs | CASCADE | |
| `links.project_id` | → projects | CASCADE | |
| `projects.program_id` | → programs | SET NULL | Keep project if program deleted |
| `users.functional_area_id` | → functional_areas | SET NULL | |
| `users.rate_id` | → rates | SET NULL | |

---

## Legacy methods → Tracker services

Business logic from legacy Rails models that must be reimplemented as tracker services.

### Project-level calculations (legacy: Contract model)

| Legacy method | Description | Implementation notes |
|---|---|---|
| `total_burn(with_projections)` | SUM(report_parts.cost) + SUM(non_staff_costs.cost). Optional: include/exclude estimated reports | Core query. Filter `reports.estimated = false` by default. Uses partial index. |
| `burn_percentage` | `total_burn / budget * 100` | Derives from total_burn + tracker_project_settings.budget |
| `income_to_date` | `budget * latest_progress.percentage` | Derives from progress_reports + budget |
| `income_percentage` | Latest progress_report.percentage for project | Single query with ORDER BY period DESC LIMIT 1 |
| `budget_left` | `budget - income_to_date` | Derived |
| `linear_income` | Remaining budget / remaining months | Derived. Needs project dates + latest progress |
| `latest_progress_report` | Most recent progress_report for project | `progress_reports(project_id, reporting_period_id)` index |

### Period-level calculations (legacy: ReportingPeriod model)

| Legacy method | Description | Implementation notes |
|---|---|---|
| `total_contracts_reported` | COUNT(DISTINCT project_id) from report_parts in period | Via reports → report_parts JOIN |
| `total_time_reported` | SUM(days) from report_parts in period | Same JOIN |
| `copy_reports_from(source)` | Duplicate reports from previous period (active users, non-finished projects only) | Write operation. Marks copies as `estimated = true`. Skips finished projects. |
| `contracts_mean_variance_and_stdev` | Statistical analysis: mean/variance/stdev of project count per user | Complex aggregation. Uses `array_agg` + Python statistics. |
| `analyse` | Cross-period statistics breakdown | Iterates all periods. May be better as a materialized view or cached query. |

### Report-level calculations (legacy: ReportPart model)

| Legacy method | Description | Implementation notes |
|---|---|---|
| `calculate_cost_and_days` | `cost = (pct/100 * rate_value * dedication) * rate_multiplier`; `days = pct/5.0 * dedication` | **before_save hook**. Crosses 4 entities. After 0-1 conversion: `cost = pct * rate_value * dedication * rate_multiplier`; `days = pct * 20.0 * dedication` (since pct/5.0 at 0-100 = pct*20 at 0-1). **Verify formula conversion carefully.** |
| `rate_multiplier` | `contract_rate / base_rate` | From tracker_project_settings.contract_rate / reporting_period.base_rate |

### Progress calculations (legacy: ProgressReport model)

| Legacy method | Description | Implementation notes |
|---|---|---|
| `calculate_delta` | `delta = percentage - previous_percentage`. Also cascades: updates next report's delta. | **before_save hook**. Must handle editing old progress reports. |
| `bounded_progress` | Validates percentage >= previous percentage | Validation. 3 known legacy exceptions with negative delta. |

### Invoice logic (legacy: Invoice model)

| Legacy method | Description | Implementation notes |
|---|---|---|
| `must_issue?` | `due_date <= today AND status = pending_to_issue` | Simple check. Used for dashboard alerts. |
| `send_announcement` | Slack notification on state change | Reuse vizzhub Slack infrastructure (already in scorecard). |

### Recreated views (as services, not DB views)

| Legacy view | Vizzhub equivalent | Notes |
|---|---|---|
| `full_reports` | Tracker query service with dynamic filters (project, user, functional_area, period, threshold) | No longer needs team filter. Add program filter. |
| `monthly_incomes` | Tracker query service: `budget * delta` per project per period | Simple derived query from progress_reports + budget |

---

## Open questions

1. ~~**project_links mapping**~~: Resolved — generic `links` table for both programs and projects.
2. ~~**contracts.alias**~~: Resolved — deprecated, not migrated.
3. ~~**contracts.notes / summary**~~: Resolved — moved to core `projects` as new fields.
4. **Existing vizzhub projects**: There is overlap with legacy data (3 in dev, more in production). Will need manual mapping by name during import. Import script must handle: match existing → update; no match → create.
5. ~~**Legacy users**~~: Resolved — all @vizzuality.com, matched by email. No external users.
