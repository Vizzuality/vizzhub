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

### Database: One PostgreSQL, Three Schemas

```
shared.*        -> users, teams, projects, roles (common entities)
scorecard.*     -> metrics, config_parameters, oauth_tokens, slack...
trackr.*        -> contracts, invoices, budget_lines, reports, rates...
```

### Backend: One FastAPI, Separate Routers

```
/api/auth/*          -> shared
/api/projects/*      -> shared
/api/scorecard/*     -> scorecard module
/api/trackr/*        -> trackr module
```

### Frontend: One React App, Routes per Module

```
/projects            -> unified list
/projects/:id        -> project view with tabs from both modules
/projects/:id/scores -> scorecard
/projects/:id/budget -> trackr
```

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

1. **Create SQLAlchemy models** in `trackr` schema matching the optimized structure
2. **Write migration script** (one-time execution) with ID mapping
3. **Run on local copy first** - never touch production until verified
4. **Validate**: row counts, FK integrity, financial totals match
5. **Build CRUD endpoints** under `/api/trackr/`
6. **Build React components** for budget/time tracking views
7. **Integrate with project view** as additional tabs

## Future Scalability

The modular monolith with separate schemas makes it straightforward to:

- Add more modules to the Hub (same pattern: new schema, new router, new routes)
- Extract a module to its own service if needed (schema is already isolated)
- Share data between modules through well-defined service interfaces, not cross-schema queries
