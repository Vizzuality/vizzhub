# DevStack Popularity + npm Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add install counters + npm vulnerability/deprecation signals to the DevStack catalog so admins and the sync contract can reason about entry health and adoption.

**Architecture:** Six new columns on `devstack_entries`. `install_count` increments fire-and-log inside `mcp_server/data/devstack.py::get_installable`. The existing daily cron (`refresh_devstack_sources`) fetches deprecation from the npm registry and vulnerabilities from the GitHub Advisory Database. The UI surfaces badges (EntryCard), a security section (EntryDetail), and a new sort option (Catalog).

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Alembic, Pydantic v2, httpx, ARQ worker, React 18 + TanStack Query, shadcn/ui, Vitest.

**Spec:** `docs/superpowers/specs/2026-04-19-devstack-popularity-npm-lifecycle-design.md`

---

## File Structure

**Backend (create):**
- `backend/alembic/versions/061_devstack_install_and_security.py` — schema migration
- `backend/app/modules/devstack/services/npm_security.py` — GitHub Advisory DB fetcher
- `backend/tests/modules/devstack/test_npm_security.py` — tests for the above

**Backend (modify):**
- `backend/app/modules/devstack/models/entry.py` — add 6 columns to `DevstackEntryDB`
- `backend/app/modules/devstack/schemas.py` — extend `EntryResponse`
- `backend/app/modules/devstack/services/npm_version.py` — add `fetch_npm_package_info` that returns version + deprecation together
- `backend/app/modules/devstack/services/sha_refresh.py` — call new services, persist new fields
- `backend/app/modules/devstack/api/entries.py` — extend `sort_by` whitelist to include `install_count`
- `backend/tests/modules/devstack/test_npm_version.py` — tests for deprecation parsing
- `backend/tests/modules/devstack/test_sha_refresh.py` — integration tests for new fields

**MCP (modify):**
- `mcp_server/data/devstack.py` — increment counter in `get_installable`; add new fields to `_CATALOG_FIELDS`
- `mcp_server/tests/test_devstack_tools.py` — tests for counter increment + catalog projection

**Frontend (create):**
- `frontend/src/modules/devstack/components/__tests__/EntryCard.test.tsx` — tests for new badges

**Frontend (modify):**
- `frontend/src/modules/devstack/types/devstack.ts` — extend `DevstackEntry` with 6 new fields
- `frontend/src/modules/devstack/components/EntryCard.tsx` — vulnerability badge, deprecated badge, install count chip
- `frontend/src/modules/devstack/pages/EntryDetail.tsx` — security section, deprecation banner, stats row
- `frontend/src/modules/devstack/pages/Catalog.tsx` — add "Most installed" sort option

---

## Task 1: Add migration + model columns

**Files:**
- Create: `backend/alembic/versions/061_devstack_install_and_security.py`
- Modify: `backend/app/modules/devstack/models/entry.py`

- [ ] **Step 1: Create the Alembic migration**

```python
# backend/alembic/versions/061_devstack_install_and_security.py
"""Add install metrics + npm vulnerability/deprecation columns.

Revision ID: 061_devstack_inst
Revises: 060_devstack_npm
"""

from alembic import op

revision = "061_devstack_inst"
down_revision = "060_devstack_npm"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN install_count INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN last_installed_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN deprecated BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN deprecation_message TEXT"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN vulnerabilities JSONB"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN vulnerabilities_checked_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE devstack_entries DROP COLUMN IF EXISTS vulnerabilities_checked_at")
    op.execute("ALTER TABLE devstack_entries DROP COLUMN IF EXISTS vulnerabilities")
    op.execute("ALTER TABLE devstack_entries DROP COLUMN IF EXISTS deprecation_message")
    op.execute("ALTER TABLE devstack_entries DROP COLUMN IF EXISTS deprecated")
    op.execute("ALTER TABLE devstack_entries DROP COLUMN IF EXISTS last_installed_at")
    op.execute("ALTER TABLE devstack_entries DROP COLUMN IF EXISTS install_count")
```

- [ ] **Step 2: Add the mapped columns to the model**

Add to `backend/app/modules/devstack/models/entry.py`, after the existing `featured` column (line 63):

```python
    install_count: Mapped[int] = mapped_column(
        "install_count", server_default="0"
    )
    last_installed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    deprecated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    deprecation_message: Mapped[str | None] = mapped_column(Text)
    vulnerabilities: Mapped[dict | None] = mapped_column(JSONB)
    vulnerabilities_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
```

Add `Integer` to the SQLAlchemy imports on line 8 if it isn't there already. Check the existing imports — the file already imports `Mapped`, `mapped_column`, `DateTime`, `Boolean`, `Text`, and `JSONB`. For `install_count`, since SQLAlchemy infers `INTEGER` from `Mapped[int]`, no import change is needed.

- [ ] **Step 3: Apply the migration**

```bash
cd backend && alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade 060_devstack_npm -> 061_devstack_inst
```

- [ ] **Step 4: Verify the schema**

```bash
cd backend && python -c "
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as s:
        r = await s.execute(text('SELECT column_name FROM information_schema.columns WHERE table_name = :t'), {'t': 'devstack_entries'})
        cols = {row[0] for row in r.fetchall()}
        for c in ['install_count', 'last_installed_at', 'deprecated', 'deprecation_message', 'vulnerabilities', 'vulnerabilities_checked_at']:
            print(c, 'OK' if c in cols else 'MISSING')

asyncio.run(check())
"
```

Expected: six lines, each ending in `OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/061_devstack_install_and_security.py backend/app/modules/devstack/models/entry.py
git commit -m "feat(devstack): add install metrics + npm lifecycle columns"
```

---

## Task 2: Extend Pydantic EntryResponse

**Files:**
- Modify: `backend/app/modules/devstack/schemas.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/modules/devstack/test_schemas.py`:

```python
"""Tests for devstack Pydantic schemas."""

from datetime import datetime, timezone
from uuid import uuid4

from app.modules.devstack.schemas import EntryResponse


def test_entry_response_includes_new_fields():
    now = datetime.now(timezone.utc)
    response = EntryResponse(
        id=uuid4(),
        name="test",
        description="d",
        type="skill",
        install_method="github",
        required=False,
        origin="internal",
        active=True,
        featured=False,
        install_count=42,
        last_installed_at=now,
        deprecated=True,
        deprecation_message="use other",
        vulnerabilities={
            "critical": 1,
            "high": 0,
            "moderate": 0,
            "low": 0,
            "advisories": [{"id": "GHSA-x", "severity": "critical", "title": "t", "url": "u"}],
        },
        vulnerabilities_checked_at=now,
        created_at=now,
        updated_at=now,
    )

    dumped = response.model_dump()
    assert dumped["install_count"] == 42
    assert dumped["deprecated"] is True
    assert dumped["vulnerabilities"]["critical"] == 1
    assert dumped["vulnerabilities_checked_at"] == now
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/modules/devstack/test_schemas.py -v
```

Expected: FAIL — `ValidationError: Extra inputs are not permitted` or field missing on dump.

- [ ] **Step 3: Extend EntryResponse**

In `backend/app/modules/devstack/schemas.py`, add fields after `featured: bool` (line 83), before `created_by_id`:

```python
    install_count: int = 0
    last_installed_at: datetime | None = None
    deprecated: bool = False
    deprecation_message: str | None = None
    vulnerabilities: dict | None = None
    vulnerabilities_checked_at: datetime | None = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && pytest tests/modules/devstack/test_schemas.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/devstack/schemas.py backend/tests/modules/devstack/test_schemas.py
git commit -m "feat(devstack): expose install + lifecycle fields in EntryResponse"
```

---

## Task 3: Extend npm_version service for deprecation

**Files:**
- Modify: `backend/app/modules/devstack/services/npm_version.py`
- Modify: `backend/tests/modules/devstack/test_npm_version.py`

Goal: add a sibling function `fetch_npm_package_info` that returns both version and deprecation in one call (avoids double-fetching). Keep `fetch_npm_latest_version` untouched for backward compat within this commit.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/modules/devstack/test_npm_version.py`:

```python
import pytest
import httpx

from app.modules.devstack.services.npm_version import fetch_npm_package_info


class MockResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self):
        return self._data


@pytest.mark.asyncio
async def test_fetch_npm_package_info_returns_version_and_deprecation(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return MockResponse(200, {"version": "1.2.3", "deprecated": "use foo@2"})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    info = await fetch_npm_package_info("mypkg")

    assert info == {"version": "1.2.3", "deprecation_message": "use foo@2"}


@pytest.mark.asyncio
async def test_fetch_npm_package_info_no_deprecation(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return MockResponse(200, {"version": "2.0.0"})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    info = await fetch_npm_package_info("mypkg")

    assert info == {"version": "2.0.0", "deprecation_message": None}


@pytest.mark.asyncio
async def test_fetch_npm_package_info_http_error_returns_none(monkeypatch):
    async def fake_get(self, url, **kwargs):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    info = await fetch_npm_package_info("mypkg")

    assert info is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/modules/devstack/test_npm_version.py -v
```

Expected: FAIL on the three new tests — `ImportError: cannot import name 'fetch_npm_package_info'`.

- [ ] **Step 3: Add the new function**

Append to `backend/app/modules/devstack/services/npm_version.py`:

```python
async def fetch_npm_package_info(package: str) -> dict | None:
    """Fetch latest version + deprecation status from the npm registry.

    Returns {'version': str, 'deprecation_message': str | None} or None on failure.
    """
    url = f"{NPM_REGISTRY_BASE}/{package}/latest"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            version = data.get("version")
            if not version:
                return None
            deprecated_field = data.get("deprecated")
            message = deprecated_field if isinstance(deprecated_field, str) else None
            logger.info(
                "npm_package_info_fetched",
                package=package,
                version=version,
                deprecated=bool(message),
            )
            return {"version": version, "deprecation_message": message}
    except httpx.HTTPError as exc:
        logger.warning("npm_package_info_fetch_failed", package=package, error=str(exc))
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/modules/devstack/test_npm_version.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/devstack/services/npm_version.py backend/tests/modules/devstack/test_npm_version.py
git commit -m "feat(devstack): add fetch_npm_package_info with deprecation detection"
```

---

## Task 4: Create npm_security service (GitHub Advisory DB)

**Files:**
- Create: `backend/app/modules/devstack/services/npm_security.py`
- Create: `backend/tests/modules/devstack/test_npm_security.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/modules/devstack/test_npm_security.py`:

```python
"""Tests for npm_security service."""

import pytest
import httpx

from app.modules.devstack.services.npm_security import fetch_npm_advisories


class MockResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("e", request=None, response=None)

    def json(self):
        return self._data


@pytest.mark.asyncio
async def test_fetch_advisories_empty(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return MockResponse(200, [])

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await fetch_npm_advisories("lodash", "4.17.0", token="t")

    assert result == {
        "critical": 0,
        "high": 0,
        "moderate": 0,
        "low": 0,
        "advisories": [],
    }


@pytest.mark.asyncio
async def test_fetch_advisories_counts_by_severity(monkeypatch):
    payload = [
        {"ghsa_id": "GHSA-1", "severity": "critical", "summary": "s1", "html_url": "u1"},
        {"ghsa_id": "GHSA-2", "severity": "high", "summary": "s2", "html_url": "u2"},
        {"ghsa_id": "GHSA-3", "severity": "high", "summary": "s3", "html_url": "u3"},
        {"ghsa_id": "GHSA-4", "severity": "moderate", "summary": "s4", "html_url": "u4"},
    ]

    async def fake_get(self, url, **kwargs):
        return MockResponse(200, payload)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await fetch_npm_advisories("lodash", "4.17.0", token="t")

    assert result["critical"] == 1
    assert result["high"] == 2
    assert result["moderate"] == 1
    assert result["low"] == 0
    assert len(result["advisories"]) == 4
    assert result["advisories"][0] == {
        "id": "GHSA-1",
        "severity": "critical",
        "title": "s1",
        "url": "u1",
    }


@pytest.mark.asyncio
async def test_fetch_advisories_unknown_severity_ignored(monkeypatch):
    payload = [
        {"ghsa_id": "GHSA-X", "severity": "unknown", "summary": "s", "html_url": "u"},
    ]

    async def fake_get(self, url, **kwargs):
        return MockResponse(200, payload)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await fetch_npm_advisories("x", "1.0.0", token="t")

    assert result["critical"] == 0
    assert result["high"] == 0
    assert result["moderate"] == 0
    assert result["low"] == 0
    assert result["advisories"] == [
        {"id": "GHSA-X", "severity": "unknown", "title": "s", "url": "u"}
    ]


@pytest.mark.asyncio
async def test_fetch_advisories_http_error_returns_none(monkeypatch):
    async def fake_get(self, url, **kwargs):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await fetch_npm_advisories("lodash", "4.17.0", token="t")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_advisories_sends_auth_header(monkeypatch):
    captured = {}

    async def fake_get(self, url, **kwargs):
        captured["headers"] = kwargs.get("headers", {})
        captured["params"] = kwargs.get("params", {})
        return MockResponse(200, [])

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    await fetch_npm_advisories("lodash", "4.17.0", token="ghp_test123")

    assert captured["headers"]["Authorization"] == "token ghp_test123"
    assert captured["params"]["ecosystem"] == "npm"
    assert captured["params"]["affects"] == "lodash@4.17.0"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/modules/devstack/test_npm_security.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.devstack.services.npm_security'`.

- [ ] **Step 3: Create the service**

Create `backend/app/modules/devstack/services/npm_security.py`:

```python
"""Fetch npm package vulnerabilities from the GitHub Advisory Database."""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger()

_ADVISORY_URL = "https://api.github.com/advisories"
_SEVERITY_KEYS = ("critical", "high", "moderate", "low")


async def fetch_npm_advisories(
    package: str, version: str, token: str | None
) -> dict | None:
    """Fetch advisories for package@version from the GitHub Advisory DB.

    Returns a dict with per-severity counts and a list of {id, severity, title, url},
    or None on HTTP error.
    """
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    params = {
        "ecosystem": "npm",
        "affects": f"{package}@{version}",
        "per_page": "100",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_ADVISORY_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning(
            "npm_advisories_fetch_failed",
            package=package,
            version=version,
            error=str(exc),
        )
        return None

    summary: dict = {k: 0 for k in _SEVERITY_KEYS}
    advisories: list[dict] = []

    for item in data:
        severity = item.get("severity", "")
        if severity in _SEVERITY_KEYS:
            summary[severity] += 1
        advisories.append(
            {
                "id": item.get("ghsa_id"),
                "severity": severity,
                "title": item.get("summary"),
                "url": item.get("html_url"),
            }
        )

    summary["advisories"] = advisories
    logger.info(
        "npm_advisories_fetched",
        package=package,
        version=version,
        total=len(advisories),
        critical=summary["critical"],
        high=summary["high"],
    )
    return summary
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/modules/devstack/test_npm_security.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/devstack/services/npm_security.py backend/tests/modules/devstack/test_npm_security.py
git commit -m "feat(devstack): fetch npm vulnerabilities from GitHub Advisory DB"
```

---

## Task 5: Integrate new services into sha_refresh cron

**Files:**
- Modify: `backend/app/modules/devstack/services/sha_refresh.py`
- Modify: `backend/tests/modules/devstack/test_sha_refresh.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/modules/devstack/test_sha_refresh.py`:

```python
import pytest
from datetime import datetime, timezone
from sqlalchemy import select

from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.services import sha_refresh


@pytest.mark.asyncio
async def test_refresh_updates_deprecation_and_vulnerabilities(db_session, monkeypatch):
    entry = DevstackEntryDB(
        name="npm-entry",
        description="d",
        type="plugin",
        install_method="npm",
        package="lodash",
        package_version="4.17.0",
        active=True,
        origin="external",
    )
    db_session.add(entry)
    await db_session.commit()

    async def fake_info(pkg):
        return {"version": "4.17.21", "deprecation_message": "use foo"}

    async def fake_advisories(pkg, ver, token):
        return {
            "critical": 1,
            "high": 0,
            "moderate": 0,
            "low": 0,
            "advisories": [
                {"id": "GHSA-a", "severity": "critical", "title": "t", "url": "u"}
            ],
        }

    async def fake_token(db, name):
        return "tok"

    monkeypatch.setattr(
        "app.modules.devstack.services.sha_refresh.fetch_npm_package_info", fake_info
    )
    monkeypatch.setattr(
        "app.modules.devstack.services.sha_refresh.fetch_npm_advisories", fake_advisories
    )
    monkeypatch.setattr(
        "app.core.services.integration_token_service.IntegrationTokenService.get_token",
        fake_token,
    )

    result = await sha_refresh.refresh_all_sources(db_session)
    await db_session.refresh(entry)

    assert result["updated"] >= 1
    assert entry.latest_package_version == "4.17.21"
    assert entry.deprecated is True
    assert entry.deprecation_message == "use foo"
    assert entry.vulnerabilities["critical"] == 1
    assert len(entry.vulnerabilities["advisories"]) == 1
    assert entry.vulnerabilities_checked_at is not None


@pytest.mark.asyncio
async def test_refresh_clears_deprecation_when_unset(db_session, monkeypatch):
    entry = DevstackEntryDB(
        name="npm-entry-2",
        description="d",
        type="plugin",
        install_method="npm",
        package="ok-pkg",
        package_version="1.0.0",
        deprecated=True,
        deprecation_message="old",
        active=True,
        origin="external",
    )
    db_session.add(entry)
    await db_session.commit()

    async def fake_info(pkg):
        return {"version": "1.0.1", "deprecation_message": None}

    async def fake_advisories(pkg, ver, token):
        return {"critical": 0, "high": 0, "moderate": 0, "low": 0, "advisories": []}

    async def fake_token(db, name):
        return "tok"

    monkeypatch.setattr(
        "app.modules.devstack.services.sha_refresh.fetch_npm_package_info", fake_info
    )
    monkeypatch.setattr(
        "app.modules.devstack.services.sha_refresh.fetch_npm_advisories", fake_advisories
    )
    monkeypatch.setattr(
        "app.core.services.integration_token_service.IntegrationTokenService.get_token",
        fake_token,
    )

    await sha_refresh.refresh_all_sources(db_session)
    await db_session.refresh(entry)

    assert entry.deprecated is False
    assert entry.deprecation_message is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/modules/devstack/test_sha_refresh.py -v -k "deprecation or vulnerabilities"
```

Expected: FAIL on both new tests — `deprecation_message` not updated, `vulnerabilities` None.

- [ ] **Step 3: Update sha_refresh**

Replace the npm branch in `backend/app/modules/devstack/services/sha_refresh.py`. Start by updating imports at the top of the file (add `fetch_npm_package_info` and `fetch_npm_advisories`):

```python
from app.modules.devstack.services.github_sha import fetch_github_sha
from app.modules.devstack.services.npm_version import (
    fetch_npm_latest_version,
    fetch_npm_package_info,
)
from app.modules.devstack.services.npm_security import fetch_npm_advisories
```

Replace the `elif entry.install_method == "npm"` block inside `refresh_all_sources` (currently lines 51-60) with:

```python
        elif entry.install_method == "npm" and entry.package:
            processed += 1
            info = await fetch_npm_package_info(entry.package)
            if info is None:
                failed += 1
            else:
                changed = False
                if info["version"] != entry.latest_package_version:
                    entry.latest_package_version = info["version"]
                    changed = True
                new_message = info["deprecation_message"]
                new_deprecated = new_message is not None
                if new_deprecated != entry.deprecated or new_message != entry.deprecation_message:
                    entry.deprecated = new_deprecated
                    entry.deprecation_message = new_message
                    changed = True

                version_to_check = entry.package_version or info["version"]
                advisories = await fetch_npm_advisories(
                    entry.package, version_to_check, github_token
                )
                if advisories is not None:
                    entry.vulnerabilities = advisories
                    entry.vulnerabilities_checked_at = datetime.now(timezone.utc)
                    changed = True

                if changed:
                    updated += 1
                else:
                    unchanged += 1
```

Remove the now-unused `fetch_npm_latest_version` import if no other reference remains (grep the file first; if still referenced in tests, keep the import).

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/modules/devstack/test_sha_refresh.py -v
```

Expected: all tests PASS (new + existing).

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/devstack/services/sha_refresh.py backend/tests/modules/devstack/test_sha_refresh.py
git commit -m "feat(devstack): refresh deprecation + vulnerabilities in daily cron"
```

---

## Task 6: Increment install_count on successful get_installable

**Files:**
- Modify: `mcp_server/data/devstack.py` (add `track_install` helper using `get_write_session`)
- Modify: `mcp_server/tools/devstack.py` (call `track_install` after `get_installable` success)
- Modify: `mcp_server/tests/test_devstack_tools.py`

**Context:** `mcp_server/data/base.py::get_read_session` uses `postgresql_readonly=True`, so UPDATEs fail against that session. The same module exposes `get_write_session()` for writes. Keep `get_installable` read-only; add a sibling `track_install` that opens a write session, and call it from the tool layer after a successful fetch. If the increment fails (DB down, concurrent update), log and swallow — install must not block.

- [ ] **Step 1: Write the failing test**

In `mcp_server/tests/test_devstack_tools.py`, add a new test class after the existing `TestGetInstallable` class:

```python
class TestTrackInstall:
    """Verify track_install bumps install_count + last_installed_at."""

    @pytest.mark.asyncio
    async def test_increments_count_and_sets_timestamp(self, db_session):
        entry = DevstackEntryDB(
            name="incr-test",
            description="d",
            type="skill",
            install_method="github",
            url="https://github.com/a/b/blob/main/x.md",
            github_sha="abc",
            active=True,
            origin="internal",
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)
        entry_id = entry.id

        from mcp_server.data.base import override_session

        async with override_session(db_session):
            await devstack_data.track_install("incr-test")

        # Re-query to avoid stale session cache
        refreshed = await db_session.get(DevstackEntryDB, entry_id)
        await db_session.refresh(refreshed)
        assert refreshed.install_count == 1
        assert refreshed.last_installed_at is not None

    @pytest.mark.asyncio
    async def test_track_install_missing_entry_noop(self, db_session):
        """Silent no-op when entry doesn't exist. Must not raise."""
        from mcp_server.data.base import override_session

        async with override_session(db_session):
            await devstack_data.track_install("does-not-exist")
        # No exception = pass
```

Ensure the test file imports are in place (near the top):

```python
from app.modules.devstack.models.entry import DevstackEntryDB
from mcp_server.data import devstack as devstack_data
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Volumes/Work/Dev/vizzhub && PYTHONPATH=. pytest mcp_server/tests/test_devstack_tools.py::TestTrackInstall -v
```

Expected: FAIL — `AttributeError: module 'mcp_server.data.devstack' has no attribute 'track_install'`.

- [ ] **Step 3: Add `track_install` to the data layer**

In `mcp_server/data/devstack.py`, append:

```python
async def track_install(name: str) -> None:
    """Fire-and-log: bump install_count + last_installed_at for an active entry.

    Opens its own write session. Any DB error is logged and swallowed —
    install must not block on tracking failures.
    """
    from mcp_server.data.base import get_write_session  # noqa: PLC0415 — avoid cycle

    try:
        async with get_write_session() as session:
            await session.execute(
                update(DevstackEntryDB)
                .where(
                    DevstackEntryDB.name == name,
                    DevstackEntryDB.active.is_(True),
                )
                .values(
                    install_count=DevstackEntryDB.install_count + 1,
                    last_installed_at=datetime.now(timezone.utc),
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("devstack_install_counter_failed", name=name, error=str(exc))
```

Add imports at the top of `mcp_server/data/devstack.py` (check existing imports first; `or_` and `select` are already there):

```python
from datetime import datetime, timezone

import structlog
from sqlalchemy import or_, select, update

# existing imports below...

logger = structlog.get_logger()
```

(If a `logger` already exists, reuse it.)

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Volumes/Work/Dev/vizzhub && PYTHONPATH=. pytest mcp_server/tests/test_devstack_tools.py::TestTrackInstall -v
```

Expected: both tests PASS.

- [ ] **Step 5: Wire `track_install` into the MCP tool**

In `mcp_server/tools/devstack.py`, find `devstack_get_installable` (the `@mcp_requires("devstack:view")` handler). After the successful data call, call `track_install`:

```python
@mcp_requires("devstack:view")
async def devstack_get_installable(name: str) -> str:
    try:
        async with get_read_session() as session:
            data = await devstack_data.get_installable(session, name)
    except devstack_data.InstallableError as exc:
        return json.dumps({"error": exc.message, "code": exc.code})

    # Fire-and-log — never blocks the response.
    await devstack_data.track_install(name)

    return json.dumps(data)
```

(The exact surrounding code may differ — preserve the existing structure, just add the `await devstack_data.track_install(name)` call between the successful `get_installable` call and the `return json.dumps(data)`.)

- [ ] **Step 6: Run the full devstack MCP suite**

```bash
cd /Volumes/Work/Dev/vizzhub && PYTHONPATH=. pytest mcp_server/tests/test_devstack_tools.py -v
```

Expected: all tests PASS — existing TestGetInstallable tests still green, new TestTrackInstall tests green.

- [ ] **Step 7: Commit**

```bash
git add mcp_server/data/devstack.py mcp_server/tools/devstack.py mcp_server/tests/test_devstack_tools.py
git commit -m "feat(devstack): track install_count on successful get_installable"
```

---

## Task 7: Extend MCP catalog projection

**Files:**
- Modify: `mcp_server/data/devstack.py`
- Modify: `mcp_server/tests/test_devstack_tools.py`

- [ ] **Step 1: Write the failing test**

Append a new test to the existing `TestGetCatalog` class in `mcp_server/tests/test_devstack_tools.py`:

```python
    @pytest.mark.asyncio
    async def test_catalog_includes_lifecycle_fields(self, mcp_session):
        entry = DevstackEntryDB(
            name="lc-test",
            description="d",
            type="plugin",
            install_method="npm",
            package="lodash",
            package_version="4.17.0",
            active=True,
            origin="external",
            deprecated=True,
            deprecation_message="migrate",
            vulnerabilities={
                "critical": 1, "high": 0, "moderate": 0, "low": 0, "advisories": []
            },
            install_count=7,
        )
        mcp_session.add(entry)
        await mcp_session.commit()

        result = await devstack_data.get_catalog(mcp_session)
        target = next(e for e in result if e["name"] == "lc-test")

        assert target["install_count"] == 7
        assert target["deprecated"] is True
        assert target["deprecation_message"] == "migrate"
        assert target["vulnerabilities"]["critical"] == 1
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Volumes/Work/Dev/vizzhub && PYTHONPATH=. pytest mcp_server/tests/test_devstack_tools.py::TestGetCatalog::test_catalog_includes_lifecycle_fields -v
```

Expected: FAIL — `KeyError: 'install_count'`.

- [ ] **Step 3: Extend `_CATALOG_FIELDS`**

In `mcp_server/data/devstack.py`, update the frozenset at the top:

```python
_CATALOG_FIELDS = frozenset((
    "name", "description", "type", "install_method", "url",
    "package", "package_version", "latest_package_version",
    "required", "origin", "tech", "github_sha", "featured",
    "install_count", "last_installed_at",
    "deprecated", "deprecation_message", "vulnerabilities",
))
```

(`vulnerabilities_checked_at` stays out — it's ops-only metadata.)

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Volumes/Work/Dev/vizzhub && PYTHONPATH=. pytest mcp_server/tests/test_devstack_tools.py::TestGetCatalog -v
```

Expected: all tests in `TestGetCatalog` PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/data/devstack.py mcp_server/tests/test_devstack_tools.py
git commit -m "feat(devstack): include install + lifecycle fields in MCP catalog"
```

---

## Task 8: Allow catalog sort by install_count

**Files:**
- Modify: `backend/app/modules/devstack/api/entries.py`
- Modify: `backend/tests/modules/devstack/test_devstack_api.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/modules/devstack/test_devstack_api.py`:

```python
@pytest.mark.asyncio
async def test_list_entries_sort_by_install_count(admin_client, db_session):
    low = DevstackEntryDB(
        name="lo", description="d", type="skill",
        install_method="github", url="https://github.com/a/b/blob/main/x.md",
        install_count=1, active=True, origin="internal",
    )
    hi = DevstackEntryDB(
        name="hi", description="d", type="skill",
        install_method="github", url="https://github.com/a/b/blob/main/y.md",
        install_count=99, active=True, origin="internal",
    )
    db_session.add_all([low, hi])
    await db_session.commit()

    resp = await admin_client.get(
        "/api/devstack/entries", params={"sort_by": "install_count", "sort_dir": "desc"}
    )

    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()["items"]]
    assert names.index("hi") < names.index("lo")
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && pytest tests/modules/devstack/test_devstack_api.py::test_list_entries_sort_by_install_count -v
```

Expected: FAIL — 422 validation error, since the regex `^(name|type|created_at)$` rejects `install_count`.

- [ ] **Step 3: Extend the sort_by whitelist**

In `backend/app/modules/devstack/api/entries.py`, line 46, change:

```python
        Query(pattern=r"^(name|type|created_at)$"),
```

to:

```python
        Query(pattern=r"^(name|type|created_at|install_count)$"),
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd backend && pytest tests/modules/devstack/test_devstack_api.py::test_list_entries_sort_by_install_count -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/devstack/api/entries.py backend/tests/modules/devstack/test_devstack_api.py
git commit -m "feat(devstack): allow sort_by=install_count in catalog list"
```

---

## Task 9: Extend frontend DevstackEntry type

**Files:**
- Modify: `frontend/src/modules/devstack/types/devstack.ts`

- [ ] **Step 1: Update the interface**

In `frontend/src/modules/devstack/types/devstack.ts`, replace the `DevstackEntry` interface (lines 10-28) with:

```typescript
export interface DevstackAdvisory {
  id: string;
  severity: string;
  title: string;
  url: string;
}

export interface DevstackVulnerabilities {
  critical: number;
  high: number;
  moderate: number;
  low: number;
  advisories: DevstackAdvisory[];
}

export interface DevstackEntry {
  id: string;
  name: string;
  description: string;
  type: EntryType;
  install_method: InstallMethod;
  url: string | null;
  package: string | null;
  package_version: string | null;
  required: boolean;
  origin: EntryOrigin;
  tech: string[];
  active: boolean;
  github_sha: string | null;
  latest_package_version: string | null;
  featured: boolean;
  install_count: number;
  last_installed_at: string | null;
  deprecated: boolean;
  deprecation_message: string | null;
  vulnerabilities: DevstackVulnerabilities | null;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: Run the typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors. If any existing consumer referenced only the old fields, it still compiles (all new fields are additive).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/devstack/types/devstack.ts
git commit -m "feat(devstack): add install + lifecycle fields to frontend types"
```

---

## Task 10: Add badges + install chip to EntryCard

**Files:**
- Modify: `frontend/src/modules/devstack/components/EntryCard.tsx`
- Create: `frontend/src/modules/devstack/components/__tests__/EntryCard.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/modules/devstack/components/__tests__/EntryCard.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { EntryCard } from '../EntryCard';
import type { DevstackEntry } from '../../types/devstack';

function makeEntry(overrides: Partial<DevstackEntry> = {}): DevstackEntry {
  return {
    id: '1',
    name: 'test-entry',
    description: 'desc',
    type: 'skill',
    install_method: 'github',
    url: 'https://github.com/a/b/blob/main/x.md',
    package: null,
    package_version: null,
    required: false,
    origin: 'internal',
    tech: [],
    active: true,
    github_sha: 'abcdef1234567',
    latest_package_version: null,
    featured: false,
    install_count: 0,
    last_installed_at: null,
    deprecated: false,
    deprecation_message: null,
    vulnerabilities: null,
    created_at: '2026-04-19T00:00:00Z',
    updated_at: '2026-04-19T00:00:00Z',
    ...overrides,
  };
}

function renderCard(entry: DevstackEntry) {
  return render(
    <MemoryRouter>
      <EntryCard entry={entry} onClick={vi.fn()} />
    </MemoryRouter>
  );
}

describe('EntryCard badges', () => {
  it('shows critical vulnerability badge when critical > 0', () => {
    renderCard(makeEntry({
      vulnerabilities: { critical: 2, high: 0, moderate: 0, low: 0, advisories: [] },
    }));
    expect(screen.getByText(/2 critical/i)).toBeInTheDocument();
  });

  it('shows high vulnerability badge when high > 0 and no critical', () => {
    renderCard(makeEntry({
      vulnerabilities: { critical: 0, high: 3, moderate: 0, low: 0, advisories: [] },
    }));
    expect(screen.getByText(/3 high/i)).toBeInTheDocument();
  });

  it('shows no vulnerability badge when counts are zero', () => {
    renderCard(makeEntry({
      vulnerabilities: { critical: 0, high: 0, moderate: 0, low: 0, advisories: [] },
    }));
    expect(screen.queryByText(/critical|high/i)).not.toBeInTheDocument();
  });

  it('shows deprecated badge when deprecated is true', () => {
    renderCard(makeEntry({ deprecated: true, deprecation_message: 'use foo' }));
    expect(screen.getByText(/deprecated/i)).toBeInTheDocument();
  });

  it('shows install count chip with count when install_count > 0', () => {
    renderCard(makeEntry({ install_count: 12 }));
    expect(screen.getByTestId('install-chip')).toHaveTextContent('12');
  });

  it('hides install count chip when install_count is 0', () => {
    renderCard(makeEntry({ install_count: 0 }));
    expect(screen.queryByTestId('install-chip')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/modules/devstack/components/__tests__/EntryCard.test.tsx
```

Expected: FAIL — the new badges aren't rendered yet.

- [ ] **Step 3: Update EntryCard**

In `frontend/src/modules/devstack/components/EntryCard.tsx`, replace the file body with:

```tsx
import { ExternalLink, Star, Download } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { InstallMethodBadge } from './EntryBadges';
import type { DevstackEntry } from '../types/devstack';

interface EntryCardProps {
  readonly entry: DevstackEntry;
  readonly onClick: (id: string) => void;
}

export function EntryCard({ entry, onClick }: EntryCardProps): JSX.Element {
  const shaShort = entry.github_sha ? entry.github_sha.slice(0, 7) : null;

  const vulns = entry.vulnerabilities;
  const criticalCount = vulns?.critical ?? 0;
  const highCount = vulns?.high ?? 0;

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow flex flex-col"
      onClick={() => onClick(entry.id)}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-sm leading-tight line-clamp-2">
            {entry.name}
          </h3>
          {entry.featured && (
            <Star size={14} className="shrink-0 text-amber-500 fill-amber-500" />
          )}
        </div>
        <div className="flex flex-wrap gap-1 mt-1">
          <Badge variant="outline" className="text-xs">
            {entry.type}
          </Badge>
          <InstallMethodBadge method={entry.install_method} />
          {entry.required && (
            <Badge className="text-xs bg-blue-600 hover:bg-blue-600 text-white">
              required
            </Badge>
          )}
          {!entry.active && (
            <Badge variant="outline" className="text-xs text-muted-foreground">
              inactive
            </Badge>
          )}
          {entry.install_method === 'npm' &&
           entry.latest_package_version &&
           entry.latest_package_version !== entry.package_version && (
            <Badge className="text-xs bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 hover:bg-amber-100">
              update available
            </Badge>
          )}
          {criticalCount > 0 && (
            <Badge className="text-xs bg-red-600 hover:bg-red-600 text-white">
              {criticalCount} critical
            </Badge>
          )}
          {criticalCount === 0 && highCount > 0 && (
            <Badge className="text-xs bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200 hover:bg-red-100">
              {highCount} high
            </Badge>
          )}
          {entry.deprecated && (
            <Badge className="text-xs bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 hover:bg-amber-100">
              deprecated
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="pt-0 flex-1 flex flex-col justify-between gap-3">
        <div>
          <p className="text-xs text-muted-foreground line-clamp-3 whitespace-pre-line">
            {entry.description}
          </p>
          {entry.tech.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {entry.tech.map((tag) => (
                <Badge key={tag} variant="secondary" className="text-[10px]">
                  {tag}
                </Badge>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between pt-2 border-t">
          <div className="flex items-center gap-2">
            {shaShort && (
              <span className="font-mono text-[10px] text-muted-foreground">
                {shaShort}
              </span>
            )}
            {entry.install_count > 0 && (
              <span
                data-testid="install-chip"
                className="flex items-center gap-0.5 text-[10px] text-muted-foreground"
              >
                <Download size={10} />
                {entry.install_count}
              </span>
            )}
          </div>
          {entry.url && (
            <a
              href={entry.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground px-2 py-1 -mr-2 rounded-md hover:bg-muted transition-colors"
            >
              <ExternalLink size={14} />
            </a>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

The install chip uses `data-testid="install-chip"` so the test can query it unambiguously:

```tsx
{entry.install_count > 0 && (
  <span
    data-testid="install-chip"
    className="flex items-center gap-0.5 text-[10px] text-muted-foreground"
  >
    <Download size={10} />
    {entry.install_count}
  </span>
)}
```

This is already included in the full component body above.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npx vitest run src/modules/devstack/components/__tests__/EntryCard.test.tsx
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/devstack/components/EntryCard.tsx frontend/src/modules/devstack/components/__tests__/EntryCard.test.tsx
git commit -m "feat(devstack): add vuln/deprecated badges + install chip to EntryCard"
```

---

## Task 11: Add security + stats sections to EntryDetail

**Files:**
- Modify: `frontend/src/modules/devstack/pages/EntryDetail.tsx`

- [ ] **Step 1: Add the security/deprecation/stats section**

In `frontend/src/modules/devstack/pages/EntryDetail.tsx`, add a helper at the top of the file (after imports):

```tsx
function formatRelative(iso: string | null): string {
  if (!iso) return 'never';
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}
```

Then, inside the JSX, add three blocks immediately after the closing `</Card>` of the "Header card" (currently `</Card>` on line 155) and before the "Markdown content" comment:

```tsx
      {entry.deprecated && (
        <Card className="border-amber-500/40 bg-amber-50 dark:bg-amber-950/20">
          <CardContent className="pt-6">
            <p className="font-semibold text-amber-900 dark:text-amber-100">
              Deprecated
            </p>
            {entry.deprecation_message && (
              <p className="text-sm text-amber-800 dark:text-amber-200 mt-1">
                {entry.deprecation_message}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {entry.vulnerabilities && entry.vulnerabilities.advisories.length > 0 && (
        <Card className="border-red-500/40">
          <CardContent className="pt-6 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Security advisories</h2>
              <div className="flex gap-2 text-xs">
                {(['critical', 'high', 'moderate', 'low'] as const).map((sev) => {
                  const count = entry.vulnerabilities![sev];
                  if (count === 0) return null;
                  return (
                    <Badge key={sev} variant="outline" className="capitalize">
                      {count} {sev}
                    </Badge>
                  );
                })}
              </div>
            </div>
            <ul className="space-y-2">
              {entry.vulnerabilities.advisories.map((a) => (
                <li key={a.id} className="flex items-start gap-3 text-sm">
                  <Badge
                    variant="outline"
                    className="capitalize shrink-0 mt-0.5"
                  >
                    {a.severity}
                  </Badge>
                  <a
                    href={a.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 hover:underline"
                  >
                    <span className="font-mono text-xs text-muted-foreground mr-2">
                      {a.id}
                    </span>
                    {a.title}
                  </a>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground flex flex-wrap gap-x-6 gap-y-1">
          <span>Installed {entry.install_count} times</span>
          <span>Last install: {formatRelative(entry.last_installed_at)}</span>
        </CardContent>
      </Card>
```

- [ ] **Step 2: Run the typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Manual smoke test**

Run the dev server:
```bash
cd frontend && npm run dev
```

- Open a deprecated npm entry's detail page → see amber banner.
- Open an entry with `vulnerabilities.advisories.length > 0` (if none exist in prod, create one by calling a stale npm package via the manual "Refresh SHAs" button in the catalog, or seed via psql) → see the red-bordered Security advisories section with per-severity counts + list.
- Open any entry → see "Installed N times" + relative last install at the bottom.

If no data exists to trigger the vulnerabilities UI, verify via psql:
```bash
psql "$DATABASE_URL" -c "UPDATE devstack_entries SET vulnerabilities = '{\"critical\":1,\"high\":0,\"moderate\":0,\"low\":0,\"advisories\":[{\"id\":\"GHSA-x\",\"severity\":\"critical\",\"title\":\"Test\",\"url\":\"https://github.com/advisories/GHSA-x\"}]}'::jsonb WHERE name = 'finalize';"
```

Revert after smoke test:
```bash
psql "$DATABASE_URL" -c "UPDATE devstack_entries SET vulnerabilities = NULL WHERE name = 'finalize';"
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/devstack/pages/EntryDetail.tsx
git commit -m "feat(devstack): show security + deprecation + install stats in EntryDetail"
```

---

## Task 12: Add "Most installed" sort option to Catalog

**Files:**
- Modify: `frontend/src/modules/devstack/pages/Catalog.tsx`

- [ ] **Step 1: Extend SORT_OPTIONS**

In `frontend/src/modules/devstack/pages/Catalog.tsx`, replace the `SORT_OPTIONS` array (lines 25-31) with:

```tsx
const SORT_OPTIONS = [
  { value: 'name:asc', label: 'Name A-Z' },
  { value: 'name:desc', label: 'Name Z-A' },
  { value: 'created_at:desc', label: 'Newest first' },
  { value: 'created_at:asc', label: 'Oldest first' },
  { value: 'type:asc', label: 'Type A-Z' },
  { value: 'install_count:desc', label: 'Most installed' },
] as const;
```

- [ ] **Step 2: Run the typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Manual smoke test**

```bash
cd frontend && npm run dev
```

Open `/devstack`, open the Sort dropdown, pick "Most installed". Confirm:
- URL updates to include `?sort=install_count:desc`
- Entries re-order with the highest `install_count` first (or stay visually close if no variance in data)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/devstack/pages/Catalog.tsx
git commit -m "feat(devstack): add Most installed sort to catalog"
```

---

## Final checks

- [ ] **Step 1: Run the full backend suite**

```bash
cd backend && pytest
```

Expected: all tests pass. If any non-devstack test failed, investigate — none of the changes should touch unrelated modules.

- [ ] **Step 2: Run the full frontend suite**

```bash
cd frontend && npm test -- --run
```

Expected: all tests pass.

- [ ] **Step 3: Run the MCP suite**

```bash
cd /Volumes/Work/Dev/vizzhub && PYTHONPATH=. pytest mcp_server/tests/
```

Expected: all tests pass.

- [ ] **Step 4: Visual verification end-to-end**

- `/devstack` catalog loads, sort by "Most installed" works.
- An entry detail page renders stats row at the bottom.
- Seed a test vulnerability (psql), reload the entry detail, confirm Security advisories section, remove the seed.
- Seed a test deprecation (`UPDATE devstack_entries SET deprecated=true, deprecation_message='test' WHERE name='...'`), reload EntryCard in catalog, confirm "deprecated" badge appears, remove seed.

- [ ] **Step 5: Done**

Plan complete. Deploy to dev via the normal flow; the Alembic migration auto-applies on startup.
