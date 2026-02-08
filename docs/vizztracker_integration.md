# VizzTracker Integration Plan

## Hub Vision

The Hub (currently named Project Scorecard, repo `project-score-card`) is evolving into a unified platform for project management tools. The repo and app should be renamed to `hub` / VizzHub before integrating additional apps.

### Current State: Project Scorecard

The scorecard evaluates projects across 8 dimensions (P_time, P_cost, P_quality, P_value, P_satisfaction, P_flow, P_engineering, P_risk). Preliminary assessment:

**What delivers real value today:**

- Automated Jira/GitHub metric collection — eliminates manual data gathering
- Historical trend tracking — month-over-month project evolution
- Proactive business alerts — budget exceeded, timeline at risk, Dependabot vulnerabilities
- Configurable weights and targets — adaptable scoring model, not a rigid framework

**ISO compliance angle:**

The 8 dimensions map directly to ISO audit evidence requirements:

| Dimension | ISO Evidence |
|-----------|-------------|
| P_quality, P_engineering | Software quality control |
| P_risk | Documented risk management |
| P_flow | Continuous process improvement |
| P_time, P_cost | Planning and tracking |
| P_satisfaction | Client feedback |

Manual metrics (governance, milestones, test maturity) that might seem low-value are actually necessary for ISO — they capture process evidence that cannot be automated.

The scorecard's historical data, measurable targets, and traceability provide audit-ready evidence without last-minute Excel scrambles.

### Future State: VizzHub

A platform consolidating multiple internal tools, starting with:

1. **Scorecard** — project health and quality metrics (implemented)
2. **VizzTracker** — time tracking, budgets, and costs (to be integrated)
3. Potential future modules following the same pattern

## Context

VizzTracker is a Ruby on Rails application used to track development time reports, project budgets, and costs. It runs on PostgreSQL (`vizz_trackr_development`). The goal is to integrate it into the Hub to consolidate project management tools into a single platform.

## Business Value

- **Unified project view**: project health (scorecard) + financial status (tracker) in one place
- **Cross-domain insights**: detect projects with good scores but bleeding budget, or healthy budget but poor quality
- **Single reporting tool** for leadership instead of two separate apps
- **ISO compliance**: consolidated evidence across quality, risk, cost, and process metrics
- **Reduced maintenance**: retire a legacy Rails app, one less system to operate

## Architecture: Modular Monolith

Single deploy, clear module boundaries. No microservices overhead.

### Core Principle: Entity Ownership

The boundary between modules is defined by **who owns what data**. There are three levels of sharing:

#### Level 1: Core entities — genuinely shared, no single owner

Entities that every module needs and that have no natural "home" in any one module. These live in `core/`.

| Entity | Why core |
|--------|----------|
| **projects** | Both modules operate on projects |
| **users** | Auth, ownership, assignment |
| **teams** | Organizational grouping |
| **roles** | Used by trackr (budget lines) and potentially scorecard (team metrics) |

#### Level 2: Source-of-truth ownership — one module owns, others consume

When data is genuinely used by multiple modules but one module is the **creator and manager** of that data. The owning module exposes aggregated views via `public.py`; consumers never touch the underlying tables.

| Data | Owner | Consumer | Interface |
|------|-------|----------|-----------|
| **Budget** (total, consumed, remaining) | **trackr** (contracts, budget_lines, invoices) | scorecard (P_cost calculation) | `trackr.public.get_budget_summary(project_id)` |
| **Time allocation** (hours, dedication) | **trackr** (reports, report_parts) | scorecard (P_flow, team metrics) | `trackr.public.get_time_summary(project_id, period)` |
| **Project scores** (8 dimensions) | **scorecard** (calculators, normalizers) | trackr (health indicators in budget views) | `scorecard.public.get_project_scores(project_id)` |

This replaces manual fields in scorecard (like `budget_total`, `budget_consumed`) with live data from tracker — the source of truth.

#### Level 3: Module-private — no sharing needed

| Owner | Entities |
|-------|----------|
| **scorecard** | metrics, config_parameters, oauth_tokens, slack, alerts |
| **trackr** | invoices, non_staff_costs, reporting_periods, progress_reports |

#### What about timeline?

Timeline has components at different levels:

| Aspect | Owner | Reason |
|--------|-------|--------|
| Project dates (start_date, end_date, finished_at) | **core** | Every module needs them |
| Milestones (delivery milestones, grace periods) | **scorecard** | Used for P_time scoring |
| Reporting periods (monthly open/close) | **trackr** | Time tracking cadence |
| Contract dates (contract start/end) | **trackr** | Budget/contract lifecycle |

Both modules render timelines in their UIs, but each reads from its own data + core project dates. No single "timeline entity" — it's a UI concept composed from multiple sources.

#### Decision rule for new entities

```
Is it needed by ALL current and foreseeable modules?
  → YES: core
  → NO: Does one module create/manage it and others just read it?
    → YES: Owner module + public.py interface
    → NO (only one module uses it): Module-private
```

### Database: One PostgreSQL, Single Schema

All tables live in the default `public` schema. No multi-schema separation.

**Why not separate schemas?** Schemas are just namespaces — they don't provide real isolation (same engine, same connection, same transactions). Separate schemas add Alembic complexity and create an artificial barrier against JOINs that hurts reporting and analytics use cases, without meaningful benefit at this scale.

**Table ownership by module:**

```
Core:       projects, users, teams, roles
Scorecard:  metrics, config_parameters, oauth_tokens, slack_config, alert_definitions, ...
Trackr:     contracts, invoices, budget_lines, reports, report_parts, rates, ...
```

Table names are already descriptive enough — no prefixes needed.

**Read/Write rules:**

| Operation | Rule | Example |
|-----------|------|---------|
| **Writes** | Only through the owning module | Scorecard cannot INSERT into `contracts` |
| **Business reads** | Through `public.py` interfaces | Scorecard calls `trackr.public.get_budget_summary()` |
| **Analytical reads** | Direct JOINs allowed | Dashboard/export services can JOIN across module tables |

The distinction matters: business logic stays decoupled through service interfaces, but reporting/dashboards can use SQL JOINs freely — that's what SQL is designed for.

**Analytical query services** live in `core/` (not in any module) since they read across module boundaries:

```python
# app/core/services/reporting.py — allowed to JOIN any table
async def get_project_overview(project_id: str, db: AsyncSession) -> ProjectOverview:
    """Combines scores + budget + timeline in a single efficient query."""
    result = await db.execute(
        select(ProjectDB, MetricsDB, ContractDB)
        .join(MetricsDB, ...)
        .join(ContractDB, ...)
        .where(ProjectDB.id == project_id)
    )
    ...
```

### Backend Structure

```
app/
├── core/                      # Shared kernel
│   ├── auth.py                # Auth, middleware, dependencies
│   ├── database.py            # DB engine, session
│   └── models/
│       ├── user.py            # User (shared)
│       ├── project.py         # Project (shared)
│       └── team.py            # Team (shared)
│
├── modules/
│   ├── scorecard/
│   │   ├── api/               # Routers (metrics, scores, collectors, config)
│   │   ├── models/            # metrics, config_parameters, oauth_tokens
│   │   ├── services/          # calculators, normalizers, collectors
│   │   │   └── public.py      # Public interface for cross-module use
│   │   └── router.py          # include_router() with prefix="/api/scorecard"
│   │
│   ├── trackr/
│   │   ├── api/               # Routers (contracts, budgets, reports)
│   │   ├── models/            # contracts, invoices, budget_lines, etc.
│   │   ├── services/          # budget calculations, report generation
│   │   │   └── public.py      # Public interface for cross-module use
│   │   └── router.py          # prefix="/api/trackr"
│   │
│   └── notifications/         # Slack, alerts (cross-module)
│       ├── api/
│       ├── models/
│       └── services/
│
└── main.py                    # Mounts all module routers
```

**API routing:**

```
/api/auth/*          -> core
/api/projects/*      -> core
/api/scorecard/*     -> scorecard module
/api/trackr/*        -> trackr module
```

### Frontend Structure

```
src/
├── shared/                    # Layout, auth, UI primitives
│   ├── components/            # AppShell, Nav, common UI
│   ├── contexts/              # AuthContext
│   └── hooks/                 # useAuth, useProjects
│
├── modules/
│   ├── scorecard/
│   │   ├── components/        # ScoreCard, MetricsForm, Timeline
│   │   ├── hooks/             # useScores, useMetrics, useConfig
│   │   └── pages/             # ProjectScores, GlobalDashboard
│   │
│   ├── tracker/
│   │   ├── components/        # BudgetTable, TimeReport, ContractForm
│   │   ├── hooks/             # useBudget, useReports, useContracts
│   │   └── pages/             # ProjectBudget, TimeReports
│
└── App.tsx                    # Root routing
```

**Routes:**

```
/projects            -> unified list
/projects/:id        -> project view with tabs from both modules
/projects/:id/scores -> scorecard
/projects/:id/budget -> trackr
```

### URL-Driven State Strategy

**Problem**: Currently zero usage of `useSearchParams`. All view state (selected period, active tab, dimension filters, snapshot type) lives in `useState` — lost on page reload, impossible to share as a link, and invisible to the MCP server.

**Why this matters beyond UX:**
- **Shareable links**: PM sends a link to a specific project's March 2025 budget → recipient sees exactly that view
- **MCP traceability**: When the MCP returns "Project X budget is 120% consumed", it includes a URL like `/projects/abc/budget?period=2025-03` — the user clicks it and sees the exact data the AI analyzed
- **Audit trail**: ISO audits can reference specific URLs as evidence ("see scorecard at /projects/abc/scores?period=2025-06&snapshot=cumulative")
- **Browser behavior**: Back button, bookmarks, and tab restoration all work correctly

**Principle: The URL is the single source of truth for view state.** If the user can see it or configure it, it should be reflected in the URL.

#### URL Schema

```
# Project detail — period and tab in URL
/projects/:id/scores                          → scorecard tab (default)
/projects/:id/scores?period=2025-06           → specific period
/projects/:id/scores?period=2025-06&snapshot=punctual
/projects/:id/budget                          → trackr tab
/projects/:id/budget/contracts?status=active  → filtered view
/projects/:id/members                         → team/membership
/projects/:id/settings                        → project settings

# Global dashboard — period and filters in URL
/global?year=2025&month=6
/global?year=2025&month=6&dimensions=P_time,P_cost

# Admin — tab and subtab in URL
/admin/config                                 → configuration tab
/admin/slack                                  → slack tab
/admin/notifications/log                      → notifications > alert log
/admin/notifications/silences                 → notifications > silences
/admin/jobs                                   → jobs tab
/admin/users                                  → users tab

# Project list — filters in URL
/projects?view=grid&status=in_progress&search=foo
```

#### Implementation: `useUrlState` hook

A shared hook that syncs `useState`-like API with URL search params:

```typescript
// src/shared/hooks/useUrlState.ts
function useUrlState<T>(key: string, defaultValue: T): [T, (value: T) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  // Read from URL, fall back to default
  // Write updates URL without navigation
  ...
}

// Usage in components — drop-in replacement for useState
const [period, setPeriod] = useUrlState('period', null);
const [snapshot, setSnapshot] = useUrlState('snapshot', 'cumulative');
```

For tabs, use path segments instead of query params (cleaner URLs, better navigation):

```typescript
// Admin page uses nested routes instead of Tabs component state
<Route path="/admin/config" element={<ConfigurationTab />} />
<Route path="/admin/slack" element={<SlackTab />} />
<Route path="/admin/notifications/:subtab" element={<NotificationsTab />} />
<Route path="/admin/jobs" element={<JobsTab />} />
<Route path="/admin/users" element={<UsersTab />} />
```

#### MCP URL Generation

`public.py` interfaces and reporting services return URLs alongside data:

```python
# app/core/services/reporting.py
async def get_project_overview(project_id: str, db: AsyncSession) -> ProjectOverview:
    ...
    return ProjectOverview(
        scores=scores,
        budget=budget,
        url=f"/projects/{project_id}/scores?period={period}",  # direct link to this view
    )
```

MCP tools include these URLs in their responses, so the AI can say:
> "Project X scored 72 in P_cost this month. [View in Hub](/projects/abc/scores?period=2025-06)"

#### What breaks on reload today (will be fixed)

| View | State lost | Fix |
|------|-----------|-----|
| ProjectDetail — period | Reverts to latest | `?period=2025-06` |
| ProjectDetail — dimensions | All shown | `?dimensions=P_time,P_cost` |
| Admin — primary tab | Resets to Configuration | `/admin/jobs` path segment |
| Admin — nested tab | Resets to Alert Log | `/admin/notifications/silences` path |
| GlobalDashboard — period | Resets to current month | `?year=2025&month=6` |
| GlobalDashboard — export range | Lost completely | `?exportFrom=2025-01&exportTo=2025-06` |
| Projects — search/filters | Lost | `?search=foo&status=in_progress` |

### Module Boundary Rules

**1. A module NEVER imports directly from another module's internals.**

If tracker needs scores from scorecard, it goes through the public interface:

```python
# modules/scorecard/services/public.py  — the only file other modules can import
async def get_project_scores(project_id: str, db: AsyncSession) -> dict:
    """Public interface: returns latest scores for a project."""
    ...

# modules/trackr/services/budget_analysis.py
from app.modules.scorecard.services.public import get_project_scores  # OK
from app.modules.scorecard.services.calculators.time import ...       # FORBIDDEN
```

This means scorecard can refactor its internals freely — only `public.py` is a contract.

**2. Core imports are always allowed.**

Any module can import from `app.core.*`. Core never imports from modules.

**3. Write isolation, read flexibility.**

Each module only writes to its own tables. For business logic reads, use `public.py` interfaces to stay decoupled. For analytical/reporting reads (dashboards, exports), direct JOINs across module tables are allowed in dedicated query services under `core/services/`.

### Routing Strategy

**Problem**: Currently 18 routers mounted flat in `main.py` with inconsistent prefix strategies (some in the router file, some in `include_router`), a prefix collision (`projects_router` and `capture_router` share `/api/projects`), and inconsistent tags. With trackr this becomes 30+ routers — unmanageable.

**Solution**: Each module owns a `router.py` that aggregates its sub-routers. `main.py` only mounts module-level routers.

**AS IS** (18 flat mounts in main.py):
```python
# main.py — 18 include_router calls with mixed prefix strategies
app.include_router(auth_router, prefix="/api")              # prefix in router file
app.include_router(projects_router, prefix="/api/projects") # prefix in include_router
app.include_router(capture_router, prefix="/api/projects")  # COLLISION with above
app.include_router(metrics_router, prefix="/api/metrics")
app.include_router(scores_router, prefix="/api/scores")
# ... 13 more
```

**TO BE** (4-5 module mounts in main.py):
```python
# main.py — clean, only module-level routers
app.include_router(core_router)            # /api/auth/*, /api/projects/*, /api/admin/users/*
app.include_router(scorecard_router)       # /api/scorecard/*
app.include_router(trackr_router)          # /api/trackr/*
app.include_router(notifications_router)   # /api/notifications/*
```

```python
# app/modules/scorecard/router.py — module aggregates its own routers
from fastapi import APIRouter
from .api import metrics, scores, config, collectors, capture, exports

router = APIRouter(prefix="/api/scorecard", tags=["scorecard"])
router.include_router(metrics.router, prefix="/metrics")
router.include_router(scores.router, prefix="/scores")
router.include_router(config.router, prefix="/config")
router.include_router(capture.router)  # /api/scorecard/projects/{id}/capture-period
router.include_router(exports.router, prefix="/exports")
```

```python
# app/modules/trackr/router.py
router = APIRouter(prefix="/api/trackr", tags=["trackr"])
router.include_router(contracts.router, prefix="/contracts")
router.include_router(budgets.router, prefix="/budgets")
router.include_router(reports.router, prefix="/reports")
router.include_router(invoices.router, prefix="/invoices")
```

```python
# app/core/router.py — shared endpoints
router = APIRouter(prefix="/api", tags=["core"])
router.include_router(auth.router, prefix="/auth")
router.include_router(projects.router, prefix="/projects")
router.include_router(admin_users.router, prefix="/admin/users")
```

**Rules:**
- Prefixes always defined in `include_router`, never inside router files
- Every router has explicit `tags` for OpenAPI docs
- No two routers share the same prefix
- Module routers own all endpoints under their prefix — no cross-module routes

### Permissions Strategy

**Problem**: Currently only two global roles (`user`, `admin`). All authenticated users can view and edit all projects. This doesn't scale for trackr where:
- A PM should manage budget for **their** projects, not everyone's
- A finance user should approve invoices but not edit scorecard metrics
- A viewer should see dashboards but not modify anything

**Solution**: Three-layer permission model, built incrementally.

#### Layer 1: Global roles (exists today)

```python
CurrentUser = Annotated[TokenData, Depends(get_current_user)]  # any authenticated user
AdminUser = Annotated[TokenData, Depends(require_role("admin"))]  # platform admin
```

Kept as-is. Admin = platform administration (user management, system config).

#### Layer 2: Project membership (new — required for trackr)

New `project_members` table in core:

```sql
project_members
├── id           UUID PRIMARY KEY
├── user_id      FK → users
├── project_id   FK → projects
├── role         ENUM('viewer', 'contributor', 'manager', 'owner')
├── created_at   TIMESTAMP
└── UNIQUE(user_id, project_id)
```

| Project Role | Can view | Can edit metrics/budget | Can manage project settings | Can assign members |
|-------------|----------|------------------------|---------------------------|-------------------|
| **viewer** | Yes | No | No | No |
| **contributor** | Yes | Yes (own data) | No | No |
| **manager** | Yes | Yes (all) | Yes | Yes |
| **owner** | Yes | Yes (all) | Yes | Yes |

Composable dependencies:

```python
# app/core/permissions.py

class ProjectRole(str, Enum):
    VIEWER = "viewer"
    CONTRIBUTOR = "contributor"
    MANAGER = "manager"
    OWNER = "owner"

def require_project_role(min_role: ProjectRole):
    """Factory: checks user has at least min_role on the project."""
    async def dependency(
        project_id: UUID,
        current_user: CurrentUser,
        db: DBSession,
    ) -> ProjectMembership:
        # Admins bypass project-level checks
        if "admin" in current_user.roles:
            return ProjectMembership(role=ProjectRole.OWNER, ...)
        membership = await get_membership(current_user.user_id, project_id, db)
        if not membership or membership.role < min_role:
            raise HTTPException(403, "Insufficient project permissions")
        return membership
    return dependency

# Dependency aliases
ProjectViewer = Annotated[ProjectMembership, Depends(require_project_role(ProjectRole.VIEWER))]
ProjectContributor = Annotated[ProjectMembership, Depends(require_project_role(ProjectRole.CONTRIBUTOR))]
ProjectManager = Annotated[ProjectMembership, Depends(require_project_role(ProjectRole.MANAGER))]
```

Usage in endpoints:

```python
# Anyone on the project can view budget
@router.get("/contracts/{project_id}")
async def get_contracts(project_id: UUID, member: ProjectViewer, db: DBSession):
    ...

# Only managers can approve invoices
@router.post("/invoices/{invoice_id}/approve")
async def approve_invoice(invoice_id: UUID, member: ProjectManager, db: DBSession):
    ...
```

#### Layer 3: Module access (future, not Phase 1)

Optional — restrict which modules a user can access per project. Only implement if there's a real need (e.g., finance team shouldn't see scorecard metrics).

```sql
-- Future: add to project_members
modules TEXT[] DEFAULT '{scorecard,trackr}'  -- modules this user can access on this project
```

Not needed for Phase 1. By default all project members access all modules.

#### Backward compatibility

During the transition (scorecard still uses flat `CurrentUser`):
- Existing scorecard endpoints keep using `CurrentUser` — no breakage
- New trackr endpoints use `ProjectContributor` / `ProjectManager`
- Scorecard endpoints migrate to project-scoped permissions gradually (Phase 2)
- Admin role always bypasses project-level checks

### Shared Services

- Authentication (Google SSO + JWT) - already implemented
- Project membership and permissions — new, in core
- Projects and Teams - central entity linking both modules
- Slack notifications - already implemented
- Infrastructure and deploy - single docker compose

### Independent per Module

- **Scorecard**: metrics, calculators, normalizers, collectors (Jira/GitHub)
- **Trackr**: contracts, invoices, budget lines, time reports, rates

## Current VizzTracker Data Model

14 business tables with the following structure:

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

### State Machines (aasm_state)

- **contracts**: lifecycle states (likely draft, active, closed)
- **invoices**: payment states (likely pending, invoiced, paid)
- **reporting_periods**: period states (likely open, closed)

## Data Model Optimizations for Migration

### 1. Float to Numeric for Financial Data

Current: `double precision` for `budget`, `cost`, `amount`, `contract_rate`, `base_rate`

Change to: `numeric(12,2)` to avoid floating point rounding errors in financial calculations.

### 2. Drop Devise Columns from Users

Columns `encrypted_password`, `reset_password_token`, `reset_password_sent_at`, `remember_created_at` are not needed. The Hub uses Google SSO.

### 3. Fix Inconsistent FK Types

`users.team_id` and `reports.team_id` are `integer` while all other FKs are `bigint`. Align to the chosen PK strategy.

### 4. Primary Key Strategy: bigint to UUID

The Hub uses UUIDs, VizzTracker uses sequential bigint. Migration requires:

1. Create new tables with UUID primary keys
2. Use a mapping table per entity: `legacy_id (bigint) -> new_id (UUID)`
3. Insert in dependency order: teams/roles/rates first, then projects, contracts, etc.
4. Resolve FKs using the mapping tables
5. Validate row counts and referential integrity

## Migration Strategy

1. **Create SQLAlchemy models** matching the optimized structure
2. **Write migration script** (one-time execution) with ID mapping
3. **Run on local copy first** - never touch production until verified
4. **Validate**: row counts, FK integrity, financial totals match
5. **Build CRUD endpoints** under `/api/trackr/`
6. **Build React components** for budget/time tracking views
7. **Integrate with project view** as additional tabs

## Structure: AS IS → TO BE

### Backend AS IS

```
app/
├── api/                  # 21 router files, all flat
│   ├── auth.py
│   ├── projects.py
│   ├── metrics.py
│   ├── scores.py
│   ├── collectors.py
│   ├── capture.py
│   ├── jobs.py
│   ├── slack_admin.py
│   └── ...
├── core/                 # 7 files (auth, security)
├── models/               # 16 files, single __init__.py re-exports all
│   ├── project.py
│   ├── user.py
│   ├── metrics.py
│   ├── slack.py
│   └── ...
├── services/             # 53 files
│   ├── calculators/      # 13 scorecard calculators
│   ├── collectors/       # 25 files (Jira, GitHub, Dependabot)
│   ├── normalizers/      # 3 files
│   ├── metrics_service.py
│   ├── slack_service.py
│   ├── alert_service.py
│   └── ...
├── worker/               # 6 files (ARQ tasks, cron jobs)
├── utils/                # 4 files
├── config.py
├── database.py
└── main.py               # Mounts 17 routers
```

**111 Python files, 277 internal imports, 0 circular dependencies.**
Dependency direction is clean: models ← services ← api.

### Backend TO BE

```
app/
├── core/                          # Shared kernel (extracted first)
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── middleware/
│   └── models/
│       ├── project.py             # ← moved from app/models/
│       ├── user.py                # ← moved from app/models/
│       └── team.py
│
├── modules/
│   ├── scorecard/                 # ← current app/ code, relocated gradually
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   │   ├── calculators/
│   │   │   ├── collectors/
│   │   │   ├── normalizers/
│   │   │   └── public.py          # Cross-module interface
│   │   └── worker/
│   │
│   ├── trackr/                    # ← NEW, born clean
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   │   └── public.py
│   │   └── worker/
│   │
│   └── notifications/             # ← extracted from scorecard (Slack, alerts)
│       ├── api/
│       ├── models/
│       └── services/
│
└── main.py
```

### Frontend AS IS

```
src/
├── components/           # 90 files, flat feature folders
│   ├── ui/               # 26 shadcn primitives
│   ├── ProjectDetail/    # 21 files (biggest cluster)
│   ├── SubIndicatorCard/ # 5 files
│   ├── Forms/            # 5 files
│   ├── Admin/            # 2 files
│   ├── NotificationsAdmin/ # 4 files
│   ├── Settings/         # 2 files
│   ├── Dashboard/        # 2 files
│   ├── layout/           # 3 files
│   └── ScoreCard/        # 2 files
├── hooks/                # 22 files, all relative imports
├── pages/                # 12 files
├── services/             # 12 API client files
├── types/                # 10 files
├── utils/                # 6 files
├── constants/            # 2 files
├── contexts/             # 2 files
└── App.tsx
```

**154 source files, ~368 import statements, mixed relative/absolute paths.**

### Frontend TO BE

```
src/
├── shared/                        # Extracted shared kernel
│   ├── components/                # ← ui/, layout/, ErrorBoundary, ProtectedRoute
│   ├── contexts/                  # ← AuthContext
│   ├── hooks/                     # ← useAuth, useProjects (shared)
│   ├── services/                  # ← API client
│   ├── types/                     # ← shared types
│   ├── utils/                     # ← formatters, dateUtils
│   └── constants/                 # ← dates, timing
│
├── modules/
│   ├── scorecard/                 # ← current scorecard code, relocated gradually
│   │   ├── components/            # ProjectDetail/, ScoreCard/, SubIndicatorCard/
│   │   ├── hooks/                 # useScores, useMetrics, useConfig
│   │   └── pages/                 # ProjectScores, GlobalDashboard
│   │
│   ├── tracker/                   # ← NEW, born clean
│   │   ├── components/
│   │   ├── hooks/
│   │   └── pages/
│
└── App.tsx
```

## Migration Strategy: Strangler Fig

**NOT a big-bang refactor.** New code follows the target structure from day 1. Existing code migrates gradually, driven by need.

### Why strangler fig, not big-bang

| Approach | Risk | Time blocked | Value delivery |
|----------|------|--------------|----------------|
| **Big-bang refactor** | High — 220+ files touched at once | ~2 weeks, nothing ships | Zero until done |
| **Divide & conquer** | Medium — still refactoring before building | ~1 week | Zero until done |
| **Strangler fig** | Low — old code keeps working as-is | ~2-3h upfront, rest organic | Trackr features ship immediately |

### Execution order

```
Phase 0 (prerequisite — MUST complete before Phase 1)
│
│  T0.1-T0.3: Extract core entities + shared infra (~2-3h)
│    Project, User → app/core/models/
│    database, config, auth → app/core/
│
│  T0.4: Module router architecture (~3-4h)
│    18 flat mounts → 3-5 module routers
│    Fix prefix collision, consistent tags
│
│  T0.5-T0.6: Project membership + permissions (~4-5h)
│    project_members table, require_project_role()
│    Membership CRUD endpoints + frontend UI
│
│  T0.7-T0.8: URL-driven state (~4-5h)
│    useUrlState hook, admin nested routes
│    Scorecard views: period, snapshot, filters in URL
│
Phase 1 (trackr development)
│  Build app/modules/trackr/ from scratch — clean structure from day 1
│  Build src/modules/tracker/ — clean frontend module
│  All trackr endpoints use project-scoped permissions from T0.5
│  Scorecard stays exactly where it is, untouched
│
Phase 2 (organic scorecard migration, no deadline)
│  As scorecard files need changes for other reasons, move them to modules/scorecard/
│  Migrate scorecard endpoints to project-scoped permissions (gradually)
│  Extract notifications to modules/notifications/ when trackr needs alerts
│  Eventually all scorecard code lands in modules/scorecard/
│
Phase 3 (cleanup)
│  Remove old app/api/, app/models/, app/services/ once empty
│  Verify no legacy imports remain
```

### Coexistence during migration

During phases 1-2, both layouts coexist:

```python
# Old scorecard code — still works, untouched
from app.models.metrics import MetricsDB
from app.services.calculators.time import TimeCalculator

# New trackr code — follows target structure
from app.modules.trackr.models.contract import ContractDB
from app.core.models.project import ProjectDB

# Cross-module — through public interface only
from app.modules.trackr.services.public import get_budget_summary
```

This is intentional, not technical debt. The old paths keep working until organically replaced.

### Effort estimate

| Phase | Backend | Frontend | Total |
|-------|---------|----------|-------|
| 0. Core entities (T0.1-T0.3) | 2-3h | — | 2-3h |
| 0. Module routers (T0.4) | 3-4h | URL verification | 3-4h |
| 0. Permissions (T0.5-T0.6) | 3-4h | 1-2h | 4-5h |
| 0. URL-driven state (T0.7-T0.8) | — | 4-5h | 4-5h |
| 1. Build trackr module | New code, no refactor | New code, no refactor | (part of trackr dev) |
| 2. Migrate scorecard (organic) | ~4-5h spread over weeks | ~3-4h spread over weeks | ~7-9h |
| 3. Cleanup | ~1h | ~1h | ~2h |
| **Total refactor overhead** | | | **~23-28h** |

Phase 0 is ~14-17h total — a solid investment before building trackr. Without it, trackr would have wrong-direction imports, no project-scoped permissions, a routing mess, and URLs that can't be shared or traced by the MCP. Most of the work is mechanical or well-defined. Zero circular dependencies in current code makes it safe.

## Guardrails: Enforcing the Pattern

The modular structure only works if it's enforced consistently. Three layers of protection:

### 1. CLAUDE.md rules (AI enforcement)

Module boundary rules are documented in CLAUDE.md (see "Modular Architecture Rules" section). Every Claude Code session reads these rules before writing code. This is the primary enforcement mechanism during development.

### 2. Import linting (CI enforcement)

Backend — custom Ruff rule or pre-commit check:
```python
# Forbidden: cross-module internal imports
# modules/trackr/ importing from modules/scorecard/services/calculators/ → ERROR
# modules/trackr/ importing from modules/scorecard/services/public → OK
# Any module importing from core/ → OK
```

Frontend — ESLint `import/no-restricted-paths`:
```json
{
  "rules": {
    "import/no-restricted-paths": ["error", {
      "zones": [{
        "target": "./src/modules/tracker",
        "from": "./src/modules/scorecard",
        "except": ["./public"]
      }, {
        "target": "./src/modules/scorecard",
        "from": "./src/modules/tracker",
        "except": ["./public"]
      }]
    }]
  }
}
```

### 3. Code review checklist

For any PR that touches module boundaries:
- [ ] New models placed in correct module (core vs module-private)?
- [ ] Cross-module imports go through `public.py` / `public/` only?
- [ ] Module only writes to its own tables? (reads via `public.py` or `core/services/` for analytics)
- [ ] New shared entity follows the decision rule (Level 1/2/3)?

## Future: MCP Server for AI-Powered Analysis

An MCP (Model Context Protocol) server would allow Claude (Desktop, Code, or custom agents) to query the Hub's data across all modules — cross-referencing scores, budgets, timelines, and generating complex reports conversationally.

**IMPORTANT: The MCP server is READ-ONLY.** No write tools. This is a deliberate constraint — AI agents can analyze and report, but cannot modify project data. Write operations remain under human control through the Hub UI. This can be revisited later with proper audit trails and approval workflows.

### Why the modular architecture enables this

Each `public.py` is already a tool candidate. Each query service in `core/services/` is an analytical tool candidate. No new abstraction layer needed.

```
Claude (MCP client)
  │
  │  Tools (read — single module)
  ├── get_project_scores(project_id)        → scorecard.public
  ├── get_budget_summary(project_id)        → trackr.public
  ├── get_budget_forecast(project_id)       → trackr.public
  │
  │  Tools (analytics — cross-module)
  ├── get_project_health(project_id)        → scorecard.public + trackr.public
  ├── compare_projects(ids[])               → core.services.reporting
  ├── find_at_risk_projects()               → core.services.reporting
  ├── generate_monthly_report(project_id)   → core.services.reporting (cross-module JOINs)
  ├── team_workload_analysis(team_id)       → trackr.public + scorecard.public
  │
  │  Resources
  ├── projects://list                       → project listing
  └── projects://{id}/summary               → project summary
```

### Integration strategy: two phases

**Phase 1 — Read-only API wrapper (start here)**

The MCP server makes GET requests to the Hub's existing API. Simplest path, no code duplication, inherently read-only.

```
Claude → MCP Server → HTTP GET only → Hub API (localhost:8000)
```

```python
# mcp_server/tools/health.py
@mcp.tool()
async def get_project_health(project_id: str) -> dict:
    """Get combined health view: scores + budget + timeline."""
    async with httpx.AsyncClient(base_url=HUB_API_URL, headers=auth_headers) as client:
        scores = await client.get(f"/api/scorecard/scores/project/{project_id}")
        budget = await client.get(f"/api/trackr/contracts/project/{project_id}/summary")
        return {"scores": scores.json(), "budget": budget.json()}
```

- Only GET endpoints exposed — no POST/PUT/DELETE
- Reuses all existing validation and auth
- Limited to what the API exposes
- Effort: ~3-4 days for a useful set of read tools

**Phase 2 — Read-only direct service imports (when needed)**

The MCP server imports the Hub's Python service layer directly. Enables analytical queries that the API doesn't expose. Still read-only.

```
Claude → MCP Server → Python imports → Hub services + DB (SELECT only)
```

```python
# mcp_server/tools/analytics.py
from app.modules.scorecard.services.public import get_project_scores
from app.modules.trackr.services.public import get_budget_summary
from app.core.services.reporting import get_project_overview

@mcp.tool()
async def cross_module_analysis(project_id: str) -> dict:
    """Deep analysis combining all module data in a single efficient query."""
    async with async_session_maker() as db:
        overview = await get_project_overview(project_id, db)
        return overview
```

- Full access to read operations and cross-module JOINs
- More powerful but coupled to deployment
- Effort: ~2-3 additional days on top of Phase 1

**Phase 3 (future, not planned) — Write tools with approval workflow**

Write tools should only be considered when:
- Audit trail is implemented (who changed what, when, via which tool)
- Approval workflow exists (AI proposes change → human approves → change applied)
- Scope is limited to low-risk operations first (e.g., updating manual metrics, not deleting projects)

### Authentication for MCP

Three levels depending on deployment context:

**Level 1 — Local MCP (Claude Desktop / Claude Code)**

MCP server runs on the developer's machine. Auth via dedicated API key.

```bash
# MCP server config
HUB_API_URL=http://localhost:8000
HUB_API_KEY=mcp-dev-key-xxx
```

Backend change: extend `get_current_user()` to accept `X-API-Key` header. Add `api_keys` table (user_id, key_hash, scopes, created_at, last_used_at).

Effort: ~half day.

**Level 2 — Shared MCP (team, runs on EC2)**

MCP server runs alongside the Hub. Users connect via SSE/Streamable HTTP transport.

```
Claude Desktop → SSE → MCP Server (EC2:3001) → Hub API (localhost:8000)
```

Auth flow:
1. MCP client requests a tool → MCP server returns "auth required" + login URL
2. User authenticates via Google SSO in browser
3. Callback delivers JWT to MCP server
4. MCP server stores JWT per user session
5. All Hub requests use the user's JWT (not a service account)

Effort: ~2-3 days. Requires session management in the MCP server.

**Level 3 (future) — Granular permissions for write tools**

Only relevant if/when write tools are introduced. The Hub's existing role-based auth (user/admin) would apply automatically through the API wrapper — no extra work needed in the MCP server.

### Design guidelines for MCP readiness

These apply now, during normal development, not when building the MCP server:

1. **`public.py` signatures should be self-describing.** Clear parameter names, typed returns, docstrings. An AI agent will use these as tool descriptions.

2. **Return rich, structured data.** Not just IDs — include names, dates, status. The AI needs context to reason about results.

```python
# Good — AI can reason about this
async def get_budget_summary(project_id: str, db: AsyncSession) -> BudgetSummary:
    """Returns budget total, consumed, remaining, burn rate, and forecast date."""
    ...

# Bad — AI gets a number with no context
async def get_budget(project_id: str, db: AsyncSession) -> float:
    ...
```

3. **Analytical query services in `core/services/`** are the highest-value MCP tools. Prioritize cross-module queries that would be tedious to do manually (project comparisons, trend analysis, risk detection).

### Complexity summary

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| MCP server skeleton (Python SDK) | ~1 day | None |
| Read tools (API wrapper, Phase 1) | ~2-3 days | Existing GET endpoints |
| API key auth (Level 1) | ~half day | `api_keys` table |
| Analytical tools (direct imports, Phase 2) | ~2-3 days | `core/services/reporting.py` |
| Shared MCP with OAuth (Level 2) | ~2-3 days | Session management |
| **Total (read-only MCP server)** | **~6-9 days** | |

Not a priority now, but the modular architecture is pre-building the foundation. Every `public.py` written today is a read-only tool ready to expose tomorrow.

## Tasklist & Definition of Done

Each task has explicit acceptance criteria. A task is **not done** until all criteria are met.

### Phase 0: Extract Core + Hub Infrastructure

**T0.1 — Extract `ProjectDB` model to `app/core/models/`**
- [ ] `app/core/models/project.py` exists with `ProjectDB` class
- [ ] `app/core/models/__init__.py` re-exports `ProjectDB`
- [ ] All existing imports (`from app.models.project import ...`) updated (~9 files)
- [ ] Old `app/models/project.py` either removed or re-exports from core
- [ ] All backend tests pass (`pytest`)
- [ ] No circular imports

**T0.2 — Extract `User` model to `app/core/models/`**
- [ ] `app/core/models/user.py` exists with `User` class
- [ ] All existing imports updated (~3 files)
- [ ] All backend tests pass
- [ ] Auth flow works end-to-end (login → cookie → authenticated request)

**T0.3 — Extract shared infra to `app/core/`**
- [ ] `app/core/database.py` — DB engine, session maker, `DBSession` dependency
- [ ] `app/core/config.py` — Pydantic settings
- [ ] `app/core/auth.py` — `get_current_user`, `AdminUser`, JWT logic
- [ ] All existing imports updated
- [ ] All backend tests pass
- [ ] Server starts and all API endpoints respond correctly

**T0.4 — Module router architecture**
- [ ] `app/core/router.py` aggregates core sub-routers (auth, projects, admin/users)
- [ ] Existing scorecard routers grouped into a temporary `scorecard_router` (can still live in `app/api/` but mounted as a single unit)
- [ ] `main.py` reduced from 18 `include_router` calls to 3-5 module mounts
- [ ] Prefix collision resolved (capture_router no longer shares `/api/projects`)
- [ ] All routers use prefix in `include_router`, never inside router files
- [ ] All routers have explicit `tags` for OpenAPI docs
- [ ] OpenAPI docs (`/docs`) show endpoints grouped by module
- [ ] All existing frontend API calls still work (no URL changes for existing endpoints, or frontend updated in sync)
- [ ] All backend tests pass
- [ ] All frontend tests pass

**T0.5 — Project membership model + permissions**
- [ ] `app/core/models/project_member.py` with `ProjectMemberDB` model
- [ ] `ProjectRole` enum: `viewer`, `contributor`, `manager`, `owner`
- [ ] Alembic migration creates `project_members` table with UNIQUE(user_id, project_id)
- [ ] `app/core/permissions.py` with `require_project_role()` factory
- [ ] Dependency aliases: `ProjectViewer`, `ProjectContributor`, `ProjectManager`
- [ ] Admin role bypasses project-level checks (always treated as owner)
- [ ] CRUD endpoints for project membership:
  - [ ] `GET /api/projects/{id}/members` — list members
  - [ ] `POST /api/projects/{id}/members` — add member (ProjectManager or Admin)
  - [ ] `PATCH /api/projects/{id}/members/{user_id}` — update role (ProjectManager or Admin)
  - [ ] `DELETE /api/projects/{id}/members/{user_id}` — remove member (ProjectManager or Admin)
- [ ] Seed data: project creators are automatically assigned `owner` role
- [ ] Tests: permission denied (403) for insufficient role, permission granted for sufficient role
- [ ] Tests: admin bypass works for all project-level checks
- [ ] Existing scorecard endpoints unchanged (still use `CurrentUser`, no breakage)

**T0.6 — Frontend project membership UI**
- [ ] Members tab or section in project settings
- [ ] Add/remove members with role selector
- [ ] Current user's role visible in project view
- [ ] Non-members see appropriate access denied state (or are filtered from project list)
- [ ] Admin sees all projects regardless of membership
- [ ] All frontend tests pass

**T0.7 — URL-driven state: shared hook + admin routes**
- [ ] `src/shared/hooks/useUrlState.ts` hook implemented (syncs useState with URL search params)
- [ ] Admin page migrated from `<Tabs defaultValue>` to nested routes:
  - [ ] `/admin/config`, `/admin/slack`, `/admin/notifications/:subtab`, `/admin/jobs`, `/admin/users`
  - [ ] Active tab determined by route, not component state
  - [ ] Direct navigation to any admin tab works (paste URL → correct tab shown)
- [ ] All admin tab links updated in navigation
- [ ] Browser back/forward works between admin tabs
- [ ] All frontend tests pass

**T0.8 — URL-driven state: scorecard views**
- [ ] ProjectDetail period selection uses `?period=YYYY-MM` search param
- [ ] Snapshot type uses `?snapshot=cumulative|punctual` search param
- [ ] Page reload preserves selected period and snapshot type
- [ ] GlobalDashboard period uses `?year=YYYY&month=M` search params
- [ ] Projects list search/filter uses `?search=X&status=Y&view=list|grid` search params
- [ ] Shareable: copy URL → paste in new tab → identical view
- [ ] Dimension visibility uses `?dimensions=P_time,P_cost,...` (optional, lower priority)
- [ ] All frontend tests pass

### Phase 1: Build Trackr Module

**T1.1 — SQLAlchemy models for trackr**
- [ ] All 14 business tables modeled in `app/modules/trackr/models/`
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
- [ ] Production data never touched until local validation passes

**T1.3 — Trackr CRUD endpoints**
- [ ] `app/modules/trackr/router.py` aggregates sub-routers, prefix="/api/trackr"
- [ ] Sub-routers for: contracts, budget_lines, invoices, reports, reporting_periods
- [ ] Project-scoped permissions on all endpoints:
  - [ ] Read endpoints use `ProjectViewer`
  - [ ] Write endpoints use `ProjectContributor` or `ProjectManager`
  - [ ] Approve/manage endpoints use `ProjectManager`
- [ ] Input validation (Pydantic schemas with proper types)
- [ ] Write operations scoped to trackr's own tables only
- [ ] Tests for each endpoint (happy path + permission denied + validation errors)
- [ ] No trailing slashes on routes

**T1.4 — Trackr `public.py` interface**
- [ ] `app/modules/trackr/services/public.py` exists
- [ ] `get_budget_summary(project_id, db)` → returns `BudgetSummary` (total, consumed, remaining, burn_rate)
- [ ] `get_time_summary(project_id, period, db)` → returns aggregated time data
- [ ] Functions have typed parameters, typed returns, and docstrings
- [ ] Return rich structured data (not just numbers — include names, dates, context)
- [ ] Unit tests for each public function

**T1.5 — Trackr frontend module**
- [ ] `src/modules/tracker/` directory with `components/`, `hooks/`, `pages/`
- [ ] Hooks use centralized query keys (extend `queryKeys.ts`)
- [ ] API client uses `credentials: 'include'` for auth
- [ ] Pages accessible via routes under `/projects/:id/budget`
- [ ] All view state URL-driven from day 1 (uses `useUrlState` hook from T0.7):
  - [ ] Contract filters: `?status=active&sort=date`
  - [ ] Reporting period: `?period=2025-06`
  - [ ] Invoice filters: `?invoiceStatus=pending`
- [ ] Page reload preserves all filter/view state
- [ ] No imports from `src/modules/scorecard/` internals
- [ ] Shared components imported from `src/shared/` only
- [ ] Responsive layout (follows existing UI patterns)
- [ ] All frontend tests pass (`npm test`)

**T1.6 — Project view integration**
- [ ] Project detail page shows tabs from both modules (scores + budget)
- [ ] Tab navigation works without full page reload
- [ ] Unified project list shows summary data from both modules
- [ ] Projects without trackr data show graceful empty state (not errors)

### Phase 2: Organic Scorecard Migration

**T2.1 — Migrate scorecard to `app/modules/scorecard/`**
- [ ] All scorecard API routers in `app/modules/scorecard/api/`
- [ ] All scorecard models in `app/modules/scorecard/models/`
- [ ] All scorecard services in `app/modules/scorecard/services/`
- [ ] `app/modules/scorecard/services/public.py` exposes `get_project_scores(project_id, db)`
- [ ] No remaining scorecard code in flat `app/api/`, `app/models/`, `app/services/`
- [ ] All backend tests pass
- [ ] All frontend tests pass

**T2.2 — Extract notifications module**
- [ ] Slack service, alert service, templates in `app/modules/notifications/`
- [ ] Notification models in `app/modules/notifications/models/`
- [ ] Both scorecard and trackr can trigger notifications via `notifications.public`
- [ ] All notification tests pass

**T2.3 — Migrate scorecard frontend to `src/modules/scorecard/`**
- [ ] All scorecard components in `src/modules/scorecard/components/`
- [ ] All scorecard hooks in `src/modules/scorecard/hooks/`
- [ ] All scorecard pages in `src/modules/scorecard/pages/`
- [ ] Shared UI components in `src/shared/components/`
- [ ] No remaining scorecard code in flat `src/components/`, `src/hooks/`, `src/pages/`
- [ ] All frontend tests pass

### Phase 3: Cleanup

**T3.1 — Remove legacy structure**
- [ ] Empty `app/api/`, `app/models/`, `app/services/` directories removed
- [ ] No orphan imports pointing to old paths
- [ ] `app/models/__init__.py` removed or redirects to core + modules
- [ ] All tests pass (backend + frontend)

**T3.2 — Import linting in CI**
- [ ] Backend: pre-commit or CI check blocks cross-module internal imports
- [ ] Frontend: ESLint `import/no-restricted-paths` configured and passing
- [ ] CI pipeline rejects violations

### Analytical Layer

**T-A.1 — Core reporting services**
- [ ] `app/core/services/reporting.py` exists
- [ ] Cross-module queries for dashboards (project overview, comparatives)
- [ ] Functions have typed parameters, typed returns, and docstrings
- [ ] Used by frontend for unified views (Global Dashboard, project overview)
- [ ] Tests validate correctness of cross-module aggregations

### MCP Server (Future — Read Only)

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

**T-MCP.3 — Read tools (Phase 1 — API wrapper)**
- [ ] Tools call Hub GET endpoints only (no POST/PUT/DELETE)
- [ ] Minimum viable tools: `get_project_health`, `compare_projects`, `find_at_risk_projects`
- [ ] Error handling: Hub errors propagated as clear MCP tool errors
- [ ] Tool descriptions and parameter types suitable for AI agent consumption

**T-MCP.4 — Analytical tools (Phase 2 — direct imports)**
- [ ] Tools import from `public.py` interfaces and `core/services/reporting.py`
- [ ] Cross-module analysis: `generate_monthly_report`, `team_workload_analysis`
- [ ] DB sessions are read-only (no commits)
- [ ] Tests validate tool outputs match expected data

### Task dependencies

```
Phase 0 (prerequisite — all must complete before Phase 1):

T0.1 ─┐
T0.2 ─┼── T0.3 ──► T0.4 (routers)
      │              │
      │              ▼
      └──────────► T0.5 (permissions) ──► T0.6 (membership UI)

T0.7 (useUrlState + admin routes) ──► T0.8 (scorecard URL state)
  ↑ independent of T0.1-T0.6, can run in parallel
                                            │
                                            ▼
Phase 1 (trackr — critical path):        GATE: Phase 0 complete (T0.1-T0.8)
                                            │
                    T1.1 ──► T1.2 ──► T1.3 ──► T1.4 ──► T1.6
                                       T1.5 ──────────────► T1.6
                                                              │
Phase 2 (organic, no deadline):                               │
                    T2.1 ──► T2.2 ──► T2.3 ──► T3.1 ──► T3.2 │
                                                              │
Analytical + MCP:                                             │
                    T-A.1 ◄───────────────────────────────────┘
                      │
                    T-MCP.1 ──► T-MCP.2 ──► T-MCP.3 ──► T-MCP.4
```

**Phase 0 is a hard gate.** No Phase 1 work starts until T0.1-T0.6 are complete. This ensures trackr is built on the right foundation: core entities extracted, routers modularized, and project-scoped permissions available.

Phase 2 (scorecard migration) runs in parallel when convenient. MCP depends on the analytical layer (T-A.1) being in place.

## Future Scalability

The modular monolith makes it straightforward to:

- Add more modules to the Hub (same pattern: new module folder, new router, new routes)
- Extract a module to its own service if ever needed (write isolation already in place)
- Share data between modules through service interfaces (writes) and direct JOINs in core query services (analytics)
- Expose module capabilities to AI agents via MCP — `public.py` interfaces map directly to MCP tools
