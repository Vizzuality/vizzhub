# Modular Monolith Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate the backend flat structure to modular monolith (`core/` + `modules/scorecard/`) and restructure frontend into `modules/`, `core/`, and `shared/`.

**Architecture:** Big Bang — single branch, all moves atomic. No logic changes, purely structural. ~1,300 tests as safety net. See design doc: `docs/plans/2026-03-03-modular-monolith-refactor-design.md`.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript/Vite (frontend)

**Key Reference:** The ISO module (`app/modules/iso/`) is the reference implementation of the target architecture.

---

### Task 1: Setup — Branch and Directory Structure

**Files:**
- Create: `app/core/models/__init__.py`
- Create: `app/core/api/__init__.py`
- Create: `app/modules/scorecard/models/__init__.py`
- Create: `app/modules/scorecard/api/__init__.py`
- Create: `app/modules/scorecard/api/schemas/__init__.py`
- Create: `frontend/src/modules/scorecard/{components,hooks,pages,services,types}/` (empty dirs with .gitkeep)
- Create: `frontend/src/modules/iso/{components,hooks,pages,services,types}/` (empty dirs with .gitkeep)
- Create: `frontend/src/core/{components,hooks,pages,services,types}/` (empty dirs with .gitkeep)
- Create: `frontend/src/shared/components/ui/` (already partially exists)

**Step 1: Create feature branch**

```bash
git checkout -b refactor/modular-monolith
```

**Step 2: Create backend directories**

```bash
mkdir -p backend/app/core/models
mkdir -p backend/app/core/api
mkdir -p backend/app/modules/scorecard/models
mkdir -p backend/app/modules/scorecard/api/schemas
touch backend/app/core/models/__init__.py
touch backend/app/core/api/__init__.py
touch backend/app/modules/scorecard/models/__init__.py
touch backend/app/modules/scorecard/api/__init__.py
touch backend/app/modules/scorecard/api/schemas/__init__.py
```

**Step 3: Create frontend directories**

```bash
mkdir -p frontend/src/modules/scorecard/{components,hooks,pages,services,types}
mkdir -p frontend/src/modules/iso/{components,hooks,pages,services,types}
mkdir -p frontend/src/core/{components,hooks,pages,services,types}
mkdir -p frontend/src/shared/components
```

**Step 4: Commit**

```bash
git add -A && git commit -m "chore: create modular monolith directory structure"
```

---

### Task 2: Backend Core — Move Models

Move 5 shared models from `app/models/` to `app/core/models/`.

**Files:**
- Move: `app/models/project.py` → `app/core/models/project.py`
- Move: `app/models/user.py` → `app/core/models/user.py`
- Move: `app/models/integration_setting.py` → `app/core/models/integration_setting.py`
- Move: `app/models/oauth.py` → `app/core/models/oauth.py`
- Move: `app/models/job.py` → `app/core/models/job.py`
- Modify: `app/core/models/__init__.py` (add re-exports)
- Modify: `app/models/__init__.py` (update barrel to re-export from new locations)

**Step 1: Move the 5 model files**

```bash
cd backend
git mv app/models/project.py app/core/models/project.py
git mv app/models/user.py app/core/models/user.py
git mv app/models/integration_setting.py app/core/models/integration_setting.py
git mv app/models/oauth.py app/core/models/oauth.py
git mv app/models/job.py app/core/models/job.py
```

**Step 2: Update internal imports in moved files**

The moved files import from `app.database.Base` — this path does NOT change (database.py stays at `app/database.py`). No internal import changes needed for these files.

**Step 3: Write `app/core/models/__init__.py` re-exports**

```python
from app.core.models.project import Project, ProjectBase, ProjectCreate, ProjectDB, ProjectUpdate
from app.core.models.user import User, UserDB, UserPublic, UserRole, UserUpdate
from app.core.models.integration_setting import IntegrationSettingDB
from app.core.models.oauth import OAuthToken, OAuthTokenDB, OAuthStateDB
from app.core.models.job import Job, JobStatus, JobType
```

**Step 4: Update `app/models/__init__.py`**

Update the barrel to re-export from `app.core.models` instead of old locations. This preserves backward compatibility for consumers we haven't updated yet.

```python
# Core models (re-exported from app.core.models)
from app.core.models.user import User, UserDB, UserPublic, UserRole, UserUpdate
from app.core.models.integration_setting import IntegrationSettingDB
from app.core.models.job import Job, JobStatus, JobType
from app.core.models.oauth import OAuthToken, OAuthTokenDB
from app.core.models.project import Project, ProjectCreate, ProjectDB, ProjectUpdate

# Scorecard-specific models (remain here until Task 5 moves them)
from app.models.global_metrics import (...)  # keep existing
from app.models.indicators import IndicatorsCreate
from app.models.metrics import (...)  # keep existing
from app.models.scores import DimensionScores, FinalScore
from app.models.config import ConfigParameter, ScoringConfigModel
```

**Step 5: Update ALL consumer imports — find-and-replace**

Use the following import path replacements across the entire `backend/` tree (both `app/` and `tests/`):

| Old import | New import |
|---|---|
| `from app.models.project import` | `from app.core.models.project import` |
| `from app.models.user import` | `from app.core.models.user import` |
| `from app.models.integration_setting import` | `from app.core.models.integration_setting import` |
| `from app.models.oauth import` | `from app.core.models.oauth import` |
| `from app.models.job import` | `from app.core.models.job import` |

**Key consumers to verify (most imports):**
- `app.models.project`: ~40 files (11 production + ~29 test files)
- `app.models.oauth`: ~15 files
- `app.models.user`: ~6 files
- `app.models.job`: ~9 files
- `app.models.integration_setting`: ~6 files

Also update `alembic/env.py:13-15`:
```python
from app.core.models.job import Job
from app.core.models.project import ProjectDB
```
(MetricsDB stays at `app.models.metrics` until Task 5)

**Step 6: Run backend tests**

```bash
cd backend && python -m pytest --tb=short -q
```

Expected: all ~970 tests pass.

**Step 7: Commit**

```bash
git add -A && git commit -m "refactor: move shared models to app/core/models/"
```

---

### Task 3: Backend Core — Move Services

Move 3 shared services from `app/services/` to `app/core/services/`.

**Files:**
- Move: `app/services/oauth_service.py` → `app/core/services/oauth_service.py`
- Move: `app/services/job_service.py` → `app/core/services/job_service.py`
- Move: `app/services/integration_token_service.py` → `app/core/services/integration_token_service.py`

**Step 1: Move the 3 service files**

```bash
cd backend
git mv app/services/oauth_service.py app/core/services/oauth_service.py
git mv app/services/job_service.py app/core/services/job_service.py
git mv app/services/integration_token_service.py app/core/services/integration_token_service.py
```

**Step 2: Update internal imports in moved files**

In `app/core/services/job_service.py`:
```python
# Change: from app.models.job import Job, JobStatus, JobType
# To:
from app.core.models.job import Job, JobStatus, JobType
```

In `app/core/services/integration_token_service.py`:
```python
# Change: from app.models.integration_setting import IntegrationSettingDB
# To:
from app.core.models.integration_setting import IntegrationSettingDB
# Change: from app.models.oauth import OAuthTokenDB
# To:
from app.core.models.oauth import OAuthTokenDB
```

In `app/core/services/oauth_service.py`:
```python
# Change: from app.models.oauth import OAuthTokenDB
# To:
from app.core.models.oauth import OAuthTokenDB
```

**Step 3: Update ALL consumer imports**

| Old import | New import |
|---|---|
| `from app.services.oauth_service import` | `from app.core.services.oauth_service import` |
| `from app.services.job_service import` | `from app.core.services.job_service import` |
| `from app.services.integration_token_service import` | `from app.core.services.integration_token_service import` |

**Key consumers:**
- `job_service`: `app/api/jobs.py`, `app/worker/tasks.py`, 2 test files
- `oauth_service`: `app/api/oauth.py`, `app/services/collectors/jira/client.py`, 2 test files
- `integration_token_service`: `app/api/integrations_admin.py`, `app/api/oauth.py`, `app/api/slack_admin.py`, `app/services/collectors/github/client.py` (lazy import), `app/utils/slack.py`, `app/worker/check_dependabot.py`, 1 test file

**Step 4: Run backend tests**

```bash
cd backend && python -m pytest --tb=short -q
```

**Step 5: Commit**

```bash
git add -A && git commit -m "refactor: move shared services to app/core/services/"
```

---

### Task 4: Backend Core — Move API Layer

Move `deps.py` and 5 shared routers from `app/api/` to `app/core/api/`.

**Files:**
- Move: `app/api/deps.py` → `app/core/api/deps.py`
- Move: `app/api/auth.py` → `app/core/api/auth.py`
- Move: `app/api/projects.py` → `app/core/api/projects.py`
- Move: `app/api/admin_users.py` → `app/core/api/admin_users.py`
- Move: `app/api/jobs.py` → `app/core/api/jobs.py`
- Move: `app/api/oauth.py` → `app/core/api/oauth.py`

**Step 1: Move the 6 API files**

```bash
cd backend
git mv app/api/deps.py app/core/api/deps.py
git mv app/api/auth.py app/core/api/auth.py
git mv app/api/projects.py app/core/api/projects.py
git mv app/api/admin_users.py app/core/api/admin_users.py
git mv app/api/jobs.py app/core/api/jobs.py
git mv app/api/oauth.py app/core/api/oauth.py
```

**Step 2: Update internal imports in moved files**

In `app/core/api/deps.py`:
```python
# Change: from app.models.project import ProjectDB
# To:
from app.core.models.project import ProjectDB
# Change: from app.services.score_cache import ScoreCacheService
# To: (score_cache hasn't moved yet — leave as is, will update in Task 6)
from app.services.score_cache import ScoreCacheService
```

In `app/core/api/auth.py`:
```python
# Change: from app.api.deps import CurrentUser, DBSession
# To:
from app.core.api.deps import CurrentUser, DBSession
# Change: from app.models.user import ...
# To:
from app.core.models.user import User, UserDB, UserPublic, UserRole
```

In `app/core/api/projects.py`:
```python
# Change: from app.api.deps import ...
# To:
from app.core.api.deps import CurrentUser, DBSession, get_project_or_404, limiter
# Change: from app.api.schemas.project import ...
# To: (schemas haven't moved yet — leave as is, will update in Task 7)
from app.api.schemas.project import PaginatedProjectsResponse, ProjectSummary
# Change: from app.models.project import ...
# To:
from app.core.models.project import Project, ProjectCreate, ProjectDB, ProjectUpdate
# Change: from app.models.metrics.db import MetricsDB
# To: (metrics model hasn't moved yet — leave as is, will update in Task 5)
from app.models.metrics.db import MetricsDB
```

In `app/core/api/admin_users.py`:
```python
from app.core.api.deps import AdminUser, DBSession
from app.core.models.user import User, UserDB, UserUpdate
```

In `app/core/api/jobs.py`:
```python
from app.core.api.deps import AdminUser, CurrentUser, DBSession, get_project_or_404
# schemas haven't moved yet:
from app.api.schemas.job import JobDetailResponse, JobResponse, JobSummaryResponse
from app.core.models.job import Job, JobStatus, JobType
from app.core.services.job_service import JobService
```

In `app/core/api/oauth.py`:
```python
from app.core.api.deps import AdminUser, CurrentUser, DBSession, limiter
from app.core.services.oauth_service import OAuthService
from app.core.services.integration_token_service import IntegrationTokenService
```

**Step 3: Update ALL consumer imports — `app.api.deps` (highest-impact)**

This is the biggest change — 23+ production files and ~1 test file import from `app.api.deps`.

| Old import | New import |
|---|---|
| `from app.api.deps import` | `from app.core.api.deps import` |

**All consumers (production):**
- `app/api/capture.py`
- `app/api/collectors.py`
- `app/api/config.py`
- `app/api/global_metrics.py`
- `app/api/integrations_admin.py`
- `app/api/metrics.py`
- `app/api/notifications.py`
- `app/api/scheduled_jobs.py`
- `app/api/scores.py`
- `app/api/silences.py`
- `app/api/slack_admin.py`
- `app/main.py:34` (`from app.api.deps import limiter` → `from app.core.api.deps import limiter`)
- `app/modules/iso/api/config.py`
- `app/modules/iso/api/exports.py`
- `app/modules/iso/api/reviews.py`
- `app/modules/iso/api/snapshots.py`
- `app/modules/scorecard/api/exports.py`
- `app/worker/tasks.py:65` (lazy import inside function body)

**Test consumer:**
- `tests/conftest.py:103` (`from app.api.deps import limiter as deps_limiter` → `from app.core.api.deps import limiter as deps_limiter`)

**Step 4: Update consumer imports for router files**

| Old import | New import |
|---|---|
| `from app.api.auth import` | `from app.core.api.auth import` |
| `from app.api import auth as` | `from app.core.api import auth as` |
| `from app.api import projects as` | `from app.core.api import projects as` |
| `from app.api import admin_users as` | `from app.core.api import admin_users as` |
| `from app.api import jobs as` | `from app.core.api import jobs as` |
| `from app.api import oauth as` | `from app.core.api import oauth as` |

Only `app/main.py` imports these routers. Update lines 13-14, 20, 22-23 of main.py.

Also update `tests/conftest.py:102`:
```python
# Change:
from app.api import projects, metrics, collectors, scores, config, oauth, capture
# To:
from app.core.api import projects, oauth
from app.api import metrics, collectors, scores, config, capture
```

**Step 5: Run backend tests**

```bash
cd backend && python -m pytest --tb=short -q
```

**Step 6: Commit**

```bash
git add -A && git commit -m "refactor: move shared API layer to app/core/api/"
```

---

### Task 5: Backend Scorecard — Move Models

Move remaining scorecard-specific models from `app/models/` to `app/modules/scorecard/models/`.

**Files:**
- Move: `app/models/metrics/` → `app/modules/scorecard/models/metrics/`
- Move: `app/models/config.py` → `app/modules/scorecard/models/config.py`
- Move: `app/models/scores.py` → `app/modules/scorecard/models/scores.py`
- Move: `app/models/indicators.py` → `app/modules/scorecard/models/indicators.py`
- Move: `app/models/slack.py` → `app/modules/scorecard/models/slack.py`
- Move: `app/models/global_metrics.py` → `app/modules/scorecard/models/global_metrics.py`
- Modify: `app/models/__init__.py` (update barrel or delete)

**Step 1: Move the files**

```bash
cd backend
git mv app/models/metrics app/modules/scorecard/models/metrics
git mv app/models/config.py app/modules/scorecard/models/config.py
git mv app/models/scores.py app/modules/scorecard/models/scores.py
git mv app/models/indicators.py app/modules/scorecard/models/indicators.py
git mv app/models/slack.py app/modules/scorecard/models/slack.py
git mv app/models/global_metrics.py app/modules/scorecard/models/global_metrics.py
```

**Step 2: Update internal imports in moved files**

In `app/modules/scorecard/models/metrics/db.py` (if it imports from app.models):
- Check and update any cross-references within the metrics subpackage
- Update `from app.models.metrics.enums` → `from app.modules.scorecard.models.metrics.enums`
- Same for embedded, schemas, api_models references within the package

In `app/modules/scorecard/models/global_metrics.py`:
- Has FK to `projects.id` — this is a DB constraint, not a Python import, so no change needed

**Step 3: Update `app/models/__init__.py`**

Replace with re-exports from new locations:

```python
# Core models
from app.core.models.user import User, UserDB, UserPublic, UserRole, UserUpdate
from app.core.models.integration_setting import IntegrationSettingDB
from app.core.models.job import Job, JobStatus, JobType
from app.core.models.oauth import OAuthToken, OAuthTokenDB
from app.core.models.project import Project, ProjectCreate, ProjectDB, ProjectUpdate

# Scorecard models
from app.modules.scorecard.models.global_metrics import (
    CalculateBatchRequest, CalculateBatchResponse, GlobalIndicators,
    GlobalMetricsDB, GlobalMetricsHistoryResponse, GlobalMetricsRecord,
    GlobalScores, IndicatorValue, ScoreValue,
)
from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.models.metrics import (
    ArchitectureChecklist, ClientSurvey, EVMData, FlowMetrics,
    GitHubMetrics, JiraDefectMetrics, Metrics, MetricsCreate, MetricsDB,
    MetricsWithScores, Milestone, PMSatisfaction, SnapshotType, TestMaturity,
)
from app.modules.scorecard.models.scores import DimensionScores, FinalScore
from app.modules.scorecard.models.config import ConfigParameter, ScoringConfigModel
```

Note: Although nobody uses the barrel today, keeping it updated prevents import errors if any consumer uses it.

**Step 4: Update ALL consumer imports**

| Old import | New import |
|---|---|
| `from app.models.metrics.db import` | `from app.modules.scorecard.models.metrics.db import` |
| `from app.models.metrics.schemas import` | `from app.modules.scorecard.models.metrics.schemas import` |
| `from app.models.metrics.enums import` | `from app.modules.scorecard.models.metrics.enums import` |
| `from app.models.metrics.embedded import` | `from app.modules.scorecard.models.metrics.embedded import` |
| `from app.models.metrics.api_models import` | `from app.modules.scorecard.models.metrics.api_models import` |
| `from app.models.metrics import` | `from app.modules.scorecard.models.metrics import` |
| `from app.models.config import` | `from app.modules.scorecard.models.config import` |
| `from app.models.scores import` | `from app.modules.scorecard.models.scores import` |
| `from app.models.indicators import` | `from app.modules.scorecard.models.indicators import` |
| `from app.models.slack import` | `from app.modules.scorecard.models.slack import` |
| `from app.models.global_metrics import` | `from app.modules.scorecard.models.global_metrics import` |

Also update `alembic/env.py:14`:
```python
from app.modules.scorecard.models.metrics import MetricsDB
```

And update `app/core/api/projects.py` which still references `app.models.metrics.db`:
```python
from app.modules.scorecard.models.metrics.db import MetricsDB
```

**Step 5: Run backend tests**

```bash
cd backend && python -m pytest --tb=short -q
```

**Step 6: Commit**

```bash
git add -A && git commit -m "refactor: move scorecard models to app/modules/scorecard/models/"
```

---

### Task 6: Backend Scorecard — Move Services

Move scorecard-specific services from `app/services/` to `app/modules/scorecard/services/`.

**Files:**
- Move: `app/services/metrics_service.py` → `app/modules/scorecard/services/metrics_service.py`
- Move: `app/services/global_metrics_service.py` → `app/modules/scorecard/services/global_metrics_service.py`
- Move: `app/services/config_service.py` → `app/modules/scorecard/services/config_service.py`
- Move: `app/services/score_computation.py` → `app/modules/scorecard/services/score_computation.py`
- Move: `app/services/score_cache.py` → `app/modules/scorecard/services/score_cache.py`
- Move: `app/services/alert_service.py` → `app/modules/scorecard/services/alert_service.py`
- Move: `app/services/slack_service.py` → `app/modules/scorecard/services/slack_service.py`
- Move: `app/services/calculators/` → `app/modules/scorecard/services/calculators/`
- Move: `app/services/collectors/` → `app/modules/scorecard/services/collectors/`
- Move: `app/services/normalizers/` → `app/modules/scorecard/services/normalizers/`

**Step 1: Move all service files**

```bash
cd backend
git mv app/services/metrics_service.py app/modules/scorecard/services/metrics_service.py
git mv app/services/global_metrics_service.py app/modules/scorecard/services/global_metrics_service.py
git mv app/services/config_service.py app/modules/scorecard/services/config_service.py
git mv app/services/score_computation.py app/modules/scorecard/services/score_computation.py
git mv app/services/score_cache.py app/modules/scorecard/services/score_cache.py
git mv app/services/alert_service.py app/modules/scorecard/services/alert_service.py
git mv app/services/slack_service.py app/modules/scorecard/services/slack_service.py
git mv app/services/calculators app/modules/scorecard/services/calculators
git mv app/services/collectors app/modules/scorecard/services/collectors
git mv app/services/normalizers app/modules/scorecard/services/normalizers
```

**Step 2: Update internal imports in moved files**

For ALL moved service files, update imports that reference other moved files:
- `app.models.metrics.*` → `app.modules.scorecard.models.metrics.*`
- `app.models.config` → `app.modules.scorecard.models.config`
- `app.models.scores` → `app.modules.scorecard.models.scores`
- `app.models.slack` → `app.modules.scorecard.models.slack`
- `app.models.global_metrics` → `app.modules.scorecard.models.global_metrics`
- `app.models.indicators` → `app.modules.scorecard.models.indicators`
- `app.models.project` → `app.core.models.project`
- `app.models.oauth` → `app.core.models.oauth`
- `app.services.calculators` → `app.modules.scorecard.services.calculators`
- `app.services.collectors` → `app.modules.scorecard.services.collectors`
- `app.services.normalizers` → `app.modules.scorecard.services.normalizers`
- `app.services.metrics_service` → `app.modules.scorecard.services.metrics_service`
- `app.services.score_computation` → `app.modules.scorecard.services.score_computation`
- `app.services.score_cache` → `app.modules.scorecard.services.score_cache`
- `app.services.config_service` → `app.modules.scorecard.services.config_service`
- `app.services.alert_service` → `app.modules.scorecard.services.alert_service`
- `app.services.slack_service` → `app.modules.scorecard.services.slack_service`
- `app.services.oauth_service` → `app.core.services.oauth_service`
- `app.services.job_service` → `app.core.services.job_service`
- `app.services.integration_token_service` → `app.core.services.integration_token_service`

Also update `app/core/api/deps.py` which imports `score_cache`:
```python
# Change: from app.services.score_cache import ScoreCacheService
# To:
from app.modules.scorecard.services.score_cache import ScoreCacheService
```

And `app/main.py:77` (lazy import in lifespan):
```python
# Change: from app.services.score_cache import create_score_cache
# To:
from app.modules.scorecard.services.score_cache import create_score_cache
```

**Step 3: Update ALL consumer imports across `backend/`**

Search and replace all `from app.services.{service}` imports for moved services across the entire backend, including tests.

**Step 4: Run backend tests**

```bash
cd backend && python -m pytest --tb=short -q
```

**Step 5: Commit**

```bash
git add -A && git commit -m "refactor: move scorecard services to app/modules/scorecard/services/"
```

---

### Task 7: Backend Scorecard — Move API Layer + Schemas

Move remaining scorecard API files and update router aggregation.

**Files:**
- Move: `app/api/metrics.py` → `app/modules/scorecard/api/metrics.py`
- Move: `app/api/scores.py` → `app/modules/scorecard/api/scores.py`
- Move: `app/api/capture.py` → `app/modules/scorecard/api/capture.py`
- Move: `app/api/collectors.py` → `app/modules/scorecard/api/collectors.py`
- Move: `app/api/config.py` → `app/modules/scorecard/api/config.py`
- Move: `app/api/notifications.py` → `app/modules/scorecard/api/notifications.py`
- Move: `app/api/silences.py` → `app/modules/scorecard/api/silences.py`
- Move: `app/api/slack_admin.py` → `app/modules/scorecard/api/slack_admin.py`
- Move: `app/api/global_metrics.py` → `app/modules/scorecard/api/global_metrics.py`
- Move: `app/api/scheduled_jobs.py` → `app/modules/scorecard/api/scheduled_jobs.py`
- Move: `app/api/integrations_admin.py` → `app/modules/scorecard/api/integrations_admin.py`
- Move: `app/api/schemas/` → `app/modules/scorecard/api/schemas/`
- Modify: `app/modules/scorecard/router.py` (aggregate all sub-routers)

**Step 1: Move all API files**

```bash
cd backend
git mv app/api/metrics.py app/modules/scorecard/api/metrics.py
git mv app/api/scores.py app/modules/scorecard/api/scores.py
git mv app/api/capture.py app/modules/scorecard/api/capture.py
git mv app/api/collectors.py app/modules/scorecard/api/collectors.py
git mv app/api/config.py app/modules/scorecard/api/config.py
git mv app/api/notifications.py app/modules/scorecard/api/notifications.py
git mv app/api/silences.py app/modules/scorecard/api/silences.py
git mv app/api/slack_admin.py app/modules/scorecard/api/slack_admin.py
git mv app/api/global_metrics.py app/modules/scorecard/api/global_metrics.py
git mv app/api/scheduled_jobs.py app/modules/scorecard/api/scheduled_jobs.py
git mv app/api/integrations_admin.py app/modules/scorecard/api/integrations_admin.py
```

For schemas, since `app/modules/scorecard/api/schemas/` was created in Task 1:
```bash
git mv app/api/schemas/*.py app/modules/scorecard/api/schemas/
```
(preserve the __init__.py if it exists)

**Step 2: Update internal imports in all moved API files**

For each moved file, update:
- `from app.api.deps import` → `from app.core.api.deps import`
- `from app.api.schemas.*` → `from app.modules.scorecard.api.schemas.*`
- `from app.models.*` → appropriate new location (`app.core.models.*` or `app.modules.scorecard.models.*`)
- `from app.services.*` → appropriate new location

**Step 3: Rewrite `app/modules/scorecard/router.py`**

```python
from fastapi import APIRouter

from app.modules.scorecard.api import capture as capture_router
from app.modules.scorecard.api import collectors as collectors_router
from app.modules.scorecard.api import config as config_router
from app.modules.scorecard.api import exports as exports_router
from app.modules.scorecard.api import global_metrics as global_metrics_router
from app.modules.scorecard.api import integrations_admin as integrations_admin_router
from app.modules.scorecard.api import metrics as metrics_router
from app.modules.scorecard.api import notifications as notifications_router
from app.modules.scorecard.api import scheduled_jobs as scheduled_jobs_router
from app.modules.scorecard.api import scores as scores_router
from app.modules.scorecard.api import silences as silences_router
from app.modules.scorecard.api import slack_admin as slack_admin_router

router = APIRouter()
router.include_router(metrics_router.router, prefix="/metrics", tags=["metrics"])
router.include_router(scores_router.router, prefix="/scores", tags=["scores"])
router.include_router(config_router.router, prefix="/config", tags=["config"])
router.include_router(collectors_router.router, prefix="/collect", tags=["collectors"])
router.include_router(capture_router.router, prefix="/scorecards", tags=["capture"])
router.include_router(global_metrics_router.router, tags=["global"])
router.include_router(slack_admin_router.alerts_router)
router.include_router(slack_admin_router.templates_router)
router.include_router(integrations_admin_router.router)
router.include_router(silences_router.router)
router.include_router(notifications_router.router)
router.include_router(scheduled_jobs_router.router)
router.include_router(exports_router.router, prefix="/exports", tags=["exports"])
```

**IMPORTANT:** The prefixes in router.py must match the current mount points in main.py so that API URLs don't change. Cross-reference with the main.py mount table in the design doc.

**Step 4: Create `app/modules/scorecard/public.py`**

```python
"""Public interface for the scorecard module.

Other modules should only import from this file, never from scorecard internals.
"""
```

(Empty for now — will be populated when tracker needs scorecard data)

**Step 5: Update ALL consumer imports**

Update remaining consumers (tests, workers) that reference moved files:
- `from app.api.capture import` → `from app.modules.scorecard.api.capture import`
- `from app.api.metrics import` → `from app.modules.scorecard.api.metrics import`
- etc.

Also update `tests/conftest.py:102`:
```python
from app.core.api import projects, oauth
from app.modules.scorecard.api import metrics, collectors, scores, config, capture
```

**Step 6: Run backend tests**

```bash
cd backend && python -m pytest --tb=short -q
```

**Step 7: Commit**

```bash
git add -A && git commit -m "refactor: move scorecard API to app/modules/scorecard/api/"
```

---

### Task 8: Backend Integration — main.py, Workers, Cleanup

Update main.py, worker imports, and clean up empty legacy directories.

**Files:**
- Modify: `app/main.py`
- Modify: `app/worker/tasks.py`
- Delete: empty `app/api/` directory (if no files remain)
- Delete: empty `app/services/` directory (if no files remain)

**Step 1: Rewrite `app/main.py` router imports**

Replace all router imports (lines 13-34) with:

```python
from app.core.api import admin_users as admin_users_router
from app.core.api import auth as auth_router
from app.core.api import jobs as jobs_router
from app.core.api import oauth as oauth_router
from app.core.api import projects as projects_router
from app.core.api.deps import limiter
from app.modules.scorecard.router import router as scorecard_router
from app.modules.iso.router import router as iso_router
```

Replace the `include_router` block (lines 178-196) with:

```python
# Core routes
app.include_router(auth_router.router, prefix="/api")
app.include_router(admin_users_router.router, prefix="/api")
app.include_router(projects_router.router, prefix="/api/scorecards", tags=["projects"])
app.include_router(oauth_router.router, prefix="/api/oauth", tags=["oauth"])
app.include_router(jobs_router.router, prefix="/api")

# Module routes
app.include_router(scorecard_router, prefix="/api", tags=["scorecard"])
app.include_router(iso_router, prefix="/api/iso", tags=["iso"])
```

**CRITICAL:** The URL prefix for projects stays `/api/scorecards` — do NOT change API URLs.

**Step 2: Update `app/worker/tasks.py`**

Lines 7-8:
```python
from app.core.models.job import JobStatus
from app.core.services.job_service import JobService
```

Lines 58-65 (lazy imports inside function):
```python
from app.modules.scorecard.api.capture import (
    _build_metrics_data,
    _collect_from_github,
    _collect_from_jira,
    _first_day_of_month,
    _last_day_of_month,
)
from app.core.api.deps import get_project_or_404
from app.modules.scorecard.models.metrics import SnapshotType
from app.modules.scorecard.services.metrics_service import MetricsService
```

**Step 3: Clean up empty legacy directories**

Check what remains in `app/api/` and `app/services/` and `app/models/`:

- `app/api/` — should only have `__init__.py` left (if schemas were fully moved). Delete directory if empty.
- `app/services/` — should only have `__init__.py` left. Delete directory if empty.
- `app/models/` — should have `__init__.py` (barrel) left. Keep it as a convenience re-export layer.

```bash
# Check what's left
ls backend/app/api/
ls backend/app/services/
ls backend/app/models/
# Remove empty directories (keep app/models/__init__.py as barrel)
```

**Step 4: Run backend tests**

```bash
cd backend && python -m pytest --tb=short -q
```

Expected: all ~970 tests pass.

**Step 5: Commit**

```bash
git add -A && git commit -m "refactor: update main.py and workers for modular structure"
```

---

### Task 9: Frontend — Move Shared UI Components

Move shadcn/UI primitives from `components/ui/` to `shared/components/ui/`.

**Files:**
- Move: all `frontend/src/components/ui/*.tsx` → `frontend/src/shared/components/ui/`
- Move: `frontend/src/components/ui/timeline-chart/` → `frontend/src/shared/components/ui/timeline-chart/`
- Keep: `frontend/src/components/ErrorBoundary.tsx` and `frontend/src/components/ProtectedRoute.tsx` — move to `core/components/`

**Step 1: Move all UI primitives**

```bash
cd frontend
# Move individual ui files
git mv src/components/ui/* src/shared/components/ui/
# Move ErrorBoundary and ProtectedRoute to core
git mv src/components/ErrorBoundary.tsx src/core/components/ErrorBoundary.tsx
git mv src/components/ProtectedRoute.tsx src/core/components/ProtectedRoute.tsx
```

**Step 2: Update all imports**

Replace `@/components/ui/` with `@/shared/components/ui/` across the entire frontend.

This affects ~50+ files. Use find-and-replace:
```
from '@/components/ui/ → from '@/shared/components/ui/
```

Also update ErrorBoundary/ProtectedRoute imports in `App.tsx`:
```
from './components/ErrorBoundary' → from './core/components/ErrorBoundary'
from './components/ProtectedRoute' → from './core/components/ProtectedRoute'
```

**Step 3: Run frontend tests**

```bash
cd frontend && npx vitest run
```

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: move shared UI components to shared/components/ui/"
```

---

### Task 10: Frontend — Move Core Files

Move layout, auth, admin, and shared hooks/services/types to `core/`.

**Files:**
- Move: `components/layout/` → `core/components/layout/`
- Move: `components/Admin/` → `core/components/Admin/`
- Move: `components/NotificationsAdmin/` → `core/components/NotificationsAdmin/`
- Move: `contexts/AuthContext.tsx` → `core/contexts/AuthContext.tsx`
- Move: `hooks/useAuth.ts` → `core/hooks/useAuth.ts`
- Move: `hooks/useDownload.ts` → `core/hooks/useDownload.ts`
- Move: `hooks/queryKeys.ts` → `core/hooks/queryKeys.ts`
- Move: `hooks/useAlertDefinitions.ts` → `core/hooks/useAlertDefinitions.ts`
- Move: `hooks/useNotifications.ts` → `core/hooks/useNotifications.ts`
- Move: `hooks/useSilences.ts` → `core/hooks/useSilences.ts`
- Move: `hooks/useJobs.ts` → `core/hooks/useJobs.ts`
- Move: `hooks/useUsers.ts` → `core/hooks/useUsers.ts`
- Move: `hooks/useSlackChannels.ts` → `core/hooks/useSlackChannels.ts`
- Move: `services/api/client.ts` → `core/services/client.ts`
- Move: `services/api/projects.ts` → `core/services/projects.ts`
- Move: `services/api/jobs.ts` → `core/services/jobs.ts`
- Move: `services/api/integrations.ts` → `core/services/integrations.ts`
- Move: `services/api/notifications.ts` → `core/services/notifications.ts`
- Move: `types/auth.ts` → `core/types/auth.ts`
- Move: `types/project.ts` → `core/types/project.ts`
- Move: `types/jobs.ts` → `core/types/jobs.ts`
- Move: `types/alerts.ts` → `core/types/alerts.ts`
- Move: `types/common.ts` → `core/types/common.ts`
- Move: `pages/Admin.tsx` → `core/pages/Admin.tsx`
- Move: `pages/LoginPage.tsx` → `core/pages/LoginPage.tsx`

**Step 1: Create subdirectories and move files**

```bash
cd frontend
mkdir -p src/core/contexts
git mv src/components/layout src/core/components/layout
git mv src/components/Admin src/core/components/Admin
git mv src/components/NotificationsAdmin src/core/components/NotificationsAdmin
git mv src/contexts/AuthContext.tsx src/core/contexts/AuthContext.tsx
git mv src/hooks/useAuth.ts src/core/hooks/useAuth.ts
git mv src/hooks/useDownload.ts src/core/hooks/useDownload.ts
git mv src/hooks/queryKeys.ts src/core/hooks/queryKeys.ts
git mv src/hooks/useAlertDefinitions.ts src/core/hooks/useAlertDefinitions.ts
git mv src/hooks/useNotifications.ts src/core/hooks/useNotifications.ts
git mv src/hooks/useSilences.ts src/core/hooks/useSilences.ts
git mv src/hooks/useJobs.ts src/core/hooks/useJobs.ts
git mv src/hooks/useUsers.ts src/core/hooks/useUsers.ts
git mv src/hooks/useSlackChannels.ts src/core/hooks/useSlackChannels.ts
git mv src/services/api/client.ts src/core/services/client.ts
git mv src/services/api/projects.ts src/core/services/projects.ts
git mv src/services/api/jobs.ts src/core/services/jobs.ts
git mv src/services/api/integrations.ts src/core/services/integrations.ts
git mv src/services/api/notifications.ts src/core/services/notifications.ts
git mv src/types/auth.ts src/core/types/auth.ts
git mv src/types/project.ts src/core/types/project.ts
git mv src/types/jobs.ts src/core/types/jobs.ts
git mv src/types/alerts.ts src/core/types/alerts.ts
git mv src/types/common.ts src/core/types/common.ts
git mv src/pages/Admin.tsx src/core/pages/Admin.tsx
git mv src/pages/LoginPage.tsx src/core/pages/LoginPage.tsx
```

**Step 2: Update all imports**

Replace across the entire frontend:

| Old import path | New import path |
|---|---|
| `@/components/layout/` | `@/core/components/layout/` |
| `@/components/Admin/` | `@/core/components/Admin/` |
| `@/components/NotificationsAdmin/` | `@/core/components/NotificationsAdmin/` |
| `@/contexts/AuthContext` | `@/core/contexts/AuthContext` |
| `@/hooks/useAuth` | `@/core/hooks/useAuth` |
| `@/hooks/useDownload` | `@/core/hooks/useDownload` |
| `@/hooks/queryKeys` | `@/core/hooks/queryKeys` |
| `@/hooks/useAlertDefinitions` | `@/core/hooks/useAlertDefinitions` |
| `@/hooks/useNotifications` | `@/core/hooks/useNotifications` |
| `@/hooks/useSilences` | `@/core/hooks/useSilences` |
| `@/hooks/useJobs` | `@/core/hooks/useJobs` |
| `@/hooks/useUsers` | `@/core/hooks/useUsers` |
| `@/hooks/useSlackChannels` | `@/core/hooks/useSlackChannels` |
| `@/services/api/client` | `@/core/services/client` |
| `@/services/api/projects` | `@/core/services/projects` |
| `@/services/api/jobs` | `@/core/services/jobs` |
| `@/services/api/integrations` | `@/core/services/integrations` |
| `@/services/api/notifications` | `@/core/services/notifications` |
| `@/types/auth` | `@/core/types/auth` |
| `@/types/project` | `@/core/types/project` |
| `@/types/jobs` | `@/core/types/jobs` |
| `@/types/alerts` | `@/core/types/alerts` |
| `@/types/common` | `@/core/types/common` |
| `./pages/Admin` | `./core/pages/Admin` |
| `./pages/LoginPage` | `./core/pages/LoginPage` |

Also update internal imports within moved files (e.g., `AdminNotificationsLayout` importing from `@/hooks/queryKeys` → `@/core/hooks/queryKeys`).

**Step 3: Run frontend tests**

```bash
cd frontend && npx vitest run
```

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: move core frontend files to src/core/"
```

---

### Task 11: Frontend — Move Scorecard Files

Move all scorecard-specific frontend code to `modules/scorecard/`.

**Files:**
- Move: `components/ProjectDetail/` → `modules/scorecard/components/ProjectDetail/`
- Move: `components/ScoreCard/` → `modules/scorecard/components/ScoreCard/`
- Move: `components/SubIndicatorCard/` → `modules/scorecard/components/SubIndicatorCard/`
- Move: `components/DimensionChart/` → `modules/scorecard/components/DimensionChart/`
- Move: `components/Dashboard/` → `modules/scorecard/components/Dashboard/`
- Move: `components/Forms/` → `modules/scorecard/components/Forms/`
- Move: `components/Settings/` → `modules/scorecard/components/Settings/`
- Move: `components/ParameterSection.tsx` → `modules/scorecard/components/ParameterSection.tsx`
- Move: `hooks/useMetrics.ts` → `modules/scorecard/hooks/useMetrics.ts`
- Move: `hooks/useScores.ts` → `modules/scorecard/hooks/useScores.ts`
- Move: `hooks/useConfig.ts` → `modules/scorecard/hooks/useConfig.ts`
- Move: `hooks/useConfigEditor.ts` → `modules/scorecard/hooks/useConfigEditor.ts`
- Move: `hooks/usePeriodCapture.ts` → `modules/scorecard/hooks/usePeriodCapture.ts`
- Move: `hooks/useProjects.ts` → `core/hooks/useProjects.ts` (projects are core!)
- Move: `hooks/useProjectListParams.ts` → `modules/scorecard/hooks/useProjectListParams.ts`
- Move: `hooks/useProjectScoresMap.ts` → `modules/scorecard/hooks/useProjectScoresMap.ts`
- Move: `hooks/useSnapshots.ts` → `modules/scorecard/hooks/useSnapshots.ts`
- Move: `hooks/useGlobalMetrics.ts` → `modules/scorecard/hooks/useGlobalMetrics.ts`
- Move: `hooks/useTrendExpand.ts` → `modules/scorecard/hooks/useTrendExpand.ts`
- Move: `hooks/useExport.ts` → `modules/scorecard/hooks/useExport.ts`
- Move: `hooks/cacheUtils.ts` → `modules/scorecard/hooks/cacheUtils.ts` (only used by scorecard)
- Move: `services/api/scores.ts` → `modules/scorecard/services/scores.ts`
- Move: `services/api/metrics.ts` → `modules/scorecard/services/metrics.ts`
- Move: `services/api/exports.ts` → `modules/scorecard/services/exports.ts`
- Move: `services/api/global.ts` → `modules/scorecard/services/global.ts`
- Move: `types/scores.ts` → `modules/scorecard/types/scores.ts`
- Move: `types/metrics.ts` → `modules/scorecard/types/metrics.ts`
- Move: `types/config.ts` → `modules/scorecard/types/config.ts`
- Move: `types/global.ts` → `modules/scorecard/types/global.ts`
- Move: `pages/Projects.tsx` → `modules/scorecard/pages/Projects.tsx`
- Move: `pages/ProjectDetail.tsx` → `modules/scorecard/pages/ProjectDetail.tsx`
- Move: `pages/GlobalDashboard/` → `modules/scorecard/pages/GlobalDashboard/`

**Step 1: Move all files**

```bash
cd frontend
# Components
git mv src/components/ProjectDetail src/modules/scorecard/components/ProjectDetail
git mv src/components/ScoreCard src/modules/scorecard/components/ScoreCard
git mv src/components/SubIndicatorCard src/modules/scorecard/components/SubIndicatorCard
git mv src/components/DimensionChart src/modules/scorecard/components/DimensionChart
git mv src/components/Dashboard src/modules/scorecard/components/Dashboard
git mv src/components/Forms src/modules/scorecard/components/Forms
git mv src/components/Settings src/modules/scorecard/components/Settings
git mv src/components/ParameterSection.tsx src/modules/scorecard/components/ParameterSection.tsx

# Hooks
git mv src/hooks/useMetrics.ts src/modules/scorecard/hooks/useMetrics.ts
git mv src/hooks/useScores.ts src/modules/scorecard/hooks/useScores.ts
git mv src/hooks/useConfig.ts src/modules/scorecard/hooks/useConfig.ts
git mv src/hooks/useConfigEditor.ts src/modules/scorecard/hooks/useConfigEditor.ts
git mv src/hooks/usePeriodCapture.ts src/modules/scorecard/hooks/usePeriodCapture.ts
git mv src/hooks/useProjects.ts src/core/hooks/useProjects.ts
git mv src/hooks/useProjectListParams.ts src/modules/scorecard/hooks/useProjectListParams.ts
git mv src/hooks/useProjectScoresMap.ts src/modules/scorecard/hooks/useProjectScoresMap.ts
git mv src/hooks/useSnapshots.ts src/modules/scorecard/hooks/useSnapshots.ts
git mv src/hooks/useGlobalMetrics.ts src/modules/scorecard/hooks/useGlobalMetrics.ts
git mv src/hooks/useTrendExpand.ts src/modules/scorecard/hooks/useTrendExpand.ts
git mv src/hooks/useExport.ts src/modules/scorecard/hooks/useExport.ts
git mv src/hooks/cacheUtils.ts src/modules/scorecard/hooks/cacheUtils.ts

# Services
git mv src/services/api/scores.ts src/modules/scorecard/services/scores.ts
git mv src/services/api/metrics.ts src/modules/scorecard/services/metrics.ts
git mv src/services/api/exports.ts src/modules/scorecard/services/exports.ts
git mv src/services/api/global.ts src/modules/scorecard/services/global.ts

# Types
git mv src/types/scores.ts src/modules/scorecard/types/scores.ts
git mv src/types/metrics.ts src/modules/scorecard/types/metrics.ts
git mv src/types/config.ts src/modules/scorecard/types/config.ts
git mv src/types/global.ts src/modules/scorecard/types/global.ts

# Pages
git mv src/pages/Projects.tsx src/modules/scorecard/pages/Projects.tsx
git mv src/pages/ProjectDetail.tsx src/modules/scorecard/pages/ProjectDetail.tsx
git mv src/pages/GlobalDashboard src/modules/scorecard/pages/GlobalDashboard
```

**Step 2: Update all imports**

Replace across the entire frontend. Main patterns:

| Old import path | New import path |
|---|---|
| `@/components/ProjectDetail/` | `@/modules/scorecard/components/ProjectDetail/` |
| `@/components/ScoreCard/` | `@/modules/scorecard/components/ScoreCard/` |
| `@/components/SubIndicatorCard/` | `@/modules/scorecard/components/SubIndicatorCard/` |
| `@/components/DimensionChart/` | `@/modules/scorecard/components/DimensionChart/` |
| `@/components/Dashboard/` | `@/modules/scorecard/components/Dashboard/` |
| `@/components/Forms/` | `@/modules/scorecard/components/Forms/` |
| `@/components/Settings/` | `@/modules/scorecard/components/Settings/` |
| `@/components/ParameterSection` | `@/modules/scorecard/components/ParameterSection` |
| `@/hooks/useMetrics` | `@/modules/scorecard/hooks/useMetrics` |
| `@/hooks/useScores` | `@/modules/scorecard/hooks/useScores` |
| `@/hooks/useConfig` | `@/modules/scorecard/hooks/useConfig` |
| `@/hooks/useConfigEditor` | `@/modules/scorecard/hooks/useConfigEditor` |
| `@/hooks/usePeriodCapture` | `@/modules/scorecard/hooks/usePeriodCapture` |
| `@/hooks/useProjects` | `@/core/hooks/useProjects` |
| `@/hooks/useProjectListParams` | `@/modules/scorecard/hooks/useProjectListParams` |
| `@/hooks/useProjectScoresMap` | `@/modules/scorecard/hooks/useProjectScoresMap` |
| `@/hooks/useSnapshots` | `@/modules/scorecard/hooks/useSnapshots` |
| `@/hooks/useGlobalMetrics` | `@/modules/scorecard/hooks/useGlobalMetrics` |
| `@/hooks/useTrendExpand` | `@/modules/scorecard/hooks/useTrendExpand` |
| `@/hooks/useExport` | `@/modules/scorecard/hooks/useExport` |
| `@/hooks/cacheUtils` | `@/modules/scorecard/hooks/cacheUtils` |
| `@/services/api/scores` | `@/modules/scorecard/services/scores` |
| `@/services/api/metrics` | `@/modules/scorecard/services/metrics` |
| `@/services/api/exports` | `@/modules/scorecard/services/exports` |
| `@/services/api/global` | `@/modules/scorecard/services/global` |
| `@/types/scores` | `@/modules/scorecard/types/scores` |
| `@/types/metrics` | `@/modules/scorecard/types/metrics` |
| `@/types/config` | `@/modules/scorecard/types/config` |
| `@/types/global` | `@/modules/scorecard/types/global` |

**CRITICAL — Barrel file consumers:** Many files import types from `@/types` (the barrel `types/index.ts`). Each of these imports must be split into the correct module path. For example:

```typescript
// Before:
import { Project, Metrics, DimensionScores } from '@/types';

// After:
import { Project } from '@/core/types/project';
import { Metrics } from '@/modules/scorecard/types/metrics';
import { DimensionScores } from '@/modules/scorecard/types/scores';
```

Same for `@/services/api` barrel consumers — split into module paths.

**Step 3: Run frontend tests**

```bash
cd frontend && npx vitest run
```

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: move scorecard frontend files to src/modules/scorecard/"
```

---

### Task 12: Frontend — Move ISO Files

Move ISO-specific frontend code to `modules/iso/`.

**Files:**
- Move: `hooks/useIso.ts` → `modules/iso/hooks/useIso.ts`
- Move: `hooks/useIsoExport.ts` → `modules/iso/hooks/useIsoExport.ts`
- Move: `hooks/isoStaleCheck.ts` → `modules/iso/hooks/isoStaleCheck.ts`
- Move: `services/api/iso.ts` → `modules/iso/services/iso.ts`
- Move: `types/iso.ts` → `modules/iso/types/iso.ts`
- Move: `pages/ISO.tsx` → `modules/iso/pages/ISO.tsx`
- Move: `pages/ISOSnapshots.tsx` → `modules/iso/pages/ISOSnapshots.tsx`
- Move: `pages/ISOConfig.tsx` → `modules/iso/pages/ISOConfig.tsx`
- Move: `pages/iso/` → `modules/iso/pages/` (merge ISOSnapshotDetail + components)

**Step 1: Move all files**

```bash
cd frontend
git mv src/hooks/useIso.ts src/modules/iso/hooks/useIso.ts
git mv src/hooks/useIsoExport.ts src/modules/iso/hooks/useIsoExport.ts
git mv src/hooks/isoStaleCheck.ts src/modules/iso/hooks/isoStaleCheck.ts
git mv src/services/api/iso.ts src/modules/iso/services/iso.ts
git mv src/types/iso.ts src/modules/iso/types/iso.ts
git mv src/pages/ISO.tsx src/modules/iso/pages/ISO.tsx
git mv src/pages/ISOSnapshots.tsx src/modules/iso/pages/ISOSnapshots.tsx
git mv src/pages/ISOConfig.tsx src/modules/iso/pages/ISOConfig.tsx
git mv src/pages/iso/ISOSnapshotDetail.tsx src/modules/iso/pages/ISOSnapshotDetail.tsx
git mv src/pages/iso/components src/modules/iso/components
```

Also move ISO-specific UI components:
```bash
git mv src/shared/components/ui/review-status-badge.tsx src/modules/iso/components/review-status-badge.tsx
git mv src/shared/components/ui/stat-cards.tsx src/modules/iso/components/stat-cards.tsx
```

**Step 2: Update all imports**

| Old import path | New import path |
|---|---|
| `@/hooks/useIso` | `@/modules/iso/hooks/useIso` |
| `@/hooks/useIsoExport` | `@/modules/iso/hooks/useIsoExport` |
| `@/hooks/isoStaleCheck` | `@/modules/iso/hooks/isoStaleCheck` |
| `@/services/api/iso` | `@/modules/iso/services/iso` |
| `@/types/iso` | `@/modules/iso/types/iso` |
| `./pages/ISO` (in App.tsx) | `./modules/iso/pages/ISO` |
| `./pages/ISOSnapshots` | `./modules/iso/pages/ISOSnapshots` |
| `./pages/iso/ISOSnapshotDetail` | `./modules/iso/pages/ISOSnapshotDetail` |
| `@/shared/components/ui/review-status-badge` | `@/modules/iso/components/review-status-badge` |
| `@/shared/components/ui/stat-cards` | `@/modules/iso/components/stat-cards` |

**Cross-module coupling:** `IntegrationsTab` (now at `modules/scorecard/components/Settings/IntegrationsTab.tsx`) imports `ISOConfig`. Update to:
```typescript
import ISOConfig from '@/modules/iso/pages/ISOConfig';
```

**Step 3: Run frontend tests**

```bash
cd frontend && npx vitest run
```

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: move ISO frontend files to src/modules/iso/"
```

---

### Task 13: Frontend Integration — App.tsx, Barrel Cleanup

Update App.tsx imports and remove/update old barrel files.

**Files:**
- Modify: `App.tsx`
- Modify or delete: `types/index.ts`
- Modify or delete: `services/api/index.ts`
- Clean up: empty directories under `src/components/`, `src/hooks/`, `src/pages/`, `src/services/`, `src/types/`

**Step 1: Rewrite App.tsx imports**

```typescript
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './core/contexts/AuthContext';
import { ErrorBoundary } from './core/components/ErrorBoundary';
import { ProtectedRoute, AdminRoute } from './core/components/ProtectedRoute';
import { AppLayout } from './core/components/layout/AppLayout';
import Projects from './modules/scorecard/pages/Projects';
import ProjectDetail from './modules/scorecard/pages/ProjectDetail';
import GlobalDashboard from './modules/scorecard/pages/GlobalDashboard';
import Admin from './core/pages/Admin';
import ISO from './modules/iso/pages/ISO';
import ISOSnapshots from './modules/iso/pages/ISOSnapshots';
import ISOSnapshotDetail from './modules/iso/pages/ISOSnapshotDetail';
import { LoginPage } from './core/pages/LoginPage';
import ConfigurationTab from './modules/scorecard/components/Settings/ConfigurationTab';
import IntegrationsTab from './modules/scorecard/components/Settings/IntegrationsTab';
import AdminNotificationsLayout from './core/components/NotificationsAdmin/AdminNotificationsLayout';
import AlertLogTab from './core/components/NotificationsAdmin/AlertLogTab';
import SilencesTab from './core/components/NotificationsAdmin/SilencesTab';
import AlertConfigTab from './core/components/NotificationsAdmin/AlertConfigTab';
import StatisticsTab from './core/components/NotificationsAdmin/StatisticsTab';
import JobsContent from './core/components/Admin/JobsContent';
import { UsersContent } from './core/components/Admin/UsersContent';
```

The rest of App.tsx (routes) stays the same — no URL changes.

**Step 2: Update barrel files**

Update `types/index.ts` to re-export from new locations (keep as convenience barrel):

```typescript
// Core types
export type { Project, ProjectCreate, ProjectUpdate, ... } from '@/core/types/project';
export type { JobStatus, JobType, ... } from '@/core/types/jobs';
export type { AlertDefinition, ... } from '@/core/types/alerts';
export type { ApiErrorResponse, PaginatedResponse } from '@/core/types/common';

// Scorecard types
export type { Metrics, MetricsCreate, ... } from '@/modules/scorecard/types/metrics';
export type { DimensionScores, FinalScore, ... } from '@/modules/scorecard/types/scores';
export type { ConfigParameter, ... } from '@/modules/scorecard/types/config';
export type { GlobalMetricsRecord, ... } from '@/modules/scorecard/types/global';
export { ALL_DIMENSIONS } from '@/modules/scorecard/types/scores';

// ISO types
export type { AccessSnapshot, ... } from '@/modules/iso/types/iso';
```

Update `services/api/index.ts` similarly with re-exports from new locations.

**Note:** The barrel files are now thin re-export layers. If any consumer still imports from `@/types` or `@/services/api`, it will work. Over time, consumers should import directly from modules.

**Step 3: Clean up empty directories**

```bash
cd frontend
# Remove empty legacy directories (check each is actually empty first)
# src/components/ should only have the src/components/ directory itself if everything moved
# src/hooks/ should be empty
# src/pages/ should be empty
# src/services/api/ may have just index.ts
# src/types/ may have just index.ts
# src/contexts/ should be empty
```

**Step 4: Run frontend tests**

```bash
cd frontend && npx vitest run
```

Expected: all ~340 tests pass.

**Step 5: Commit**

```bash
git add -A && git commit -m "refactor: update App.tsx and barrel files for modular structure"
```

---

### Task 14: Final Verification and Cleanup

Run the full test suite, verify no broken imports, and clean up.

**Step 1: Run full backend test suite**

```bash
cd backend && python -m pytest --tb=short -q
```

Expected: all ~970 tests pass.

**Step 2: Run full frontend test suite**

```bash
cd frontend && npx vitest run
```

Expected: all ~340 tests pass.

**Step 3: Verify TypeScript compilation**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

**Step 4: Verify the dev servers start**

```bash
# Backend
cd backend && timeout 10 python run_server.py || true
# Frontend
cd frontend && timeout 10 npm run dev || true
```

**Step 5: Check for orphaned imports**

```bash
# Backend: check no remaining imports from old paths
cd backend
grep -r "from app\.api\." app/ --include="*.py" | grep -v "__pycache__" | grep -v "app.api.deps"
grep -r "from app\.services\." app/ --include="*.py" | grep -v "__pycache__"
grep -r "from app\.models\." app/ --include="*.py" | grep -v "__pycache__" | grep -v "app.models.__init__"

# Frontend: check no remaining imports from old paths
cd frontend
grep -r "from '@/components/" src/ --include="*.ts" --include="*.tsx" | grep -v "node_modules"
grep -r "from '@/hooks/" src/ --include="*.ts" --include="*.tsx" | grep -v "node_modules"
grep -r "from '@/pages/" src/ --include="*.ts" --include="*.tsx" | grep -v "node_modules"
```

Expected: no results (or only the barrel re-exports).

**Step 6: Update CLAUDE.md if needed**

Verify the module architecture rules in CLAUDE.md still reflect reality. No changes should be needed since the rules already describe the target state.

**Step 7: Final commit**

```bash
git add -A && git commit -m "chore: final cleanup for modular monolith refactor"
```

---

## Summary

| Task | Description | Estimated files touched |
|------|-------------|------------------------|
| 1 | Setup (branch + dirs) | ~20 new dirs |
| 2 | Backend core models | ~50 files |
| 3 | Backend core services | ~15 files |
| 4 | Backend core API | ~25 files |
| 5 | Backend scorecard models | ~40 files |
| 6 | Backend scorecard services | ~50 files |
| 7 | Backend scorecard API + schemas | ~30 files |
| 8 | Backend integration (main.py, workers) | ~5 files |
| 9 | Frontend shared UI | ~55 files |
| 10 | Frontend core | ~40 files |
| 11 | Frontend scorecard | ~60 files |
| 12 | Frontend ISO | ~15 files |
| 13 | Frontend integration (App.tsx, barrels) | ~5 files |
| 14 | Final verification | 0 files (tests only) |

**Total: ~14 tasks, ~390 file touches (mostly import-only changes)**
