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

### Shared Services

- Authentication (Google SSO + JWT) - already implemented
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
Phase 0 (prerequisite, ~2-3h)
│  Extract Project + User models to app/core/models/
│  Update imports in existing code (9 files for Project, 3 for User)
│  This unblocks trackr without creating wrong-direction dependencies
│
Phase 1 (trackr development)
│  Build app/modules/trackr/ from scratch — clean structure from day 1
│  Build src/modules/tracker/ — clean frontend module
│  Scorecard stays exactly where it is, untouched
│
Phase 2 (organic scorecard migration, no deadline)
│  As scorecard files need changes for other reasons, move them to modules/scorecard/
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
| 0. Extract core entities | 2-3h | — | 2-3h |
| 1. Build trackr module | New code, no refactor | New code, no refactor | (part of trackr dev) |
| 2. Migrate scorecard (organic) | ~4-5h spread over weeks | ~3-4h spread over weeks | ~7-9h |
| 3. Cleanup | ~1h | ~1h | ~2h |
| **Total refactor overhead** | | | **~12-14h** |

Most of this is mechanical (move file + update imports), not architectural. Zero circular dependencies in current code makes it safe.

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

An MCP (Model Context Protocol) server would allow Claude (Desktop, Code, or custom agents) to interact with the Hub's data across all modules — cross-referencing scores, budgets, timelines, and generating complex reports conversationally.

### Why the modular architecture enables this

Each `public.py` is already a tool candidate. Each query service in `core/services/` is an analytical tool candidate. No new abstraction layer needed.

```
Claude (MCP client)
  │
  │  Tools (read)
  ├── get_project_health(project_id)        → scorecard.public + trackr.public
  ├── compare_projects(ids[])               → core.services.reporting
  ├── find_at_risk_projects()               → core.services.reporting
  │
  │  Tools (analytics)
  ├── generate_monthly_report(project_id)   → core.services.reporting (cross-module JOINs)
  ├── budget_forecast(project_id)           → trackr.public
  ├── team_workload_analysis(team_id)       → trackr.public + scorecard.public
  │
  │  Tools (write)
  ├── update_metrics(project_id, data)      → scorecard services
  ├── log_time_report(project_id, data)     → trackr services
  │
  │  Resources
  ├── projects://list                       → project listing
  └── projects://{id}/summary               → project summary
```

### Integration strategy: two phases

**Phase 1 — API wrapper (start here)**

The MCP server makes HTTP calls to the Hub's existing API. Simplest path, no code duplication.

```
Claude → MCP Server → HTTP requests → Hub API (localhost:8000)
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

- Reuses all existing validation and auth
- Limited to what the API exposes
- Effort: ~3-4 days for a useful set of read tools

**Phase 2 — Direct service imports (when needed)**

The MCP server imports the Hub's Python service layer directly. Enables analytical queries that the API doesn't expose.

```
Claude → MCP Server → Python imports → Hub services + DB
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

- Full access to business logic and cross-module JOINs
- More powerful but coupled to deployment
- Effort: ~2-3 additional days on top of Phase 1

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

**Level 3 — Granular permissions**

Different tools require different roles. This works automatically if using the API wrapper approach — the Hub already validates roles per endpoint.

```python
@mcp.tool()
async def delete_project(project_id: str) -> dict:
    """Requires admin role. Hub API validates the user's JWT."""
    response = await client.delete(f"/api/projects/{project_id}")
    # Hub returns 403 if user is not admin — MCP propagates the error
    ...
```

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
| Read tools (API wrapper) | ~2-3 days | Existing API endpoints |
| API key auth (Level 1) | ~half day | `api_keys` table |
| Write tools | ~1-2 days | Existing API endpoints |
| Analytical tools (direct imports) | ~2-3 days | `core/services/reporting.py` |
| Shared MCP with OAuth (Level 2) | ~2-3 days | Session management |
| **Total (full MCP server)** | **~8-12 days** | |

Not a priority now, but the modular architecture is pre-building the foundation. Every `public.py` written today is a tool ready to expose tomorrow.

## Future Scalability

The modular monolith makes it straightforward to:

- Add more modules to the Hub (same pattern: new module folder, new router, new routes)
- Extract a module to its own service if ever needed (write isolation already in place)
- Share data between modules through service interfaces (writes) and direct JOINs in core query services (analytics)
- Expose module capabilities to AI agents via MCP — `public.py` interfaces map directly to MCP tools
