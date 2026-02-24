# CLAUDE.md

## Project Overview

Project Scorecard evaluates software development projects across 8 dimensions (P_time, P_cost, P_quality, P_value, P_satisfaction, P_flow, P_engineering, P_risk). FastAPI + React.

## Commands

```bash
# Backend
cd backend
python run_server.py                          # Start server
pytest                                        # All tests (~970)
pytest tests/test_integration.py              # Integration tests (60)
pytest --cov=app --cov-report=html            # Coverage
ruff check app/ && black app/                 # Lint

# Frontend
cd frontend
npm run dev                                   # Dev server (:5173)
npm test                                      # All tests (~340)
npm run build && npm run lint

# Worker (requires Redis)
cd backend && arq app.worker.settings.WorkerSettings

# Docker (alternative)
docker-compose up -d
```

## Git Workflow

| Branch | Purpose |
|--------|---------|
| `main` | Production, auto-deploys to AWS |
| `dev` | Active development (default) |
| `feature/*` | PRs target `dev` |

CI: push to `main`/`dev` runs tests. Push to `main` also deploys.

## Architecture

### Modular Architecture Rules (MUST FOLLOW)

The Hub is a multi-module platform (scorecard, iso, tracker). See `docs/vizztracker_integration.md`.

1. **New code in modules**: `app/modules/{scorecard,iso,tracker}/`. Existing scorecard code stays until migrated.
2. **Core entities** (`Project`, `User`) in `app/core/models/`.
3. **Cross-module imports through `public.py` ONLY** — never import another module's internals.
4. **Write isolation, read flexibility**: Each module writes only to its own tables. Cross-module reads via `public.py`. Analytical JOINs allowed in `app/core/services/`.
5. **Entity placement**: ALL modules → `core/`. One creates, others read → owner + `public.py`. Single module → private.
6. **Frontend modules self-contained**: own `components/`, `hooks/`, `pages/`. Shared → `src/shared/`.
7. **Router aggregation**: Module `router.py` aggregates sub-routers. `main.py` only mounts module routers. Prefixes in `include_router`, never in router files.
8. **Project-scoped permissions**: New endpoints use `ProjectViewer`/`ProjectContributor`/`ProjectManager` from `app/core/permissions.py`. Existing scorecard can keep `CurrentUser`.
9. **URL = source of truth**: All view state in URL params. Use `useUrlState` hook, not bare `useState`. Tabs use nested routes.

### Backend Data Flow

```
Raw Metrics → Normalizers → Indicators (0-1) → Calculators → Scores (0-100)
```

- **Collectors** (`services/collectors/`): Fetch from Jira/GitHub. Return typed Pydantic models.
- **Normalizers** (`services/normalizers/`): Higher-is-better: `min(1, value)`. Lower-is-better: `min(1, target / max(value, 0.001))`. Missing: 0.5. Zero target+nonzero value: 0.
- **Calculators** (`services/calculators/`): Weights from DB config → 0-100 scores.
- **FinalScoreCalculator**: Aggregates 8 dimensions with global weights.

### Configuration

Weights, targets, ideals in `config_parameters` DB table. Seed: `backend/seeds/config_parameters.csv`. Weights must sum to 1.0.

Access: `get_target(name)`, `get_ideal(name)`, `get_weight(group, name)`, `get_constant(name)`.

### Targets vs Ideals

| Concept | Purpose | Example |
|---------|---------|---------|
| **Target** | Minimum acceptable (color coding) | SPI target = 0.8 |
| **Ideal** | Perfect score benchmark (100 pts) | SPI ideal = 1.0 |

SPI 0.85 → green (above target) but 85 points (not 100). Only SPI/CPI have explicit ideals.

### Project Status & Lifecycle

Status: `in_progress` (default) or `finished`.

- `end_date` = contractual deadline. `finished_at` = actual completion date.
- Timeline uses `finished_at` to stop. On reopen, `finished_at` cleared.
- When finished: collectors blocked, regular updates blocked, end-of-project metrics available.
- End-of-project: `strategic_impact` (LOW=25, MEDIUM=55, HIGH=80, TRANSFORMATIONAL=100), `client_survey` (8 questions, 1-5 weighted).

### Metrics & Snapshot Types

| Type | Description | Date Range |
|------|-------------|------------|
| **cumulative** | Project-to-date | `start_date` → `period_end` |
| **punctual** | Single month | First → last day of month |

- Default is CUMULATIVE. Unique constraint: `(project_id, period_year, period_month, snapshot_type)`.
- Capture endpoint creates BOTH types. Manual fields synced between types (collector fields are NOT).
- Manual fields defined in `MetricsDB.MANUAL_FIELDS`.

### Key Design Rules

- **Scores computed on-the-fly**, cached in Redis (optional). See `docs/CLAUDE_REFERENCE.md#redis-score-cache`.
- **Sev1 caps** P_quality at 60. Milestones have grace period (3 days).
- **Disabled governance tools** → score 0, not neutral.
- **No trailing slashes**: `redirect_slashes=False`. Routes use `""` not `"/"`.
- **PUT vs PATCH**: Use correctly. They are not interchangeable.
- **Metrics consolidation**: `_consolidate_metrics` in `app/api/scores.py` handles multiple records per period.
- **Never hardcode config**: `config.py` has empty defaults. Values in `.env`.

### Database Transactions

**CRITICAL**: `DBSession` dependency manages transactions. Do NOT use `async with db.begin()` inside endpoints — causes nested transaction error. Only use manual `db.begin()` outside request context (background tasks, scripts).

## Frontend Patterns

### React Query Keys

**Always** use `queryKeys` from `hooks/queryKeys.ts`. Never string literals.

```typescript
import { queryKeys } from './queryKeys';
queryKey: queryKeys.projects.all
queryKey: queryKeys.scores.byProject(projectId)
```

Keys: `projects.{all,list(params),summary,detail(id)}`, `metrics.byProject(id)`, `scores.{all,byProject(id),history(id,limit),batch(ids)}`, `config.{all,parameters,validation}`

### Hook Organization

- `useProjects.ts` - `usePaginatedProjects(params)`, `useProjectSummaries()` (lightweight), `useProject(id)`, CRUD
- `useProjectListParams.ts` - Filter/sort/page via `useUrlState`, resets page on changes
- `useMetrics.ts` - Field-specific mutation hooks (factory pattern)
- `useScores.ts` - Score queries
- `useProjectScoresMap.ts` - Batch scores for index (`POST /scores/batch`)
- `usePeriodCapture.ts` - **Primary** capture hook (UI "Collect Metrics" button)
- `useJobs.ts` - Background job management with polling
- `useSnapshots.ts` - Metrics history
- `cacheUtils.ts` - Centralized query invalidation

## Reference Documentation

Detailed docs for specific subsystems (consult when needed):
- **`docs/CLAUDE_REFERENCE.md`** - Auth/security details, Slack system, background jobs, Redis cache, AWS deployment, full API endpoints
- **`docs/OAUTH_SETUP.md`** - Jira OAuth 2.0 setup
- **`docs/vizztracker_integration.md`** - Multi-module architecture spec
- **`docs/API.md`** - Full API documentation
