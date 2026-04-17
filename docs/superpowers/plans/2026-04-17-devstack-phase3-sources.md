# DevStack Phase 3 — Source Tracking (npm versions + claude_plugin) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify SHA (github) and version (npm) tracking in a single cron job, add `claude_plugin` install method for marketplace plugins, validate npm package format.

**Architecture:** Rename `refresh_devstack_shas` → `refresh_devstack_sources`. Extend the refresh service to also fetch npm latest versions. Add `latest_package_version` column for npm detect-but-not-auto-update pattern. Add `claude_plugin` install method (no version tracking — admin-managed).

**Tech Stack:** Python 3.11 (FastAPI, SQLAlchemy, ARQ, httpx), TypeScript (React)

---

## File Structure

**Create:**
- `backend/alembic/versions/060_devstack_npm_latest.py` — migration
- `backend/app/modules/devstack/services/npm_version.py` — fetch npm latest version
- `backend/tests/modules/devstack/test_npm_version.py` — service tests

**Modify:**
- `backend/app/modules/devstack/constants.py` — add `CLAUDE_PLUGIN` to `InstallMethod`
- `backend/app/modules/devstack/models/entry.py` — add `latest_package_version`
- `backend/app/modules/devstack/schemas.py` — add field + npm format validator
- `backend/app/modules/devstack/services/sha_refresh.py` — extend for npm, rename
- `backend/app/worker/refresh_devstack_shas.py` — rename file + function
- `backend/app/worker/settings.py` — update import + cron
- `backend/app/modules/notifications/api/scheduled_jobs.py` — rename in SCHEDULED_JOBS
- `backend/tests/modules/devstack/test_devstack_api.py` — tests for npm validation + claude_plugin
- `backend/tests/modules/devstack/test_sha_refresh.py` — update existing tests + add npm tests
- `backend/tests/test_scheduled_jobs_api.py` — update job name
- `mcp_server/data/devstack.py` — add `latest_package_version` to catalog fields
- `frontend/src/modules/devstack/types/devstack.ts` — add field + install method
- `frontend/src/modules/devstack/components/EntryCard.tsx` — "update available" badge
- `frontend/src/modules/devstack/components/EntryForm.tsx` — claude_plugin option + latest version hint
- `frontend/src/modules/devstack/components/EntryBadges.tsx` — claude_plugin icon

---

### Task 1: Database Migration + Constants

**Files:**
- Create: `backend/alembic/versions/060_devstack_npm_latest.py`
- Modify: `backend/app/modules/devstack/constants.py`
- Modify: `backend/app/modules/devstack/models/entry.py`

- [ ] **Step 1: Create migration**

```python
# backend/alembic/versions/060_devstack_npm_latest.py
"""Add latest_package_version and claude_plugin install method.

Revision ID: 060_devstack_npm
Revises: 059_devstack_feat
"""

from alembic import op

revision = "060_devstack_npm"
down_revision = "059_devstack_feat"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN latest_package_version VARCHAR(50)"
    )
    op.execute("ALTER TABLE devstack_entries DROP CONSTRAINT ck_devstack_entries_install_method")
    op.execute(
        "ALTER TABLE devstack_entries ADD CONSTRAINT ck_devstack_entries_install_method "
        "CHECK (install_method IN ('github', 'npm', 'claude_plugin'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE devstack_entries DROP CONSTRAINT ck_devstack_entries_install_method")
    op.execute(
        "ALTER TABLE devstack_entries ADD CONSTRAINT ck_devstack_entries_install_method "
        "CHECK (install_method IN ('github', 'npm'))"
    )
    op.execute(
        "ALTER TABLE devstack_entries DROP COLUMN IF EXISTS latest_package_version"
    )
```

- [ ] **Step 2: Add CLAUDE_PLUGIN to InstallMethod enum**

In `backend/app/modules/devstack/constants.py`:

```python
class InstallMethod(StrEnum):
    GITHUB = "github"
    NPM = "npm"
    CLAUDE_PLUGIN = "claude_plugin"
```

- [ ] **Step 3: Update model CheckConstraint + add field**

In `backend/app/modules/devstack/models/entry.py`:

Update the install_method check constraint:
```python
        CheckConstraint(
            "install_method IN ('github', 'npm', 'claude_plugin')",
            name="ck_devstack_entries_install_method",
        ),
```

Add `claude_plugin` to the `npm_package` constraint so it doesn't require a package format — actually, `claude_plugin` uses the `package` field too (stores `plugin@marketplace`), so the existing `ck_devstack_entries_npm_package` constraint can be renamed/broadened:

Update to:
```python
        CheckConstraint(
            "install_method != 'npm' OR package IS NOT NULL",
            name="ck_devstack_entries_npm_package",
        ),
        CheckConstraint(
            "install_method != 'claude_plugin' OR package IS NOT NULL",
            name="ck_devstack_entries_claude_plugin_package",
        ),
```

Add the new constraint to the migration too. Update migration step 1 above to add:
```python
    op.execute(
        "ALTER TABLE devstack_entries ADD CONSTRAINT ck_devstack_entries_claude_plugin_package "
        "CHECK (install_method != 'claude_plugin' OR package IS NOT NULL)"
    )
```

And in downgrade:
```python
    op.execute("ALTER TABLE devstack_entries DROP CONSTRAINT ck_devstack_entries_claude_plugin_package")
```

Add the field after `github_sha`:
```python
    latest_package_version: Mapped[str | None] = mapped_column(String(50))
```

- [ ] **Step 4: Run tests** — Expected all PASS

- [ ] **Step 5: Commit** — `feat(devstack): add latest_package_version and claude_plugin method`

---

### Task 2: Schema Validators + API Tests

**Files:**
- Modify: `backend/app/modules/devstack/schemas.py`
- Modify: `backend/tests/modules/devstack/test_devstack_api.py`

- [ ] **Step 1: Add npm format validator + latest_package_version field**

In `schemas.py`:

```python
import re
from pydantic import field_validator

_NPM_PACKAGE_RE = re.compile(r"^(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$")
```

Add to `EntryCreate`:
```python
    @field_validator("package")
    @classmethod
    def validate_npm_package(cls, v: str | None, info) -> str | None:
        if v is None:
            return v
        method = info.data.get("install_method")
        if method == "npm" and not _NPM_PACKAGE_RE.match(v):
            raise ValueError("Invalid npm package name format")
        return v
```

Same validator on `EntryUpdate` (but make it tolerant when `install_method` isn't present).

Add `latest_package_version: str | None = None` to `EntryResponse` after `github_sha`.

- [ ] **Step 2: Write tests for validation + claude_plugin**

```python
class TestInstallMethodValidation:
    @pytest.mark.asyncio
    async def test_rejects_invalid_npm_package(self, client: AsyncClient) -> None:
        resp = await client.post("/api/devstack", json=_entry_payload(
            type="plugin",
            install_method="npm",
            package="superpowers@claude-plugins-official",  # invalid npm format
            url=None,
        ))
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_accepts_scoped_npm_package(self, client: AsyncClient) -> None:
        resp = await client.post("/api/devstack", json=_entry_payload(
            name="valid-npm",
            type="plugin",
            install_method="npm",
            package="@vizzuality/claude-plugin",
            url=None,
        ))
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_accepts_claude_plugin(self, client: AsyncClient) -> None:
        resp = await client.post("/api/devstack", json=_entry_payload(
            name="superpowers",
            type="plugin",
            install_method="claude_plugin",
            package="superpowers@claude-plugins-official",
            url=None,
        ))
        assert resp.status_code == 201
        assert resp.json()["install_method"] == "claude_plugin"

    @pytest.mark.asyncio
    async def test_claude_plugin_requires_package(self, client: AsyncClient) -> None:
        resp = await client.post("/api/devstack", json=_entry_payload(
            type="plugin",
            install_method="claude_plugin",
            package=None,
            url=None,
        ))
        # Either 422 (pydantic) or 500 (db constraint) acceptable
        assert resp.status_code in (422, 500)
```

- [ ] **Step 3: Run tests** — Expected: all PASS

- [ ] **Step 4: Commit** — `feat(devstack): validate npm package format and accept claude_plugin`

---

### Task 3: npm Version Service (TDD)

**Files:**
- Create: `backend/app/modules/devstack/services/npm_version.py`
- Create: `backend/tests/modules/devstack/test_npm_version.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for npm version service."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.modules.devstack.services.npm_version import fetch_npm_latest_version


class TestFetchNpmLatestVersion:
    @pytest.mark.asyncio
    async def test_returns_version_on_success(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"version": "18.3.1"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("app.modules.devstack.services.npm_version.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await fetch_npm_latest_version("react")

        assert result == "18.3.1"

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self) -> None:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPError("Not found")

        with patch("app.modules.devstack.services.npm_version.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await fetch_npm_latest_version("does-not-exist")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_missing_version(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("app.modules.devstack.services.npm_version.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await fetch_npm_latest_version("some-package")

        assert result is None
```

- [ ] **Step 2: Implement service**

```python
"""Fetch latest npm package version from the npm registry."""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger()

NPM_REGISTRY_BASE = "https://registry.npmjs.org"


async def fetch_npm_latest_version(package: str) -> str | None:
    """Fetch the latest published version of an npm package.

    Returns the version string or None if the package doesn't exist or fetch fails.
    """
    url = f"{NPM_REGISTRY_BASE}/{package}/latest"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            version = resp.json().get("version")
            if version:
                logger.info("npm_version_fetched", package=package, version=version)
            return version
    except httpx.HTTPError as exc:
        logger.warning("npm_version_fetch_failed", package=package, error=str(exc))
        return None
```

- [ ] **Step 3: Run tests** — Expected all PASS

- [ ] **Step 4: Commit** — `feat(devstack): add npm version fetch service`

---

### Task 4: Extend Refresh Service + Rename

**Files:**
- Modify: `backend/app/modules/devstack/services/sha_refresh.py` — rename + extend
- Modify: `backend/app/modules/devstack/api/entries.py` — update import
- Modify: `backend/tests/modules/devstack/test_sha_refresh.py` — rename + add npm tests

- [ ] **Step 1: Extend the service**

Rename the JOB_NAME constant and update the tracked function. Keep the existing `refresh_all_shas` for GitHub, add an npm handler:

```python
# backend/app/modules/devstack/services/sha_refresh.py
"""Refresh catalog entry metadata (GitHub SHAs + npm versions)."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.services.github_sha import fetch_github_sha
from app.modules.devstack.services.npm_version import fetch_npm_latest_version
from app.modules.notifications.public import ScheduledJobRunDB

logger = structlog.get_logger()

JOB_NAME = "refresh_devstack_sources"


async def refresh_all_sources(db: AsyncSession) -> dict[str, int]:
    """Refresh github_sha and latest_package_version for all active entries.

    Returns: {total, updated, unchanged, failed}.
    """
    result = await db.execute(
        select(DevstackEntryDB).where(DevstackEntryDB.active.is_(True))
    )
    entries = result.scalars().all()
    github_token = await IntegrationTokenService.get_token(db, "github")

    updated = unchanged = failed = 0
    github_count = 0
    npm_count = 0

    for entry in entries:
        if entry.install_method == "github" and entry.url:
            github_count += 1
            new_sha = await fetch_github_sha(entry.url, github_token)
            if new_sha is None:
                failed += 1
            elif new_sha != entry.github_sha:
                entry.github_sha = new_sha
                updated += 1
            else:
                unchanged += 1
        elif entry.install_method == "npm" and entry.package:
            npm_count += 1
            new_version = await fetch_npm_latest_version(entry.package)
            if new_version is None:
                failed += 1
            elif new_version != entry.latest_package_version:
                entry.latest_package_version = new_version
                updated += 1
            else:
                unchanged += 1
        # claude_plugin entries skipped — no auto-tracking

    if updated > 0:
        await db.commit()

    summary = {
        "total": github_count + npm_count,
        "updated": updated,
        "unchanged": unchanged,
        "failed": failed,
    }
    logger.info("devstack_sources_refresh_completed", **summary)
    return summary


async def refresh_all_sources_tracked(db: AsyncSession) -> dict[str, int]:
    """Run refresh_all_sources and record the run in ScheduledJobRunDB."""
    job_run = ScheduledJobRunDB(job_name=JOB_NAME, status="running")
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)

    try:
        result = await refresh_all_sources(db)
        job_run.status = "completed"
        job_run.completed_at = datetime.now(timezone.utc)
        job_run.projects_checked = result["total"]
        job_run.alerts_sent = result["updated"]
        await db.commit()
        return result
    except Exception as e:
        job_run.status = "error"
        job_run.completed_at = datetime.now(timezone.utc)
        job_run.error_message = str(e)
        await db.commit()
        raise
```

Delete the old `refresh_all_shas` and `refresh_all_shas_tracked` functions (replaced by the new names).

- [ ] **Step 2: Update endpoint import**

In `backend/app/modules/devstack/api/entries.py`:

Change:
```python
from app.modules.devstack.services.sha_refresh import refresh_all_shas_tracked
```
to:
```python
from app.modules.devstack.services.sha_refresh import refresh_all_sources_tracked
```

And in the endpoint:
```python
return await refresh_all_sources_tracked(db)
```

- [ ] **Step 3: Update existing tests**

In `backend/tests/modules/devstack/test_sha_refresh.py`:

Replace `refresh_all_shas` with `refresh_all_sources` in imports and calls. Update patch paths from `app.modules.devstack.services.sha_refresh.fetch_github_sha` (still works).

Add npm tests:

```python
@pytest_asyncio.fixture
async def npm_entry_with_pkg(db_session: AsyncSession) -> DevstackEntryDB:
    entry = DevstackEntryDB(
        name="test-npm",
        description="A test npm package",
        type="plugin",
        install_method="npm",
        package="react",
        required=False,
        active=True,
        origin="external",
        latest_package_version=None,
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


class TestRefreshNpm:
    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_latest_version",
        new_callable=AsyncMock,
        return_value="18.3.1",
    )
    async def test_sets_latest_version(
        self, mock_fetch: AsyncMock, db_session: AsyncSession, npm_entry_with_pkg: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_sources(db_session)
        await db_session.refresh(npm_entry_with_pkg)

        assert npm_entry_with_pkg.latest_package_version == "18.3.1"
        assert result["updated"] == 1

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_latest_version",
        new_callable=AsyncMock,
        return_value=None,
    )
    async def test_counts_npm_failures(
        self, mock_fetch: AsyncMock, db_session: AsyncSession, npm_entry_with_pkg: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_sources(db_session)
        assert result["failed"] == 1
```

- [ ] **Step 4: Run all devstack tests** — Expected all PASS

- [ ] **Step 5: Commit** — `feat(devstack): unify github+npm refresh into refresh_all_sources`

---

### Task 5: Worker Cron Rename

**Files:**
- Rename (delete + create): `backend/app/worker/refresh_devstack_shas.py` → `backend/app/worker/refresh_devstack_sources.py`
- Modify: `backend/app/worker/settings.py`
- Modify: `backend/app/modules/notifications/api/scheduled_jobs.py`
- Modify: `backend/tests/test_scheduled_jobs_api.py`

- [ ] **Step 1: Create new worker file**

```python
# backend/app/worker/refresh_devstack_sources.py
"""Daily devstack source refresh — cron task. Refreshes GitHub SHAs + npm versions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devstack.services.sha_refresh import refresh_all_sources_tracked


async def refresh_devstack_sources(ctx: dict) -> dict:
    """Refresh GitHub SHAs and npm latest versions. Daily at 6 AM UTC."""
    db: AsyncSession = ctx["db"]
    return await refresh_all_sources_tracked(db)
```

- [ ] **Step 2: Delete old worker file**

```bash
rm backend/app/worker/refresh_devstack_shas.py
```

- [ ] **Step 3: Update settings.py**

Replace the import and registration:
```python
from app.worker.refresh_devstack_sources import refresh_devstack_sources  # noqa: E402
```

In `WorkerSettings.functions`, replace `refresh_devstack_shas` with `refresh_devstack_sources`.

In `WorkerSettings.cron_jobs`, replace:
```python
    cron(refresh_devstack_sources, hour=6, minute=0),  # Daily 6 AM UTC — refresh devstack sources
```

- [ ] **Step 4: Update SCHEDULED_JOBS dict**

In `backend/app/modules/notifications/api/scheduled_jobs.py`:

Replace the `refresh_devstack_shas` entry with:
```python
    "refresh_devstack_sources": {
        "name": "refresh_devstack_sources",
        "schedule": "Daily at 6:00 AM UTC",
        "description": "Refreshes GitHub file SHAs and npm latest versions for DevStack catalog entries",
    },
```

- [ ] **Step 5: Update scheduled jobs test**

In `backend/tests/test_scheduled_jobs_api.py`:

Replace:
```python
        assert "refresh_devstack_shas" in job_names
```
with:
```python
        assert "refresh_devstack_sources" in job_names
```

- [ ] **Step 6: Run tests**

Run both backend test suites. Expected: PASS.

- [ ] **Step 7: Commit** — `refactor(devstack): rename cron to refresh_devstack_sources`

---

### Task 6: MCP Catalog Field

**Files:**
- Modify: `mcp_server/data/devstack.py`

- [ ] **Step 1: Add `latest_package_version` to `_CATALOG_FIELDS`**

```python
_CATALOG_FIELDS = frozenset((
    "name", "description", "type", "install_method", "url",
    "package", "package_version", "latest_package_version",
    "required", "origin", "tech", "github_sha", "featured",
))
```

- [ ] **Step 2: Run MCP tests** — Expected PASS

- [ ] **Step 3: Commit** — `feat(devstack): expose latest_package_version in MCP catalog`

---

### Task 7: Frontend — Types + UI Updates

**Files:**
- Modify: `frontend/src/modules/devstack/types/devstack.ts`
- Modify: `frontend/src/modules/devstack/components/EntryBadges.tsx`
- Modify: `frontend/src/modules/devstack/components/EntryCard.tsx`
- Modify: `frontend/src/modules/devstack/components/EntryForm.tsx`
- Modify: `frontend/src/modules/devstack/pages/EntryDetail.tsx`

- [ ] **Step 1: Update types**

In `frontend/src/modules/devstack/types/devstack.ts`:

```typescript
export const INSTALL_METHODS = ['github', 'npm', 'claude_plugin'] as const;
```

Add to `DevstackEntry`:
```typescript
  latest_package_version: string | null;
```

Add to `DevstackEntryCreate`:
```typescript
  latest_package_version?: string | null;  // optional — backend-managed
```

- [ ] **Step 2: Update InstallMethodBadge**

In `EntryBadges.tsx`, add support for `claude_plugin`:

```typescript
import { Github, Package, Puzzle } from 'lucide-react';

// inside the component:
if (method === 'github') return <span><Github size={iconSize} /> github</span>;
if (method === 'npm') return <span><Package size={iconSize} /> npm</span>;
return <span><Puzzle size={iconSize} /> plugin</span>;
```

Adjust the Badge wrapping accordingly.

- [ ] **Step 3: Add "update available" badge to EntryCard**

In `EntryCard.tsx`, after the existing badges:

```typescript
{entry.install_method === 'npm' &&
 entry.latest_package_version &&
 entry.latest_package_version !== entry.package_version && (
  <Badge className="text-xs bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 hover:bg-amber-100">
    update available
  </Badge>
)}
```

- [ ] **Step 4: Update EntryForm**

In `EntryForm.tsx`:

- Add `'claude_plugin'` to the install method Select options
- When `install_method === 'claude_plugin'`, show the package field with placeholder like `plugin-name@marketplace-name`, but NOT the version field
- When `install_method === 'npm'` and `existing.latest_package_version && existing.latest_package_version !== existing.package_version`, show a hint below the version input:

```tsx
{form.install_method === 'npm' && existing?.latest_package_version &&
 existing.latest_package_version !== form.package_version && (
  <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
    Latest on npm: <code className="font-mono">{existing.latest_package_version}</code>{' '}
    <button
      type="button"
      className="underline hover:text-foreground"
      onClick={() => setField('package_version', existing.latest_package_version ?? '')}
    >
      Use latest
    </button>
  </p>
)}
```

- [ ] **Step 5: Update EntryDetail**

In `EntryDetail.tsx`, in the package info section on the right side:

```tsx
{entry.package && (
  <>
    <p className="text-xs">
      {entry.package}
      {entry.package_version ? `@${entry.package_version}` : ''}
    </p>
    {entry.install_method === 'npm' &&
     entry.latest_package_version &&
     entry.latest_package_version !== entry.package_version && (
      <p className="text-xs text-amber-600 dark:text-amber-400">
        Latest: {entry.latest_package_version}
      </p>
    )}
  </>
)}
```

- [ ] **Step 6: Type check + browser verify**

- [ ] **Step 7: Commit** — `feat(devstack): show update-available indicator and support claude_plugin`

---

## Self-Review

**Spec coverage:**
- ✅ npm format validation — Task 2
- ✅ claude_plugin install method — Tasks 1, 2, 7
- ✅ latest_package_version field — Task 1
- ✅ npm registry fetch service — Task 3
- ✅ Unified cron refresh_all_sources — Task 4
- ✅ Worker rename — Task 5
- ✅ MCP exposes new field — Task 6
- ✅ "Update available" indicator — Task 7
- ✅ Form hint with "Use latest" button — Task 7
