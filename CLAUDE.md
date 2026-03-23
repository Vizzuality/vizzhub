# CLAUDE.md

## Commands

Backend: `cd backend && pytest` / `python run_server.py`
Frontend: `cd frontend && npm test` / `npm run dev`
Worker: `cd backend && arq app.worker.settings.WorkerSettings`

## Project Structure

### Backend (`backend/app/`)

```
app/
├── core/                  # Shared across all modules
│   ├── api/               # auth, projects, admin_users, jobs, oauth, currencies, rates, deps.py
│   ├── models/            # Project, User, Job, OAuthToken, IntegrationSetting, ExchangeRate
│   └── services/          # oauth_service, job_service, integration_token_service, exchange_rate_service
├── modules/
│   ├── scorecard/         # Scoring, metrics, collectors, calculators
│   │   ├── api/           # 13 sub-routers (scores, metrics, capture, config, etc.)
│   │   ├── models/        # Metrics, Scores, Config, GlobalMetrics, Indicators
│   │   ├── services/      # calculators/, collectors/, normalizers/, export, cache
│   │   ├── router.py      # Aggregates all scorecard sub-routers
│   │   └── public.py      # Cross-module interface
│   ├── capacity/          # Capacity insights (cross-module analytical views)
│   │   ├── api/           # insights, fa_detail, user_detail, _validation
│   │   ├── router.py      # Aggregates capacity sub-routers
│   │   └── public.py      # Cross-module interface
│   └── iso/               # ISO compliance (snapshots, reviews, exports)
│       ├── api/           # snapshots, reviews, config, exports
│       ├── models/        # AccessSnapshot, AccessReview
│       ├── services/      # google_workspace, export
│       └── public.py
├── worker/                # ARQ background tasks
├── main.py                # Mounts core routers + module routers
├── config.py
└── database.py
```

### Frontend (`frontend/src/`)

```
src/
├── core/                  # Shared across all modules
│   ├── components/        # layout/, Admin/, NotificationsAdmin/, ErrorBoundary, ProtectedRoute
│   ├── contexts/          # AuthContext
│   ├── hooks/             # queryKeys, useProjects, useJobs, useAlertDefinitions, etc.
│   ├── pages/             # Admin, LoginPage, Landing, UserDetail
│   ├── services/          # client (axios), projects, jobs, notifications, integrations
│   └── types/             # project, jobs, alerts, auth, common
├── modules/
│   ├── scorecard/         # Score dashboard, metrics, global scores
│   │   ├── components/    # ProjectDetail/, ScoreCard/, Settings/, etc.
│   │   ├── hooks/         # useScores, useMetrics, useSnapshots, useConfig, etc.
│   │   ├── pages/         # Projects, ProjectDetail, GlobalDashboard
│   │   ├── services/      # scores, metrics, global, exports
│   │   └── types/         # scores, metrics, config, global
│   ├── tracker/           # Budget tracking, time reports
│   │   ├── components/    # BurnDashboard, TimeByAreaTable, DaysByPeopleChart, BudgetLinesEditor
│   │   ├── hooks/         # useReportingPeriods, useReports, useProjectCosts, useBudgetLines, useInvoices
│   │   ├── pages/         # ProjectTrackerDetail, ReportingPeriods, MyReport, PeriodDetail, AdminInvoices
│   │   ├── services/      # tracker (API client)
│   │   ├── types/         # tracker (all tracker types)
│   │   └── utils/         # constants (formatCurrency, shortMonth, etc.)
│   ├── capacity/          # Capacity insights: overview → FA detail → user detail
│   │   ├── components/    # InsightsChart, FADetailChart, UserDetailChart, ChartPagination, GroupSeparators, MonthRangePicker
│   │   ├── hooks/         # useCapacityInsights, useCapacityFADetail, useCapacityUserDetail, useReportableUsers
│   │   ├── pages/         # Insights
│   │   ├── services/      # capacity (API client)
│   │   ├── types/         # capacity (PeriodInsight, PeriodUserInsight, PeriodProjectInsight, ChartDataPoint)
│   │   └── utils/         # constants (FA_COLORS, FA_ORDER, ITEM_PALETTE)
│   └── iso/               # ISO compliance UI
│       ├── components/    # ISOConfig
│       ├── hooks/         # useIso
│       ├── pages/         # ISO, ISOSnapshots, ISOSnapshotDetail
│       ├── services/      # iso
│       └── types/         # iso
├── shared/                # Reusable across everything
│   ├── components/        # ui/ (shadcn), theme-provider
│   ├── constants/         # timing, dates, palette
│   └── hooks/             # useUrlState
├── types/index.ts         # Re-export barrel (convenience for cross-module type imports)
├── utils/                 # dateUtils, formatters
├── App.tsx
└── main.tsx
```

## Modular Architecture Rules (MUST FOLLOW)

The Hub is a multi-module platform (scorecard, iso, tracker, capacity). See `docs/tracker_integration.md`.

1. **ALL code lives in `core/`, `modules/`, or `shared/`** — no files in legacy flat directories (`app/api/`, `app/models/`, `app/services/`, `src/components/`, `src/hooks/`, etc.).
2. **Core entities** (`Project`, `User`, `Job`) in `app/core/models/`. Frontend core types in `src/core/types/`.
3. **Cross-module imports through `public.py` ONLY** — never import another module's internals.
4. **Write isolation, read flexibility**: Each module writes only to its own tables. Cross-module reads via `public.py`. Analytical JOINs allowed in `app/core/services/`.
5. **Entity placement**: ALL modules need it → `core/`. One creates, others read → owner + `public.py`. Single module → private.
6. **Frontend modules self-contained**: own `components/`, `hooks/`, `pages/`, `services/`, `types/`. Shared UI → `src/shared/`. Cross-module shared → `src/core/`.
7. **Router aggregation**: Module `router.py` aggregates sub-routers. `main.py` only mounts core routers + module routers. Prefixes in `include_router`, never in router files.
8. **Permissions**: RBAC via `core/permissions/`. 3 roles (`user`, `manager`, `admin`), multiple per user (union of perms). Use `require_permission(Action.X)` for endpoint gating. `AdminUser` = alias for `require_permission("*")`. `CurrentUser` = any authenticated user. Permissions resolved at login, cached in JWT. Frontend: `usePermission()`, `<Can do={Action.X}>`, `<PermissionRoute require={...}>`. No project-scoped permissions yet.
9. **URL = source of truth**: All view state in URL params. Use `useUrlState` hook, not bare `useState`. Tabs use nested routes.
10. **Frontend imports**: Use direct module paths (`@/core/services/jobs`, `@/modules/scorecard/types/scores`). The `@/types` barrel is acceptable for cross-module type imports. No barrel files for services.

## Constraints

- **Targets vs Ideals**: Target = minimum acceptable (color coding). Ideal = perfect score (100 pts). SPI 0.85 → green (above target) but 85 points (not 100). Only SPI/CPI have explicit ideals.
- **Snapshot types**: Capture creates BOTH cumulative and punctual. Manual fields synced between types; collector fields are NOT. EVM fields (cost_to_date, percent_completed, percent_planned) are derived from tracker data, not manual — see `TRACKER_EVM_FIELDS` in `MetricsDB`.
- **Disabled governance tools** → score 0, not neutral.
- **No trailing slashes**: Routes use `""` not `"/"`. `redirect_slashes=False` in main.py.
- **DBSession manages transactions**: Do NOT use `async with db.begin()` inside endpoints — nested transaction error. Only use manual `db.begin()` outside request context.
- **Weights must sum to 1.0** per group in `config_parameters`.
- **React Query keys**: Always use `queryKeys` from `core/hooks/queryKeys.ts`. Never string literals.
- **Invoice effective status**: Derived at query time, not stored. Uses SQL CASE with postponement subquery. `postponed` = has active postponement (postponed_to > today). `pending_to_issue` = scheduled past due OR postponement expired. Transitions blocked for postponed invoices. Postpone max date: `max(base_date, today) + 30 days`. Admin sort by due_date pushes paid invoices last.
- **Report estimated flag**: `estimated=true` excludes report from burn calculations. UI has Confirm/Reopen button to toggle. Confirmed reports show green badge, estimated show yellow.
- **Reporting period uniqueness**: Date normalized to first of month via Pydantic validator. Unique constraint on `date` column. 409 response on duplicate creation.
- **Scorecard cost dimension**: `budget_variance` returns `None` when `cost_to_date <= 0` — projects with budget but no actual cost data show "-" instead of 100.
- **Exchange rates**: ECB rates stored in `exchange_rates` table, fetched daily at 14:30 UTC. EUR-based (rate = units per 1 EUR). Conversion: `amount / rate`. EUR passthrough (rate = 1.0). Currencies endpoint: `GET /api/currencies`.
- **Landing page**: `/` renders `Landing.tsx` inside `AppLayout` (with sidebar). Logo links to `/`. Uses `--lnd-green` CSS var: `deepTeal` in light mode, `neonGrass` in dark. Top 5 scores widget uses `useActiveProjectSummaries` + `useProjectScoresMap`.
- **Status display pattern**: Always use colored dot + plain text (`<span className="inline-block w-2 h-2 rounded-full shrink-0 bg-{color}" />` + text in `text-foreground`). Never use colored badges or background-tinted pills for status indicators.
- **Admin impersonation**: Token swap via `admin_token` httpOnly cookie. `stop-impersonate` uses `CurrentUser` (not `AdminUser`) because the session is the impersonated user. Use `delete_auth_cookie(response, key)` from `core/auth.py` for cookie deletion — never hand-unpack `get_cookie_settings()`.
- **User display helpers**: Use `getFullName(first, last, fallback?)` and `getInitials(first, last)` from `src/utils/formatters.ts` — don't inline `[first, last].filter(Boolean).join(' ')`.
- **User active scope**: `GET /admin/users` filters inactive by default (`include_inactive=true` to see all). Inactive users cannot log in (403) or be impersonated (400). Deactivation requires confirmation dialog.
- **Slack integration on users**: `slack_user_id` and `slack_display_name` on `UserDB`. Auto-linked on signup via `users.lookupByEmail`. Bulk sync via `POST /admin/users/sync-slack-all`. Display name extraction: `SlackService.extract_display_name(slack_user)`. Bot token requires `users:read.email` scope.
- **Rates API**: `GET /api/rates` lists rate bands (A-D). Endpoint in `core/api/rates.py`.
- **Capacity insights**: Analytical cross-module JOINs in `core/services/capacity_insights.py`. Three drill-down levels: overview (`GET /api/capacity/insights`, FA-level averages) → FA detail (`GET /api/capacity/insights/detail?fa=FE`, per-user breakdown) → user detail (`GET /api/capacity/insights/user-detail?user_id=X`, per-project breakdown). Reportable users list: `GET /api/capacity/insights/user-detail/users`. 6 target FAs: FE, BE, Design, PM, Sci, Coms (`TARGET_FA_MAPPING`). Excludes users with `requires_project_reporting=false`, inactive users, and on-leave users (total report = 0). Name formatting: first/last > `name` field > email prefix fallback. Charts paginated to max 6 months with `<>` navigation. Shared `ITEM_PALETTE` (15 colors) and `ChartDataPoint` type across all chart components. User detail selector uses searchable Combobox (Command/Popover pattern).
- **Project manager**: `project_manager_id` FK to `users.id` (SET NULL on delete). `project_manager_name` resolved via SQL join in list/detail responses. Use `_user_full_name_expr()` helper in `projects_v2.py` for the SQL name expression.

## Reference Docs

- `docs/CLAUDE_REFERENCE.md` — Auth, Slack, jobs, Redis cache, AWS, API endpoints
- `docs/tracker_integration.md` — Multi-module architecture spec
- `docs/OAUTH_SETUP.md` — Jira OAuth setup
- `docs/API.md` — Full API documentation
