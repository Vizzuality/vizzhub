# DevStack Phase 1.5 — SHA Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GitHub SHA tracking to devstack catalog entries so the MCP sync mechanism can detect when remote files have changed.

**Architecture:** New `github_sha` column on `devstack_entries`, auto-populated by calling the GitHub Contents API on entry create/update. The MCP catalog returns this SHA for clients to compare against local `devstack_sha` frontmatter. For npm entries, `package_version` already serves this purpose — no SHA needed. The GitHub token is read from `IntegrationTokenService` (same token used by the scorecard GitHub collector). If no token is configured, SHA fetching is skipped gracefully.

**Tech Stack:** Python 3.11 (FastAPI, SQLAlchemy, httpx, Alembic), TypeScript (React, TanStack Query), PostgreSQL

**Spec:** `docs/devstack.md` — Phase 1.5 section

---

## File Structure

**Create:**
- `backend/alembic/versions/058_devstack_sha.py` — migration adding `github_sha` column
- `backend/app/modules/devstack/services/github_sha.py` — URL parsing + SHA fetching via GitHub Contents API
- `backend/tests/modules/devstack/test_github_sha.py` — service unit tests

**Modify:**
- `backend/app/modules/devstack/models/entry.py` — add `github_sha` field to model
- `backend/app/modules/devstack/schemas.py` — add `github_sha` to `EntryResponse`
- `backend/app/modules/devstack/api/entries.py` — auto-fetch SHA on create/update
- `backend/tests/modules/devstack/test_devstack_api.py` — API tests for SHA behavior
- `mcp_server/data/devstack.py` — add `github_sha` + `required` to catalog fields
- `mcp_server/tests/test_devstack_tools.py` — verify catalog includes SHA
- `frontend/src/modules/devstack/types/devstack.ts` — add `github_sha` to types
- `frontend/src/modules/devstack/pages/Catalog.tsx` — show SHA column in table

---

### Task 1: Database Migration + Model Update

**Files:**
- Create: `backend/alembic/versions/058_devstack_sha.py`
- Modify: `backend/app/modules/devstack/models/entry.py:36` (after `active` field)

- [ ] **Step 1: Create migration**

```python
# backend/alembic/versions/058_devstack_sha.py
"""Add github_sha column to devstack_entries.

Revision ID: 058_devstack_sha
Revises: 057_devstack
"""

from alembic import op

revision = "058_devstack_sha"
down_revision = "057_devstack"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN github_sha VARCHAR(40)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries DROP COLUMN IF EXISTS github_sha"
    )
```

- [ ] **Step 2: Add field to SQLAlchemy model**

In `backend/app/modules/devstack/models/entry.py`, add after the `active` field (line ~36):

```python
    github_sha: Mapped[str | None] = mapped_column(String(40))
```

- [ ] **Step 3: Verify migration applies**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -c "from app.modules.devstack.models.entry import DevstackEntryDB; print('Model OK:', [c.name for c in DevstackEntryDB.__table__.columns if c.name == 'github_sha'])" && popd > /dev/null`

Expected: `Model OK: ['github_sha']`

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/058_devstack_sha.py backend/app/modules/devstack/models/entry.py
git commit -m "feat(devstack): add github_sha column to devstack_entries"
```

---

### Task 2: GitHub SHA Service (TDD)

**Files:**
- Create: `backend/app/modules/devstack/services/github_sha.py`
- Create: `backend/tests/modules/devstack/test_github_sha.py`

- [ ] **Step 1: Write failing tests for `parse_github_url`**

```python
# backend/tests/modules/devstack/test_github_sha.py
"""Tests for GitHub SHA resolution service."""

import pytest

from app.modules.devstack.services.github_sha import parse_github_url


class TestParseGithubUrl:
    def test_blob_url(self) -> None:
        result = parse_github_url(
            "https://github.com/Vizzuality/devstack/blob/main/skills/finalize.md"
        )
        assert result == ("Vizzuality", "devstack", "main", "skills/finalize.md")

    def test_raw_url(self) -> None:
        result = parse_github_url(
            "https://raw.githubusercontent.com/Vizzuality/devstack/main/org-claude.md"
        )
        assert result == ("Vizzuality", "devstack", "main", "org-claude.md")

    def test_nested_path(self) -> None:
        result = parse_github_url(
            "https://github.com/Vizzuality/devstack/blob/main/deep/nested/file.md"
        )
        assert result == ("Vizzuality", "devstack", "main", "deep/nested/file.md")

    def test_commit_sha_as_ref(self) -> None:
        result = parse_github_url(
            "https://github.com/Vizzuality/devstack/blob/abc123def/file.md"
        )
        assert result == ("Vizzuality", "devstack", "abc123def", "file.md")

    def test_non_github_url_returns_none(self) -> None:
        assert parse_github_url("https://example.com/file.md") is None

    def test_repo_root_url_returns_none(self) -> None:
        assert parse_github_url("https://github.com/Vizzuality/devstack") is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_github_url("") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/devstack/test_github_sha.py -v && popd > /dev/null`

Expected: FAIL with `ModuleNotFoundError` (service module doesn't exist yet)

- [ ] **Step 3: Implement `parse_github_url` and `fetch_github_sha`**

```python
# backend/app/modules/devstack/services/github_sha.py
"""GitHub SHA resolution for devstack catalog entries."""

from __future__ import annotations

import re

import httpx
import structlog

logger = structlog.get_logger()

# Standard GitHub blob URL: github.com/{owner}/{repo}/blob/{ref}/{path}
# Note: refs with '/' (e.g. feature/test) are not supported — first segment is taken as ref.
_BLOB_RE = re.compile(
    r"https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)"
)
# Raw content URL: raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}
_RAW_RE = re.compile(
    r"https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)"
)

GITHUB_API_BASE = "https://api.github.com"


def parse_github_url(url: str) -> tuple[str, str, str, str] | None:
    """Extract (owner, repo, ref, path) from a GitHub file URL.

    Supports:
    - github.com/{owner}/{repo}/blob/{ref}/{path}
    - raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}

    Returns None if the URL format is not recognized.
    """
    for pattern in (_BLOB_RE, _RAW_RE):
        match = pattern.match(url)
        if match:
            return match.group(1), match.group(2), match.group(3), match.group(4)
    return None


async def fetch_github_sha(url: str, token: str | None = None) -> str | None:
    """Fetch the blob SHA of a file from the GitHub Contents API.

    Returns the 40-char hex SHA string, or None on any failure.
    """
    parsed = parse_github_url(url)
    if parsed is None:
        logger.warning("devstack_sha_url_unparseable", url=url)
        return None

    owner, repo, ref, path = parsed
    api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(api_url, headers=headers, params={"ref": ref})
            resp.raise_for_status()
            sha = resp.json().get("sha")
            if sha:
                logger.info("devstack_sha_fetched", url=url, sha=sha[:8])
            return sha
    except httpx.HTTPError as exc:
        logger.warning("devstack_sha_fetch_failed", url=url, error=str(exc))
        return None
```

- [ ] **Step 4: Run URL parsing tests to verify they pass**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/devstack/test_github_sha.py::TestParseGithubUrl -v && popd > /dev/null`

Expected: 7 tests PASS

- [ ] **Step 5: Add fetch test (no HTTP mock — only tests the unparseable-URL path)**

Append to `backend/tests/modules/devstack/test_github_sha.py`:

```python
from app.modules.devstack.services.github_sha import fetch_github_sha


class TestFetchGithubSha:
    @pytest.mark.asyncio
    async def test_returns_none_for_unparseable_url(self) -> None:
        result = await fetch_github_sha("https://example.com/not-github")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_url(self) -> None:
        result = await fetch_github_sha("")
        assert result is None
```

- [ ] **Step 6: Run all service tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/devstack/test_github_sha.py -v && popd > /dev/null`

Expected: 9 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/devstack/services/github_sha.py backend/tests/modules/devstack/test_github_sha.py
git commit -m "feat(devstack): add github SHA service with URL parsing"
```

---

### Task 3: Schema + API Integration (TDD)

**Files:**
- Modify: `backend/app/modules/devstack/schemas.py:43` (EntryResponse class)
- Modify: `backend/app/modules/devstack/api/entries.py:1-10` (imports) and create/update endpoints
- Modify: `backend/tests/modules/devstack/test_devstack_api.py` (add TestGithubSha class)

- [ ] **Step 1: Add `github_sha` to `EntryResponse` schema**

In `backend/app/modules/devstack/schemas.py`, add to the `EntryResponse` class after the `active` field:

```python
    github_sha: str | None = None
```

- [ ] **Step 2: Write failing API tests for SHA auto-fetch**

Append to `backend/tests/modules/devstack/test_devstack_api.py`:

```python
from unittest.mock import AsyncMock, patch


class TestGithubSha:
    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.api.entries.fetch_github_sha",
        new_callable=AsyncMock,
        return_value="a" * 40,
    )
    async def test_create_fetches_sha_for_github_entry(
        self, mock_fetch: AsyncMock, client: AsyncClient,
    ) -> None:
        resp = await client.post(
            "/api/devstack",
            json=_entry_payload(
                url="https://github.com/Vizzuality/devstack/blob/main/skills/test.md",
            ),
        )
        assert resp.status_code == 201
        assert resp.json()["github_sha"] == "a" * 40
        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_npm_entry_has_no_sha(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/devstack",
            json=_entry_payload(
                name="npm-plugin",
                type="plugin",
                install_method="npm",
                package="@vizzuality/test-plugin",
                url=None,
            ),
        )
        assert resp.status_code == 201
        assert resp.json()["github_sha"] is None

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.api.entries.fetch_github_sha",
        new_callable=AsyncMock,
        return_value="b" * 40,
    )
    async def test_update_refetches_sha_when_url_changes(
        self, mock_fetch: AsyncMock, client: AsyncClient,
    ) -> None:
        create_resp = await client.post(
            "/api/devstack",
            json=_entry_payload(
                url="https://github.com/Vizzuality/devstack/blob/main/skills/old.md",
            ),
        )
        entry_id = create_resp.json()["id"]
        mock_fetch.reset_mock()

        resp = await client.put(
            f"/api/devstack/{entry_id}",
            json={"url": "https://github.com/Vizzuality/devstack/blob/main/skills/new.md"},
        )
        assert resp.status_code == 200
        assert resp.json()["github_sha"] == "b" * 40
        mock_fetch.assert_called_once()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/devstack/test_devstack_api.py::TestGithubSha -v && popd > /dev/null`

Expected: FAIL — `fetch_github_sha` not imported in entries.py, SHA not populated.

- [ ] **Step 4: Update `entries.py` — add imports and SHA resolution helper**

Add these imports at the top of `backend/app/modules/devstack/api/entries.py` (after existing imports):

```python
from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.devstack.services.github_sha import fetch_github_sha
```

Add this helper function before the endpoint definitions (after `logger = structlog.get_logger()`):

```python
async def _resolve_github_sha(db: DBSession, entry: DevstackEntryDB) -> None:
    """Auto-fetch and set github_sha for github entries. No-op for npm entries."""
    if entry.install_method != "github" or not entry.url:
        return
    token = await IntegrationTokenService.get_token(db, "github")
    sha = await fetch_github_sha(entry.url, token)
    if sha:
        entry.github_sha = sha
```

Note: `DBSession` here is the annotated type (`Annotated[AsyncSession, Depends(get_db)]`). The helper receives the already-resolved session from the endpoint, so it's typed as `AsyncSession`. Adjust the type hint:

```python
async def _resolve_github_sha(db: AsyncSession, entry: DevstackEntryDB) -> None:
```

And add the import at the top:

```python
from sqlalchemy.ext.asyncio import AsyncSession
```

- [ ] **Step 5: Update `create_entry` endpoint to call SHA resolution**

In the `create_entry` function, add the SHA resolution call **after** `db.add(entry)` and **before** `await db.commit()`:

```python
    entry = DevstackEntryDB(**body.model_dump(), created_by_id=user.user_id)
    db.add(entry)
    await _resolve_github_sha(db, entry)          # ← add this line
    await db.commit()
    await db.refresh(entry)
```

- [ ] **Step 6: Update `update_entry` endpoint to call SHA resolution**

In the `update_entry` function, add the SHA resolution call **after** the field updates loop and **before** `await db.commit()`:

```python
    for field, value in updates.items():
        setattr(entry, field, value)
    entry.updated_by_id = user.user_id
    await _resolve_github_sha(db, entry)          # ← add this line
    await db.commit()
    await db.refresh(entry)
```

- [ ] **Step 7: Run SHA tests to verify they pass**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/devstack/test_devstack_api.py::TestGithubSha -v && popd > /dev/null`

Expected: 3 tests PASS

- [ ] **Step 8: Run ALL devstack API tests to verify no regressions**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/devstack/test_devstack_api.py -v && popd > /dev/null`

Expected: 12 tests PASS (9 existing + 3 new). Existing tests still pass because their URLs (`https://github.com/Vizzuality/devstack/test-skill.md`) don't match the blob/raw pattern, so `parse_github_url` returns None and SHA stays None.

- [ ] **Step 9: Commit**

```bash
git add backend/app/modules/devstack/schemas.py backend/app/modules/devstack/api/entries.py backend/tests/modules/devstack/test_devstack_api.py
git commit -m "feat(devstack): auto-fetch github SHA on entry create/update"
```

---

### Task 4: MCP Catalog Update (TDD)

**Files:**
- Modify: `mcp_server/data/devstack.py:9` (`_CATALOG_FIELDS` tuple)
- Modify: `mcp_server/tests/test_devstack_tools.py:37-48` (active_entry fixture + test assertions)

- [ ] **Step 1: Update `active_entry` fixture to include `github_sha`**

In `mcp_server/tests/test_devstack_tools.py`, update the `active_entry` fixture to include the new field:

```python
@pytest_asyncio.fixture
async def active_entry(db_session: AsyncSession) -> DevstackEntryDB:
    entry = DevstackEntryDB(
        name="org-skill",
        description="Required org-wide Claude Code skill",
        type="skill",
        install_method="github",
        url="https://github.com/vizzuality/skills",
        required=True,
        active=True,
        origin="internal",
        tech=["claude-code"],
        github_sha="a" * 40,
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry
```

- [ ] **Step 2: Write failing test asserting `github_sha` and `required` in catalog response**

In `mcp_server/tests/test_devstack_tools.py`, update the `test_returns_active_entries` test to assert the new fields:

```python
    @pytest.mark.asyncio
    async def test_returns_active_entries(
        self, db_session: AsyncSession, active_entry: DevstackEntryDB,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_get_catalog()

        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "org-skill"
        assert data[0]["github_sha"] == "a" * 40
        assert data[0]["required"] is True
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest ../mcp_server/tests/test_devstack_tools.py::TestGetCatalog::test_returns_active_entries -v && popd > /dev/null`

Expected: FAIL — `github_sha` and `required` not in catalog response (not in `_CATALOG_FIELDS`).

- [ ] **Step 4: Add `github_sha` and `required` to `_CATALOG_FIELDS`**

In `mcp_server/data/devstack.py`, update the tuple:

```python
_CATALOG_FIELDS = (
    "name", "description", "type", "install_method", "url",
    "package", "package_version", "required", "origin", "tech", "github_sha",
)
```

- [ ] **Step 5: Run MCP tests to verify they pass**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest ../mcp_server/tests/test_devstack_tools.py -v && popd > /dev/null`

Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add mcp_server/data/devstack.py mcp_server/tests/test_devstack_tools.py
git commit -m "feat(devstack): return github_sha and required in MCP catalog"
```

---

### Task 5: Frontend Update

**Files:**
- Modify: `frontend/src/modules/devstack/types/devstack.ts:18` (DevstackEntry interface)
- Modify: `frontend/src/modules/devstack/pages/Catalog.tsx` (table columns)

- [ ] **Step 1: Add `github_sha` to TypeScript type**

In `frontend/src/modules/devstack/types/devstack.ts`, add to the `DevstackEntry` interface after the `active` field:

```typescript
  github_sha: string | null;
```

- [ ] **Step 2: Add SHA column to catalog table**

In `frontend/src/modules/devstack/pages/Catalog.tsx`, add a new table header after the "Active" column header:

```typescript
              <TableHead>SHA</TableHead>
```

Add the corresponding table cell after the Active cell, before the actions cell:

```typescript
                <TableCell className="text-sm text-muted-foreground font-mono">
                  {entry.github_sha ? entry.github_sha.slice(0, 7) : '—'}
                </TableCell>
```

- [ ] **Step 3: Run frontend type check**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npx tsc --noEmit && popd > /dev/null`

Expected: No type errors

- [ ] **Step 4: Verify in browser**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npm run dev && popd > /dev/null`

Open `http://localhost:5173/devstack`. Verify:
- SHA column appears in the table
- Existing entries show "—" (no SHA yet)
- Creating a new entry with a valid GitHub blob URL shows a 7-char SHA prefix

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/devstack/types/devstack.ts frontend/src/modules/devstack/pages/Catalog.tsx
git commit -m "feat(devstack): show github SHA column in catalog UI"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Add `github_sha` column → Task 1
- ✅ Auto-fetch SHA from GitHub API on create/edit → Task 3
- ✅ Return `github_sha` in MCP catalog → Task 4
- ✅ Write sync instructions in org CLAUDE.md → **Not included** (out of scope for code implementation — the CLAUDE.md content is authored manually and deployed via Miradore, not generated by code)

**Placeholder scan:** No TBD/TODO/placeholders found.

**Type consistency:** `github_sha` is consistently `str | None` (Python) / `string | null` (TypeScript) across model, schema, MCP, and frontend types. `fetch_github_sha` returns `str | None` everywhere.
