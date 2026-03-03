# Modular Monolith Refactor Design

**Date:** 2026-03-03
**Approach:** Big Bang — single branch, atomic migration
**Scope:** Backend + Frontend

## Motivation

- Tracker module coming soon; needs clean module boundaries
- 76% of backend code in legacy flat structure; growing technical debt
- ISO module proves the architecture works — time to apply it to scorecard

## Approach

Move all files in a single branch. No logic changes — purely structural (mv + import updates). ~1,300 tests as safety net.

## Target Structure

### Backend: Core Layer

```
app/core/
├── auth.py                            # existing, no changes
├── exceptions.py                      # existing, no changes
├── error_handler.py                   # existing, no changes
├── security_logger.py                 # existing, no changes
├── security_middleware.py             # existing, no changes
├── oauth_state.py                     # existing, no changes
├── token_encryption.py                # existing, no changes
├── models/
│   ├── __init__.py                    # re-exports all core models
│   ├── project.py                     # FROM app/models/project.py
│   ├── user.py                        # FROM app/models/user.py
│   ├── integration_setting.py         # FROM app/models/integration_setting.py
│   ├── oauth.py                       # FROM app/models/oauth.py
│   └── job.py                         # FROM app/models/job.py
├── api/
│   ├── __init__.py
│   ├── deps.py                        # FROM app/api/deps.py (CurrentUser, AdminUser, etc.)
│   ├── auth.py                        # FROM app/api/auth.py
│   ├── oauth.py                       # FROM app/api/oauth.py
│   ├── projects.py                    # FROM app/api/projects.py
│   ├── admin_users.py                 # FROM app/api/admin_users.py
│   └── jobs.py                        # FROM app/api/jobs.py
└── services/
    ├── export_helpers.py              # existing, no changes
    ├── oauth_service.py               # FROM app/services/
    ├── job_service.py                 # FROM app/services/
    └── integration_token_service.py   # FROM app/services/
```

### Backend: Scorecard Module

```
app/modules/scorecard/
├── __init__.py
├── router.py                          # aggregates all scorecard sub-routers
├── public.py                          # cross-module interface (minimal)
├── models/
│   ├── __init__.py
│   ├── metrics/                       # FROM app/models/metrics/ (db, schemas, enums, embedded, api_models)
│   ├── config.py                      # FROM app/models/config.py
│   ├── scores.py                      # FROM app/models/scores.py
│   ├── indicators.py                  # FROM app/models/indicators.py
│   ├── slack.py                       # FROM app/models/slack.py
│   └── global_metrics.py             # FROM app/models/global_metrics.py
├── api/
│   ├── __init__.py
│   ├── metrics.py                     # FROM app/api/metrics.py
│   ├── scores.py                      # FROM app/api/scores.py
│   ├── capture.py                     # FROM app/api/capture.py
│   ├── collectors.py                  # FROM app/api/collectors.py
│   ├── config.py                      # FROM app/api/config.py
│   ├── notifications.py              # FROM app/api/notifications.py
│   ├── silences.py                    # FROM app/api/silences.py
│   ├── slack_admin.py                 # FROM app/api/slack_admin.py
│   ├── global_metrics.py             # FROM app/api/global_metrics.py
│   ├── scheduled_jobs.py             # FROM app/api/scheduled_jobs.py
│   ├── integrations_admin.py         # FROM app/api/integrations_admin.py
│   ├── exports.py                     # existing in modules/scorecard/api/
│   └── schemas/                       # FROM app/api/schemas/
├── services/
│   ├── __init__.py
│   ├── metrics_service.py
│   ├── global_metrics_service.py
│   ├── config_service.py
│   ├── score_computation.py
│   ├── score_cache.py
│   ├── alert_service.py
│   ├── slack_service.py
│   ├── export_service.py             # existing
│   ├── export_definitions.py         # existing
│   ├── calculators/                   # FROM app/services/calculators/ (12 files)
│   ├── collectors/
│   │   ├── github/                    # FROM app/services/collectors/github/ (9 files)
│   │   └── jira/                      # FROM app/services/collectors/jira/ (9 files)
│   └── normalizers/                   # FROM app/services/normalizers/ (3 files)
```

### Backend: ISO Module

No changes — already follows the target architecture.

### Backend: Workers

```
app/worker/
├── settings.py                        # no changes
├── tasks.py                           # fix imports: use modules/ paths, not app/api/
├── collect_iso_snapshot.py            # no changes
```

### Backend: main.py

From 13+ direct imports to 7:

```python
from app.core.api.auth import router as auth_router
from app.core.api.oauth import router as oauth_router
from app.core.api.projects import router as projects_router
from app.core.api.admin_users import router as admin_users_router
from app.core.api.jobs import router as jobs_router
from app.modules.scorecard.router import router as scorecard_router
from app.modules.iso.router import router as iso_router
```

### Frontend: Module Structure

```
frontend/src/
├── App.tsx                            # update imports
├── modules/
│   ├── scorecard/
│   │   ├── components/                # FROM components/ProjectDetail/, ScoreCard/, SubIndicatorCard/, etc.
│   │   ├── hooks/                     # FROM hooks/useMetrics, useScores, useConfig, etc. (12 hooks)
│   │   ├── pages/                     # FROM pages/Projects, ProjectDetail, GlobalDashboard/
│   │   ├── services/                  # FROM services/api/scores.ts, metrics.ts, exports.ts, global.ts
│   │   └── types/                     # FROM types/scores.ts, metrics.ts, config.ts, global.ts
│   └── iso/
│       ├── components/                # FROM pages/iso/components/ + review-status-badge, stat-cards
│       ├── hooks/                     # FROM hooks/useIso.ts, useIsoExport.ts, isoStaleCheck.ts
│       ├── pages/                     # FROM pages/ISO.tsx, ISOSnapshots.tsx, ISOConfig.tsx, ISOSnapshotDetail.tsx
│       ├── services/                  # FROM services/api/iso.ts
│       └── types/                     # FROM types/iso.ts
├── core/
│   ├── components/                    # FROM components/layout/, admin components
│   ├── hooks/                         # useAuth, useDownload, cacheUtils, queryKeys
│   ├── pages/                         # Admin.tsx, LoginPage
│   ├── services/                      # client.ts, projects.ts, jobs.ts, integrations.ts, notifications.ts
│   └── types/                         # auth.ts, jobs.ts, alerts.ts, project.ts
├── shared/
│   ├── hooks/
│   │   └── useUrlState.ts             # existing, no change
│   └── components/
│       └── ui/                        # FROM components/ui/ (shadcn primitives)
└── utils/                             # no changes (dateUtils, formatters, etc.)
```

### Tests

Tests stay in their current locations. Only imports are updated to point to new module paths.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| No permissions.py | Keep CurrentUser/AdminUser as-is; new permission model is feature work |
| Project model → core | Tracker will need projects; creation will likely originate from tracker |
| Projects API → core | Pure CRUD on core entity; scorecard owns the dashboard UI, not the API |
| deps.py → core/api | CurrentUser/AdminUser needed by any module |
| No test moves | Reduces risk; import updates only |
| Frontend pages in scorecard | List shows scores, detail is the scorecard dashboard |
| Frontend services/types split | projects.ts → core (shared), scores/metrics/config → scorecard |
| Admin → core | Admin is cross-cutting infra, not a module |
| Notifications → core | Conceptually infra even though currently scorecard-coupled |

## Out of Scope

- No logic changes — purely structural
- No new permissions model
- No test file reorganization
- No data model changes
- No API contract changes (all URLs stay the same)

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Large PR (~200+ files) | Changes are mechanical (mv + imports); tests validate |
| Import chain breakage | Run full test suite after each batch of moves |
| Circular imports | Follow strict dependency direction: core ← modules |
| Worker coupling (tasks.py → capture.py) | Update to import from modules/scorecard/ |
