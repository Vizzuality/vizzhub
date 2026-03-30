# ISO Documentation Module — Design Doc

## Overview

Wiki-like module for ISO 27001:2022 / ISO 9001:2015 documentation. Replicates the Playbook's tree navigation, WYSIWYG editing, and version control, adding ISO-specific metadata, filtering, and cross-linking.

## Architecture Decision: Shared Components

Extract common components from Playbook into `shared/` so both Playbook and ISO Docs consume them. Each module customizes via props/slots/composition.

### Components to extract to shared

| Component | Current location | Shared API |
|-----------|-----------------|------------|
| `DocTree` | `playbook/components/PlaybookTree.tsx` | `nodes`, `onReorder`, `onSelect`, `renderNodeExtra?`, `showPublicToggle?` |
| `DocEditor` | `playbook/components/PageEditor.tsx` | `content`, `onSave`, `toolbar?`, `enableImageUpload?` |
| `DocViewer` | `playbook/components/PageViewer.tsx` | `content`, `linkResolver?` |
| `VersionHistoryDialog` | `playbook/components/VersionHistoryDialog.tsx` | `versions`, `onRestore`, `renderMeta?` |
| `NodeForm` | `playbook/components/NodeForm.tsx` | `nodeTypes`, `onSubmit`, `extraFields?` |

### What stays module-specific

**Playbook**: `PublishButton`, asset upload, `is_public` toggle, static site generation.

**ISO Docs**: `MetadataPanel`, clause/category filters, cross-link resolver, bulk import, metadata DB.

## Phase 1 — Backend: Models + API

### Database Models

#### `iso_doc_nodes`

Same structure as `playbook_nodes` minus `is_public`:

```
iso_doc_nodes
├── id (UUID PK)
├── title (String 255)
├── slug (String, unique within parent)
├── type (Enum: page | group)
├── parent_id (FK → self, nullable, CASCADE delete)
├── position (Int)
├── created_by_id (FK → users.id)
├── updated_by_id (FK → users.id)
├── created_at, updated_at (DateTime)
└── Unique(parent_id, slug)
```

#### `iso_doc_versions`

Reuses `ContentVersionService` from `core/services/content_version_service.py`:

```
iso_doc_versions
├── id (UUID PK)
├── node_id (FK → iso_doc_nodes.id, CASCADE)
├── content (Text, markdown)
├── version (Int)
├── created_by_id (FK → users.id)
├── created_at (DateTime)
└── Unique(node_id, version)
```

#### `iso_doc_metadata`

One-to-one with `iso_doc_nodes` (only for type=page):

```
iso_doc_metadata
├── id (UUID PK)
├── node_id (FK → iso_doc_nodes.id, UNIQUE, CASCADE)
├── code (String, nullable — e.g., "POL04", "PR06")
├── standard (ARRAY[String] — ["ISO 27001:2022", "ISO 9001:2015"])
├── clauses (ARRAY[String] — ["A.5.15", "A.5.18", "8.2"])
├── category (Enum: manual | policy | procedure | plan | record | report)
├── doc_version (String — "1.1", distinct from content version)
├── status (Enum: draft | approved | under_review)
├── original_filename (String, nullable)
├── changelog (JSONB — [{version, date, author, description}])
└── created_at, updated_at (DateTime)
```

### API Endpoints

Router: `/api/iso-docs` mounted in `main.py`.

**Tree (same pattern as Playbook)**:
- `GET /tree` — full nested tree
- `POST /nodes` — create page/group
- `PATCH /nodes/{id}` — update title, move parent
- `DELETE /nodes/{id}` — cascade delete
- `PUT /nodes/reorder` — batch reorder

**Pages (same pattern as Playbook)**:
- `GET /pages/{node_id}` — current content + metadata
- `PUT /pages/{node_id}` — save content (new version)
- `GET /pages/{node_id}/versions` — version list with diffs
- `GET /pages/{node_id}/versions/{version}` — specific version

**Metadata (ISO-specific)**:
- `GET /pages/{node_id}/metadata` — get metadata
- `PUT /pages/{node_id}/metadata` — update metadata
- `GET /metadata/search?standard=...&category=...&clause=...` — filter docs

**Import (one-time)**:
- `POST /import` — bulk import from markdown files with frontmatter (admin only)

### Permissions

- Read: any authenticated user (`CurrentUser`)
- Edit: `Action.ISO_DOCS_EDIT` (new permission, assigned to managers + admins)
- Import: admin only

### Services

- `IsoDocTreeService` — reuse Playbook's tree logic (slug gen, position, depth validation, circular check). Consider extracting to `core/services/tree_service.py`.
- `ContentVersionService` — already generic in core, reuse as-is.
- `IsoDocImportService` — parse YAML frontmatter from .md files, create tree structure, populate metadata.

## Phase 2 — Frontend: UI

### Shared component extraction

1. Extract `PlaybookTree` → `shared/components/DocTree`
2. Extract `PageEditor` → `shared/components/DocEditor`
3. Extract `PageViewer` → `shared/components/DocViewer`
4. Extract `VersionHistoryDialog` → `shared/components/VersionHistoryDialog`
5. Extract `NodeForm` → `shared/components/NodeForm`
6. Update Playbook imports to use shared versions
7. Verify Playbook still works identically

### ISO Docs module structure

```
frontend/src/modules/iso-docs/
├── components/
│   ├── MetadataPanel.tsx      — code, standard, clauses, category, status, changelog
│   ├── MetadataFilters.tsx    — sidebar filters by category/standard/clause
│   └── CrossLinkRenderer.tsx  — resolve doc cross-links in viewer
├── hooks/
│   ├── useIsoDocTree.ts
│   ├── useIsoDocPage.ts
│   ├── useIsoDocMetadata.ts
│   ├── useIsoDocVersions.ts
│   └── useIsoDocImport.ts
├── pages/
│   └── IsoDocs.tsx            — main page (sidebar + content)
├── services/
│   └── isoDocs.ts             — API client
└── types/
    └── isoDocs.ts             — TypeScript types
```

### Main page layout

```
┌─────────────────────────────────────────────────┐
│ ISO Documentation                               │
├──────────┬──────────────────────────────────────┤
│ Filters  │                                      │
│ ──────── │  Document Title            [Edit] [⏱]│
│ Category │                                      │
│ Standard │  ┌──────────────────────────────────┐│
│ Status   │  │                                  ││
│          │  │  Markdown content                ││
│ ──────── │  │  with resolved cross-links       ││
│ Tree     │  │                                  ││
│  📁 Man  │  │                                  ││
│  📁 Pol  │  └──────────────────────────────────┘│
│   📄 P02 │                                      │
│   📄 P03 │  ┌──────────────────────────────────┐│
│   📄 P04 │  │ Metadata: POL04 | ISO 27001:2022 ││
│  📁 Proc │  │ Clauses: A.5.15, A.5.18          ││
│   📄 PR1 │  │ Status: ✓ Approved | v1.1        ││
│   📄 PR2 │  │ Changelog: [expand]              ││
│          │  └──────────────────────────────────┘│
└──────────┴──────────────────────────────────────┘
```

## Phase 3 — Cross-links + Polish

### Cross-link resolution

Documents reference each other via relative `.md` links (e.g., `[POL04 - Access Control Policy](pol04-access-control-policy.md)`). The viewer needs to:

1. Intercept markdown links ending in `.md`
2. Look up the target document by filename → node slug
3. Replace with internal navigation link (click navigates to that doc in the sidebar)

Implementation: custom `linkResolver` prop on the shared `DocViewer` component.

### Search

Full-text search across document content + metadata fields. Backend: PostgreSQL `tsvector` or simple `ILIKE` on content + title. Frontend: search input above the tree.

### Import flow

Admin triggers import → backend reads .md files from a configured path (or uploaded ZIP) → parses YAML frontmatter → creates tree (groups from categories, pages from docs) → populates metadata → creates initial version with content.

Tree structure for import:
```
📁 Manual
  📄 Integrated Management System Manual
📁 Policies
  📄 POL02 - Employee Security / Acceptable Use
  📄 POL03 - Information Classification
  ...
📁 Procedures
  📄 PC01 - Information Security Risk Analysis
  📄 PR01 - Access Control
  ...
📁 Plans
  📄 POL07 - Business Continuity Plan
📁 Records
  📄 Equipment Handover Form
  📄 Critical Recovery Test 2025
  ...
```

## Implementation Order

1. **Extract shared components** from Playbook (frontend). Verify Playbook unchanged.
2. **Backend models** + Alembic migration for `iso_doc_nodes`, `iso_doc_versions`, `iso_doc_metadata`.
3. **Extract tree service** to core (backend). Verify Playbook unchanged.
4. **Backend API** — tree CRUD, pages, versions, metadata, import.
5. **Frontend ISO Docs module** — page, hooks, services, types.
6. **ISO-specific components** — MetadataPanel, filters, cross-link resolver.
7. **Bulk import** — load 30 translated docs.
8. **Cross-links** — resolve `.md` references to internal navigation.
9. **Tests** — backend + frontend.
