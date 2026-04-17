# DevStack Phase 2 — Catalog Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add featured field, SHA refresh (manual + cron), redesign catalog as card-based UI with search/sort, and add a detail page that renders the skill's markdown content.

**Architecture:** New `featured` boolean column. SHA refresh service called by API endpoint (manual) and ARQ cron (daily). Frontend redesigned from table to card grid following events module pattern. Detail page at `/devstack/:id` fetches raw markdown from GitHub and renders it with `@uiw/react-md-editor`. A `toRawGithubUrl()` utility auto-converts blob URLs to raw URLs.

**Tech Stack:** Python 3.11 (FastAPI, SQLAlchemy, ARQ, httpx), TypeScript (React, TanStack Query, shadcn/ui, @uiw/react-md-editor), PostgreSQL

---

## File Structure

**Create:**
- `backend/alembic/versions/059_devstack_featured.py` — migration
- `backend/app/modules/devstack/services/sha_refresh.py` — refresh all SHAs
- `backend/app/worker/refresh_devstack_shas.py` — ARQ cron task
- `backend/tests/modules/devstack/test_sha_refresh.py` — refresh tests
- `frontend/src/modules/devstack/components/EntryCard.tsx` — card component
- `frontend/src/modules/devstack/pages/EntryDetail.tsx` — detail page with markdown render
- `frontend/src/modules/devstack/utils/github.ts` — `toRawGithubUrl` utility

**Modify:**
- `backend/app/modules/devstack/models/entry.py` — add `featured`
- `backend/app/modules/devstack/schemas.py` — add `featured` to schemas
- `backend/app/modules/devstack/api/entries.py` — search/sort + refresh endpoint
- `backend/app/worker/settings.py` — register cron
- `backend/tests/modules/devstack/test_devstack_api.py` — new tests
- `mcp_server/data/devstack.py` — add `featured` to catalog fields
- `frontend/src/modules/devstack/types/devstack.ts` — update types
- `frontend/src/modules/devstack/services/devstack.ts` — add refreshShas
- `frontend/src/modules/devstack/hooks/useDevstack.ts` — add hooks
- `frontend/src/modules/devstack/pages/Catalog.tsx` — card grid redesign
- `frontend/src/modules/devstack/components/EntryForm.tsx` — featured toggle
- `frontend/src/App.tsx` — add `/devstack/:id` route

---

### Task 1: Featured Field — Migration + Model + Schemas

**Files:**
- Create: `backend/alembic/versions/059_devstack_featured.py`
- Modify: `backend/app/modules/devstack/models/entry.py`
- Modify: `backend/app/modules/devstack/schemas.py`
- Modify: `mcp_server/data/devstack.py`

- [ ] **Step 1: Create migration**

```python
# backend/alembic/versions/059_devstack_featured.py
"""Add featured column to devstack_entries.

Revision ID: 059_devstack_feat
Revises: 058_devstack_sha
"""

from alembic import op

revision = "059_devstack_feat"
down_revision = "058_devstack_sha"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN featured BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries DROP COLUMN IF EXISTS featured"
    )
```

- [ ] **Step 2: Add field to model**

In `backend/app/modules/devstack/models/entry.py`, add after `github_sha`:

```python
    featured: Mapped[bool] = mapped_column(Boolean, server_default="false")
```

- [ ] **Step 3: Add to schemas**

In `backend/app/modules/devstack/schemas.py`:

Add to `EntryCreate` after `active`: `featured: bool = False`

Add to `EntryUpdate` after `active`: `featured: bool | None = None`

Add to `EntryResponse` after `github_sha`: `featured: bool`

- [ ] **Step 4: Add to MCP catalog fields**

In `mcp_server/data/devstack.py`, add `"featured"` to `_CATALOG_FIELDS` tuple.

- [ ] **Step 5: Run tests** — Expected: 23 PASS

- [ ] **Step 6: Commit** — `feat(devstack): add featured field to catalog entries`

---

### Task 2: Backend — Enhanced List with Search + Sort (TDD)

**Files:**
- Modify: `backend/app/modules/devstack/api/entries.py`
- Modify: `backend/tests/modules/devstack/test_devstack_api.py`

- [ ] **Step 1: Write tests for search, sort, featured filter, pagination metadata**

Add `TestSearchAndSort` class to test file with tests for:
- `test_search_by_name` — ilike filter on name
- `test_search_case_insensitive`
- `test_sort_by_name_asc` / `test_sort_by_name_desc`
- `test_response_includes_pagination_metadata` — `page`, `page_size` in response
- `test_featured_filter`

- [ ] **Step 2: Update `list_entries` endpoint**

Add params: `search: str | None`, `featured: bool | None`, `sort_by` (validated: name|type|created_at), `sort_dir` (validated: asc|desc).

Add search filter: `DevstackEntryDB.name.ilike(f"%{search}%")`

Add featured filter: `DevstackEntryDB.featured == featured`

Add dynamic sort: `order_col = getattr(DevstackEntryDB, sort_by, DevstackEntryDB.name)` with `desc()/asc()`.

Update response to include `page` and `page_size`.

- [ ] **Step 3: Run all tests** — Expected: all PASS

- [ ] **Step 4: Commit** — `feat(devstack): add search, sort, featured filter to list endpoint`

---

### Task 3: Backend — SHA Refresh Service + Endpoint (TDD)

**Files:**
- Create: `backend/app/modules/devstack/services/sha_refresh.py`
- Create: `backend/tests/modules/devstack/test_sha_refresh.py`
- Modify: `backend/app/modules/devstack/api/entries.py`

- [ ] **Step 1: Write tests for `refresh_all_shas`**

4 tests: updates changed SHA, skips unchanged, skips npm entries, counts failures.

- [ ] **Step 2: Implement service**

```python
# backend/app/modules/devstack/services/sha_refresh.py
"""Refresh GitHub SHAs for all active devstack catalog entries."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.services.github_sha import fetch_github_sha

logger = structlog.get_logger()


async def refresh_all_shas(db: AsyncSession) -> dict[str, int]:
    """Refresh github_sha for all active github entries.

    Returns: {total, updated, unchanged, failed}.
    """
    result = await db.execute(
        select(DevstackEntryDB).where(
            DevstackEntryDB.active.is_(True),
            DevstackEntryDB.install_method == "github",
            DevstackEntryDB.url.isnot(None),
        )
    )
    entries = result.scalars().all()
    token = await IntegrationTokenService.get_token(db, "github")

    updated = unchanged = failed = 0
    for entry in entries:
        new_sha = await fetch_github_sha(entry.url, token)
        if new_sha is None:
            failed += 1
        elif new_sha != entry.github_sha:
            entry.github_sha = new_sha
            updated += 1
        else:
            unchanged += 1

    if updated > 0:
        await db.commit()

    summary = {"total": len(entries), "updated": updated, "unchanged": unchanged, "failed": failed}
    logger.info("devstack_sha_refresh_completed", **summary)
    return summary
```

- [ ] **Step 3: Add endpoint**

In `entries.py`, add `POST /refresh-shas` (DevstackManager) **before** `/{entry_id}` routes:

```python
@router.post("/refresh-shas")
async def refresh_shas(db: DBSession, user: DevstackManager) -> dict:
    from app.modules.devstack.services.sha_refresh import refresh_all_shas
    return await refresh_all_shas(db)
```

- [ ] **Step 4: Add API test for endpoint**

- [ ] **Step 5: Run all tests** — Expected: all PASS

- [ ] **Step 6: Commit** — `feat(devstack): add SHA refresh service and endpoint`

---

### Task 4: Backend — ARQ Cron Job

**Files:**
- Create: `backend/app/worker/refresh_devstack_shas.py`
- Modify: `backend/app/worker/settings.py`

- [ ] **Step 1: Create worker task**

```python
# backend/app/worker/refresh_devstack_shas.py
"""Daily devstack SHA refresh — cron task."""

import structlog
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devstack.services.sha_refresh import refresh_all_shas

logger = structlog.get_logger()


async def refresh_devstack_shas(ctx: dict) -> dict[str, Any]:
    """Refresh GitHub SHAs for all active devstack entries. Daily at 6 AM UTC."""
    db: AsyncSession = ctx["db"]
    logger.info("devstack_sha_cron_started")
    try:
        result = await refresh_all_shas(db)
        logger.info("devstack_sha_cron_completed", **result)
        return {"status": "completed", **result}
    except Exception as e:
        logger.exception("devstack_sha_cron_failed")
        return {"status": "error", "error": str(e)}
```

- [ ] **Step 2: Register in settings.py**

Add import: `from app.worker.refresh_devstack_shas import refresh_devstack_shas`

Add to `WorkerSettings.functions` list.

Add to `WorkerSettings.cron_jobs`: `cron(refresh_devstack_shas, hour=6, minute=0)`

- [ ] **Step 3: Verify import** — `python -c "from app.worker.refresh_devstack_shas import refresh_devstack_shas; print('OK')"`

- [ ] **Step 4: Commit** — `feat(devstack): add daily cron job for SHA refresh`

---

### Task 5: Frontend — Types, Services, Hooks, and GitHub URL Utility

**Files:**
- Modify: `frontend/src/modules/devstack/types/devstack.ts`
- Modify: `frontend/src/modules/devstack/services/devstack.ts`
- Modify: `frontend/src/modules/devstack/hooks/useDevstack.ts`
- Create: `frontend/src/modules/devstack/utils/github.ts`

- [ ] **Step 1: Update types**

Add to `DevstackEntry`: `featured: boolean`

Add to `DevstackEntryCreate`/`DevstackEntryUpdate`: `featured`

Update `DevstackEntryListResponse`: add `page: number; page_size: number`

Update `DevstackEntryListParams`: add `search?`, `featured?`, `sort_by?`, `sort_dir?`, `page?`, `page_size?`

Add new type:
```typescript
export interface ShaRefreshResult {
  total: number;
  updated: number;
  unchanged: number;
  failed: number;
}
```

- [ ] **Step 2: Update service**

Add `refreshShas` method:
```typescript
refreshShas: async (): Promise<ShaRefreshResult> => {
  const response = await api.post<ShaRefreshResult>('/devstack/refresh-shas');
  return response.data;
},
```

- [ ] **Step 3: Update hooks**

Add `useRefreshShas` mutation hook that invalidates `queryKeys.devstack.all` on success.

- [ ] **Step 4: Create GitHub URL utility**

```typescript
// frontend/src/modules/devstack/utils/github.ts

/**
 * Convert a GitHub blob URL to a raw.githubusercontent.com URL.
 * If already raw or unrecognized, returns the original URL.
 */
export function toRawGithubUrl(url: string): string {
  const blobMatch = url.match(
    /^https?:\/\/github\.com\/([^/]+)\/([^/]+)\/blob\/(.+)$/
  );
  if (blobMatch) {
    const [, owner, repo, refAndPath] = blobMatch;
    return `https://raw.githubusercontent.com/${owner}/${repo}/${refAndPath}`;
  }
  return url;
}
```

- [ ] **Step 5: Type check** — `npx tsc --noEmit`

- [ ] **Step 6: Commit** — `feat(devstack): update frontend types, services, hooks for phase 2`

---

### Task 6: Frontend — EntryCard Component

**Files:**
- Create: `frontend/src/modules/devstack/components/EntryCard.tsx`

- [ ] **Step 1: Create card component**

Card shows: name (line-clamp-2), featured star, type badge, install method badge (Github/Package icon), required badge, description (line-clamp-3), tech tag pills, footer with SHA + external link. Click calls `onClick(id)`.

Follow the `EventCard` pattern: `Card` with `cursor-pointer hover:shadow-md transition-shadow flex flex-col`, `CardHeader` for name + badges, `CardContent` for description + footer.

- [ ] **Step 2: Type check**

- [ ] **Step 3: Commit** — `feat(devstack): add EntryCard component`

---

### Task 7: Frontend — Catalog Page Redesign + EntryForm Featured Toggle

**Files:**
- Modify: `frontend/src/modules/devstack/pages/Catalog.tsx` — full rewrite
- Modify: `frontend/src/modules/devstack/components/EntryForm.tsx` — add featured toggle

- [ ] **Step 1: Rewrite Catalog page**

Follow the events page pattern exactly:
- `useUrlState` with schema: `search`, `type`, `sort` (default `name:asc`)
- Debounced search input (300ms) with Search icon
- Type dropdown filter (`ENTRY_TYPES` + "All types")
- Sort dropdown: Name A-Z/Z-A, Newest/Oldest, Type A-Z
- Card grid: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4`
- Empty state with "Add your first entry" CTA
- Header with "Refresh SHAs" button (spinning RefreshCw icon when pending) + "Add Entry" button
- Card click navigates to `/devstack/${id}` via `useNavigate`
- Remove old table, StatusDot, delete dialog (delete moves to detail page or edit form)

- [ ] **Step 2: Add featured toggle to EntryForm**

Add `featured: boolean` to `FormState` and `INITIAL_FORM`. Add `Switch` in the form alongside Required and Active (change grid to `grid-cols-3`).

- [ ] **Step 3: Type check + browser verify**

- [ ] **Step 4: Commit** — `feat(devstack): redesign catalog as card grid with search, sort, refresh`

---

### Task 8: Frontend — Detail Page with Markdown Rendering

**Files:**
- Create: `frontend/src/modules/devstack/pages/EntryDetail.tsx`
- Modify: `frontend/src/App.tsx` — add route

- [ ] **Step 1: Create detail page**

```typescript
// frontend/src/modules/devstack/pages/EntryDetail.tsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Github, Package, Pencil, Star, Trash2 } from 'lucide-react';
import MDEditor from '@uiw/react-md-editor';
import { usePermission, Action } from '@/core/permissions';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Card, CardContent } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import { useDevstackEntry, useDeleteDevstackEntry } from '../hooks/useDevstack';
import { EntryForm } from '../components/EntryForm';
import { toRawGithubUrl } from '../utils/github';

export default function EntryDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const canManage = usePermission(Action.DEVSTACK_MANAGE);
  const { data: entry, isLoading } = useDevstackEntry(id ?? '');
  const deleteEntry = useDeleteDevstackEntry();

  const [markdown, setMarkdown] = useState<string | null>(null);
  const [mdLoading, setMdLoading] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  useEffect(() => {
    if (!entry?.url || entry.install_method !== 'github') return;
    const rawUrl = toRawGithubUrl(entry.url);
    setMdLoading(true);
    fetch(rawUrl)
      .then((res) => (res.ok ? res.text() : Promise.reject(new Error(`${res.status}`))))
      .then(setMarkdown)
      .catch(() => setMarkdown(null))
      .finally(() => setMdLoading(false));
  }, [entry?.url, entry?.install_method]);

  const handleDelete = (): void => {
    if (!id) return;
    deleteEntry.mutate(id, {
      onSuccess: () => navigate('/devstack'),
    });
  };

  if (isLoading) return <LoadingSpinner />;
  if (!entry) return <p className="text-muted-foreground">Entry not found</p>;

  return (
    <div className="space-y-6">
      {/* Back + actions */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => navigate('/devstack')}>
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          Back to catalog
        </Button>
        {canManage && (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
              <Pencil className="w-4 h-4 mr-1.5" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={() => setDeleteOpen(true)}
            >
              <Trash2 className="w-4 h-4 mr-1.5" />
              Delete
            </Button>
          </div>
        )}
      </div>

      {/* Header card */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-semibold">{entry.name}</h1>
                {entry.featured && (
                  <Star size={18} className="text-amber-500 fill-amber-500" />
                )}
              </div>
              <p className="text-muted-foreground">{entry.description}</p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{entry.type}</Badge>
                <Badge variant="outline">
                  {entry.install_method === 'github' ? (
                    <span className="flex items-center gap-1"><Github size={12} /> github</span>
                  ) : (
                    <span className="flex items-center gap-1"><Package size={12} /> npm</span>
                  )}
                </Badge>
                <Badge variant="outline">{entry.origin}</Badge>
                {entry.required && (
                  <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 hover:bg-blue-100">
                    required
                  </Badge>
                )}
                {!entry.active && (
                  <Badge variant="destructive">inactive</Badge>
                )}
              </div>
              {entry.tech.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {entry.tech.map((t) => (
                    <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>
                  ))}
                </div>
              )}
            </div>
            <div className="text-right text-sm text-muted-foreground space-y-1 shrink-0">
              {entry.github_sha && (
                <p className="font-mono">{entry.github_sha.slice(0, 7)}</p>
              )}
              {entry.url && (
                <a
                  href={entry.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs hover:text-foreground"
                >
                  <ExternalLink size={12} /> Source
                </a>
              )}
              {entry.package && (
                <p className="text-xs">{entry.package}{entry.package_version ? `@${entry.package_version}` : ''}</p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Markdown content */}
      {entry.install_method === 'github' && (
        <Card>
          <CardContent className="pt-6">
            {mdLoading ? (
              <LoadingSpinner />
            ) : markdown ? (
              <div data-color-mode="auto">
                <MDEditor.Markdown source={markdown} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Could not load content from source URL.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Edit form dialog */}
      {editOpen && (
        <EntryForm selectedId={entry.id} onClose={() => setEditOpen(false)} />
      )}

      {/* Delete confirmation */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete entry?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete &quot;{entry.name}&quot; from the catalog.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => { e.preventDefault(); handleDelete(); }}
            >
              {deleteEntry.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
```

- [ ] **Step 2: Add route in App.tsx**

Add import at top: `import EntryDetail from './modules/devstack/pages/EntryDetail';`

Add route right after the existing `/devstack` route (in BOTH admin and regular route blocks):

```typescript
<Route path="/devstack/:id" element={<EntryDetail />} />
```

- [ ] **Step 3: Type check + browser verify**

Verify:
- Click card → navigates to `/devstack/:id`
- Header shows all metadata (name, featured star, badges, tech tags, SHA, source link)
- Markdown renders for github entries
- npm entries show header only (no markdown section)
- Edit button opens form dialog
- Delete button opens confirmation → redirects to `/devstack` on success
- Back button returns to catalog

- [ ] **Step 4: Commit** — `feat(devstack): add detail page with markdown rendering`

---

## Self-Review

**Spec coverage:**
- ✅ Featured field — Task 1
- ✅ Search + sort + pagination — Task 2
- ✅ SHA refresh service + endpoint — Task 3
- ✅ SHA refresh cron — Task 4
- ✅ Frontend types/services/hooks — Task 5
- ✅ Card component — Task 6
- ✅ Catalog redesign — Task 7
- ✅ Detail page with markdown — Task 8
- ✅ URL blob→raw conversion — Task 5 (utility)
- ✅ Featured toggle in form — Task 7
- ✅ Edit/Delete from detail — Task 8
- ✅ Route registration — Task 8

**Note on private repos:** The detail page fetches raw content via `fetch()` from the browser. This works for **public** repos only. For private repos, the fetch will 404 and the page will show "Could not load content." To support private repos, a backend proxy endpoint would be needed (future enhancement). For now, catalog URLs should point to public repos or the raw content URL should be accessible.
