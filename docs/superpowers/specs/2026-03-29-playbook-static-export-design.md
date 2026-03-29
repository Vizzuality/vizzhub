# Playbook Static Export to S3

## Overview

Export public playbook pages as a standalone static website served from `playbook.vizzuality.com`. Admin triggers a full rebuild via a "Publish" button. The site features Vizzuality branding, a collapsible sidebar for navigation, and renders markdown to HTML server-side using Python.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Audience | External (clients, candidates, public) | Requires polished branding |
| Trigger | Manual "Publish" button (admin-only) | Simple, predictable |
| Layout | Collapsible sidebar, no TOC | Familiar docs pattern, lighter than 3-column |
| Branding | Vizzuality corporate (vizzuality.com style) | External audience |
| Domain | `playbook.vizzuality.com` via CloudFront | Professional URL |
| Image URLs | Keep S3 absolute URLs as-is | Already public, no rewrite needed |
| Rebuild strategy | Full rebuild every publish | Low page count, simpler logic |
| Markdown renderer | `markdown-it-py` (Python) | No Node dependency, fast, testable |
| CloudFront | Separate step, optional config | Decouple infra from core feature |

## Architecture

### Flow

```
Admin clicks "Publish"
  → POST /api/playbook/publish (admin-only)
    → Enqueues ARQ job `publish_playbook`
      → PublishService.publish(db):
          1. Query public nodes + latest content
          2. Build navigation tree (public nodes only)
          3. Render markdown → HTML (markdown-it-py)
          4. Apply Jinja2 template (branding, sidebar, content)
          5. Generate index.html + group index pages + 404.html
          6. Upload all to S3 playbook/public/
          7. Clean orphan files via manifest diff
          8. (Optional) Invalidate CloudFront cache
          9. Log result to playbook_publish_log
```

### S3 Structure

```
playbook/public/
├── index.html                    # Redirect to first page
├── 404.html                      # Custom not-found page
├── culture/
│   ├── index.html                # Group: lists children or redirects to first
│   ├── values.html
│   └── growth-framework.html
├── processes/
│   ├── index.html
│   ├── onboarding.html
│   └── incident-response.html
├── assets/
│   ├── style.css
│   └── navigation.js
└── manifest.json
```

- Bucket: configured via `ASSETS_BUCKET_NAME` / `ASSETS_BUCKET_URL` (existing config in `app/config.py`)
- URLs follow slug hierarchy: `playbook.vizzuality.com/culture/values.html`
- Root `index.html` uses `<meta http-equiv="refresh">` to redirect to the first page in the tree
- Groups generate an `index.html` listing their children with links
- `manifest.json` tracks published files for orphan cleanup
- CSS and JS as separate files for browser caching

## Backend

### New Files

| File | Purpose |
|------|---------|
| `modules/playbook/services/publish_service.py` | Core export orchestration |
| `modules/playbook/services/publish_renderer.py` | Markdown → HTML rendering with markdown-it-py |
| `modules/playbook/services/publish_templates/` | Jinja2 templates (page.html, index.html, 404.html) |
| `modules/playbook/api/publish.py` | Publish endpoints |
| `worker/publish_playbook.py` | ARQ job wrapper (registered in `WorkerSettings.functions`) |

### PublishService

```python
class PublishService:
    async def publish(self, db: AsyncSession) -> PublishResult:
        """Full rebuild of static playbook site."""

    async def _query_public_tree(self, db) -> list[PublicNode]:
        """Fetch ALL nodes (pages + groups) with latest content for pages, ordered by position.
        Returns the full tree so _build_nav_tree can include ancestor groups of public pages."""

    def _build_nav_tree(self, nodes: list[PublicNode]) -> NavTree:
        """Build hierarchical navigation from flat node list.
        Include non-public groups that have public descendants."""

    def _render_page(self, node: PublicNode, nav: NavTree) -> str:
        """Render single page: markdown → HTML → Jinja2 template."""

    async def _upload_site(self, files: dict[str, bytes]) -> None:
        """Upload all files to S3 playbook/public/.
        Sets Content-Type per file extension (text/html, text/css, application/javascript, application/json).
        Uses asyncio.to_thread() for boto3 calls to avoid blocking the event loop."""

    async def _cleanup_orphans(self, current_files: set[str]) -> int:
        """Compare with previous manifest, delete removed files.
        On first publish (no existing manifest), cleanup is skipped."""
```

`PublishResult`: `status: str, page_count: int, started_at: datetime, completed_at: datetime, errors: list[str]`

### Group Inclusion Logic

A group node is included in the navigation even if `is_public=False`, as long as it has public descendants. This preserves the tree hierarchy. Groups without any public descendants are excluded entirely.

### Concurrency Guard

`POST /publish` checks `playbook_publish_log` for `status='running'` before enqueueing. Returns 409 Conflict if a publish is already in progress.

### Empty Playbook

If zero public pages exist, the publish fails with a clear error ("No public pages to publish") and the log entry is marked `failed`. No files are uploaded or deleted.

### Path Construction

S3 keys are built by walking from root to node, joining slugs with `/`, and appending `.html`. Example: node with slug `values` under group `culture` → `culture/values.html`. Sibling slug uniqueness is enforced by the DB constraint `(parent_id, slug)`, which guarantees unique paths since the path mirrors the tree structure.

### Markdown Rendering

- Library: `markdown-it-py` with `mdit-py-plugins`
- Plugins: linkify, breaks (equivalent to `remark-breaks`)
- Code highlighting: not included initially (can add `pygments` later if needed)

### API Endpoints

Added to `modules/playbook/api/publish.py`, mounted under `/api/playbook`:

| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /publish` | Admin | Enqueue publish job, returns `{ publish_log_id: UUID }`. Returns 409 if a publish is already running. |
| `GET /publish/status` | Admin | Latest publish log entry: timestamp, status, page_count |

### Database

New table `playbook_publish_log`:

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| status | VARCHAR | `running`, `completed`, `failed` |
| page_count | INTEGER | Pages published |
| started_at | TIMESTAMP | Job start |
| completed_at | TIMESTAMP | nullable, job end |
| error_message | TEXT | nullable, on failure |
| published_by_id | UUID | FK to users.id |

New Alembic migration for `playbook_publish_log` table.

### ARQ Job

```python
async def publish_playbook(ctx, publish_log_id: str):
    """ARQ task: runs PublishService.publish(), updates publish_log."""
```

Follows existing job patterns: log `job_started` / `job_completed` / `job_failed` with structlog.

**Publish lifecycle:**
1. `POST /publish` endpoint creates the `playbook_publish_log` row with `status='running'`, `published_by_id` from authenticated user, `started_at=now()`
2. Endpoint enqueues ARQ job with `publish_log_id`
3. Job runs `PublishService.publish()`, updates the same log row on completion/failure
4. Job configured with `max_tries=1` (no automatic retry) — a failed partial upload is cleaned up by the next successful publish via manifest diff

**Partial failure:** If a publish fails after uploading some files but before writing the manifest, those files become orphans until the next successful publish overwrites them. Acceptable given low volume and manual trigger.

## Frontend

### UI Changes

**Publish button** in playbook header (admin-only):
- Location: alongside existing edit controls in `Playbook.tsx`
- Icon: `Upload` or `Globe` from lucide
- Confirmation dialog before publish

**Publish status:**
- Tooltip or small text below button: "Last published: 2h ago (15 pages)"
- During publish: spinner + "Publishing..."
- On completion: success toast with page count
- On error: error toast

### New Hooks

| Hook | Purpose |
|------|---------|
| `usePublishPlaybook` | Mutation: `POST /publish` |
| `usePublishStatus` | Query: `GET /publish/status`, polls every 3s while `status === 'running'`, stops on `completed`/`failed` (`refetchInterval` conditional) |

### Query Keys

Add to `core/hooks/queryKeys.ts`:
```typescript
playbook: {
  // ...existing keys
  publishStatus: ['playbook', 'publish', 'status'],
}
```

### Service

Add to `modules/playbook/services/playbook.ts`:
```typescript
publishPlaybook(): Promise<{ publish_log_id: string }>
getPublishStatus(): Promise<PublishStatus>
```

### Frontend Types

```typescript
interface PublishStatus {
  status: 'running' | 'completed' | 'failed';
  page_count: number;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}
```

## Template & Branding

### Jinja2 Page Template

Each page is a complete HTML document with:

**Header:**
- Vizzuality logo (inline SVG, extracted from `VizzualityLogo.tsx`)
- "Playbook" title text
- Hamburger toggle for mobile sidebar

**Sidebar (left, collapsible):**
- Tree navigation with groups as collapsible sections
- Current page highlighted
- Collapse/expand state in `localStorage`
- Hidden by default on mobile, toggle via hamburger

**Content (center):**
- Breadcrumb: `Playbook > Group > Page`
- Page title (h1)
- Rendered HTML content
- Prev/Next navigation at bottom (within same group)

**Footer:**
- Minimal: "© Vizzuality" + year

### Branding Reference (from vizzuality.com)

- Primary teal: `#2ba4a0` (from existing `VizzualityLogo.tsx`)
- Font: `DM Sans` via Google Fonts `<link>` in HTML `<head>`
- Light mode only
- Clean, professional, minimal

### Static Assets

- `style.css`: all styles, responsive breakpoints, sidebar animations
- `navigation.js`: sidebar toggle, collapse/expand with localStorage, mobile hamburger
- Both generated during publish and uploaded to `playbook/public/assets/`

### Progressive Enhancement

The site must be functional without JavaScript:
- All content visible
- Sidebar expanded by default (JS collapses on load if state saved)
- Navigation links are standard `<a>` tags

## CloudFront (Deferred)

Not part of initial implementation. When configured later:

- CloudFront distribution with S3 origin path `playbook/public/`
- `playbook.vizzuality.com` CNAME
- ACM certificate for SSL
- Config: `CLOUDFRONT_DISTRIBUTION_ID` env var
- If set, publish job calls `create_invalidation(Paths=["/*"])` after upload
- If not set, publish completes without invalidation

When CloudFront is added, consider whether image URLs should be rewritten to use the CloudFront domain or if CORS headers on the S3 bucket are sufficient.

Terraform additions to `infrastructure/` will be done at that point.

## Dependencies

### Python (new)

- `markdown-it-py` — Markdown parser
- `mdit-py-plugins` — Breaks plugin, linkify
- `Jinja2` — Already in use (FastAPI dependency)

### No new frontend dependencies

## Testing

### Backend

- `publish_renderer`: unit tests for markdown → HTML rendering edge cases
- `publish_service`: integration tests with test DB, mock S3 (moto)
- `publish API`: endpoint tests (auth, job enqueueing)
- Template rendering: snapshot tests for generated HTML structure

### Frontend

- `usePublishPlaybook`: mutation hook test
- `usePublishStatus`: polling behavior test
- Publish button: renders for admin, hidden for non-admin

## Out of Scope

- Code syntax highlighting (can add later with Pygments)
- Search within the static site
- Dark mode on the static site
- Analytics/tracking scripts
- RSS feed
- Sitemap.xml (can add later for SEO)
