# ISO Doc Notes — Design

**Date:** 2026-04-13
**Module:** `iso_docs`
**Goal:** Allow ISO editors to capture short notes against any ISO doc node (page, registry, widget, group). Notes are intended for use during ISO audits, can be marked done, and are reviewed centrally from an admin page.

## Requirements

- Any ISO doc node can have zero or more notes.
- Notes accept long text (markdown). No rich editor — plain textarea.
- In the node detail view, notes are hidden behind a toggle button. Editors can add, mark done/undone, and delete from there.
- An admin page lists all notes grouped by node. Default filter shows pending only; toggle reveals completed.
- Editors can edit, mark done, and delete notes from the admin page.
- All operations are restricted to ISO editors.

## Backend

### Database

New table `iso_doc_notes` (added in module `iso_docs`):

| Column          | Type            | Notes                                  |
| --------------- | --------------- | -------------------------------------- |
| `id`            | UUID PK         | `gen_random_uuid()`                    |
| `node_id`       | UUID FK         | → `iso_doc_nodes(id)` ON DELETE CASCADE |
| `content`       | TEXT NOT NULL   | Markdown                               |
| `done`          | BOOLEAN NOT NULL | default `false`                       |
| `done_at`       | TIMESTAMPTZ     | nullable                               |
| `done_by_id`    | UUID FK         | → `users(id)`, nullable                |
| `created_by_id` | UUID FK         | → `users(id)`, NOT NULL                |
| `created_at`    | TIMESTAMPTZ     | default `now()`                        |
| `updated_at`    | TIMESTAMPTZ     | default `now()`, on update             |

Indexes:
- `ix_iso_doc_notes_node_id` on `(node_id)`
- `ix_iso_doc_notes_done_created` on `(done, created_at DESC)` for the admin listing

Migration: `053_iso_doc_notes.py`.

### Models / Schemas

- Model: `app/modules/iso_docs/models/note.py` — `IsoDocNoteDB`.
- Schemas: `app/modules/iso_docs/schemas/note.py`
  - `NoteResponse` — full note (with `created_by_name`, `done_by_name` resolved server-side)
  - `NoteCreate` — `{ content: str }`
  - `NoteUpdate` — `{ content: str | None, done: bool | None }` (patch semantics)
  - `AdminNoteResponse` extends `NoteResponse` with `node_id`, `node_title`, `node_slug`

### API

New router `app/modules/iso_docs/api/notes.py`. All endpoints require `IsoDocsEditor`.

| Method | Path                                            | Body                             | Returns                  |
| ------ | ----------------------------------------------- | -------------------------------- | ------------------------ |
| GET    | `/api/iso-docs/nodes/{node_id}/notes`           | —                                | `list[NoteResponse]`     |
| POST   | `/api/iso-docs/nodes/{node_id}/notes`           | `{ content }`                    | `NoteResponse`           |
| PATCH  | `/api/iso-docs/notes/{note_id}`                 | `{ content?, done? }`            | `NoteResponse`           |
| DELETE | `/api/iso-docs/notes/{note_id}`                 | —                                | 204                      |
| GET    | `/api/iso-docs/notes?include_done=false`        | —                                | `list[AdminNoteResponse]` |

Behavior:
- `POST` sets `created_by_id` from the auth context.
- `PATCH`: when `done` transitions `false → true`, set `done_at = now()` and `done_by_id = current user`. When `true → false`, clear both.
- `GET` per-node returns all notes (done + pending) ordered by `done ASC, created_at DESC` (pending first, newest first).
- Admin `GET` returns flat list ordered by `node_title ASC, created_at DESC`. Frontend groups by `node_id`. Default `include_done=false`; when `true`, includes everything.

The router is mounted from `app/modules/iso_docs/router.py`. No changes needed in `main.py`.

### Logging

- `iso_doc_note_created` (`node_id`, `note_id`, `user_id`)
- `iso_doc_note_updated` (`note_id`, `done` if changed, `user_id`)
- `iso_doc_note_deleted` (`note_id`, `user_id`)

## Frontend

### Types

`frontend/src/modules/iso-docs/types/notes.ts`:

```ts
export interface IsoDocNote {
  id: string;
  node_id: string;
  content: string;
  done: boolean;
  done_at: string | null;
  done_by_id: string | null;
  done_by_name: string | null;
  created_by_id: string;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminIsoDocNote extends IsoDocNote {
  node_title: string;
  node_slug: string | null;
}

export interface NoteCreate { content: string; }
export interface NoteUpdate { content?: string; done?: boolean; }
```

### Hooks / Service

`frontend/src/modules/iso-docs/services/notes.ts` — REST client.

`frontend/src/modules/iso-docs/hooks/useIsoDocNotes.ts`:
- `useNodeNotes(nodeId)` — query key `['iso-docs', 'notes', 'node', nodeId]`
- `useAllNotes(includeDone)` — query key `['iso-docs', 'notes', 'admin', includeDone]`
- `useCreateNote(nodeId)`, `useUpdateNote()`, `useDeleteNote()` — invalidate both query roots

### Node detail UI

In `IsoDocs.tsx`, next to the metadata edit pencil, render a `NotesToggleButton` (only when `isEditor`):

- Icon `MessageSquare` + count badge (number of pending notes).
- Toggle state lives in URL via `useUrlState('notes', '0' | '1')` so refreshes preserve it.

When open, render `NotesPanel` between `MetadataPanel` and the body content:

- Header: "Notes (N)".
- List of notes (pending first, then completed). Each note:
  - Markdown content (`DocViewer`).
  - Author name and relative date.
  - Checkbox "Done" (toggles via `useUpdateNote`).
  - Delete button with confirm.
  - Done notes shown with `opacity-60` and a green check.
- Footer: textarea + "Add note" button. Clears on success.

Component: `frontend/src/modules/iso-docs/components/NotesPanel.tsx`.

### Admin page

Route: `/admin/iso/notes`. Add new admin sidebar group "ISO" with this entry.

Component: `frontend/src/modules/iso-docs/pages/IsoNotesAdmin.tsx`.

Layout:
- Header with title and toggle "Show completed" (default off; persisted in URL via `useUrlState('done', '0' | '1')`).
- Empty state when no notes match the filter.
- Notes grouped by `node_id`. Group header:
  - Node title as a link to `/iso/docs?page={slug}`.
  - Count of pending notes for that node.
- Each note in a card with: content (rendered + inline edit on click), done toggle, delete.

### Permissions / routing

- `AdminRoutes()` gains `<Route path="iso/notes" element={<IsoNotesAdmin />} />`.
- The admin gate already wraps `/admin` with `Action.ADMIN_USERS` — keep it.
- The "Notes" toggle in the node view is rendered only when `isEditor` is true.

## Out of scope (YAGNI)

- Soft delete / history of notes.
- Threading, replies, mentions.
- Slack notifications when notes are added.
- Per-note assignment to a user.
- Bulk operations (mark all done, etc.).

## Testing

### Backend

- `tests/modules/iso_docs/test_notes.py`:
  - Editor can create / patch / delete notes.
  - Non-editor (regular user) gets 403 on all endpoints.
  - PATCH transitioning `done` sets/clears `done_at` and `done_by_id`.
  - Cascade: deleting a node deletes its notes.
  - Admin list filters `include_done` correctly and embeds `node_title` / `node_slug`.

### Frontend

- `NotesPanel.test.tsx`: renders list, optimistic create, delete confirm, done toggle.
- `IsoNotesAdmin.test.tsx`: groups by node, toggle filter, edit inline, delete.

## Migration / rollout

- Single Alembic migration adds the table; no data backfill.
- Feature ships as a single PR.
- No breaking changes to existing endpoints or schemas.
