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
│   ├── api/               # auth, projects, admin_users, jobs, oauth, currencies, deps.py
│   ├── models/            # Project, User, Job, OAuthToken, IntegrationSetting, ExchangeRate
│   └── services/          # oauth_service, job_service, integration_token_service, exchange_rate_service
├── modules/
│   ├── scorecard/         # Scoring, metrics, collectors, calculators
│   │   ├── api/           # 13 sub-routers (scores, metrics, capture, config, etc.)
│   │   ├── models/        # Metrics, Scores, Config, GlobalMetrics, Indicators
│   │   ├── services/      # calculators/, collectors/, normalizers/, export, cache
│   │   ├── router.py      # Aggregates all scorecard sub-routers
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
│   ├── pages/             # Admin, LoginPage
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

The Hub is a multi-module platform (scorecard, iso, tracker). See `docs/tracker_integration.md`.

1. **ALL code lives in `core/`, `modules/`, or `shared/`** — no files in legacy flat directories (`app/api/`, `app/models/`, `app/services/`, `src/components/`, `src/hooks/`, etc.).
2. **Core entities** (`Project`, `User`, `Job`) in `app/core/models/`. Frontend core types in `src/core/types/`.
3. **Cross-module imports through `public.py` ONLY** — never import another module's internals.
4. **Write isolation, read flexibility**: Each module writes only to its own tables. Cross-module reads via `public.py`. Analytical JOINs allowed in `app/core/services/`.
5. **Entity placement**: ALL modules need it → `core/`. One creates, others read → owner + `public.py`. Single module → private.
6. **Frontend modules self-contained**: own `components/`, `hooks/`, `pages/`, `services/`, `types/`. Shared UI → `src/shared/`. Cross-module shared → `src/core/`.
7. **Router aggregation**: Module `router.py` aggregates sub-routers. `main.py` only mounts core routers + module routers. Prefixes in `include_router`, never in router files.
8. **Permissions**: `CurrentUser`/`AdminUser` from `app/core/api/deps.py`. No project-scoped permissions yet.
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
- **Status display pattern**: Always use colored dot + plain text (`<span className="inline-block w-2 h-2 rounded-full shrink-0 bg-{color}" />` + text in `text-foreground`). Never use colored badges or background-tinted pills for status indicators.

## Reference Docs

- `docs/CLAUDE_REFERENCE.md` — Auth, Slack, jobs, Redis cache, AWS, API endpoints
- `docs/tracker_integration.md` — Multi-module architecture spec
- `docs/OAUTH_SETUP.md` — Jira OAuth setup
- `docs/API.md` — Full API documentation
