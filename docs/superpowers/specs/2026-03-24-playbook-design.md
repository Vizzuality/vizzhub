# Playbook Module - Design Spec

## Overview

Wiki-like module for managing team documentation. Markdown pages organized in a tree menu, with a WYSIWYG editor, content versioning, and public/private visibility. Phase 2 will add static HTML export to S3.

## Decisions

| Decision | Choice |
|----------|--------|
| Who can edit | Any authenticated user |
| Storage | PostgreSQL (DB as source of truth) |
| Tree structure | Unlimited nesting; groups are containers only (no content) |
| Visibility | Per-page `is_public` flag (no inheritance) |
| Versioning | Full history from day 1; reusable service in `core/` |
| Editor | WYSIWYG inline (react-md-editor in WYSIWYG mode) |
| Format support | Headings, bold, italic, lists, links, code inline, images, tables, code blocks with syntax highlight |
| Image storage | S3 with prefix `playbook/uploads/` in existing bucket (Terraform deferred; no uploads until bucket exists) |
| UI layout | Fixed sidebar tree + content area |
| Edit mode | WYSIWYG replaces the view inline (Save/Cancel buttons) |
| Navigation | Sidebar item at top level (same level as Projects, Scorecard) |
| Phase 2 export | Static HTML to S3 (public pages only) |

## Data Model

### playbook_nodes

Tree structure using adjacency list (parent_id).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| title | varchar(255) | |
| slug | varchar(255) | URL-friendly, unique within parent |
| type | enum('page', 'group') | Groups have no content |
| parent_id | UUID, nullable | FK -> playbook_nodes.id, ON DELETE CASCADE |
| position | integer | Sort order within same parent |
| is_public | boolean | Default false, only meaningful for pages |
| created_by_id | UUID | FK -> users.id |
| updated_by_id | UUID | FK -> users.id |
| created_at | timestamp | |
| updated_at | timestamp | |

Constraints:
- Unique: `(parent_id, slug)` — allows same slug under different parents
- ON DELETE CASCADE on parent_id — deleting a group removes its children

### playbook_page_versions

Content versioning. Only pages (not groups) have versions.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| node_id | UUID | FK -> playbook_nodes.id, ON DELETE CASCADE |
| content | text | Markdown content |
| version | integer | Auto-increment per node |
| created_by_id | UUID | FK -> users.id |
| created_at | timestamp | |

The latest version (highest `version` number) is the current content.

## Core Reusable Service

`app/core/services/content_version_service.py`

Generic content versioning that playbook uses now and ISO will reuse later. Operates on any table that follows the version pattern (entity FK + content + version number).

```
class ContentVersionService:
    save_version(db, entity_id, content, user_id) -> version_num
    get_latest(db, entity_id) -> {content, version, created_by, created_at}
    get_version(db, entity_id, version) -> {content, version, created_by, created_at}
    list_versions(db, entity_id) -> [{version, created_by, created_at}]
```

Phase 2 additions: `diff(entity_id, v1, v2)`, `restore(entity_id, version, user_id)`.

The service is parameterized by the SQLAlchemy model class, so each module provides its own version table but shares the logic.

## Module Structure

### Backend: `app/modules/playbook/`

```
api/
  nodes.py          # CRUD tree nodes + reorder
  pages.py          # content read/write + versions
  assets.py         # image upload (S3)
models/
  node.py           # PlaybookNodeDB
  page_version.py   # PlaybookPageVersionDB
schemas/
  node.py           # Create/Update/Response schemas
  page.py           # Content/Version schemas
services/
  tree_service.py   # tree operations, reorder, slug generation
  asset_service.py  # S3 upload with prefix playbook/uploads/
router.py           # aggregates sub-routers
public.py           # cross-module interface
```

### Frontend: `src/modules/playbook/`

```
components/
  PlaybookTree.tsx    # tree nav (react-arborist), drag & drop reorder
  PageEditor.tsx      # WYSIWYG editor (react-md-editor)
  PageViewer.tsx      # rendered markdown view
  NodeForm.tsx        # create/rename dialog for page or group
  VersionHistory.tsx  # version list panel
hooks/
  usePlaybookTree.ts
  usePlaybookPage.ts
  usePlaybookVersions.ts
pages/
  Playbook.tsx        # main layout: sidebar tree + content area
services/
  playbook.ts         # API client
types/
  playbook.ts         # TypeScript interfaces
```

## API Endpoints

All under `/api/playbook`. Require authenticated user.

### Tree

| Method | Path | Description |
|--------|------|-------------|
| GET | /tree | Full tree (nested JSON) |
| POST | /nodes | Create page or group |
| PATCH | /nodes/:id | Rename, toggle is_public, move parent |
| DELETE | /nodes/:id | Delete node (cascades children) |
| PUT | /nodes/reorder | Batch update positions `[{id, parent_id, position}]` |

### Pages

| Method | Path | Description |
|--------|------|-------------|
| GET | /pages/:id | Latest content + metadata |
| PUT | /pages/:id | Save content (creates new version) |
| GET | /pages/:id/versions | Version history list |
| GET | /pages/:id/versions/:v | Specific version content |

### Assets

| Method | Path | Description |
|--------|------|-------------|
| POST | /assets/upload | Image upload -> S3 URL |

## UI Layout

### Main View (Playbook.tsx)

```
+--sidebar(35%)--+--------content(65%)--------+
|                 |  Title          [Edit] [P] |
| Playbook        |  ─────────────────────     |
|                 |                             |
| v Getting Start |  Rendered markdown          |
|   > Welcome     |  content here...            |
|     Setup Guide |                             |
| > Processes     |                             |
| > Engineering   |                             |
|                 |                             |
| [+ Page][+ Grp] |                             |
+-----------------+-----------------------------+
```

- Tree: react-arborist with drag & drop for reorder
- Click page = view (PageViewer)
- `[Edit]` button = switches to PageEditor inline (same area)
- `[P]` = public/private toggle badge
- `[+ Page]` / `[+ Group]` = NodeForm dialog

### Edit Mode

```
+--sidebar(35%)--+--------content(65%)--------+
|                 |  Title        [Save][Cancel]|
| (same tree)     |  [B][I][H1][H2][UL][OL]...|
|                 |  ─────────────────────     |
|                 |                             |
|                 |  WYSIWYG editable area      |
|                 |  with inline formatting     |
|                 |                             |
+-----------------+-----------------------------+
```

Toolbar: bold, italic, headings (H1-H3), bullet list, ordered list, link, image upload, code inline, code block, table.

### Navigation

New sidebar item in AppSidebar at same level as Projects/Scorecard:
- Icon: `BookOpen` (lucide)
- Label: "Playbook"
- Route: `/playbook`
- Visible to all authenticated users

URL structure: `/playbook/:nodeId?` — nodeId in URL selects the page in the tree.

## Frontend Libraries

| Library | Purpose |
|---------|---------|
| `@uiw/react-md-editor` | Markdown WYSIWYG editor with toolbar |
| `react-arborist` | Tree component with drag & drop |

Both are well-maintained, lightweight, and compatible with React 18.

## Permissions

No new RBAC permissions for phase 1 — any authenticated user can read and edit. Endpoints use `CurrentUser` dependency (same pattern as `/tracker/my-report`). The existing `ProtectedRoute` wrapper is sufficient for frontend. Admin-only features (if any) can be added later.

## PATCH /nodes/:id — Updatable Fields

- `title`: yes (slug remains unchanged to preserve URLs)
- `is_public`: yes (toggle)
- `parent_id`: yes (move node to different group)
- `slug`: no (immutable after creation)
- `type`: no (cannot convert page to group or vice versa)
- `position`: no (use `PUT /nodes/reorder` for batch position updates)

## Concurrent Edits

Last-write-wins. Each `PUT /pages/:id` creates a new version regardless. The `PUT` request includes `expected_version` (the version the editor loaded). If `expected_version` < current version, backend still saves but returns `{ conflict: true, current_version: N }` so the frontend can warn: "This page was edited by someone else. Your changes have been saved as the latest version."

## Tree Constraints

- Max depth: 10 levels (backend validates on create/move, returns 400 if exceeded)
- Circular reference prevention: backend validates that new `parent_id` is not a descendant of the node being moved
- Empty state: when tree has no nodes, content area shows "Create your first page" prompt

## Query Keys

Frontend hooks use `queryKeys` from `core/hooks/queryKeys.ts`:

```typescript
playbook: {
  tree: ['playbook', 'tree'] as const,
  page: (id: string) => ['playbook', 'page', id] as const,
  versions: (id: string) => ['playbook', 'versions', id] as const,
  version: (id: string, v: number) => ['playbook', 'version', id, v] as const,
}
```

## Slug Generation

Auto-generated from title on create: `slugify(title)`. If duplicate within same parent, append `-2`, `-3`, etc. Slugs are immutable after creation (renaming title does not change slug) to preserve URLs.

## Tree Reorder

The `PUT /nodes/reorder` endpoint receives the full list of affected nodes with their new `parent_id` and `position`. This handles both reordering within a group and moving nodes between groups in a single request. react-arborist provides the new tree state after drag & drop.

## Delete Behavior

Deleting a group cascades to all children (DB cascade). `DELETE /nodes/:id` returns `{ deleted_count: N }` (node + all descendants). Frontend shows confirmation dialog: "Delete 'Processes' and its 5 pages?" — count fetched from `GET /tree` (frontend already has the full tree in cache).

## Image Upload Flow

1. User clicks image button in toolbar
2. File picker opens
3. Frontend POSTs file to `/api/playbook/assets/upload`
4. Backend uploads to S3 under `playbook/uploads/{uuid}.{ext}`
5. Returns the S3 URL
6. Editor inserts `![](url)` into markdown

Constraints:
- Max file size: 5MB
- Allowed formats: jpg, png, gif, webp
- Backend validates both before uploading to S3

Until the S3 bucket is provisioned, the upload endpoint returns 503 with `{ detail: "Image uploads are not yet available" }`. Frontend checks upload availability on mount via `GET /assets/status` and hides the image button in the toolbar if unavailable.

## Public/Private Scope

In phase 1, `is_public` is a metadata flag stored on the page — it has no effect on access control. All pages require authentication. In phase 2, public pages will be exported as static HTML to S3 for unauthenticated access. The flag exists from day 1 so editors can mark pages as they create them.
