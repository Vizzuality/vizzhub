Good. Now I have all the information I need. Here is the complete implementation plan.

---

# ISO Registries -- Complete Implementation Plan

## 1. Requirements Summary

**What**: Add an ISO Registries system to the ISO Docs module. Registries are structured data tables (e.g., "Asset Inventory", "Supplier Register", "KPI Register") where each registry type defines a column schema, and users fill in rows of JSONB data. Some registries are yearly (partitioned by year).

**Why**: ISO compliance requires maintaining ~18 distinct registers/inventories with very different schemas. Currently these live in spreadsheets outside the app.

**Key decisions confirmed**:
- Registries appear as `registry` node type in the existing `iso_doc_nodes` tree
- Each registry node links to a `registry_type_id` that defines its column schema
- Yearly registries use a `year` column on rows with a year selector in UI
- Row editing via dialog (not inline)
- Row ordering via `row_index` column
- Attachments uploaded to S3 `iso-registries/` prefix, linked to rows
- Schema field types: `string`, `number`, `date`, `boolean`, `select`
- Registry type management: UI form with name + column editor
- ~18 initial registry types seeded via script
- Import from Excel deferred to later phase
- Drive export includes attachment hyperlinks (to the app, not S3 direct)

## 2. Approach Chosen

**Option C**: Seed ~18 registry types, allow editors to create new types and modify schemas via UI.

This means:
- `registry_types` table stores the schema as JSONB
- `registry_rows` table stores row data as JSONB validated against the type schema
- `registry_attachments` table links files to rows (and optionally to a specific field)
- The `iso_doc_nodes` enum gets a new `registry` value
- Node creation for type `registry` requires a `registry_type_id`

## 3. Codebase Analysis

**Existing patterns to follow**:
- Tree: `IsoDocNodeDB` with `type` enum (`page`, `group`) -- extend to `registry`
- Tree service: `core/services/tree_service.py` shared with playbook
- Versioning: `core/services/content_version_service.py` (not needed for registries -- rows, not content)
- Permissions: `IsoDocsEditor` for write, `CurrentUser` for read
- S3 uploads: `playbook/services/asset_service.py` pattern (boto3, same bucket)
- API: sub-routers aggregated in `iso_docs/router.py`, mounted at `/api/iso-docs`
- Frontend: `modules/iso-docs/` with hooks, services, types, components, pages
- Query keys: centralized in `core/hooks/queryKeys.ts`
- Alembic: raw SQL, one `op.execute()` per DDL, `create_type=False` on model enums

**Impact areas**:
- `iso_doc_nodes.type` enum needs `registry` value
- Node creation endpoint needs optional `registry_type_id`
- Tree endpoint needs to include `registry_type_id` in response
- Drive export needs to render registries as HTML tables

## 4. Technical Design

### 4.1 Database Schema

#### New Tables

**`registry_types`**
```sql
CREATE TABLE IF NOT EXISTS registry_types (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    is_yearly BOOLEAN NOT NULL DEFAULT false,
    schema JSONB NOT NULL DEFAULT '[]',
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
)
```

`schema` JSONB structure (array of column definitions):
```json
[
  {
    "key": "asset_name",
    "label": "Asset Name",
    "type": "string",
    "required": true,
    "width": 200
  },
  {
    "key": "category",
    "label": "Category",
    "type": "select",
    "options": ["Hardware", "Software", "Network"],
    "required": true,
    "width": 150
  },
  {
    "key": "acquisition_date",
    "label": "Acquisition Date",
    "type": "date",
    "required": false,
    "width": 130
  },
  {
    "key": "is_critical",
    "label": "Critical",
    "type": "boolean",
    "required": false,
    "width": 80
  },
  {
    "key": "value",
    "label": "Value (EUR)",
    "type": "number",
    "required": false,
    "width": 120
  }
]
```

**`registry_rows`**
```sql
CREATE TABLE IF NOT EXISTS registry_rows (
    id UUID PRIMARY KEY,
    node_id UUID NOT NULL REFERENCES iso_doc_nodes(id) ON DELETE CASCADE,
    year INTEGER,
    row_index INTEGER NOT NULL DEFAULT 0,
    data JSONB NOT NULL DEFAULT '{}',
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
)
```

Index: `CREATE INDEX idx_registry_rows_node_year ON registry_rows(node_id, year)`

**`registry_attachments`**
```sql
CREATE TABLE IF NOT EXISTS registry_attachments (
    id UUID PRIMARY KEY,
    row_id UUID NOT NULL REFERENCES registry_rows(id) ON DELETE CASCADE,
    field_key VARCHAR(255),
    filename VARCHAR(500) NOT NULL,
    s3_key VARCHAR(1000) NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    size_bytes INTEGER NOT NULL,
    uploaded_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT now()
)
```

#### Modified Tables

**`iso_doc_nodes`** -- add column:
```sql
ALTER TABLE iso_doc_nodes ADD COLUMN registry_type_id UUID REFERENCES registry_types(id) ON DELETE SET NULL
```

**`iso_doc_node_type`** enum -- add value:
```sql
ALTER TYPE iso_doc_node_type ADD VALUE IF NOT EXISTS 'registry'
```

### 4.2 Backend Models

**`/backend/app/modules/iso_docs/models/registry_type.py`**
```python
class RegistryTypeDB(Base):
    __tablename__ = "registry_types"
    id, name, slug, description, is_yearly, schema (JSONB),
    created_by_id, updated_by_id, created_at, updated_at
```

**`/backend/app/modules/iso_docs/models/registry_row.py`**
```python
class RegistryRowDB(Base):
    __tablename__ = "registry_rows"
    id, node_id (FK iso_doc_nodes), year, row_index, data (JSONB),
    created_by_id, updated_by_id, created_at, updated_at
```

**`/backend/app/modules/iso_docs/models/registry_attachment.py`**
```python
class RegistryAttachmentDB(Base):
    __tablename__ = "registry_attachments"
    id, row_id (FK registry_rows), field_key, filename,
    s3_key, content_type, size_bytes, uploaded_by_id, created_at
```

### 4.3 Backend Schemas (Pydantic)

**`/backend/app/modules/iso_docs/schemas/registry.py`**

```python
# -- Column definition within a type schema --
class ColumnDef(BaseModel):
    key: str = Field(min_length=1, max_length=100, pattern=r'^[a-z][a-z0-9_]*$')
    label: str = Field(min_length=1, max_length=255)
    type: Literal['string', 'number', 'date', 'boolean', 'select']
    required: bool = False
    options: list[str] | None = None  # only for select
    width: int | None = None

# -- Registry type CRUD --
class RegistryTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_yearly: bool = False
    schema_: list[ColumnDef] = Field(alias='schema', min_length=1)

class RegistryTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_yearly: bool | None = None
    schema_: list[ColumnDef] | None = Field(None, alias='schema')

class RegistryTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    description: str | None
    is_yearly: bool
    schema_: list[ColumnDef] = Field(alias='schema')
    created_at: datetime
    updated_at: datetime

# -- Registry row CRUD --
class RegistryRowCreate(BaseModel):
    year: int | None = None
    data: dict[str, Any]

class RegistryRowUpdate(BaseModel):
    data: dict[str, Any]

class RegistryRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    node_id: UUID
    year: int | None
    row_index: int
    data: dict[str, Any]
    created_by_id: UUID | None
    updated_by_id: UUID | None
    created_at: datetime
    updated_at: datetime
    attachments: list[AttachmentResponse] = []

class RegistryRowReorder(BaseModel):
    row_ids: list[UUID]  # ordered list of row IDs

# -- Attachment --
class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    row_id: UUID
    field_key: str | None
    filename: str
    url: str  # computed from s3_key
    content_type: str
    size_bytes: int
    created_at: datetime
```

### 4.4 Backend Services

**`/backend/app/modules/iso_docs/services/registry_service.py`**
- `validate_row_data(schema: list[ColumnDef], data: dict) -> list[str]` -- validates JSONB data against type schema, returns error list
- `get_next_row_index(db, node_id, year) -> int`

**`/backend/app/modules/iso_docs/services/registry_attachment_service.py`**
- `upload_attachment(file_bytes, filename, content_type) -> str` -- uploads to S3 under `iso-registries/` prefix, returns s3_key
- `get_attachment_url(s3_key) -> str` -- constructs URL from bucket settings
- `delete_attachment(s3_key) -> None` -- deletes from S3
- `ALLOWED_CONTENT_TYPES` -- images, PDFs, documents
- `MAX_FILE_SIZE = 10MB`

### 4.5 Backend API Endpoints

All under the existing `/api/iso-docs` prefix.

**Registry Types** -- sub-router `/backend/app/modules/iso_docs/api/registry_types.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/registry-types` | `CurrentUser` | List all registry types |
| `GET` | `/registry-types/{type_id}` | `CurrentUser` | Get registry type with schema |
| `POST` | `/registry-types` | `IsoDocsEditor` | Create registry type |
| `PATCH` | `/registry-types/{type_id}` | `IsoDocsEditor` | Update registry type |
| `DELETE` | `/registry-types/{type_id}` | `IsoDocsEditor` | Delete registry type (only if no nodes use it) |

**Registry Rows** -- sub-router `/backend/app/modules/iso_docs/api/registry_rows.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/registries/{node_id}/rows` | `CurrentUser` | List rows (query param: `year`) |
| `POST` | `/registries/{node_id}/rows` | `IsoDocsEditor` | Create row |
| `PATCH` | `/registries/{node_id}/rows/{row_id}` | `IsoDocsEditor` | Update row |
| `DELETE` | `/registries/{node_id}/rows/{row_id}` | `IsoDocsEditor` | Delete row |
| `PUT` | `/registries/{node_id}/rows/reorder` | `IsoDocsEditor` | Reorder rows |
| `GET` | `/registries/{node_id}/export` | `CurrentUser` | Export as XLSX |

**Registry Attachments** -- sub-router `/backend/app/modules/iso_docs/api/registry_attachments.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/registries/{node_id}/rows/{row_id}/attachments` | `IsoDocsEditor` | Upload attachment (multipart) |
| `DELETE` | `/registries/attachments/{attachment_id}` | `IsoDocsEditor` | Delete attachment |

### 4.6 Modifications to Existing Endpoints

**Node creation** (`POST /iso-docs/nodes`):
- Accept optional `registry_type_id` in `NodeCreate` schema
- When `type=registry`, require `registry_type_id`
- Validate that the referenced registry type exists

**Node schema** (`NodeCreate`, `NodeResponse`):
- Add `registry_type_id: UUID | None` to both

**Tree endpoint** (`GET /iso-docs/tree`):
- Include `registry_type_id` in tree node response

**Drive export** (future enhancement -- not in initial scope, mark as TODO):
- Render registry nodes as HTML tables instead of Google Docs

### 4.7 Frontend Types

**`/frontend/src/modules/iso-docs/types/registry.ts`**

```typescript
export interface ColumnDef {
  key: string;
  label: string;
  type: 'string' | 'number' | 'date' | 'boolean' | 'select';
  required: boolean;
  options?: string[];
  width?: number;
}

export interface RegistryType {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_yearly: boolean;
  schema: ColumnDef[];
  created_at: string;
  updated_at: string;
}

export interface RegistryTypeCreate {
  name: string;
  description?: string | null;
  is_yearly?: boolean;
  schema: ColumnDef[];
}

export interface RegistryTypeUpdate {
  name?: string;
  description?: string | null;
  is_yearly?: boolean;
  schema?: ColumnDef[];
}

export interface RegistryAttachment {
  id: string;
  row_id: string;
  field_key: string | null;
  filename: string;
  url: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface RegistryRow {
  id: string;
  node_id: string;
  year: number | null;
  row_index: number;
  data: Record<string, unknown>;
  created_by_id: string | null;
  updated_by_id: string | null;
  created_at: string;
  updated_at: string;
  attachments: RegistryAttachment[];
}

export interface RegistryRowCreate {
  year?: number | null;
  data: Record<string, unknown>;
}

export interface RegistryRowUpdate {
  data: Record<string, unknown>;
}
```

### 4.8 Frontend Services

**`/frontend/src/modules/iso-docs/services/registries.ts`**

```typescript
export const registriesApi = {
  // Registry types
  listTypes: () => GET<RegistryType[]>('/iso-docs/registry-types'),
  getType: (id: string) => GET<RegistryType>(`/iso-docs/registry-types/${id}`),
  createType: (body: RegistryTypeCreate) => POST<RegistryType>('/iso-docs/registry-types', body),
  updateType: (id: string, body: RegistryTypeUpdate) => PATCH<RegistryType>(`/iso-docs/registry-types/${id}`, body),
  deleteType: (id: string) => DELETE(`/iso-docs/registry-types/${id}`),

  // Registry rows
  listRows: (nodeId: string, year?: number) => GET<RegistryRow[]>(`/iso-docs/registries/${nodeId}/rows`, { params: { year } }),
  createRow: (nodeId: string, body: RegistryRowCreate) => POST<RegistryRow>(`/iso-docs/registries/${nodeId}/rows`, body),
  updateRow: (nodeId: string, rowId: string, body: RegistryRowUpdate) => PATCH<RegistryRow>(`/iso-docs/registries/${nodeId}/rows/${rowId}`, body),
  deleteRow: (nodeId: string, rowId: string) => DELETE(`/iso-docs/registries/${nodeId}/rows/${rowId}`),
  reorderRows: (nodeId: string, rowIds: string[]) => PUT(`/iso-docs/registries/${nodeId}/rows/reorder`, { row_ids: rowIds }),
  exportXlsx: (nodeId: string, year?: number) => GET_BLOB(`/iso-docs/registries/${nodeId}/export`, { params: { year } }),

  // Attachments
  uploadAttachment: (nodeId: string, rowId: string, file: File, fieldKey?: string) => POST_MULTIPART(`/iso-docs/registries/${nodeId}/rows/${rowId}/attachments`, file, fieldKey),
  deleteAttachment: (attachmentId: string) => DELETE(`/iso-docs/registries/attachments/${attachmentId}`),
};
```

### 4.9 Frontend Hooks

**`/frontend/src/modules/iso-docs/hooks/useRegistryTypes.ts`**
- `useRegistryTypes()` -- list all types
- `useRegistryType(id)` -- single type
- `useCreateRegistryType()` -- mutation
- `useUpdateRegistryType()` -- mutation
- `useDeleteRegistryType()` -- mutation

**`/frontend/src/modules/iso-docs/hooks/useRegistryRows.ts`**
- `useRegistryRows(nodeId, year?)` -- list rows
- `useCreateRegistryRow(nodeId)` -- mutation
- `useUpdateRegistryRow(nodeId)` -- mutation
- `useDeleteRegistryRow(nodeId)` -- mutation
- `useReorderRegistryRows(nodeId)` -- mutation
- `useExportRegistry(nodeId)` -- mutation (blob download)

**`/frontend/src/modules/iso-docs/hooks/useRegistryAttachments.ts`**
- `useUploadAttachment(nodeId)` -- mutation
- `useDeleteAttachment()` -- mutation

### 4.10 Frontend Components

**`/frontend/src/modules/iso-docs/components/RegistryView.tsx`** (Complex)
- Main registry view: data table + toolbar
- Year selector (for yearly registries)
- Add row button, export button
- Columns derived from registry type schema
- Row click opens edit dialog
- Drag handle for reordering

**`/frontend/src/modules/iso-docs/components/RegistryRowDialog.tsx`** (Complex)
- Dialog for creating/editing a row
- Dynamic form fields based on schema column types
- String -> Input, Number -> Input type=number, Date -> DatePicker, Boolean -> Switch, Select -> Select dropdown
- Attachment upload area per row (and optionally per field)
- Validation based on `required` flag

**`/frontend/src/modules/iso-docs/components/RegistryTypeDialog.tsx`** (Medium)
- Dialog for creating/editing a registry type
- Name, description, is_yearly toggle
- Column editor: add/remove/reorder columns
- Each column: key (auto-generated from label), label, type, required, options (for select)

**`/frontend/src/modules/iso-docs/components/RegistryColumnEditor.tsx`** (Medium)
- Inline editor for the schema columns in RegistryTypeDialog
- Add column, remove column, drag to reorder
- Type selector shows appropriate sub-fields (options for select)

**`/frontend/src/modules/iso-docs/components/RegistryTypePicker.tsx`** (Simple)
- Shown when creating a `registry` node
- Combobox to pick an existing registry type or create new
- Links to RegistryTypeDialog for creating new

### 4.11 Modifications to Existing Frontend

**`IsoDocs.tsx`**:
- When selected node is type `registry`, show `RegistryView` instead of `DocViewer`/`DocEditor`
- Node creation form: when type `registry` is selected, show `RegistryTypePicker`

**`DocTree.tsx` / `NodeForm.tsx`** (shared):
- Add `registry` as a valid node type option (with a Table icon)
- Show registry type name as subtitle in tree

**`isoDocs.ts` (types)**:
- Add `registry_type_id?: string | null` to `IsoDocNode`, `NodeCreateRequest`
- Add `registry` to node type union

**`queryKeys.ts`**:
- Add registry keys

## 5. File Changes

### New Files

| File | Complexity | Description |
|------|-----------|-------------|
| `backend/alembic/versions/042_create_registries.py` | Medium | Migration: new tables + enum value |
| `backend/app/modules/iso_docs/models/registry_type.py` | Simple | RegistryTypeDB model |
| `backend/app/modules/iso_docs/models/registry_row.py` | Simple | RegistryRowDB model |
| `backend/app/modules/iso_docs/models/registry_attachment.py` | Simple | RegistryAttachmentDB model |
| `backend/app/modules/iso_docs/schemas/registry.py` | Medium | All Pydantic schemas for registries |
| `backend/app/modules/iso_docs/services/registry_service.py` | Medium | Row validation, helpers |
| `backend/app/modules/iso_docs/services/registry_attachment_service.py` | Medium | S3 upload/delete |
| `backend/app/modules/iso_docs/api/registry_types.py` | Medium | Registry type CRUD endpoints |
| `backend/app/modules/iso_docs/api/registry_rows.py` | Complex | Row CRUD + reorder + export |
| `backend/app/modules/iso_docs/api/registry_attachments.py` | Simple | Upload/delete endpoints |
| `backend/scripts/seed_registry_types.py` | Complex | Seed 18 registry types |
| `frontend/src/modules/iso-docs/types/registry.ts` | Simple | TypeScript types |
| `frontend/src/modules/iso-docs/services/registries.ts` | Simple | API client |
| `frontend/src/modules/iso-docs/hooks/useRegistryTypes.ts` | Simple | TanStack Query hooks |
| `frontend/src/modules/iso-docs/hooks/useRegistryRows.ts` | Medium | Row query + mutations |
| `frontend/src/modules/iso-docs/hooks/useRegistryAttachments.ts` | Simple | Attachment mutations |
| `frontend/src/modules/iso-docs/components/RegistryView.tsx` | Complex | Main registry table view |
| `frontend/src/modules/iso-docs/components/RegistryRowDialog.tsx` | Complex | Row edit dialog |
| `frontend/src/modules/iso-docs/components/RegistryTypeDialog.tsx` | Medium | Type editor dialog |
| `frontend/src/modules/iso-docs/components/RegistryColumnEditor.tsx` | Medium | Schema column editor |
| `frontend/src/modules/iso-docs/components/RegistryTypePicker.tsx` | Simple | Type selector for node creation |

### Modified Files

| File | Complexity | Changes |
|------|-----------|---------|
| `backend/app/modules/iso_docs/models/node.py` | Simple | Add `registry_type_id` column |
| `backend/app/modules/iso_docs/models/__init__.py` | Simple | Import new models |
| `backend/app/modules/iso_docs/schemas/node.py` | Simple | Add `registry_type_id` to NodeCreate, NodeResponse |
| `backend/app/modules/iso_docs/api/nodes.py` | Medium | Validate registry_type_id on create, include in tree |
| `backend/app/modules/iso_docs/router.py` | Simple | Mount 3 new sub-routers |
| `backend/app/modules/iso_docs/public.py` | Simple | Export new models |
| `frontend/src/modules/iso-docs/types/isoDocs.ts` | Simple | Add registry_type_id to node types |
| `frontend/src/modules/iso-docs/pages/IsoDocs.tsx` | Medium | Render RegistryView for registry nodes |
| `frontend/src/core/hooks/queryKeys.ts` | Simple | Add registry query keys |
| `frontend/src/shared/types/doc.ts` | Simple | Add `registry` to type union |
| `frontend/src/shared/components/doc/NodeForm.tsx` | Medium | Add registry type option + picker |

## 6. Files NOT Changed

| File | Reason |
|------|--------|
| `backend/app/main.py` | No change needed -- registries are sub-routers within iso_docs which is already mounted |
| `backend/app/core/permissions/actions.py` | Reuse existing `ISO_DOCS_EDIT` permission |
| `backend/app/core/permissions/roles.py` | Same permission, no new role needed |
| `frontend/src/App.tsx` | No new routes -- registries render within the existing IsoDocs page |
| `frontend/src/core/permissions/constants.ts` | Reuse existing `ISO_DOCS_EDIT` |
| `backend/app/modules/iso_docs/services/drive_export_service.py` | Drive export for registries is deferred |
| `frontend/src/shared/components/doc/DocTree.tsx` | The tree already renders based on node data; only NodeForm needs changes for creation |
| `frontend/src/shared/components/doc/DocViewer.tsx` | Not used for registry nodes |
| `frontend/src/shared/components/doc/DocEditor.tsx` | Not used for registry nodes |

## 7. Implementation Phases

### Phase 1: Database + Models (dependency: none)

1. Create Alembic migration `042_create_registries.py`:
   - Add `'registry'` to `iso_doc_node_type` enum
   - Create `registry_types` table
   - Create `registry_rows` table with index
   - Create `registry_attachments` table
   - Add `registry_type_id` column to `iso_doc_nodes`

2. Create SQLAlchemy models:
   - `registry_type.py`
   - `registry_row.py`
   - `registry_attachment.py`
   - Update `node.py` to add `registry_type_id`
   - Update `models/__init__.py`

3. Create Pydantic schemas:
   - `schemas/registry.py`
   - Update `schemas/node.py`

4. Update `public.py` exports

### Phase 2: Backend Services + API (dependency: Phase 1)

5. Create `services/registry_service.py` (validation logic)

6. Create `services/registry_attachment_service.py` (S3 operations)

7. Create `api/registry_types.py` (CRUD endpoints)

8. Create `api/registry_rows.py` (CRUD + reorder + XLSX export)

9. Create `api/registry_attachments.py` (upload/delete)

10. Update `api/nodes.py`:
    - Validate `registry_type_id` on node creation when type=registry
    - Include `registry_type_id` in tree response

11. Update `router.py` to mount new sub-routers

### Phase 3: Seed Script (dependency: Phase 1)

12. Create `backend/scripts/seed_registry_types.py` with all 18 types

### Phase 4: Frontend Types + Services + Hooks (dependency: Phase 2)

13. Create `types/registry.ts`
14. Update `types/isoDocs.ts`
15. Update `shared/types/doc.ts`
16. Create `services/registries.ts`
17. Update `core/hooks/queryKeys.ts`
18. Create hooks: `useRegistryTypes.ts`, `useRegistryRows.ts`, `useRegistryAttachments.ts`

### Phase 5: Frontend Components (dependency: Phase 4)

19. Create `RegistryColumnEditor.tsx`
20. Create `RegistryTypeDialog.tsx`
21. Create `RegistryTypePicker.tsx`
22. Create `RegistryRowDialog.tsx`
23. Create `RegistryView.tsx`
24. Update `NodeForm.tsx` (shared) for registry creation
25. Update `IsoDocs.tsx` to render RegistryView

## 8. Testing Strategy

### Backend Tests

| File | Tests | Description |
|------|-------|-------------|
| `tests/modules/iso_docs/test_registry_types_api.py` | ~12 | CRUD, slug uniqueness, delete protection, schema validation |
| `tests/modules/iso_docs/test_registry_rows_api.py` | ~18 | CRUD, reorder, year filter, data validation against schema, export |
| `tests/modules/iso_docs/test_registry_attachments_api.py` | ~6 | Upload, delete, size limit, content type validation |
| `tests/modules/iso_docs/test_registry_service.py` | ~10 | validate_row_data for each field type, required fields, select options |
| `tests/modules/iso_docs/test_node_registry.py` | ~5 | Node creation with registry type, tree includes registry_type_id |

**Estimated backend tests: ~51**

### Frontend Tests

| File | Tests | Description |
|------|-------|-------------|
| `__tests__/RegistryView.test.tsx` | ~8 | Renders table, year selector, add/edit/delete row |
| `__tests__/RegistryRowDialog.test.tsx` | ~6 | Form fields per type, validation, submit |
| `__tests__/RegistryTypeDialog.test.tsx` | ~5 | Create/edit type, column editor |

**Estimated frontend tests: ~19**

## 9. Risks & Considerations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Schema evolution: changing a type's columns when rows already exist | HIGH | Additive changes only are safe. Removing a column leaves orphan keys in JSONB (harmless). Renaming a key loses data for that column. Add UI warning on destructive schema changes. |
| Large registries (>1000 rows) performance | MEDIUM | Add pagination to `GET /registries/{node_id}/rows` (offset/limit). Initial implementation returns all rows; add pagination if needed. |
| JSONB validation at app layer only | LOW | Validate in `registry_service.py` before insert/update. No DB-level constraint on JSONB structure. |
| Enum migration (`ALTER TYPE ... ADD VALUE`) cannot be transactional | MEDIUM | Must be run outside a transaction block. Alembic handles this with `op.execute()` at top level. |
| S3 bucket permissions for `iso-registries/` prefix | LOW | Same bucket as playbook -- already configured. Just a new prefix. |
| `NodeForm.tsx` is shared between playbook and iso-docs | MEDIUM | Make registry type picker conditional on a prop (e.g., `showRegistryType`). Playbook does not use it. |

## 10. Acceptance Criteria

### Configuration
- [ ] `registry_types` table exists with JSONB schema column
- [ ] Editors can create, update, and delete registry types via API and UI
- [ ] Schema supports 5 field types: string, number, date, boolean, select
- [ ] Registry type deletion blocked when nodes reference it

### Tree Integration
- [ ] `registry` is a valid node type in the tree
- [ ] Creating a registry node requires selecting a registry type
- [ ] Registry nodes display with a distinct icon in the tree
- [ ] Registry type name shown as subtitle in tree

### Data Entry
- [ ] Rows can be created, updated, deleted via dialog
- [ ] Row data is validated against the registry type schema
- [ ] Required fields are enforced
- [ ] Select fields constrain to defined options
- [ ] Rows can be reordered via drag or API

### Yearly Registries
- [ ] Yearly registries show a year selector
- [ ] Rows are filtered by selected year
- [ ] Default year is current year

### Attachments
- [ ] Files can be uploaded to a row (optionally to a specific field)
- [ ] Attachments stored in S3 under `iso-registries/`
- [ ] Attachments can be deleted
- [ ] File size limit: 10MB
- [ ] Allowed types: images, PDFs, common document formats

### Export
- [ ] Registry data exportable as XLSX
- [ ] Columns match the schema definition
- [ ] Year filter applied to export

### Permissions
- [ ] Any authenticated user can view registries
- [ ] Only `IsoDocsEditor` can create/edit/delete types, rows, and attachments

### Backward Compatibility
- [ ] Existing `page` and `group` nodes are unaffected
- [ ] Existing tree, page, and metadata endpoints work unchanged
- [ ] Drive export continues to work for page/group nodes

## 11. Estimated Effort

| Phase | Description | Effort |
|-------|-------------|--------|
| Phase 1 | Database + Models | 3-4 hours |
| Phase 2 | Backend Services + API | 6-8 hours |
| Phase 3 | Seed Script | 2-3 hours |
| Phase 4 | Frontend Types + Services + Hooks | 2-3 hours |
| Phase 5 | Frontend Components | 8-10 hours |
| Testing | Backend + Frontend | 4-6 hours |
| **Total** | | **25-34 hours** |

## 12. Seed Script -- 18 Registry Types

The seed script at `/backend/scripts/seed_registry_types.py` will be idempotent (skip existing by slug). Here are all 18 registry types with their schemas:

```python
REGISTRY_TYPES = [
    {
        "name": "Asset Inventory",
        "slug": "asset-inventory",
        "description": "Information assets: hardware, software, data, people, facilities",
        "is_yearly": False,
        "schema": [
            {"key": "asset_id", "label": "Asset ID", "type": "string", "required": True, "width": 100},
            {"key": "name", "label": "Asset Name", "type": "string", "required": True, "width": 200},
            {"key": "category", "label": "Category", "type": "select", "required": True, "options": ["Hardware", "Software", "Data", "People", "Facilities", "Network", "Cloud Service"], "width": 130},
            {"key": "description", "label": "Description", "type": "string", "required": False, "width": 250},
            {"key": "owner", "label": "Owner", "type": "string", "required": True, "width": 150},
            {"key": "custodian", "label": "Custodian", "type": "string", "required": False, "width": 150},
            {"key": "location", "label": "Location", "type": "string", "required": False, "width": 150},
            {"key": "classification", "label": "Classification", "type": "select", "required": True, "options": ["Public", "Internal", "Confidential", "Restricted"], "width": 120},
            {"key": "criticality", "label": "Criticality", "type": "select", "required": True, "options": ["Low", "Medium", "High", "Critical"], "width": 100},
            {"key": "acquisition_date", "label": "Acquisition Date", "type": "date", "required": False, "width": 130},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Active", "Decommissioned", "Under Review"], "width": 120},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Risk Register",
        "slug": "risk-register",
        "description": "Information security risk assessment and treatment",
        "is_yearly": True,
        "schema": [
            {"key": "risk_id", "label": "Risk ID", "type": "string", "required": True, "width": 100},
            {"key": "title", "label": "Risk Title", "type": "string", "required": True, "width": 200},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 300},
            {"key": "category", "label": "Category", "type": "select", "required": True, "options": ["Operational", "Technical", "Legal", "Physical", "Human", "Environmental"], "width": 120},
            {"key": "threat", "label": "Threat", "type": "string", "required": False, "width": 200},
            {"key": "vulnerability", "label": "Vulnerability", "type": "string", "required": False, "width": 200},
            {"key": "affected_assets", "label": "Affected Assets", "type": "string", "required": False, "width": 200},
            {"key": "likelihood", "label": "Likelihood", "type": "select", "required": True, "options": ["Very Low", "Low", "Medium", "High", "Very High"], "width": 100},
            {"key": "impact", "label": "Impact", "type": "select", "required": True, "options": ["Very Low", "Low", "Medium", "High", "Very High"], "width": 100},
            {"key": "inherent_risk", "label": "Inherent Risk", "type": "select", "required": True, "options": ["Low", "Medium", "High", "Critical"], "width": 110},
            {"key": "treatment", "label": "Treatment", "type": "select", "required": True, "options": ["Accept", "Mitigate", "Transfer", "Avoid"], "width": 100},
            {"key": "controls", "label": "Controls", "type": "string", "required": False, "width": 250},
            {"key": "residual_likelihood", "label": "Residual Likelihood", "type": "select", "required": False, "options": ["Very Low", "Low", "Medium", "High", "Very High"], "width": 130},
            {"key": "residual_impact", "label": "Residual Impact", "type": "select", "required": False, "options": ["Very Low", "Low", "Medium", "High", "Very High"], "width": 130},
            {"key": "residual_risk", "label": "Residual Risk", "type": "select", "required": False, "options": ["Low", "Medium", "High", "Critical"], "width": 110},
            {"key": "risk_owner", "label": "Risk Owner", "type": "string", "required": True, "width": 150},
            {"key": "review_date", "label": "Review Date", "type": "date", "required": False, "width": 130},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Open", "In Treatment", "Accepted", "Closed"], "width": 120},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Statement of Applicability",
        "slug": "statement-of-applicability",
        "description": "Annex A controls applicability and implementation status",
        "is_yearly": False,
        "schema": [
            {"key": "control_id", "label": "Control ID", "type": "string", "required": True, "width": 100},
            {"key": "control_name", "label": "Control Name", "type": "string", "required": True, "width": 200},
            {"key": "applicable", "label": "Applicable", "type": "boolean", "required": True, "width": 90},
            {"key": "justification", "label": "Justification", "type": "string", "required": False, "width": 250},
            {"key": "implementation_status", "label": "Implementation Status", "type": "select", "required": True, "options": ["Implemented", "Partially Implemented", "Planned", "Not Implemented", "N/A"], "width": 160},
            {"key": "responsible", "label": "Responsible", "type": "string", "required": False, "width": 150},
            {"key": "evidence", "label": "Evidence/Reference", "type": "string", "required": False, "width": 200},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Incident Register",
        "slug": "incident-register",
        "description": "Security incidents, data breaches, and near-misses",
        "is_yearly": True,
        "schema": [
            {"key": "incident_id", "label": "Incident ID", "type": "string", "required": True, "width": 100},
            {"key": "title", "label": "Title", "type": "string", "required": True, "width": 200},
            {"key": "date_reported", "label": "Date Reported", "type": "date", "required": True, "width": 130},
            {"key": "date_occurred", "label": "Date Occurred", "type": "date", "required": False, "width": 130},
            {"key": "reporter", "label": "Reporter", "type": "string", "required": True, "width": 150},
            {"key": "severity", "label": "Severity", "type": "select", "required": True, "options": ["Low", "Medium", "High", "Critical"], "width": 100},
            {"key": "category", "label": "Category", "type": "select", "required": True, "options": ["Data Breach", "Malware", "Phishing", "Unauthorized Access", "System Failure", "Physical", "Human Error", "Other"], "width": 140},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 300},
            {"key": "affected_systems", "label": "Affected Systems", "type": "string", "required": False, "width": 200},
            {"key": "root_cause", "label": "Root Cause", "type": "string", "required": False, "width": 200},
            {"key": "corrective_action", "label": "Corrective Action", "type": "string", "required": False, "width": 250},
            {"key": "date_resolved", "label": "Date Resolved", "type": "date", "required": False, "width": 130},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Open", "Investigating", "Resolved", "Closed"], "width": 120},
            {"key": "lessons_learned", "label": "Lessons Learned", "type": "string", "required": False, "width": 250},
        ],
    },
    {
        "name": "Corrective Action Register",
        "slug": "corrective-action-register",
        "description": "Non-conformities, corrective actions, and effectiveness reviews",
        "is_yearly": True,
        "schema": [
            {"key": "car_id", "label": "CAR ID", "type": "string", "required": True, "width": 100},
            {"key": "source", "label": "Source", "type": "select", "required": True, "options": ["Audit", "Incident", "Management Review", "Risk Assessment", "Customer Complaint", "Other"], "width": 130},
            {"key": "date_raised", "label": "Date Raised", "type": "date", "required": True, "width": 130},
            {"key": "non_conformity", "label": "Non-Conformity", "type": "string", "required": True, "width": 300},
            {"key": "root_cause", "label": "Root Cause", "type": "string", "required": False, "width": 250},
            {"key": "corrective_action", "label": "Corrective Action", "type": "string", "required": True, "width": 250},
            {"key": "responsible", "label": "Responsible", "type": "string", "required": True, "width": 150},
            {"key": "target_date", "label": "Target Date", "type": "date", "required": True, "width": 130},
            {"key": "completion_date", "label": "Completion Date", "type": "date", "required": False, "width": 130},
            {"key": "effectiveness_review", "label": "Effectiveness Review", "type": "string", "required": False, "width": 250},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Open", "In Progress", "Completed", "Verified", "Closed"], "width": 120},
        ],
    },
    {
        "name": "Audit Plan & Results",
        "slug": "audit-plan-results",
        "description": "Internal audit schedule, findings, and follow-up",
        "is_yearly": True,
        "schema": [
            {"key": "audit_id", "label": "Audit ID", "type": "string", "required": True, "width": 100},
            {"key": "audit_type", "label": "Audit Type", "type": "select", "required": True, "options": ["Internal", "External", "Surveillance", "Certification"], "width": 120},
            {"key": "scope", "label": "Scope / Area", "type": "string", "required": True, "width": 200},
            {"key": "clauses", "label": "Clauses / Controls", "type": "string", "required": False, "width": 200},
            {"key": "planned_date", "label": "Planned Date", "type": "date", "required": True, "width": 130},
            {"key": "actual_date", "label": "Actual Date", "type": "date", "required": False, "width": 130},
            {"key": "auditor", "label": "Auditor", "type": "string", "required": True, "width": 150},
            {"key": "findings_count", "label": "Findings", "type": "number", "required": False, "width": 80},
            {"key": "nc_major", "label": "Major NCs", "type": "number", "required": False, "width": 80},
            {"key": "nc_minor", "label": "Minor NCs", "type": "number", "required": False, "width": 80},
            {"key": "observations", "label": "Observations", "type": "number", "required": False, "width": 80},
            {"key": "summary", "label": "Summary", "type": "string", "required": False, "width": 300},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Planned", "In Progress", "Completed", "Follow-up"], "width": 120},
        ],
    },
    {
        "name": "Supplier Register",
        "slug": "supplier-register",
        "description": "Third-party suppliers and service providers with security assessments",
        "is_yearly": False,
        "schema": [
            {"key": "supplier_name", "label": "Supplier Name", "type": "string", "required": True, "width": 200},
            {"key": "service_type", "label": "Service Type", "type": "string", "required": True, "width": 200},
            {"key": "contact", "label": "Contact", "type": "string", "required": False, "width": 150},
            {"key": "data_access", "label": "Data Access", "type": "select", "required": True, "options": ["None", "Limited", "Full"], "width": 100},
            {"key": "criticality", "label": "Criticality", "type": "select", "required": True, "options": ["Low", "Medium", "High", "Critical"], "width": 100},
            {"key": "contract_start", "label": "Contract Start", "type": "date", "required": False, "width": 130},
            {"key": "contract_end", "label": "Contract End", "type": "date", "required": False, "width": 130},
            {"key": "last_assessment", "label": "Last Assessment", "type": "date", "required": False, "width": 130},
            {"key": "assessment_result", "label": "Assessment Result", "type": "select", "required": False, "options": ["Pass", "Conditional", "Fail", "Pending"], "width": 130},
            {"key": "certifications", "label": "Certifications", "type": "string", "required": False, "width": 200},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Active", "Under Review", "Suspended", "Terminated"], "width": 120},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Training Register",
        "slug": "training-register",
        "description": "Security awareness training records",
        "is_yearly": True,
        "schema": [
            {"key": "employee_name", "label": "Employee Name", "type": "string", "required": True, "width": 180},
            {"key": "department", "label": "Department", "type": "string", "required": False, "width": 150},
            {"key": "training_type", "label": "Training Type", "type": "select", "required": True, "options": ["Security Awareness", "ISMS Procedures", "Incident Response", "Data Protection", "Phishing Simulation", "Technical", "Other"], "width": 150},
            {"key": "training_name", "label": "Training Name", "type": "string", "required": True, "width": 200},
            {"key": "date_completed", "label": "Date Completed", "type": "date", "required": True, "width": 130},
            {"key": "provider", "label": "Provider", "type": "string", "required": False, "width": 150},
            {"key": "result", "label": "Result", "type": "select", "required": True, "options": ["Pass", "Fail", "Attended", "N/A"], "width": 100},
            {"key": "next_due", "label": "Next Due", "type": "date", "required": False, "width": 130},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Change Management Register",
        "slug": "change-management-register",
        "description": "Changes to the ISMS, infrastructure, and processes",
        "is_yearly": True,
        "schema": [
            {"key": "change_id", "label": "Change ID", "type": "string", "required": True, "width": 100},
            {"key": "title", "label": "Title", "type": "string", "required": True, "width": 200},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 300},
            {"key": "type", "label": "Type", "type": "select", "required": True, "options": ["ISMS", "Infrastructure", "Application", "Process", "Policy", "Other"], "width": 120},
            {"key": "requester", "label": "Requester", "type": "string", "required": True, "width": 150},
            {"key": "date_requested", "label": "Date Requested", "type": "date", "required": True, "width": 130},
            {"key": "risk_assessment", "label": "Risk Assessment", "type": "select", "required": True, "options": ["Low", "Medium", "High"], "width": 120},
            {"key": "approver", "label": "Approver", "type": "string", "required": False, "width": 150},
            {"key": "date_approved", "label": "Date Approved", "type": "date", "required": False, "width": 130},
            {"key": "date_implemented", "label": "Date Implemented", "type": "date", "required": False, "width": 140},
            {"key": "rollback_plan", "label": "Rollback Plan", "type": "boolean", "required": True, "width": 100},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Requested", "Approved", "Implementing", "Completed", "Rejected", "Rolled Back"], "width": 130},
        ],
    },
    {
        "name": "Business Continuity Plan",
        "slug": "business-continuity-plan",
        "description": "BCP scenarios, recovery procedures, and test results",
        "is_yearly": False,
        "schema": [
            {"key": "scenario", "label": "Scenario", "type": "string", "required": True, "width": 200},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 300},
            {"key": "impact_level", "label": "Impact Level", "type": "select", "required": True, "options": ["Low", "Medium", "High", "Critical"], "width": 100},
            {"key": "rto", "label": "RTO", "type": "string", "required": True, "width": 100},
            {"key": "rpo", "label": "RPO", "type": "string", "required": True, "width": 100},
            {"key": "recovery_procedure", "label": "Recovery Procedure", "type": "string", "required": True, "width": 250},
            {"key": "responsible_team", "label": "Responsible Team", "type": "string", "required": True, "width": 150},
            {"key": "last_tested", "label": "Last Tested", "type": "date", "required": False, "width": 130},
            {"key": "test_result", "label": "Test Result", "type": "select", "required": False, "options": ["Pass", "Partial", "Fail", "Not Tested"], "width": 100},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Access Control Register",
        "slug": "access-control-register",
        "description": "System access rights, privileges, and review status",
        "is_yearly": False,
        "schema": [
            {"key": "system", "label": "System / Application", "type": "string", "required": True, "width": 200},
            {"key": "user_name", "label": "User", "type": "string", "required": True, "width": 150},
            {"key": "role", "label": "Role", "type": "string", "required": True, "width": 150},
            {"key": "access_level", "label": "Access Level", "type": "select", "required": True, "options": ["Read Only", "Standard", "Privileged", "Admin"], "width": 120},
            {"key": "granted_date", "label": "Granted Date", "type": "date", "required": True, "width": 130},
            {"key": "granted_by", "label": "Granted By", "type": "string", "required": False, "width": 150},
            {"key": "last_review", "label": "Last Review", "type": "date", "required": False, "width": 130},
            {"key": "next_review", "label": "Next Review", "type": "date", "required": False, "width": 130},
            {"key": "mfa_enabled", "label": "MFA Enabled", "type": "boolean", "required": True, "width": 90},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Active", "Suspended", "Revoked"], "width": 100},
        ],
    },
    {
        "name": "Legal & Regulatory Register",
        "slug": "legal-regulatory-register",
        "description": "Applicable laws, regulations, and contractual obligations",
        "is_yearly": False,
        "schema": [
            {"key": "requirement", "label": "Requirement", "type": "string", "required": True, "width": 200},
            {"key": "type", "label": "Type", "type": "select", "required": True, "options": ["Law", "Regulation", "Standard", "Contract", "Policy"], "width": 100},
            {"key": "jurisdiction", "label": "Jurisdiction", "type": "string", "required": False, "width": 150},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 300},
            {"key": "applicable_to", "label": "Applicable To", "type": "string", "required": False, "width": 200},
            {"key": "compliance_status", "label": "Compliance Status", "type": "select", "required": True, "options": ["Compliant", "Partially Compliant", "Non-Compliant", "Under Review"], "width": 140},
            {"key": "responsible", "label": "Responsible", "type": "string", "required": True, "width": 150},
            {"key": "last_reviewed", "label": "Last Reviewed", "type": "date", "required": False, "width": 130},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "KPI Register",
        "slug": "kpi-register",
        "description": "ISMS key performance indicators and measurement results",
        "is_yearly": True,
        "schema": [
            {"key": "kpi_id", "label": "KPI ID", "type": "string", "required": True, "width": 80},
            {"key": "name", "label": "KPI Name", "type": "string", "required": True, "width": 200},
            {"key": "objective", "label": "Objective", "type": "string", "required": True, "width": 250},
            {"key": "metric", "label": "Metric / Formula", "type": "string", "required": True, "width": 200},
            {"key": "target", "label": "Target", "type": "string", "required": True, "width": 100},
            {"key": "frequency", "label": "Frequency", "type": "select", "required": True, "options": ["Monthly", "Quarterly", "Semi-Annual", "Annual"], "width": 110},
            {"key": "current_value", "label": "Current Value", "type": "string", "required": False, "width": 110},
            {"key": "trend", "label": "Trend", "type": "select", "required": False, "options": ["Improving", "Stable", "Declining"], "width": 100},
            {"key": "responsible", "label": "Responsible", "type": "string", "required": True, "width": 150},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Communication Register",
        "slug": "communication-register",
        "description": "Internal and external ISMS communications",
        "is_yearly": True,
        "schema": [
            {"key": "subject", "label": "Subject", "type": "string", "required": True, "width": 200},
            {"key": "type", "label": "Type", "type": "select", "required": True, "options": ["Internal", "External"], "width": 100},
            {"key": "audience", "label": "Audience", "type": "string", "required": True, "width": 200},
            {"key": "responsible", "label": "Responsible", "type": "string", "required": True, "width": 150},
            {"key": "frequency", "label": "Frequency", "type": "select", "required": True, "options": ["One-time", "Monthly", "Quarterly", "Annual", "As Needed"], "width": 110},
            {"key": "method", "label": "Method", "type": "string", "required": False, "width": 150},
            {"key": "last_communicated", "label": "Last Communicated", "type": "date", "required": False, "width": 140},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Management Review Register",
        "slug": "management-review-register",
        "description": "Management review meetings, inputs, decisions, and actions",
        "is_yearly": True,
        "schema": [
            {"key": "review_date", "label": "Review Date", "type": "date", "required": True, "width": 130},
            {"key": "attendees", "label": "Attendees", "type": "string", "required": True, "width": 250},
            {"key": "topics", "label": "Topics Covered", "type": "string", "required": True, "width": 300},
            {"key": "decisions", "label": "Decisions", "type": "string", "required": True, "width": 300},
            {"key": "actions", "label": "Action Items", "type": "string", "required": False, "width": 300},
            {"key": "responsible", "label": "Responsible", "type": "string", "required": False, "width": 150},
            {"key": "due_date", "label": "Due Date", "type": "date", "required": False, "width": 130},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Completed", "Actions Pending", "Overdue"], "width": 120},
        ],
    },
    {
        "name": "Document Control Register",
        "slug": "document-control-register",
        "description": "Controlled documents, versions, and approval status",
        "is_yearly": False,
        "schema": [
            {"key": "doc_id", "label": "Document ID", "type": "string", "required": True, "width": 100},
            {"key": "title", "label": "Title", "type": "string", "required": True, "width": 200},
            {"key": "category", "label": "Category", "type": "select", "required": True, "options": ["Policy", "Procedure", "Work Instruction", "Form", "Record", "Plan", "Report"], "width": 130},
            {"key": "version", "label": "Version", "type": "string", "required": True, "width": 80},
            {"key": "author", "label": "Author", "type": "string", "required": True, "width": 150},
            {"key": "reviewer", "label": "Reviewer", "type": "string", "required": False, "width": 150},
            {"key": "approver", "label": "Approver", "type": "string", "required": False, "width": 150},
            {"key": "effective_date", "label": "Effective Date", "type": "date", "required": True, "width": 130},
            {"key": "next_review", "label": "Next Review", "type": "date", "required": False, "width": 130},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Draft", "Under Review", "Approved", "Obsolete"], "width": 120},
            {"key": "distribution", "label": "Distribution", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Interested Parties Register",
        "slug": "interested-parties-register",
        "description": "Stakeholders, their requirements, and expectations",
        "is_yearly": False,
        "schema": [
            {"key": "party_name", "label": "Interested Party", "type": "string", "required": True, "width": 200},
            {"key": "type", "label": "Type", "type": "select", "required": True, "options": ["Customer", "Employee", "Regulator", "Partner", "Supplier", "Shareholder", "Community"], "width": 120},
            {"key": "requirements", "label": "Requirements & Expectations", "type": "string", "required": True, "width": 300},
            {"key": "relevance", "label": "Relevance to ISMS", "type": "string", "required": False, "width": 250},
            {"key": "influence", "label": "Influence Level", "type": "select", "required": True, "options": ["Low", "Medium", "High"], "width": 100},
            {"key": "contact", "label": "Contact", "type": "string", "required": False, "width": 150},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
    {
        "name": "Purchases Register",
        "slug": "purchases-register",
        "description": "Security-relevant purchases, subscriptions, and licenses",
        "is_yearly": True,
        "schema": [
            {"key": "purchase_id", "label": "Purchase ID", "type": "string", "required": True, "width": 100},
            {"key": "description", "label": "Description", "type": "string", "required": True, "width": 250},
            {"key": "category", "label": "Category", "type": "select", "required": True, "options": ["Hardware", "Software License", "SaaS Subscription", "Service", "Training", "Consulting", "Other"], "width": 140},
            {"key": "supplier", "label": "Supplier", "type": "string", "required": True, "width": 150},
            {"key": "amount", "label": "Amount (EUR)", "type": "number", "required": True, "width": 120},
            {"key": "date", "label": "Date", "type": "date", "required": True, "width": 130},
            {"key": "requester", "label": "Requester", "type": "string", "required": True, "width": 150},
            {"key": "approver", "label": "Approver", "type": "string", "required": False, "width": 150},
            {"key": "recurring", "label": "Recurring", "type": "boolean", "required": False, "width": 80},
            {"key": "renewal_date", "label": "Renewal Date", "type": "date", "required": False, "width": 130},
            {"key": "status", "label": "Status", "type": "select", "required": True, "options": ["Pending", "Approved", "Delivered", "Cancelled"], "width": 110},
            {"key": "notes", "label": "Notes", "type": "string", "required": False, "width": 200},
        ],
    },
]
```

### Alembic Migration Detail

File: `/backend/alembic/versions/042_create_registries.py`

```python
revision = "042_registries"
down_revision = "041_drive_map"
```

Important notes:
- `ALTER TYPE iso_doc_node_type ADD VALUE IF NOT EXISTS 'registry'` must be executed **outside a transaction**. Use `op.execute()` directly (Alembic auto-commits this for enum ADD VALUE).
- Each DDL in its own `op.execute()` call (asyncpg constraint).
- Tables use `CREATE TABLE IF NOT EXISTS`.
- No new enums needed beyond extending the existing one.

---

This plan is ready for handoff to an implementation agent. All file paths are absolute, all endpoints are specified with HTTP methods and paths, all 18 registry type schemas are defined, and the phases are ordered by dependency.
