# Extract Notifications Module — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract Slack/alert/notification code from the scorecard module into a standalone `app/modules/notifications/` module so any module can trigger notifications without importing scorecard internals.

**Architecture:** Move models, services, API routes, and schemas into `app/modules/notifications/`. Expose `SlackService`, `AlertService`, and all models via `notifications/public.py`. Update all imports across workers, core, tracker, scorecard, tests, and scripts. No logic changes — pure mechanical refactor.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest

---

## File Structure

### New files to create

```
app/modules/notifications/
├── __init__.py                  # Empty
├── models/
│   ├── __init__.py              # Empty
│   └── slack.py                 # Move from scorecard/models/slack.py (6 DB models + enums)
├── services/
│   ├── __init__.py              # Empty
│   ├── slack_service.py         # Move from scorecard/services/slack_service.py
│   └── alert_service.py         # Move from scorecard/services/alert_service.py
├── api/
│   ├── __init__.py              # Empty
│   ├── schemas/
│   │   ├── __init__.py          # Empty
│   │   └── slack.py             # Move from scorecard/api/schemas/slack.py
│   ├── notifications.py         # Move from scorecard/api/notifications.py
│   ├── slack_admin.py           # Move from scorecard/api/slack_admin.py
│   ├── silences.py              # Move from scorecard/api/silences.py
│   └── scheduled_jobs.py        # Move from scorecard/api/scheduled_jobs.py
├── router.py                    # New: aggregates notification sub-routers
└── public.py                    # New: cross-module interface
```

### Files to modify (imports only)

**Scorecard module:**
- `app/modules/scorecard/router.py` — remove 6 router includes (notifications, slack_admin×3, silences, scheduled_jobs)
- `app/modules/scorecard/api/integrations_admin.py` — update imports for `SlackService`, `SlackChannel`, `SlackTestResult`

**Core:**
- `app/core/api/auth.py` — update `SlackService` import
- `app/core/api/admin_users.py` — update `SlackService` import

**Tracker:**
- `app/modules/tracker/api/postponements.py` — update imports for `AlertDefinitionDB`, `AlertService`, `SlackService`

**Workers:**
- `app/worker/utils.py` — update `ScheduledJobRunDB` import
- `app/worker/check_business_alerts.py` — update all notification imports
- `app/worker/check_dependabot.py` — update all notification imports
- `app/worker/collect_iso_snapshot.py` — update imports
- `app/worker/report_reminder.py` — update imports
- `app/worker/report_confirmation_reminder.py` — update imports
- `app/worker/rotate_reporting_period.py` — update import
- `app/worker/monthly_scorecard_capture.py` — update import
- `app/worker/fetch_exchange_rates.py` — update import

**Scripts:**
- `scripts/seed_alert_definitions.py` — update model imports

**Main:**
- `app/main.py` — mount notifications router

**Tests:**
- `tests/test_slack_service.py` — update import
- `tests/test_alert_service.py` — update imports
- `tests/test_slack_admin_api.py` — update imports
- `tests/test_notifications_api.py` — update imports
- `tests/test_silences_api.py` — update imports
- `tests/test_slack_models.py` — update imports
- `tests/test_check_business_alerts_job.py` — update imports
- `tests/test_check_dependabot_job.py` — update imports
- `tests/test_iso_cron.py` — update import
- `tests/test_report_confirmation_reminder_job.py` — update import
- `tests/test_report_reminder_job.py` — update import
- `tests/test_rotate_reporting_period_job.py` — update import
- `tests/test_scheduled_jobs_api.py` — update import

### Files to delete

- `app/modules/scorecard/models/slack.py`
- `app/modules/scorecard/services/slack_service.py`
- `app/modules/scorecard/services/alert_service.py`
- `app/modules/scorecard/api/notifications.py`
- `app/modules/scorecard/api/slack_admin.py`
- `app/modules/scorecard/api/silences.py`
- `app/modules/scorecard/api/scheduled_jobs.py`
- `app/modules/scorecard/api/schemas/slack.py`

---

### Task 0: Promote PaginatedResponse to core

**Files:**
- Create: `app/core/schemas/__init__.py`
- Create: `app/core/schemas/common.py`
- Modify: `app/modules/scorecard/api/schemas/common.py`
- Modify: `app/modules/scorecard/api/schemas/project.py`
- Modify: `app/modules/iso/api/reviews.py`
- Modify: `app/modules/iso/api/snapshots.py`

`PaginatedResponse` currently lives in `scorecard/api/schemas/common.py` but is imported by ISO and will be imported by the new notifications module. This violates the "cross-module imports through `public.py` ONLY" rule. Promote it to `core/schemas/` where any module can use it cleanly.

- [ ] **Step 1: Create `app/core/schemas/common.py`**

Create `app/core/schemas/__init__.py` (empty) and `app/core/schemas/common.py`:
```python
"""Common API schemas shared across modules."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response envelope."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
```

- [ ] **Step 2: Update scorecard's schemas/common.py to re-export from core**

Replace the contents of `app/modules/scorecard/api/schemas/common.py` with:
```python
"""Common API schemas — re-exported from core for backwards compatibility."""

from app.core.schemas.common import PaginatedResponse

__all__ = ["PaginatedResponse"]
```

- [ ] **Step 3: Update ISO imports**

In `app/modules/iso/api/reviews.py` and `app/modules/iso/api/snapshots.py`, change:
```python
# OLD
from app.modules.scorecard.api.schemas.common import PaginatedResponse
# NEW
from app.core.schemas.common import PaginatedResponse
```

- [ ] **Step 4: Update scorecard's own usage**

In `app/modules/scorecard/api/schemas/project.py`, change:
```python
# OLD
from app.modules.scorecard.api.schemas.common import PaginatedResponse
# NEW
from app.core.schemas.common import PaginatedResponse
```

- [ ] **Step 5: Run tests to verify**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -c "from app.core.schemas.common import PaginatedResponse; print('OK')" && popd > /dev/null`
Expected: OK

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/schemas/ backend/app/modules/scorecard/api/schemas/common.py backend/app/modules/scorecard/api/schemas/project.py backend/app/modules/iso/api/reviews.py backend/app/modules/iso/api/snapshots.py
git commit -m "refactor: promote PaginatedResponse to core/schemas for cross-module use"
```

---

### Task 1: Create notifications module skeleton and move models

**Files:**
- Create: `app/modules/notifications/__init__.py`
- Create: `app/modules/notifications/models/__init__.py`
- Create: `app/modules/notifications/models/slack.py`
- Create: `app/modules/notifications/services/__init__.py`
- Create: `app/modules/notifications/api/__init__.py`
- Create: `app/modules/notifications/api/schemas/__init__.py`

- [ ] **Step 1: Create directory structure with empty `__init__.py` files**

Create these empty files:
```
app/modules/notifications/__init__.py
app/modules/notifications/models/__init__.py
app/modules/notifications/services/__init__.py
app/modules/notifications/api/__init__.py
app/modules/notifications/api/schemas/__init__.py
```

- [ ] **Step 2: Move models/slack.py**

Copy `app/modules/scorecard/models/slack.py` → `app/modules/notifications/models/slack.py`. The file content is identical — no internal imports to update (only imports `app.database.Base`).

- [ ] **Step 3: Run tests to verify models import correctly**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -c "from app.modules.notifications.models.slack import AlertDefinitionDB, ScheduledJobRunDB; print('OK')" && popd > /dev/null`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/notifications/
git commit -m "refactor: create notifications module skeleton and move models"
```

---

### Task 2: Move services

**Files:**
- Create: `app/modules/notifications/services/slack_service.py`
- Create: `app/modules/notifications/services/alert_service.py`

- [ ] **Step 1: Move slack_service.py**

Copy `app/modules/scorecard/services/slack_service.py` → `app/modules/notifications/services/slack_service.py`. No internal imports to update (only uses `httpx`).

- [ ] **Step 2: Move alert_service.py**

Copy `app/modules/scorecard/services/alert_service.py` → `app/modules/notifications/services/alert_service.py`.

Update the internal import:
```python
# OLD
from app.modules.scorecard.models.slack import (
    AlertNotificationDB,
    AlertSilenceDB,
    MessageTemplateDB,
)

# NEW
from app.modules.notifications.models.slack import (
    AlertNotificationDB,
    AlertSilenceDB,
    MessageTemplateDB,
)
```

- [ ] **Step 3: Verify imports**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -c "from app.modules.notifications.services.slack_service import SlackService; from app.modules.notifications.services.alert_service import AlertService; print('OK')" && popd > /dev/null`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/notifications/services/
git commit -m "refactor: move slack_service and alert_service to notifications module"
```

---

### Task 3: Move API schemas

**Files:**
- Create: `app/modules/notifications/api/schemas/slack.py`

- [ ] **Step 1: Move schemas/slack.py**

Copy `app/modules/scorecard/api/schemas/slack.py` → `app/modules/notifications/api/schemas/slack.py`.

Update the import to use core (promoted in Task 0):
```python
# OLD
from app.modules.scorecard.api.schemas.common import PaginatedResponse

# NEW
from app.core.schemas.common import PaginatedResponse
```

- [ ] **Step 2: Verify import**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -c "from app.modules.notifications.api.schemas.slack import AlertDefinitionResponse; print('OK')" && popd > /dev/null`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/notifications/api/schemas/
git commit -m "refactor: move notification schemas to notifications module"
```

---

### Task 4: Move API routes and create router

**Files:**
- Create: `app/modules/notifications/api/notifications.py`
- Create: `app/modules/notifications/api/slack_admin.py`
- Create: `app/modules/notifications/api/silences.py`
- Create: `app/modules/notifications/api/scheduled_jobs.py`
- Create: `app/modules/notifications/router.py`

- [ ] **Step 1: Move notifications.py**

Copy `app/modules/scorecard/api/notifications.py` → `app/modules/notifications/api/notifications.py`.

Update imports:
```python
# OLD
from app.modules.scorecard.api.schemas.slack import (
    AlertNotificationResponse,
    NotificationStatsResponse,
    PaginatedNotificationsResponse,
)
from app.modules.scorecard.models.slack import AlertDefinitionDB, AlertNotificationDB, DependabotAlertTrackedDB

# NEW
from app.modules.notifications.api.schemas.slack import (
    AlertNotificationResponse,
    NotificationStatsResponse,
    PaginatedNotificationsResponse,
)
from app.modules.notifications.models.slack import AlertDefinitionDB, AlertNotificationDB, DependabotAlertTrackedDB
```

- [ ] **Step 2: Move slack_admin.py**

Copy `app/modules/scorecard/api/slack_admin.py` → `app/modules/notifications/api/slack_admin.py`.

Update imports:
```python
# OLD
from app.modules.scorecard.api.schemas.slack import (...)
from app.modules.scorecard.models.slack import AlertDefinitionDB, MessageTemplateDB
from app.modules.scorecard.services.slack_service import SlackService

# NEW
from app.modules.notifications.api.schemas.slack import (...)
from app.modules.notifications.models.slack import AlertDefinitionDB, MessageTemplateDB
from app.modules.notifications.services.slack_service import SlackService
```

- [ ] **Step 3: Move silences.py**

Copy `app/modules/scorecard/api/silences.py` → `app/modules/notifications/api/silences.py`.

Update imports:
```python
# OLD
from app.modules.scorecard.api.schemas.slack import (...)
from app.modules.scorecard.models.slack import AlertDefinitionDB, AlertSilenceDB

# NEW
from app.modules.notifications.api.schemas.slack import (...)
from app.modules.notifications.models.slack import AlertDefinitionDB, AlertSilenceDB
```

- [ ] **Step 4: Move scheduled_jobs.py**

Copy `app/modules/scorecard/api/scheduled_jobs.py` → `app/modules/notifications/api/scheduled_jobs.py`.

Update imports:
```python
# OLD
from app.modules.scorecard.api.schemas.slack import (...)
from app.modules.scorecard.models.slack import ScheduledJobRunDB

# NEW
from app.modules.notifications.api.schemas.slack import (...)
from app.modules.notifications.models.slack import ScheduledJobRunDB
```

- [ ] **Step 5: Create router.py**

Create `app/modules/notifications/router.py`:
```python
"""Notifications module router — aggregates all notification sub-routers."""

from fastapi import APIRouter

from app.modules.notifications.api import notifications as notifications_router
from app.modules.notifications.api import scheduled_jobs as scheduled_jobs_router
from app.modules.notifications.api import silences as silences_router
from app.modules.notifications.api import slack_admin as slack_admin_router

router = APIRouter()

router.include_router(slack_admin_router.alerts_router)
router.include_router(slack_admin_router.templates_router)
router.include_router(slack_admin_router.custom_router)
router.include_router(silences_router.router)
router.include_router(notifications_router.router)
router.include_router(scheduled_jobs_router.router)
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/notifications/api/ backend/app/modules/notifications/router.py
git commit -m "refactor: move notification API routes and create notifications router"
```

---

### Task 5: Create public.py

**Files:**
- Create: `app/modules/notifications/public.py`

- [ ] **Step 1: Create public.py**

Create `app/modules/notifications/public.py`:
```python
"""Public interface for the notifications module.

Other modules should import from here, never from notifications internals.
"""

from app.modules.notifications.api.schemas.slack import SlackChannel, SlackTestResult
from app.modules.notifications.models.slack import (
    AlertDefinitionDB,
    AlertNotificationDB,
    AlertSilenceDB,
    DependabotAlertTrackedDB,
    MessageTemplateDB,
    ScheduledJobRunDB,
)
from app.modules.notifications.services.alert_service import AlertService
from app.modules.notifications.services.slack_service import SlackService

__all__ = [
    "AlertDefinitionDB",
    "AlertNotificationDB",
    "AlertSilenceDB",
    "AlertService",
    "DependabotAlertTrackedDB",
    "MessageTemplateDB",
    "ScheduledJobRunDB",
    "SlackChannel",
    "SlackService",
    "SlackTestResult",
]
```

- [ ] **Step 2: Verify public interface**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -c "from app.modules.notifications.public import SlackService, AlertService, AlertDefinitionDB, ScheduledJobRunDB; print('OK')" && popd > /dev/null`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/notifications/public.py
git commit -m "refactor: add notifications module public interface"
```

---

### Task 6: Update scorecard router and main.py

**Files:**
- Modify: `app/modules/scorecard/router.py`
- Modify: `app/main.py`

- [ ] **Step 1: Remove notification routers from scorecard/router.py**

Remove these lines from `app/modules/scorecard/router.py`:
```python
# REMOVE these imports:
from app.modules.scorecard.api import notifications as notifications_router
from app.modules.scorecard.api import scheduled_jobs as scheduled_jobs_router
from app.modules.scorecard.api import silences as silences_router
from app.modules.scorecard.api import slack_admin as slack_admin_router

# REMOVE these router includes:
router.include_router(slack_admin_router.alerts_router)
router.include_router(slack_admin_router.templates_router)
router.include_router(slack_admin_router.custom_router)
router.include_router(silences_router.router)
router.include_router(notifications_router.router)
router.include_router(scheduled_jobs_router.router)
```

The remaining scorecard router should look like:
```python
"""Scorecard module router — aggregates all scorecard sub-routers."""

from fastapi import APIRouter

from app.modules.scorecard.api import capture as capture_router
from app.modules.scorecard.api import collectors as collectors_router
from app.modules.scorecard.api import config as config_router
from app.modules.scorecard.api import exports as exports_router
from app.modules.scorecard.api import global_metrics as global_metrics_router
from app.modules.scorecard.api import integrations_admin as integrations_admin_router
from app.modules.scorecard.api import metrics as metrics_router
from app.modules.scorecard.api import scores as scores_router

router = APIRouter()

router.include_router(metrics_router.router, prefix="/metrics", tags=["metrics"])
router.include_router(scores_router.router, prefix="/scores", tags=["scores"])
router.include_router(config_router.router, prefix="/config", tags=["config"])
router.include_router(collectors_router.router, prefix="/collect", tags=["collectors"])
router.include_router(capture_router.router, prefix="/scorecards", tags=["capture"])
router.include_router(exports_router.router, prefix="/exports", tags=["exports"])

router.include_router(global_metrics_router.router)
router.include_router(integrations_admin_router.router)
```

- [ ] **Step 2: Mount notifications router in main.py**

Add import and mount in `app/main.py`:
```python
# Add import (after playbook_router import):
from app.modules.notifications.router import router as notifications_router

# Add mount (after playbook_router mount):
app.include_router(notifications_router, prefix="/api", tags=["notifications"])
```

- [ ] **Step 3: Verify server starts**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -c "from app.main import app; print(f'Routes: {len(app.routes)}')" && popd > /dev/null`
Expected: Should print route count without errors.

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/scorecard/router.py backend/app/main.py
git commit -m "refactor: mount notifications router in main, remove from scorecard"
```

---

### Task 7: Update scorecard integrations_admin imports

**Files:**
- Modify: `app/modules/scorecard/api/integrations_admin.py`

- [ ] **Step 1: Update imports**

In `app/modules/scorecard/api/integrations_admin.py`, change:
```python
# OLD
from app.modules.scorecard.api.schemas.slack import SlackChannel, SlackTestResult
from app.modules.scorecard.services.slack_service import SlackService

# NEW (via public interface — cross-module rule)
from app.modules.notifications.public import SlackChannel, SlackService, SlackTestResult
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/modules/scorecard/api/integrations_admin.py
git commit -m "refactor: update scorecard integrations_admin to use notifications module"
```

---

### Task 8: Update core imports

**Files:**
- Modify: `app/core/api/auth.py`
- Modify: `app/core/api/admin_users.py`

- [ ] **Step 1: Update auth.py**

In `app/core/api/auth.py`, change:
```python
# OLD
from app.modules.scorecard.services.slack_service import SlackService

# NEW
from app.modules.notifications.services.slack_service import SlackService
```

- [ ] **Step 2: Update admin_users.py**

In `app/core/api/admin_users.py`, change:
```python
# OLD
from app.modules.scorecard.services.slack_service import SlackService

# NEW
from app.modules.notifications.services.slack_service import SlackService
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/api/auth.py backend/app/core/api/admin_users.py
git commit -m "refactor: update core imports to use notifications module"
```

---

### Task 9: Update tracker imports

**Files:**
- Modify: `app/modules/tracker/api/postponements.py`

- [ ] **Step 1: Update postponements.py**

In `app/modules/tracker/api/postponements.py`, change:
```python
# OLD
from app.modules.scorecard.models.slack import AlertDefinitionDB
from app.modules.scorecard.services.alert_service import AlertService
from app.modules.scorecard.services.slack_service import SlackService

# NEW
from app.modules.notifications.models.slack import AlertDefinitionDB
from app.modules.notifications.services.alert_service import AlertService
from app.modules.notifications.services.slack_service import SlackService
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/modules/tracker/api/postponements.py
git commit -m "refactor: update tracker imports to use notifications module"
```

---

### Task 10: Update worker imports

**Files:**
- Modify: `app/worker/utils.py`
- Modify: `app/worker/check_business_alerts.py`
- Modify: `app/worker/check_dependabot.py`
- Modify: `app/worker/collect_iso_snapshot.py`
- Modify: `app/worker/report_reminder.py`
- Modify: `app/worker/report_confirmation_reminder.py`
- Modify: `app/worker/rotate_reporting_period.py`
- Modify: `app/worker/monthly_scorecard_capture.py`
- Modify: `app/worker/fetch_exchange_rates.py`

- [ ] **Step 1: Update utils.py**

```python
# OLD
from app.modules.scorecard.models.slack import ScheduledJobRunDB
# NEW
from app.modules.notifications.models.slack import ScheduledJobRunDB
```

- [ ] **Step 2: Update check_business_alerts.py**

```python
# OLD
from app.modules.scorecard.models.slack import (...)
from app.modules.scorecard.services.alert_service import AlertService
from app.modules.scorecard.services.slack_service import SlackService
# NEW
from app.modules.notifications.models.slack import (...)
from app.modules.notifications.services.alert_service import AlertService
from app.modules.notifications.services.slack_service import SlackService
```

- [ ] **Step 3: Update check_dependabot.py**

```python
# OLD
from app.modules.scorecard.models.slack import (...)
from app.modules.scorecard.services.alert_service import AlertService
from app.modules.scorecard.services.slack_service import SlackService
# NEW
from app.modules.notifications.models.slack import (...)
from app.modules.notifications.services.alert_service import AlertService
from app.modules.notifications.services.slack_service import SlackService
```

- [ ] **Step 4: Update collect_iso_snapshot.py**

```python
# OLD
from app.modules.scorecard.models.slack import ScheduledJobRunDB
from app.modules.scorecard.services.slack_service import SlackService
# NEW
from app.modules.notifications.models.slack import ScheduledJobRunDB
from app.modules.notifications.services.slack_service import SlackService
```

- [ ] **Step 5: Update report_reminder.py**

```python
# OLD
from app.modules.scorecard.models.slack import ScheduledJobRunDB
from app.modules.scorecard.services.slack_service import SlackService
# NEW
from app.modules.notifications.models.slack import ScheduledJobRunDB
from app.modules.notifications.services.slack_service import SlackService
```

- [ ] **Step 6: Update report_confirmation_reminder.py**

```python
# OLD
from app.modules.scorecard.models.slack import ScheduledJobRunDB
from app.modules.scorecard.services.slack_service import SlackService
# NEW
from app.modules.notifications.models.slack import ScheduledJobRunDB
from app.modules.notifications.services.slack_service import SlackService
```

- [ ] **Step 7: Update rotate_reporting_period.py**

```python
# OLD
from app.modules.scorecard.models.slack import ScheduledJobRunDB
# NEW
from app.modules.notifications.models.slack import ScheduledJobRunDB
```

- [ ] **Step 8: Update monthly_scorecard_capture.py**

```python
# OLD
from app.modules.scorecard.models.slack import ScheduledJobRunDB
# NEW
from app.modules.notifications.models.slack import ScheduledJobRunDB
```

- [ ] **Step 9: Update fetch_exchange_rates.py**

```python
# OLD
from app.modules.scorecard.models.slack import ScheduledJobRunDB
# NEW
from app.modules.notifications.models.slack import ScheduledJobRunDB
```

- [ ] **Step 10: Commit**

```bash
git add backend/app/worker/
git commit -m "refactor: update all worker imports to use notifications module"
```

---

### Task 11: Update scripts

**Files:**
- Modify: `scripts/seed_alert_definitions.py`

- [ ] **Step 1: Update seed_alert_definitions.py**

```python
# OLD
from app.modules.scorecard.models.slack import AlertDefinitionDB, MessageTemplateDB
# NEW
from app.modules.notifications.models.slack import AlertDefinitionDB, MessageTemplateDB
```

- [ ] **Step 2: Commit**

```bash
git add backend/scripts/seed_alert_definitions.py
git commit -m "refactor: update seed script to use notifications module"
```

---

### Task 12: Update test imports

**Files:**
- Modify: `tests/test_slack_service.py`
- Modify: `tests/test_alert_service.py`
- Modify: `tests/test_slack_admin_api.py`
- Modify: `tests/test_notifications_api.py`
- Modify: `tests/test_silences_api.py`
- Modify: `tests/test_slack_models.py`
- Modify: `tests/test_check_business_alerts_job.py`
- Modify: `tests/test_check_dependabot_job.py`
- Modify: `tests/test_iso_cron.py`
- Modify: `tests/test_report_confirmation_reminder_job.py`
- Modify: `tests/test_report_reminder_job.py`
- Modify: `tests/test_rotate_reporting_period_job.py`
- Modify: `tests/test_scheduled_jobs_api.py`

- [ ] **Step 1: Update all test files**

In every test file, replace:
```python
from app.modules.scorecard.models.slack import ...
from app.modules.scorecard.services.slack_service import SlackService
from app.modules.scorecard.services.alert_service import AlertService
```
with:
```python
from app.modules.notifications.models.slack import ...
from app.modules.notifications.services.slack_service import SlackService
from app.modules.notifications.services.alert_service import AlertService
```

Apply to all 13 test files listed above.

**Important:** `tests/test_check_dependabot_job.py` has an additional inline import at line 464 inside a test method:
```python
# OLD (line 464)
from app.modules.scorecard.models.slack import AlertSilenceDB
# NEW
from app.modules.notifications.models.slack import AlertSilenceDB
```
Make sure to update this inline import too, not just the top-level imports.

- [ ] **Step 2: Commit**

```bash
git add backend/tests/
git commit -m "refactor: update all test imports to use notifications module"
```

---

### Task 13: Delete old scorecard notification files

**Files:**
- Delete: `app/modules/scorecard/models/slack.py`
- Delete: `app/modules/scorecard/services/slack_service.py`
- Delete: `app/modules/scorecard/services/alert_service.py`
- Delete: `app/modules/scorecard/api/notifications.py`
- Delete: `app/modules/scorecard/api/slack_admin.py`
- Delete: `app/modules/scorecard/api/silences.py`
- Delete: `app/modules/scorecard/api/scheduled_jobs.py`
- Delete: `app/modules/scorecard/api/schemas/slack.py`

- [ ] **Step 1: Verify no remaining imports reference old paths**

Run: `grep -r "from app.modules.scorecard.*slack\|from app.modules.scorecard.*alert_service\|from app.modules.scorecard.*notification\|from app.modules.scorecard.*silence\|from app.modules.scorecard.*scheduled_job" backend/app/ backend/tests/ backend/scripts/ --include="*.py" | grep -v __pycache__`
Expected: No output (all imports already updated).

- [ ] **Step 2: Delete old files**

```bash
rm backend/app/modules/scorecard/models/slack.py
rm backend/app/modules/scorecard/services/slack_service.py
rm backend/app/modules/scorecard/services/alert_service.py
rm backend/app/modules/scorecard/api/notifications.py
rm backend/app/modules/scorecard/api/slack_admin.py
rm backend/app/modules/scorecard/api/silences.py
rm backend/app/modules/scorecard/api/scheduled_jobs.py
rm backend/app/modules/scorecard/api/schemas/slack.py
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: delete old notification files from scorecard module"
```

---

### Task 14: Run full test suite

- [ ] **Step 1: Run backend tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && pytest -x -q 2>&1 | tail -20 && popd > /dev/null`
Expected: All ~1371 tests pass.

- [ ] **Step 2: Run frontend tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npm test -- --run 2>&1 | tail -20 && popd > /dev/null`
Expected: All ~378 tests pass.

- [ ] **Step 3: Fix any failures**

If any test fails, it will be an import error. Fix the missed import and re-run.

- [ ] **Step 4: Final commit if fixes were needed**

```bash
git add -A
git commit -m "fix: resolve remaining import issues from notifications extraction"
```

---

### Task 15: Update CLAUDE.md project structure

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add notifications module to backend structure**

In the Backend project structure section, add after the `capacity/` module:
```
│   ├── notifications/     # Slack, alerts, templates, scheduled jobs
│   │   ├── api/           # notifications, slack_admin, silences, scheduled_jobs
│   │   ├── models/        # AlertDefinition, MessageTemplate, AlertSilence, AlertNotification, etc.
│   │   ├── services/      # slack_service, alert_service
│   │   └── public.py      # Cross-module interface
```

- [ ] **Step 2: Remove notification references from scorecard description**

Update the scorecard module description to reflect that notification code has moved out.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update project structure for notifications module extraction"
```
