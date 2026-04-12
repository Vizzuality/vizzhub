# MCP Command Queue Design

## Goal

Add write operations to the MCP server for ISO docs, ISO registries, and Playbook via a human-in-the-loop command queue. Every write is enqueued as a pending command that requires explicit approval before execution. This provides auditability (critical for ISO compliance) and safety (no accidental writes from AI).

## Scope

- **Modules**: ISO docs (pages + metadata), ISO registries (rows), Playbook (articles)
- **Operations**: 12 write tools + 3 queue management tools
- **Approval**: Conversational (via MCP) + REST API (for future UI)
- **No transacciones**: Each command is independent (transaction grouping is a future enhancement)
- **No reorder**: Reorder operations are UI-only, excluded from MCP

## Architecture

```
MCP Write Tools (12)  +  Queue Mgmt Tools (3)
         ↓                       ↓
    Command Service (enqueue / approve / reject / list)
         ↓
    Module Handlers (iso_docs, playbook)
         ↓
    Backend Services (TreeService, ContentVersionService, models)
```

### Layers

| Layer | Responsibility |
|---|---|
| **MCP Write Tools** | Accept parameters, validate permission via `@mcp_requires`, call `command_service.enqueue()` |
| **Queue Mgmt Tools** | `get_pending_commands`, `approve_command`, `reject_command` |
| **Command Service** | Persist commands to DB, manage state transitions, delegate execution to handlers |
| **Module Handlers** | One handler per module (`iso_docs`, `playbook`). Each receives `(action, target, payload, user_id)` and dispatches to the appropriate backend service |
| **Backend Services** | Existing `TreeService`, `ContentVersionService`, SQLAlchemy models. No changes needed. |

## Data Model

### `command_queue` table

```sql
CREATE TABLE command_queue (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  module        TEXT NOT NULL,        -- 'iso_docs' | 'playbook'
  action        TEXT NOT NULL,        -- 'create_page', 'update_registry_row', etc.
  target        TEXT,                 -- slug or node_id of affected resource (NULL for creates)
  payload       JSONB NOT NULL,       -- operation-specific data
  summary       TEXT NOT NULL,        -- human-readable description of the command
  status        TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected | executed | failed
  requested_by  UUID NOT NULL REFERENCES users(id),
  requested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_by   UUID REFERENCES users(id),
  reviewed_at   TIMESTAMPTZ,
  result        JSONB,               -- response after execution
  error         TEXT,                 -- error message if execution fails
  executed_at   TIMESTAMPTZ
);

CREATE INDEX idx_command_queue_status ON command_queue(status);
CREATE INDEX idx_command_queue_requested_by ON command_queue(requested_by);
CREATE INDEX idx_command_queue_module ON command_queue(module);
```

**Future extension**: Add `transaction_id UUID REFERENCES command_transactions(id)` nullable column when transaction grouping is needed.

### Status transitions

```
pending → approved → executed
pending → approved → failed
pending → rejected
```

`approved` is a transient state — the command is immediately executed after approval. If execution succeeds, the status moves to `executed`. If it fails, the status moves to `failed` with the error message preserved.

## MCP Write Tools

### ISO Docs (5 tools)

| Tool | Parameters | Permission |
|---|---|---|
| `iso_create_page` | `parent_slug: str`, `title: str` | `iso_docs:edit` |
| `iso_update_page_content` | `slug: str`, `content: str` | `iso_docs:edit` |
| `iso_update_page_metadata` | `slug: str`, `code?: str`, `standard?: list[str]`, `clauses?: list[str]`, `classification?: str`, `status?: str`, `document_date?: str`, `original_filename?: str`, `guidance?: str`, `changelog?: list[ChangelogEntry]` | `iso_docs:edit` |
| `iso_update_node` | `slug: str`, `title?: str`, `parent_slug?: str` | `iso_docs:edit` |
| `iso_delete_node` | `slug: str` | `iso_docs:edit` |

### ISO Registries (3 tools)

| Tool | Parameters | Permission |
|---|---|---|
| `iso_create_registry_row` | `slug: str`, `year?: int`, `data: dict` | `iso_docs:edit` |
| `iso_update_registry_row` | `slug: str`, `row_id: str`, `data: dict` | `iso_docs:edit` |
| `iso_delete_registry_row` | `slug: str`, `row_id: str` | `iso_docs:edit` |

### Playbook (4 tools)

| Tool | Parameters | Permission |
|---|---|---|
| `playbook_create_article` | `parent_slug: str`, `title: str` | `playbook:edit` |
| `playbook_update_article_content` | `slug: str`, `content: str` | `playbook:edit` |
| `playbook_update_node` | `slug: str`, `title?: str`, `parent_slug?: str` | `playbook:edit` |
| `playbook_delete_node` | `slug: str` | `playbook:edit` |

### Queue Management (3 tools)

| Tool | Parameters | Permission |
|---|---|---|
| `get_pending_commands` | `module?: str` | Authenticated (sees own commands only) |
| `approve_command` | `command_id: str` | Module permission of the command |
| `reject_command` | `command_id: str` | Module permission of the command |

All write tools use **slugs** as identifiers (consistent with read tools). Exception: `row_id` for registry rows since they have no slug.

### Delete safety

`iso_delete_node` and `playbook_delete_node` **only delete leaf nodes** (nodes with no children). If the node has children, the command is rejected at enqueue time with an error asking the user to delete children first. Cascading tree deletion is too destructive for a conversational AI context.

## Command Flow

### 1. Enqueue (write tool called)

1. `@mcp_requires` checks user has module permission
2. **Light validation** — resource exists, payload has correct shape, registry data matches schema structure
3. **Generate summary** — human-readable description with titles, labels, diffs (see Summary section)
4. Persist `CommandDB` with `status=pending`
5. Return:
```json
{
  "status": "queued",
  "command_id": "uuid",
  "summary": "Create row in Incident Register: Number: INC-004, Severity: High",
  "message": "Command queued. Use approve_command('uuid') to execute."
}
```

### 2. Approve (approve_command called)

1. Verify command `status == pending`
2. Verify user has permission for the command's module
3. Set `status=approved`, `reviewed_by=user_id`, `reviewed_at=now()`
4. Look up handler: `handlers[command.module]`
5. Call `handler.execute(command.action, command.target, command.payload, command.requested_by)`
6. On success: set `status=executed`, `result=response`, `executed_at=now()`
7. On failure: set `status=failed`, `error=message`
8. Return result or error

### 3. Reject (reject_command called)

1. Verify command `status == pending`
2. Set `status=rejected`, `reviewed_by=user_id`, `reviewed_at=now()`

## Summary Generation

Each action produces a human-readable summary at enqueue time. Summaries use **titles** (not IDs), **field labels** (not keys), and **diffs** (old → new) where applicable.

| Action | Summary pattern |
|---|---|
| `create_page` | "Create page **{title}** in {parent_title}" |
| `update_page_content` | "Update content of **{title}** (v{current} → v{next})" |
| `update_metadata` | "Update metadata of **{title}**: {changed_fields}" |
| `update_node` | "Rename **{old_title}** → **{new_title}**" or "Move **{title}** to {new_parent}" |
| `delete_node` | "Delete **{title}**" (leaf only, rejected if has children) |
| `create_registry_row` | "Create row in **{registry_name}**: {key_fields}" |
| `update_registry_row` | "Update row {identifier} in **{registry_name}**: {changed_fields}" |
| `delete_registry_row` | "Delete row {identifier} from **{registry_name}**" |
| `create_article` | "Create article **{title}** in {parent_title}" |
| `update_article_content` | "Update content of **{title}** (v{current} → v{next})" |
| `update_node` (playbook) | "Rename **{old_title}** → **{new_title}**" or "Move **{title}** to {new_parent}" |
| `delete_node` (playbook) | "Delete **{title}**" (leaf only, rejected if has children) |

For registry rows, field labels come from the registry type's schema definition, not the raw JSON keys.

For metadata updates, `changed_fields` shows the diff: "status: draft → approved, classification: internal_use → confidential".

## Module Handlers

Each handler exposes a single interface:

```python
async def execute(
    action: str,
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
```

### iso_docs handler — 8 actions

| Action | Backend service used |
|---|---|
| `create_page` | `TreeService.create_node()` + `IsoDocMetadataDB` creation |
| `update_page_content` | `ContentVersionService.save()` with `created_by_id=user_id` |
| `update_metadata` | Direct `IsoDocMetadataDB` update, changelog author = user name |
| `update_node` | `TreeService.update_node()` (title, parent_id) |
| `delete_node` | Verify no children, then delete single node |
| `create_registry_row` | Resolve node + validate data vs schema + create `RegistryRowDB` |
| `update_registry_row` | Merge payload with existing data + validate + update `RegistryRowDB` |
| `delete_registry_row` | Delete `RegistryRowDB` |

### playbook handler — 4 actions

| Action | Backend service used |
|---|---|
| `create_article` | `TreeService.create_node()` (playbook tree) |
| `update_article_content` | `ContentVersionService.save()` with `created_by_id=user_id` |
| `update_node` | `TreeService.update_node()` (title, parent_id, is_public) |
| `delete_node` | Verify no children, then delete single node |

### User attribution

The `user_id` from `McpUserContext` (the authenticated user's UUID from the JWT) is propagated to:
- `created_by_id` / `updated_by_id` on all DB records
- `author` field in changelog entries (resolved to user's display name)
- `requested_by` and `reviewed_by` on the command itself

No writes are ever attributed to "system".

## Validation Strategy

**Two-phase validation:**

1. **At enqueue time (light)**: Fail fast on obviously invalid commands
   - Resource exists (slug resolves to a node)
   - Payload has required fields
   - Registry data keys are valid for the schema
   - Enum values are valid (classification, status)

2. **At execution time (full)**: Complete validation via backend services
   - DB constraints (unique slugs, FK references)
   - Optimistic locking conflicts (expected_version for content updates)
   - Registry row data type validation against schema
   - Tree depth limits, circular move detection

This accepts that state can change between enqueue and execution. A command that passed light validation may fail at execution — that's expected and the failure is recorded.

## REST API Endpoints

Three endpoints in `backend/app/core/api/commands.py` for future UI integration:

| Endpoint | Method | Permission |
|---|---|---|
| `/api/commands` | GET | Authenticated (filtered by user's module permissions) |
| `/api/commands/{id}/approve` | POST | Module permission of the command |
| `/api/commands/{id}/reject` | POST | Module permission of the command |

Query parameters for GET: `status` (pending, executed, etc.), `module` (iso_docs, playbook).

These endpoints share the same `CommandService` as the MCP tools — identical logic, different transport.

## File Structure

### New files in `mcp_server/`

| File | Responsibility |
|---|---|
| `models/command.py` | `CommandDB` SQLAlchemy model |
| `services/command_service.py` | `enqueue()`, `approve()`, `reject()`, `list_pending()` |
| `handlers/iso_docs.py` | ISO docs + registries handler (8 actions) |
| `handlers/playbook.py` | Playbook handler (4 actions) |
| `tools/iso_write.py` | 8 ISO write MCP tools |
| `tools/playbook_write.py` | 4 Playbook write MCP tools |
| `tools/commands.py` | 3 queue management MCP tools |

### New files in `backend/`

| File | Responsibility |
|---|---|
| `app/core/api/commands.py` | REST endpoints for command queue |

### Modified files

| File | Change |
|---|---|
| `mcp_server/server.py` | Register new tools |
| `mcp_server/data/base.py` | Add `get_write_session()` context manager |

### Alembic migration

One migration adding the `command_queue` table. Following project conventions: raw SQL with `op.execute()`, one statement per call.

## Testing

| Test file | Coverage |
|---|---|
| `mcp_server/tests/test_command_service.py` | Enqueue, approve, reject, invalid state transitions, permission checks |
| `mcp_server/tests/test_handler_iso_docs.py` | All 8 ISO actions: create/update/delete pages, metadata, registry rows |
| `mcp_server/tests/test_handler_playbook.py` | All 4 Playbook actions |
| `mcp_server/tests/test_command_tools.py` | Integration: tool call → enqueue → approve → verify DB state |
| `backend/tests/test_commands_api.py` | REST endpoints: GET/approve/reject, filters, permissions |

Summary generation is tested within each handler test — verify that summaries contain titles and labels, not UUIDs or raw keys.

## Future Enhancements (out of scope)

- **Transaction grouping**: `command_transactions` table + `transaction_id` FK on `command_queue`. Group related commands for batch approval.
- **Saga pattern**: Cross-referencing between commands via `ref_alias` + `$ref` syntax.
- **VizzHub UI inbox**: "Pending Actions" page for async review and batch approval.
- **Additional modules**: Tracker, Capacity, Scorecard write operations.
- **Policy engine**: Risk-based routing (low-risk writes skip queue), role-based approval.
