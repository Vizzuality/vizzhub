# Tracker Integration Plan

## Hub Vision

The Hub (repo `vizzhub`) is a unified platform for project management tools.

### Current Modules

1. **Scorecard** — project health and quality metrics (implemented)
2. **ISO** — compliance access reviews for Google Workspace, GitHub, Jira (implemented)
3. **Tracker** — budget tracking, time reports, invoicing (planned — replaces the legacy VizzTracker app)

### Future

4. **MCP Server** — AI-powered read-only analysis across all modules (planned)

## Module Boundary Rules

**1. A module NEVER imports directly from another module's internals.**

Cross-module access goes through `public.py`:

```python
from app.modules.scorecard.services.public import get_project_scores  # OK
from app.modules.scorecard.services.calculators.time import ...       # FORBIDDEN
```

**2. Core imports are always allowed.**

Any module can import from `app.core.*`. Core never imports from modules.

**3. Write isolation, read flexibility.**

Each module only writes to its own tables. For business logic reads, use `public.py` interfaces. For analytical/reporting reads (dashboards, exports), direct JOINs across module tables are allowed in `core/services/`.

### Routing Strategy

Each module owns a `router.py` that aggregates its sub-routers. `main.py` only mounts module-level routers.

Rules:
- Prefixes always defined in `include_router`, never inside router files
- Every router has explicit `tags` for OpenAPI docs
- No two routers share the same prefix
- Module routers own all endpoints under their prefix

### Permissions Strategy

#### Layer 1: Global roles (implemented)

```python
CurrentUser = Annotated[TokenData, Depends(get_current_user)]  # any authenticated user
AdminUser = Annotated[TokenData, Depends(require_role("admin"))]  # platform admin
```

#### Layer 2: Project membership (planned, required for tracker write operations)

New `project_members` table in core:

| Project Role | Can view | Can edit metrics/budget | Can manage settings | Can assign members |
|-------------|----------|------------------------|--------------------|--------------------|
| viewer | Yes | No | No | No |
| contributor | Yes | Yes (own data) | No | No |
| manager | Yes | Yes (all) | Yes | Yes |
| owner | Yes | Yes (all) | Yes | Yes |

Admin role always bypasses project-level checks.

### Shared Services

- Authentication (Google SSO + JWT) — implemented
- Project membership and permissions — planned (T0.5)
- Projects and Programs — central entities linking modules
- Slack notifications — implemented (in scorecard module, extractable when tracker needs it)
- ARQ worker + Redis — single worker, single Redis. Each module defines tasks in `modules/<name>/worker/tasks.py`

## Data Model

### Key Architectural Decisions

Full details in `docs/plans/tracker-data-migration-design.md`.

1. **Contract → Project flattening**: Each legacy VizzTracker contract becomes a vizzhub project. Legacy projects with multiple contracts become programs (grouping entity).
2. **Users — vizzhub is source of truth**: Legacy users matched by email. Devise auth deprecated. New fields (name, functional_area, rate, dedication, active) added to core users.
3. **Teams deprecated**: Legacy teams not migrated.
4. **Roles → Functional Areas**: Legacy job roles renamed to avoid confusion with auth roles. New `functional_areas` table in core.
5. **Percentages as decimals 0-1**: All percentage fields stored as Numeric 0.0-1.0.
6. **Float → Numeric**: All financial fields use Numeric(12,2).
7. **Bigint → UUID**: All new tables use UUID primary keys.
8. **Currency on project**: Moved from invoices to project level.

### New Core Tables

| Table | Purpose |
|-------|---------|
| `programs` | Optional grouping of related projects (replaces legacy project hierarchy) |
| `functional_areas` | Job roles: Backend Developer, Designer, PM, etc. (replaces legacy `roles`) |
| `rates` | Billing rate bands: A, B, C, D |
| `links` | Generic URL links for programs and projects |

### Extended Core Tables

| Table | New fields |
|-------|------------|
| `users` | `name`, `functional_area_id`, `rate_id`, `dedication`, `active` |
| `projects` | `program_id`, `code`, `is_billable`, `currency`, `notes`, `summary` |

### Tracker Module Tables

| Table | Purpose |
|-------|---------|
| `tracker_project_settings` | Per-project budget and contract rate (1:1 with projects) |
| `reporting_periods` | Monthly periods with state machine (unstarted → active → finished) |
| `budget_lines` | Budget allocation per project and functional area |
| `invoices` | Invoice tracking with state machine and milestones |
| `non_staff_costs` | Non-personnel costs per project and period |
| `reports` | Time reports per user per period |
| `report_parts` | Time breakdown per report by project and functional area |
| `progress_reports` | Project completion tracking per period (percentage, delta) |

### Entity Relationships

```
programs ----+---> projects ---+---> tracker_project_settings
             |                 |---> budget_lines ---> functional_areas
             |                 |---> invoices
             |                 |---> non_staff_costs ---> reporting_periods
             |                 |---> progress_reports ---> reporting_periods
             |                 +---> report_parts ---> reports
             |                                           |
users -------+---> reports ---> reporting_periods         |
  |                                                      |
  +---> functional_areas                                 |
  +---> rates                                            |
                                                         |
functional_areas <---------------------------------------+

links ---> programs OR projects
```

## Tasklist & Definition of Done

### Phase 0: Remaining Prerequisites

> T0.1–T0.4 (core extraction, router architecture) and T0.7–T0.8 (URL-driven state) are **complete**.

**T0.5 — Project membership model + permissions**
- [ ] `app/core/models/project_member.py` with `ProjectMemberDB` model
- [ ] `ProjectRole` enum: `viewer`, `contributor`, `manager`, `owner`
- [ ] Alembic migration creates `project_members` table with UNIQUE(user_id, project_id)
- [ ] `app/core/permissions.py` with `require_project_role()` factory
- [ ] Dependency aliases: `ProjectViewer`, `ProjectContributor`, `ProjectManager`
- [ ] Admin role bypasses project-level checks (always treated as owner)
- [ ] CRUD endpoints for project membership
- [ ] Tests: permission denied (403) for insufficient role, granted for sufficient role
- [ ] Tests: admin bypass works for all project-level checks
- [ ] Existing scorecard endpoints unchanged (still use `CurrentUser`, no breakage)

**T0.6 — Frontend project membership UI**
- [ ] Members tab or section in project settings
- [ ] Add/remove members with role selector
- [ ] Current user's role visible in project view
- [ ] Non-members see appropriate access denied state
- [ ] Admin sees all projects regardless of membership
- [ ] All frontend tests pass

### Phase 1: Schema & Data Migration

**T1.1 — Core schema extensions (Alembic migration)**
- [ ] `functional_areas` table (id UUID, name unique)
- [ ] `rates` table (id UUID, code unique, value Numeric(12,2))
- [ ] `programs` table (id UUID, name unique)
- [ ] `links` table (id UUID, program_id/project_id dual FK, title, url, link_type, CHECK constraint)
- [ ] `users` extended: `name`, `functional_area_id` FK, `rate_id` FK, `dedication` Numeric(3,2), `active` bool
- [ ] `projects` extended: `program_id` FK, `code`, `is_billable` bool, `currency`, `notes`, `summary`
- [ ] `projects` CHECK: end_date > start_date
- [ ] Migration is reversible

**T1.2 — Tracker module schema (Alembic migration)**
- [ ] `tracker_project_settings` (project_id unique FK, budget, contract_rate)
- [ ] `reporting_periods` (date unique, base_rate, status + partial unique for active)
- [ ] `budget_lines` (project_id FK, functional_area_id FK, days, adjusted_days, percentage)
- [ ] `invoices` (project_id FK, code, amount, due_date, status + CHECK constraints)
- [ ] `non_staff_costs` (project_id FK, reporting_period_id FK, cost, cost_type + CHECK)
- [ ] `reports` (user_id FK, reporting_period_id FK, estimated + UNIQUE user/period)
- [ ] `report_parts` (report_id FK, project_id FK, functional_area_id FK, percentage, days, cost + UNIQUE constraint)
- [ ] `progress_reports` (reporting_period_id FK, project_id FK, percentage, delta + UNIQUE + CHECK)
- [ ] All FK ondelete behaviors as specified in design doc
- [ ] All composite and partial indexes as specified in design doc
- [ ] Migration is reversible

**T1.3 — Data import script**
- [ ] Reads from `vizz_trackr_development` (legacy DB), writes to `scorecard` (vizzhub DB)
- [ ] Mapping tables for FK resolution (legacy bigint → UUID)
- [ ] Insert order respects dependencies (functional_areas → rates → programs → users → projects → ...)
- [ ] Percentage fields converted /100 (except dedication, already 0-1)
- [ ] Float → Numeric conversion
- [ ] Legacy `created_at` preserved
- [ ] Existing vizzhub projects matched by name, updated not duplicated
- [ ] Users matched by email
- [ ] Duplicate report (id 2470) discarded
- [ ] Script is idempotent (can re-run safely)
- [ ] Validation checks pass:
  - [ ] Row counts match per table
  - [ ] Financial totals match (SUM budget, cost, amount)
  - [ ] All FKs resolve (no orphans)
  - [ ] Percentages in 0-1 range
  - [ ] Programs have correct child project count
- [ ] Tested on local copy of production data

### Phase 2: Tracker Module Backend

**T2.1 — SQLAlchemy models**
- [ ] All tracker tables modeled in `app/modules/tracker/models/`
- [ ] Core extensions modeled in `app/core/models/`
- [ ] Pydantic schemas for API input/output
- [ ] State machine logic for reporting_periods and invoices

**T2.2 — Tracker services (business logic)**
- [ ] Project-level: `total_burn`, `burn_percentage`, `income_to_date`, `budget_left`, `linear_income`
- [ ] Period-level: `total_contracts_reported`, `total_time_reported`, `copy_reports_from`
- [ ] Report-level: `calculate_cost_and_days` (before-save hook)
- [ ] Progress: `calculate_delta` with cascade, `bounded_progress` validation
- [ ] Statistics: mean/variance/stdev of project distribution per user
- [ ] Full reports query service (replaces legacy `full_reports` view)
- [ ] Monthly income query service (replaces legacy `monthly_incomes` view)

**T2.3 — Tracker CRUD endpoints**
- [ ] `app/modules/tracker/router.py` aggregates sub-routers, prefix="/api/tracker"
- [ ] Sub-routers for: reporting_periods, budget_lines, invoices, reports, report_parts, progress_reports
- [ ] Input validation (Pydantic schemas with proper types)
- [ ] Write operations scoped to tracker's own tables only
- [ ] Tests for each endpoint (happy path + validation errors)
- [ ] No trailing slashes on routes

**T2.4 — Tracker `public.py` interface**
- [ ] `app/modules/tracker/services/public.py` exists
- [ ] `get_budget_summary(project_id, db)` → returns BudgetSummary
- [ ] `get_time_summary(project_id, period, db)` → returns aggregated time data
- [ ] Functions have typed parameters, typed returns, and docstrings
- [ ] Return rich structured data (names, dates, context — not just numbers)
- [ ] Unit tests for each public function

### Phase 3: Tracker Frontend

**T3.1 — Tracker frontend module**
- [ ] `src/modules/tracker/` directory with `components/`, `hooks/`, `pages/`, `services/`, `types/`
- [ ] Hooks use centralized query keys (extend `queryKeys.ts`)
- [ ] API client uses `credentials: 'include'` for auth
- [ ] All view state URL-driven from day 1 (uses `useUrlState`)
- [ ] No imports from `src/modules/scorecard/` internals
- [ ] Shared components imported from `src/shared/` only
- [ ] All frontend tests pass

**T3.2 — Project view integration**
- [ ] Project detail page shows tabs from both modules (scores + budget)
- [ ] Tab navigation works without full page reload
- [ ] Unified project list shows summary data from both modules
- [ ] Projects without tracker data show graceful empty state

### Phase 4: Cleanup & Extraction

**T4.1 — Extract notifications module** (when tracker needs alerts)
- [ ] Slack service, alert service, templates in `app/modules/notifications/`
- [ ] Both scorecard and tracker can trigger notifications via `notifications.public`
- [ ] All notification tests pass

**T4.2 — Import linting in CI**
- [ ] Backend: pre-commit or CI check blocks cross-module internal imports
- [ ] Frontend: ESLint `import/no-restricted-paths` configured and passing

### Task Dependencies

```
Phase 0 (prerequisites):
  T0.5 (permissions) ──► T0.6 (membership UI)

Phase 1 (schema + data):          GATE: can start independently of T0.5
  T1.1 (core schema) ──► T1.2 (tracker schema) ──► T1.3 (data import)

Phase 2 (backend):                 GATE: T1.3 complete
  T2.1 (models) ──► T2.2 (services) ──► T2.3 (endpoints) ──► T2.4 (public.py)

Phase 3 (frontend):                GATE: T2.3 complete
  T3.1 (tracker UI) ──► T3.2 (integration)

Phase 4 (cleanup, when needed):
  T4.1 (notifications)
  T4.2 (import linting)

Analytical + MCP (future):
  T-A.1 ──► T-MCP.1 ──► T-MCP.2 ──► T-MCP.3 ──► T-MCP.4
```

## Guardrails

### CLAUDE.md rules (AI enforcement)

Module boundary rules are documented in CLAUDE.md ("Modular Architecture Rules" section). Every Claude Code session reads these rules before writing code.

### Code review checklist

For any PR that touches module boundaries:
- [ ] New models placed in correct module (core vs module-private)?
- [ ] Cross-module imports go through `public.py` only?
- [ ] Module only writes to its own tables?
- [ ] New shared entity follows the decision rule?

## Reference Docs

- `docs/plans/tracker-data-migration-design.md` — Field-by-field mapping, constraints, indexes, import rules, legacy method analysis
- `docs/legacy/schema.rb` — Legacy VizzTracker database schema
- `docs/legacy/models.md` — Legacy Rails models with associations, validations, state machines, business logic

## MCP Server Design

**READ-ONLY by design.** No write tools. AI agents analyze and report but cannot modify project data.

### Phase 1 — API wrapper

```
Claude → MCP Server → HTTP GET only → Hub API (localhost:8000)
```

### Phase 2 — Direct service imports

```
Claude → MCP Server → Python imports → Hub services + DB (SELECT only)
```

### Authentication levels

| Level | Context | Auth method |
|-------|---------|-------------|
| 1 | Local (Claude Desktop/Code) | API key via `X-API-Key` header |
| 2 | Shared (team, EC2) | Google SSO → JWT per user session |
| 3 | Write tools (future) | Existing role-based auth via API |

### MCP readiness guidelines (apply during normal development)

1. `public.py` signatures should be self-describing — typed params, typed returns, docstrings
2. Return rich structured data (names, dates, status — not just IDs)
3. Analytical query services in `core/services/` are highest-value MCP tools
