# VizzHub Data Model Guide

VizzHub is Vizzuality's internal operations platform. It has 6 modules, each with its own MCP tools. This guide tells you how they fit together so you can plan queries efficiently.

## Modules Overview

| Module | What it holds | Key identifier |
|--------|--------------|----------------|
| **Users** | Team directory, functional areas, rate bands | `user_id` (UUID) |
| **Tracker** | Projects, budgets, invoices, time allocation, progress | `project_id` (UUID) |
| **Scorecard** | Project quality scores across 8 dimensions | `project_id` (UUID) |
| **Capacity** | Monthly allocation of users to projects | `user_id` + `period` (YYYY-MM) |
| **ISO** | Compliance registries (JSONB rows) and policy documents | `slug` (string) |
| **Playbook** | Internal knowledge base articles | `slug` (string) |

## How Modules Connect

```
Users ──────────┐
  user_id       │
  functional_area (FE, BE, Design, PM, Sci, Coms)
  rate_band (A-D, determines hourly cost)
                │
Capacity ◄──────┘ user_id + period ──► project allocations (%)
                │
Tracker ◄───────┘ project_id ──► budget, invoices, time, progress
                │
Scorecard ◄─────┘ project_id ──► 8 dimension scores (0-100)

ISO ──── standalone (registries + documents, linked by slug)
Playbook ── standalone (articles, linked by slug)
```

**The key join:** `user_id` is the same UUID across Users, Capacity, and Tracker. A `project_id` is the same UUID across Tracker and Scorecard.

## Module Details

### Users (4 tools)

| Tool | Use for | Key params |
|------|---------|------------|
| `users_get_team` | List team members | `active_only` (bool, default true), `functional_area` (full name) |
| `users_get_detail(user_id)` | Full profile for one person | `user_id` (UUID) |
| `users_get_functional_areas` | List all FAs with IDs | — |
| `users_get_rates` | List rate bands with hourly values | — |

**Returns:** `users_get_team` → name, email, functional_area, rate_code, dedication (FTE 0-1), roles, slack_display_name, requires_project_reporting. `users_get_detail` adds first_name, last_name, rate_value, last_login_at.

**Conventions:**
- Functional areas have full names in Users (`Frontend Developer`) but short codes in Capacity (`FE`)
- Mapping: FE = Frontend Developer, BE = Backend Developer, Design = Designer, PM = Project Manager, Sci = Scientist, Coms = Communications
- `users_get_team(functional_area="Frontend Developer")` filters by full name — not the short code
- `dedication` is a decimal FTE value (e.g., 1.00 = full-time, 0.50 = half-time)

### Tracker (6 tools)

| Tool | Use for | Key params |
|------|---------|------------|
| `tracker_get_projects` | List all projects with cost summary | `status` (proposal/live/finished), `is_billable` (bool) |
| `tracker_get_project_detail(project_id)` | Full project info + budget lines by FA | `project_id` (UUID) |
| `tracker_get_project_time(project_id)` | Time allocation by user or FA | `project_id`, `group_by` (user/functional_area) |
| `tracker_get_project_invoices(project_id)` | Invoice schedule and payment status | `project_id` (UUID) |
| `tracker_get_project_progress(project_id)` | Completion % over time | `project_id` (UUID) |
| `tracker_get_periods` | Reporting periods with status | `status` (unstarted/active/finished) |

**Returns:** `tracker_get_projects` → id, name, code, status, is_billable, currency, budget, start_date, end_date, project_manager, staff_cost, non_staff_cost, total_cost, burn_percentage, income. `tracker_get_project_detail` adds budget_lines (per FA), cost_summary with per-period breakdown, contract_rate, summary. `tracker_get_project_invoices` → id, code, amount, due_date, invoiced_on, milestone, observations, status (effective), stored_status, postpone_count, postponed_to.

**Conventions:**
- Absence projects are automatically excluded from `tracker_get_projects`
- Invoice `status` is the effective status (accounts for postponements): `scheduled`, `pending_to_issue`, `postponed`, `paid`
- `burn_percentage` is null when budget is zero
- `tracker_get_project_time(project_id, group_by="functional_area")` groups by role instead of person
- Cost values are in the project's currency (check the `currency` field)

### Scorecard (4 tools)

| Tool | Use for | Key params |
|------|---------|------------|
| `scorecard_get_project_scores` | All projects with latest scores | `status` (proposal/live/finished) |
| `scorecard_get_project_scorecard(project_id)` | Full scorecard for one project | `project_id`, `year`, `month` |
| `scorecard_get_project_history(project_id)` | Score trend over time | `project_id`, `limit` (default 12, max 48) |
| `scorecard_get_global_metrics` | Org-wide averages by month | `limit` (default 12, max 48) |

**The 8 dimensions** (all scored 0-100):
1. **time** — schedule performance (SPI)
2. **cost** — cost performance (CPI)
3. **quality** — defect rates, code quality
4. **value** — delivered value vs planned
5. **satisfaction** — client satisfaction
6. **flow** — delivery flow efficiency
7. **engineering** — DORA metrics (deploy frequency, lead time, MTTR, change failure)
8. **risk** — risk exposure

**Returns:** `scorecard_get_project_scores` → project name, overall score, 8 dimension scores. `scorecard_get_project_scorecard` → dimensions, normalized indicators (0-1 scale), DORA classifications, EVM data (budget, cost_to_date, percent_completed, percent_planned), milestones. `scorecard_get_project_history` → per-period scores and indicators (newest first). `scorecard_get_global_metrics` → monthly averages with contributing project count.

**Conventions:**
- `scorecard_get_project_scorecard` defaults to latest period; pass `year` + `month` for historical
- Projects without metrics have null scores
- Use `scorecard_get_global_metrics` as a benchmark to compare individual projects against the org average
- A score of null/None means no data available (not zero)

### Capacity (4 tools)

| Tool | Use for | Key params |
|------|---------|------------|
| `capacity_get_insights` | Overview by FA and period | `start_month`, `end_month` (YYYY-MM) |
| `capacity_get_fa_detail(fa)` | Per-user breakdown for one FA | `fa` (short code), `start_month`, `end_month` |
| `capacity_get_user_detail(user_id)` | Per-project breakdown for one user | `user_id` (UUID), `start_month`, `end_month` |
| `capacity_get_allocation` | Allocation segments (users or projects) | `view` (users/projects), `start_month`, `end_month` |

**Returns:** `capacity_get_insights` → per-period array, each with FA entries: short code, billable_pct, absence_pct, user_count. `capacity_get_fa_detail` → per-period array with per-user: user_id, name, billable_pct, absence_pct, billable_project_count. `capacity_get_user_detail` → per-period array with project allocations. `capacity_get_allocation` → averaged segments over finished periods.

**Conventions:**
- FA short codes: `FE`, `BE`, `Design`, `PM`, `Sci`, `Coms`
- Periods are `YYYY-MM` strings (e.g., `2026-03`)
- Default range: last 6 months. Override with `start_month` / `end_month`
- `billable_pct` and `absence_pct` are on a 0-100 scale (e.g., 75.5 means 75.5% of time)
- `capacity_get_allocation(view="projects")` shows which users work on each project
- Users with `requires_project_reporting=false` or inactive users are excluded

### ISO (5 tools)

| Tool | Use for | Key params |
|------|---------|------------|
| `iso_get_registries` | List all registry types with column schemas | — |
| `iso_get_registry_rows(slug)` | Rows for a specific registry | `slug`, `year` (for yearly registries) |
| `iso_get_documents` | List ISO documents with metadata | `category`, `search` (title substring) |
| `iso_get_document(slug)` | Full content of one document | `slug` |
| `iso_search_documents(query)` | Full-text search across document content | `query` |

**Returns:** `iso_get_registries` → slug, name, description, is_yearly, columns (schema). `iso_get_registry_rows` → registry metadata + rows with JSONB data and computed fields. `iso_get_documents` → slug, title, category, doc_version, summary. `iso_get_document` → full markdown content. `iso_search_documents` → snippet, section heading, ts_rank score.

**Conventions:**
- Registries use `slug` as identifier (e.g., `incident-register`, `risk-register`)
- `iso_search_documents` uses PostgreSQL full-text search (tsvector). `rank` is ts_rank — use only for ordering, not as a relevance percentage
- `iso_get_documents(search=...)` does title substring match only. For content search, use `iso_search_documents`
- Document categories: `policy`, `procedure`, `plan`, `record`, `manual`
- There are ~34 registry types and ~40 documents

**Yearly registries** (require `year` param, defaults to current year if omitted):
`audit-findings-register`, `audit-plan-results`, `authorization-matrix`, `awareness-plan`, `continual-improvement-register`, `corrective-action-register`, `incident-register`, `management-review-register`, `management-system-objectives`, `opportunity-register`, `purchases-register`, `risk-register`, `security-incident-register`, `supplier-evaluation-register`, `swot-analysis`, `test-calendar`, `training-register`

**Non-yearly registries** (no year param needed):
`access-control-register`, `asset-inventory`, `asset-inventory---intellectual-property`, `asset-inventory---licenses`, `asset-inventory---movements`, `authorities-contact-register`, `business-continuity-plan`, `change-management-register`, `communication-register`, `document-control-register`, `guest-access-register`, `interested-parties-register`, `legal-regulatory-register`, `statement-of-applicability`, `supplier-register`, `threat-monitoring-register`

### Playbook (3 tools)

| Tool | Use for | Key params |
|------|---------|------------|
| `playbook_get_tree` | Navigation tree of all articles | — |
| `playbook_get_article(slug)` | Full content of one article | `slug` |
| `playbook_search_articles(query)` | Search articles by title and content | `query` |

**Returns:** `playbook_get_tree` → hierarchical structure with id, title, slug, type (page/group), children. `playbook_get_article` → title, content (markdown), version, is_public, last_updated. `playbook_search_articles` → title, slug, is_public, summary (first 200 chars).

**Conventions:**
- `playbook_search_articles` uses substring matching (ILIKE), not full-text search — partial words work
- Articles are versioned; `playbook_get_article` always returns the latest version
- Tree structure has groups containing pages — use the tree to understand the knowledge base structure

## Cross-Module Query Patterns

### "Which projects have the highest cost and worst delivery?"

1. `tracker_get_projects(status="live")` → get project list with costs
2. `scorecard_get_project_scores(status="live")` → get scores
3. Cross-reference by `project_id`: sort by cost descending, filter by low time or cost dimension scores

### "How is the frontend team allocated this quarter?"

1. `capacity_get_fa_detail(fa="FE", start_month="2026-01", end_month="2026-03")` → per-user breakdown
2. For deep dive on a specific user: `capacity_get_user_detail(user_id, start_month, end_month)` → per-project detail
3. Cross-reference with `users_get_detail(user_id)` for rate and dedication info

### "What's the budget situation for project X?"

1. `tracker_get_project_detail(project_id)` → budget lines by FA, monthly costs, burn %
2. `tracker_get_project_invoices(project_id)` → payment schedule and status
3. `scorecard_get_project_scorecard(project_id)` → EVM data (CPI, SPI) for earned value context

### "Who worked on projects with security incidents?"

1. `iso_get_registry_rows(slug="security-incident-register", year=2026)` → incidents
2. Match affected project names to `tracker_get_projects` → get project_ids
3. `tracker_get_project_time(project_id, group_by="user")` → who worked on each project

### "What does our policy say about X?"

1. `iso_search_documents(query="X")` → find relevant docs with ranked snippets
2. `iso_get_document(slug)` → read full content of the most relevant match

### "Show me the org health dashboard"

1. `scorecard_get_global_metrics(limit=6)` → org-wide score trends
2. `capacity_get_insights(start_month, end_month)` → utilization by FA
3. `tracker_get_projects(status="live")` → active project count and burn rates

### "Who's available for a new project?"

1. `users_get_team(active_only=true)` → full team with dedication levels
2. `capacity_get_insights()` → current billable % by FA (low billable = more availability)
3. `capacity_get_fa_detail(fa="FE")` → drill into specific FA to find individuals with low allocation

### "Compare project X to the org average"

1. `scorecard_get_project_scorecard(project_id)` → individual project scores
2. `scorecard_get_global_metrics(limit=1)` → latest org-wide average
3. Compare each dimension: project score vs org average

## App URLs

When presenting results, include direct links to the app so the user can navigate there. The base URL is `https://hub.vizzuality.com`.

| Context | URL pattern | Built from |
|---------|------------|------------|
| Project list | `/projects` | — |
| Project edit | `/projects/{project_id}/edit` | `project_id` from Tracker |
| Scorecard list | `/scorecard` | — |
| Project scorecard | `/scorecard/{project_id}` | `project_id` from Scorecard |
| Tracker project | `/tracker/projects/{project_id}` | `project_id` from Tracker |
| Invoice detail | `/tracker/invoices/{invoice_id}` | `id` from `tracker_get_project_invoices` |
| Capacity insights | `/capacity/insights` | — |
| Capacity insights by FA | `/capacity/insights?fa={FA_CODE}` | FA short code (`FE`, `BE`, etc.) |
| Capacity allocation | `/capacity/allocation` | — |
| Capacity planner | `/capacity/planner` | — |
| ISO documents | `/iso/docs` | — |
| ISO document detail | `/iso/docs?page={slug}` | `slug` from `iso_get_documents` |
| ISO registries | (within ISO docs) | — |
| Playbook | `/playbook` | — |
| Playbook article | `/playbook?page={slug}` | `slug` from `playbook_get_article` |
| Admin users | `/admin/users` | — |
| Admin user detail | `/admin/users/{user_id}` | `user_id` from Users |
| Global scores | `/admin/global-scores` | — |
| Reporting periods | `/admin/tracker/periods` | — |
| Admin invoices | `/admin/tracker/invoices` | — |

**Conventions:**
- Always use the full URL (e.g., `https://hub.vizzuality.com/scorecard/{project_id}`)
- `project_id` and `user_id` are UUIDs returned by MCP tools — plug them directly into the URL
- ISO docs and Playbook use `?page={slug}` query param, not path segments
- Include links inline in tables or after key findings (e.g., "ICIMOD has low delivery scores — [view scorecard](https://hub.vizzuality.com/scorecard/abc-123)")

## Tips

- **Start broad, then drill down.** Use list tools first (`tracker_get_projects`, `scorecard_get_project_scores`, `capacity_get_insights`, `users_get_team`) to find what you need, then detail tools for specific items.
- **Don't call `users_get_functional_areas` just to map FA names.** The mapping is fixed: FE = Frontend Developer, BE = Backend Developer, Design = Designer, PM = Project Manager, Sci = Scientist, Coms = Communications.
- **Capacity and Tracker complement each other.** Capacity shows allocation (planned %), Tracker shows actual time and cost. Compare them to find over/under-utilization.
- **Scorecard + Tracker = project health.** Scorecard gives quality metrics, Tracker gives financial metrics. Together they answer "is this project healthy?"
- **ISO registries are schema-driven.** Each registry type defines its own columns. The column schema is included in the `iso_get_registry_rows` response — read it before interpreting row data.
- **Null scores mean no data, not zero.** A project with null in a scorecard dimension has no metrics for that dimension — don't treat it as 0.
- **Cost values are currency-specific.** Always check the `currency` field from tracker data before comparing costs across projects.
- **Combine Users + Capacity for team planning.** Users gives you the team structure (who, what FA, what rate), Capacity gives you what they're actually working on.
