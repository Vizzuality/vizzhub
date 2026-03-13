# VizzTracker Integration Plan

## Hub Vision

The Hub (repo `vizzhub`) is a unified platform for project management tools.

### Current Modules

1. **Scorecard** — project health and quality metrics (implemented)
2. **ISO** — compliance access reviews for Google Workspace, GitHub, Jira (implemented)
3. **Tracker** — budget tracking, contracts, time reports (planned)

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

#### Layer 2: Project membership (required for tracker)

New `project_members` table in core:

| Project Role | Can view | Can edit metrics/budget | Can manage settings | Can assign members |
|-------------|----------|------------------------|--------------------|--------------------|
| viewer | Yes | No | No | No |
| contributor | Yes | Yes (own data) | No | No |
| manager | Yes | Yes (all) | Yes | Yes |
| owner | Yes | Yes (all) | Yes | Yes |

Admin role always bypasses project-level checks.

#### Layer 3: Module access (future, not planned)

Optional — restrict which modules a user can access per project.

### Shared Services

- Authentication (Google SSO + JWT) — implemented
- Project membership and permissions — planned (T0.5)
- Projects and Teams — central entity linking modules
- Slack notifications — implemented (in scorecard module, extractable when tracker needs it)
- ARQ worker + Redis — single worker, single Redis. Each module defines tasks in `modules/<name>/worker/tasks.py`

## Current VizzTracker Data Model

14 business tables:

```
teams --------+---> projects ---> contracts ---+---> budget_lines ---> roles
              |                                |---> invoices
              |                                |---> non_staff_costs ---> reporting_periods
              |                                |---> progress_reports ---> reporting_periods
              |                                +---> report_parts ---> reports
              |                                                          |
users --------+---> reports ---> reporting_periods                       |
  |                                                                     |
  +---> rates                                                           |
                                                                        |
roles <-----------------------------------------------------------------+

project_links ---> projects
```

### Key Entities

| Table | Purpose |
|-------|---------|
| projects | Projects with team assignment and billable flag |
| contracts | Project contracts with budget, dates, state machine, rate |
| budget_lines | Budget allocation per contract and role (days, percentage) |
| invoices | Invoice tracking with milestones, amounts, currency, state |
| non_staff_costs | Non-personnel costs per contract and period |
| reporting_periods | Monthly periods with state and base rate |
| reports | Time reports per user per period (can be estimated) |
| report_parts | Time breakdown per report by contract and role (days, cost, %) |
| progress_reports | Contract completion tracking per period (percentage, delta) |
| project_links | External links associated to projects |
| teams | Team groupings |
| roles | Job roles (used in budget lines and report parts) |
| rates | Billing rates (linked to users) |
| users | User accounts with team, role, rate, and dedication |

### State Machines

- **contracts**: lifecycle states (draft, active, closed)
- **invoices**: payment states (pending, invoiced, paid)
- **reporting_periods**: period states (open, closed)

### Data Model Optimizations for Migration

1. **Float → Numeric(12,2)** for all financial fields
2. **Drop Devise columns** from users (encrypted_password, etc.) — Hub uses Google SSO
3. **Fix FK types** — align to consistent type
4. **bigint → UUID** primary keys with mapping tables during migration

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
- [ ] CRUD endpoints for project membership:
  - [ ] `GET /api/scorecards/{id}/members` — list members
  - [ ] `POST /api/scorecards/{id}/members` — add member (ProjectManager or Admin)
  - [ ] `PATCH /api/scorecards/{id}/members/{user_id}` — update role
  - [ ] `DELETE /api/scorecards/{id}/members/{user_id}` — remove member
- [ ] Seed data: project creators automatically assigned `owner` role
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

### Phase 1: Build Tracker Module

**T1.1 — SQLAlchemy models for tracker**
- [ ] All 14 business tables modeled in `app/modules/tracker/models/`
- [ ] UUID primary keys (not bigint)
- [ ] Financial fields use `Numeric(12,2)` (not float)
- [ ] State machine fields modeled as Enum types
- [ ] FK relationships defined with proper `ondelete` behavior
- [ ] Alembic migration creates all tables
- [ ] Migration is reversible (`alembic downgrade` works)

**T1.2 — Data migration script (Rails → Hub)**
- [ ] Mapping tables: `legacy_id (bigint) → new_id (UUID)` per entity
- [ ] Inserts in dependency order (teams/roles first, then projects, contracts, etc.)
- [ ] FKs resolved via mapping tables
- [ ] Validation checks:
  - [ ] Row counts match source per table
  - [ ] Financial totals match (sum of budgets, costs, amounts)
  - [ ] All FKs resolve (no orphans)
  - [ ] No data truncation on text fields
- [ ] Script is idempotent (can re-run safely)
- [ ] Tested on local copy of production data

**T1.3 — Tracker CRUD endpoints**
- [ ] `app/modules/tracker/router.py` aggregates sub-routers, prefix="/api/tracker"
- [ ] Sub-routers for: contracts, budget_lines, invoices, reports, reporting_periods
- [ ] Project-scoped permissions on all endpoints:
  - [ ] Read endpoints use `ProjectViewer`
  - [ ] Write endpoints use `ProjectContributor` or `ProjectManager`
  - [ ] Approve/manage endpoints use `ProjectManager`
- [ ] Input validation (Pydantic schemas with proper types)
- [ ] Write operations scoped to tracker's own tables only
- [ ] Tests for each endpoint (happy path + permission denied + validation errors)
- [ ] No trailing slashes on routes

**T1.4 — Tracker `public.py` interface**
- [ ] `app/modules/tracker/services/public.py` exists
- [ ] `get_budget_summary(project_id, db)` → returns `BudgetSummary`
- [ ] `get_time_summary(project_id, period, db)` → returns aggregated time data
- [ ] Functions have typed parameters, typed returns, and docstrings
- [ ] Return rich structured data (names, dates, context — not just numbers)
- [ ] Unit tests for each public function

**T1.5 — Tracker frontend module**
- [ ] `src/modules/tracker/` directory with `components/`, `hooks/`, `pages/`
- [ ] Hooks use centralized query keys (extend `queryKeys.ts`)
- [ ] API client uses `credentials: 'include'` for auth
- [ ] Pages accessible via routes under `/projects/:id/budget`
- [ ] All view state URL-driven from day 1 (uses `useUrlState`)
- [ ] No imports from `src/modules/scorecard/` internals
- [ ] Shared components imported from `src/shared/` only
- [ ] All frontend tests pass

**T1.6 — Project view integration**
- [ ] Project detail page shows tabs from both modules (scores + budget)
- [ ] Tab navigation works without full page reload
- [ ] Unified project list shows summary data from both modules
- [ ] Projects without tracker data show graceful empty state

### Phase 2: Cleanup & Extraction

**T2.2 — Extract notifications module** (when tracker needs alerts)
- [ ] Slack service, alert service, templates in `app/modules/notifications/`
- [ ] Notification models in `app/modules/notifications/models/`
- [ ] Both scorecard and tracker can trigger notifications via `notifications.public`
- [ ] All notification tests pass

**T3.2 — Import linting in CI**
- [ ] Backend: pre-commit or CI check blocks cross-module internal imports
- [ ] Frontend: ESLint `import/no-restricted-paths` configured and passing
- [ ] CI pipeline rejects violations

### Analytical Layer & MCP Server

**T-A.1 — Core reporting services**
- [ ] `app/core/services/reporting.py` exists
- [ ] Cross-module queries for dashboards (project overview, comparatives)
- [ ] Functions have typed parameters, typed returns, and docstrings
- [ ] Tests validate correctness of cross-module aggregations

**T-MCP.1 — MCP server skeleton**
- [ ] `mcp_server/` directory at repo root (or `app/mcp/`)
- [ ] Python MCP SDK integrated
- [ ] Server starts and responds to MCP protocol
- [ ] **READ-ONLY: no write tools exposed**
- [ ] Configuration via environment variables (HUB_API_URL, HUB_API_KEY)

**T-MCP.2 — API key authentication**
- [ ] `api_keys` table (user_id, key_hash, scopes, created_at, last_used_at)
- [ ] `get_current_user()` accepts `X-API-Key` header
- [ ] API keys scoped to read-only operations
- [ ] Admin UI to create/revoke API keys

**T-MCP.3 — Read tools (API wrapper)**
- [ ] Tools call Hub GET endpoints only (no POST/PUT/DELETE)
- [ ] Minimum viable tools: `get_project_health`, `compare_projects`, `find_at_risk_projects`
- [ ] Error handling: Hub errors propagated as clear MCP tool errors
- [ ] Tool descriptions suitable for AI agent consumption

**T-MCP.4 — Analytical tools (direct imports)**
- [ ] Tools import from `public.py` interfaces and `core/services/reporting.py`
- [ ] Cross-module analysis: `generate_monthly_report`, `team_workload_analysis`
- [ ] DB sessions are read-only (no commits)
- [ ] Tests validate tool outputs match expected data

### Task Dependencies

```
Phase 0 remaining:
  T0.5 (permissions) ──► T0.6 (membership UI)
                                │
Phase 1 (tracker):              ▼  GATE: T0.5-T0.6 complete
  T1.1 ──► T1.2 ──► T1.3 ──► T1.4 ──► T1.6
                     T1.5 ──────────────► T1.6

Phase 2 (when needed):
  T2.2 (extract notifications)
  T3.2 (import linting)

Analytical + MCP:
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
