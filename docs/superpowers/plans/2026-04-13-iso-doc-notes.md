# ISO Doc Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-node notes to the ISO docs module so editors can capture audit notes on any node, mark them done, and review everything from an admin page.

**Architecture:** A new `iso_doc_notes` table inside the `iso_docs` module, exposed through a dedicated REST router gated by `IsoDocsEditor`. The frontend adds a togglable `NotesPanel` to the existing node detail view and a new admin page at `/admin/iso/notes` that groups notes by node.

**Tech Stack:** SQLAlchemy 2 + asyncpg, Alembic, FastAPI, Pydantic v2, React + TanStack Query, shadcn UI, `@uiw/react-md-editor` (markdown render only).

**Spec:** `docs/superpowers/specs/2026-04-13-iso-doc-notes-design.md`

---

## File Structure

**Backend (create):**
- `backend/alembic/versions/053_iso_doc_notes.py` — migration
- `backend/app/modules/iso_docs/models/note.py` — `IsoDocNoteDB`
- `backend/app/modules/iso_docs/schemas/note.py` — Pydantic schemas
- `backend/app/modules/iso_docs/api/notes.py` — REST router
- `backend/tests/iso_docs/test_notes_api.py` — API tests

**Backend (modify):**
- `backend/app/modules/iso_docs/models/__init__.py` — export `IsoDocNoteDB`
- `backend/app/modules/iso_docs/router.py` — mount notes router

**Frontend (create):**
- `frontend/src/modules/iso-docs/types/notes.ts` — types
- `frontend/src/modules/iso-docs/services/notes.ts` — REST client
- `frontend/src/modules/iso-docs/hooks/useIsoDocNotes.ts` — TanStack Query hooks
- `frontend/src/modules/iso-docs/components/NotesPanel.tsx` — node-view notes panel
- `frontend/src/modules/iso-docs/pages/IsoNotesAdmin.tsx` — admin page
- `frontend/src/modules/iso-docs/components/__tests__/NotesPanel.test.tsx`
- `frontend/src/modules/iso-docs/pages/__tests__/IsoNotesAdmin.test.tsx`

**Frontend (modify):**
- `frontend/src/core/hooks/queryKeys.ts` — add notes keys
- `frontend/src/modules/iso-docs/pages/IsoDocs.tsx` — add NotesToggle + NotesPanel render
- `frontend/src/App.tsx` — add `iso/notes` admin route
- `frontend/src/core/components/Admin/` — admin sidebar (locate the menu definition during Task 11 and add an "ISO" group with a "Notes" entry)

---

## Task 1: Migration for `iso_doc_notes` table

**Files:**
- Create: `backend/alembic/versions/053_iso_doc_notes.py`

- [ ] **Step 1: Write the migration**

```python
"""Add iso_doc_notes table.

Revision ID: 053_iso_notes
Revises: 052_meta_instr
"""

from alembic import op

revision = "053_iso_notes"
down_revision = "052_meta_instr"


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS iso_doc_notes ("
        "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "  node_id UUID NOT NULL REFERENCES iso_doc_nodes(id) ON DELETE CASCADE,"
        "  content TEXT NOT NULL,"
        "  done BOOLEAN NOT NULL DEFAULT false,"
        "  done_at TIMESTAMPTZ,"
        "  done_by_id UUID REFERENCES users(id) ON DELETE SET NULL,"
        "  created_by_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        "  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ")"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_iso_doc_notes_node_id "
        "ON iso_doc_notes (node_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_iso_doc_notes_done_created "
        "ON iso_doc_notes (done, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS iso_doc_notes")
```

> Note: `created_by_id` is `NOT NULL` but the FK is `ON DELETE SET NULL`, which would conflict with NOT NULL if a referenced user were deleted. We accept this trade-off (matching `iso_doc_nodes.created_by_id` pattern used in this repo, which is nullable). For consistency with `iso_doc_nodes`, **keep `created_by_id` nullable** — change the column definition to drop `NOT NULL`. Final schema:

```python
        "  created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,"
```

- [ ] **Step 2: Apply the migration**

```bash
cd backend && alembic upgrade head
```

Expected output: `Running upgrade 052_meta_instr -> 053_iso_notes, Add iso_doc_notes table.`

- [ ] **Step 3: Verify in psql**

```bash
psql "$DATABASE_URL" -c "\d iso_doc_notes"
```

Expected: table with 9 columns and the two indexes.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/053_iso_doc_notes.py
git commit -m "feat(iso-docs): migration for iso_doc_notes table"
```

---

## Task 2: SQLAlchemy model `IsoDocNoteDB`

**Files:**
- Create: `backend/app/modules/iso_docs/models/note.py`
- Modify: `backend/app/modules/iso_docs/models/__init__.py`

- [ ] **Step 1: Write the model**

`backend/app/modules/iso_docs/models/note.py`:

```python
"""ISO doc notes — captured during audits, attached to any node."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base

_SET_NULL = "SET NULL"


class IsoDocNoteDB(Base):
    """A markdown note attached to an ISO doc node, used for audit capture."""

    __tablename__ = "iso_doc_notes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    node_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("iso_doc_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    done_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    done_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete=_SET_NULL),
        nullable=True,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete=_SET_NULL),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Export from package**

Edit `backend/app/modules/iso_docs/models/__init__.py` — append:

```python
from app.modules.iso_docs.models.note import IsoDocNoteDB
```

- [ ] **Step 3: Verify importability**

```bash
cd backend && python -c "from app.modules.iso_docs.models import IsoDocNoteDB; print(IsoDocNoteDB.__tablename__)"
```

Expected: `iso_doc_notes`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/iso_docs/models/note.py backend/app/modules/iso_docs/models/__init__.py
git commit -m "feat(iso-docs): add IsoDocNoteDB model"
```

---

## Task 3: Pydantic schemas for notes

**Files:**
- Create: `backend/app/modules/iso_docs/schemas/note.py`

- [ ] **Step 1: Write schemas**

```python
"""Pydantic schemas for ISO doc notes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    node_id: UUID
    content: str
    done: bool
    done_at: datetime | None
    done_by_id: UUID | None
    done_by_name: str | None = None
    created_by_id: UUID | None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminNoteResponse(NoteResponse):
    node_title: str
    node_slug: str | None


class NoteCreate(BaseModel):
    content: str = Field(min_length=1)


class NoteUpdate(BaseModel):
    content: str | None = Field(None, min_length=1)
    done: bool | None = None
```

- [ ] **Step 2: Verify importability**

```bash
cd backend && python -c "from app.modules.iso_docs.schemas.note import NoteResponse, NoteCreate, NoteUpdate, AdminNoteResponse; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/iso_docs/schemas/note.py
git commit -m "feat(iso-docs): add note pydantic schemas"
```

---

## Task 4: API tests for notes (write failing tests first)

**Files:**
- Create: `backend/tests/iso_docs/test_notes_api.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for ISO docs notes API."""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def page_node(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "POL04 Access Control", "type": "page"},
    )
    return response.json()


@pytest_asyncio.fixture
async def registry_node(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Opportunity Register", "type": "registry"},
    )
    return response.json()


@pytest.mark.asyncio
async def test_create_note(client: AsyncClient, page_node: dict):
    response = await client.post(
        f"/api/iso-docs/nodes/{page_node['id']}/notes",
        json={"content": "Auditor flagged inconsistent versions"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "Auditor flagged inconsistent versions"
    assert data["done"] is False
    assert data["node_id"] == page_node["id"]
    assert data["created_by_id"] is not None


@pytest.mark.asyncio
async def test_list_notes_for_node(client: AsyncClient, page_node: dict):
    for content in ["first", "second", "third"]:
        await client.post(
            f"/api/iso-docs/nodes/{page_node['id']}/notes",
            json={"content": content},
        )
    response = await client.get(f"/api/iso-docs/nodes/{page_node['id']}/notes")
    assert response.status_code == 200
    notes = response.json()
    assert len(notes) == 3
    # Newest first within each done-bucket; here all pending so latest first.
    assert notes[0]["content"] == "third"


@pytest.mark.asyncio
async def test_patch_note_content(client: AsyncClient, page_node: dict):
    created = (await client.post(
        f"/api/iso-docs/nodes/{page_node['id']}/notes",
        json={"content": "draft"},
    )).json()
    response = await client.patch(
        f"/api/iso-docs/notes/{created['id']}",
        json={"content": "edited"},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "edited"


@pytest.mark.asyncio
async def test_patch_note_done_sets_metadata(client: AsyncClient, page_node: dict):
    created = (await client.post(
        f"/api/iso-docs/nodes/{page_node['id']}/notes",
        json={"content": "x"},
    )).json()

    done = (await client.patch(
        f"/api/iso-docs/notes/{created['id']}",
        json={"done": True},
    )).json()
    assert done["done"] is True
    assert done["done_at"] is not None
    assert done["done_by_id"] is not None

    reopened = (await client.patch(
        f"/api/iso-docs/notes/{created['id']}",
        json={"done": False},
    )).json()
    assert reopened["done"] is False
    assert reopened["done_at"] is None
    assert reopened["done_by_id"] is None


@pytest.mark.asyncio
async def test_delete_note(client: AsyncClient, page_node: dict):
    created = (await client.post(
        f"/api/iso-docs/nodes/{page_node['id']}/notes",
        json={"content": "x"},
    )).json()
    response = await client.delete(f"/api/iso-docs/notes/{created['id']}")
    assert response.status_code == 204
    listing = (await client.get(f"/api/iso-docs/nodes/{page_node['id']}/notes")).json()
    assert listing == []


@pytest.mark.asyncio
async def test_node_cascade_deletes_notes(client: AsyncClient, page_node: dict):
    await client.post(
        f"/api/iso-docs/nodes/{page_node['id']}/notes",
        json={"content": "x"},
    )
    await client.delete(f"/api/iso-docs/nodes/{page_node['id']}")
    # Querying by node_id returns 404 because the node is gone.
    response = await client.get(f"/api/iso-docs/nodes/{page_node['id']}/notes")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_list_default_excludes_done(
    client: AsyncClient, page_node: dict, registry_node: dict
):
    pending = (await client.post(
        f"/api/iso-docs/nodes/{page_node['id']}/notes",
        json={"content": "pending"},
    )).json()
    done_note = (await client.post(
        f"/api/iso-docs/nodes/{registry_node['id']}/notes",
        json={"content": "done"},
    )).json()
    await client.patch(
        f"/api/iso-docs/notes/{done_note['id']}", json={"done": True}
    )

    response = await client.get("/api/iso-docs/notes")
    assert response.status_code == 200
    items = response.json()
    ids = {n["id"] for n in items}
    assert pending["id"] in ids
    assert done_note["id"] not in ids
    # Embedded node info present.
    assert all("node_title" in n and "node_slug" in n for n in items)


@pytest.mark.asyncio
async def test_admin_list_include_done(
    client: AsyncClient, page_node: dict
):
    note = (await client.post(
        f"/api/iso-docs/nodes/{page_node['id']}/notes",
        json={"content": "x"},
    )).json()
    await client.patch(f"/api/iso-docs/notes/{note['id']}", json={"done": True})
    response = await client.get("/api/iso-docs/notes?include_done=true")
    assert response.status_code == 200
    ids = {n["id"] for n in response.json()}
    assert note["id"] in ids


@pytest.mark.asyncio
async def test_patch_404_for_unknown_note(client: AsyncClient):
    response = await client.patch(
        "/api/iso-docs/notes/00000000-0000-0000-0000-000000000000",
        json={"content": "x"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_404_for_unknown_node(client: AsyncClient):
    response = await client.post(
        "/api/iso-docs/nodes/00000000-0000-0000-0000-000000000000/notes",
        json={"content": "x"},
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && pytest tests/iso_docs/test_notes_api.py -v
```

Expected: every test errors (router not registered → 404 / collection error). Failure mode is acceptable; we'll implement next.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/iso_docs/test_notes_api.py
git commit -m "test(iso-docs): failing tests for notes API"
```

---

## Task 5: Notes API router + mount

**Files:**
- Create: `backend/app/modules/iso_docs/api/notes.py`
- Modify: `backend/app/modules/iso_docs/router.py`

- [ ] **Step 1: Write the router**

`backend/app/modules/iso_docs/api/notes.py`:

```python
"""ISO Docs note endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import desc, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql import func

from app.core.api.deps import DBSession
from app.core.models.user import UserDB
from app.modules.iso_docs.api.deps import IsoDocsEditor
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.note import IsoDocNoteDB
from app.modules.iso_docs.schemas.note import (
    AdminNoteResponse,
    NoteCreate,
    NoteResponse,
    NoteUpdate,
)

router = APIRouter()
logger = structlog.get_logger()


def _user_name_expr(user_alias):
    return func.coalesce(
        func.nullif(
            func.concat_ws(
                " ",
                func.nullif(user_alias.first_name, ""),
                func.nullif(user_alias.last_name, ""),
            ),
            "",
        ),
        user_alias.name,
        user_alias.email,
    )


async def _hydrate_response(db, note: IsoDocNoteDB) -> NoteResponse:
    Creator = aliased(UserDB)
    Doner = aliased(UserDB)
    row = (await db.execute(
        select(_user_name_expr(Creator), _user_name_expr(Doner))
        .select_from(IsoDocNoteDB)
        .outerjoin(Creator, Creator.id == IsoDocNoteDB.created_by_id)
        .outerjoin(Doner, Doner.id == IsoDocNoteDB.done_by_id)
        .where(IsoDocNoteDB.id == note.id)
    )).one()
    resp = NoteResponse.model_validate(note)
    resp.created_by_name = row[0]
    resp.done_by_name = row[1]
    return resp


@router.get("/nodes/{node_id}/notes")
async def list_node_notes(
    node_id: UUID, db: DBSession, _: IsoDocsEditor
) -> list[NoteResponse]:
    node = await db.get(IsoDocNodeDB, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    Creator = aliased(UserDB)
    Doner = aliased(UserDB)
    rows = (await db.execute(
        select(IsoDocNoteDB, _user_name_expr(Creator), _user_name_expr(Doner))
        .outerjoin(Creator, Creator.id == IsoDocNoteDB.created_by_id)
        .outerjoin(Doner, Doner.id == IsoDocNoteDB.done_by_id)
        .where(IsoDocNoteDB.node_id == node_id)
        .order_by(IsoDocNoteDB.done.asc(), desc(IsoDocNoteDB.created_at))
    )).all()

    out: list[NoteResponse] = []
    for note, creator_name, doner_name in rows:
        item = NoteResponse.model_validate(note)
        item.created_by_name = creator_name
        item.done_by_name = doner_name
        out.append(item)
    return out


@router.post(
    "/nodes/{node_id}/notes", status_code=status.HTTP_201_CREATED
)
async def create_note(
    node_id: UUID, data: NoteCreate, db: DBSession, user: IsoDocsEditor
) -> NoteResponse:
    node = await db.get(IsoDocNodeDB, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    note = IsoDocNoteDB(
        node_id=node_id,
        content=data.content,
        created_by_id=user.user_id,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)
    logger.info(
        "iso_doc_note_created",
        node_id=str(node_id),
        note_id=str(note.id),
        user_id=str(user.user_id),
    )
    return await _hydrate_response(db, note)


@router.patch("/notes/{note_id}")
async def update_note(
    note_id: UUID, data: NoteUpdate, db: DBSession, user: IsoDocsEditor
) -> NoteResponse:
    note = await db.get(IsoDocNoteDB, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if data.content is not None:
        note.content = data.content
    if data.done is not None and data.done != note.done:
        note.done = data.done
        if data.done:
            note.done_at = func.now()
            note.done_by_id = user.user_id
        else:
            note.done_at = None
            note.done_by_id = None

    await db.flush()
    await db.refresh(note)
    logger.info(
        "iso_doc_note_updated",
        note_id=str(note_id),
        done=note.done,
        user_id=str(user.user_id),
    )
    return await _hydrate_response(db, note)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID, db: DBSession, user: IsoDocsEditor
) -> Response:
    note = await db.get(IsoDocNoteDB, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    logger.info(
        "iso_doc_note_deleted",
        note_id=str(note_id),
        user_id=str(user.user_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/notes")
async def list_all_notes(
    db: DBSession,
    _: IsoDocsEditor,
    include_done: Annotated[bool, Query()] = False,
) -> list[AdminNoteResponse]:
    Creator = aliased(UserDB)
    Doner = aliased(UserDB)
    stmt = (
        select(
            IsoDocNoteDB,
            IsoDocNodeDB.title.label("node_title"),
            IsoDocNodeDB.slug.label("node_slug"),
            _user_name_expr(Creator),
            _user_name_expr(Doner),
        )
        .join(IsoDocNodeDB, IsoDocNodeDB.id == IsoDocNoteDB.node_id)
        .outerjoin(Creator, Creator.id == IsoDocNoteDB.created_by_id)
        .outerjoin(Doner, Doner.id == IsoDocNoteDB.done_by_id)
        .order_by(IsoDocNodeDB.title.asc(), desc(IsoDocNoteDB.created_at))
    )
    if not include_done:
        stmt = stmt.where(IsoDocNoteDB.done.is_(False))

    rows = (await db.execute(stmt)).all()
    out: list[AdminNoteResponse] = []
    for note, title, slug, creator_name, doner_name in rows:
        item = AdminNoteResponse.model_validate(note)
        item.node_title = title
        item.node_slug = slug
        item.created_by_name = creator_name
        item.done_by_name = doner_name
        out.append(item)
    return out
```

- [ ] **Step 2: Mount the router**

Edit `backend/app/modules/iso_docs/router.py`:

Add import after the existing imports:

```python
from app.modules.iso_docs.api.notes import router as notes_router
```

Add at the bottom (after other `include_router` lines):

```python
router.include_router(notes_router)
```

- [ ] **Step 3: Run the tests**

```bash
cd backend && pytest tests/iso_docs/test_notes_api.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/iso_docs/api/notes.py backend/app/modules/iso_docs/router.py
git commit -m "feat(iso-docs): add notes API endpoints"
```

---

## Task 6: Frontend types + service

**Files:**
- Create: `frontend/src/modules/iso-docs/types/notes.ts`
- Create: `frontend/src/modules/iso-docs/services/notes.ts`

- [ ] **Step 1: Types**

```ts
export interface IsoDocNote {
  id: string;
  node_id: string;
  content: string;
  done: boolean;
  done_at: string | null;
  done_by_id: string | null;
  done_by_name: string | null;
  created_by_id: string | null;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminIsoDocNote extends IsoDocNote {
  node_title: string;
  node_slug: string | null;
}

export interface NoteCreate {
  content: string;
}

export interface NoteUpdate {
  content?: string;
  done?: boolean;
}
```

- [ ] **Step 2: Service**

`frontend/src/modules/iso-docs/services/notes.ts`:

```ts
import api from '@/core/services/client';
import type { IsoDocNote, AdminIsoDocNote, NoteCreate, NoteUpdate } from '../types/notes';

export const isoDocNotesApi = {
  list: async (nodeId: string): Promise<IsoDocNote[]> => {
    const { data } = await api.get<IsoDocNote[]>(`/iso-docs/nodes/${nodeId}/notes`);
    return data;
  },

  create: async (nodeId: string, body: NoteCreate): Promise<IsoDocNote> => {
    const { data } = await api.post<IsoDocNote>(`/iso-docs/nodes/${nodeId}/notes`, body);
    return data;
  },

  update: async (noteId: string, body: NoteUpdate): Promise<IsoDocNote> => {
    const { data } = await api.patch<IsoDocNote>(`/iso-docs/notes/${noteId}`, body);
    return data;
  },

  remove: async (noteId: string): Promise<void> => {
    await api.delete(`/iso-docs/notes/${noteId}`);
  },

  listAll: async (includeDone: boolean): Promise<AdminIsoDocNote[]> => {
    const { data } = await api.get<AdminIsoDocNote[]>(
      '/iso-docs/notes',
      { params: { include_done: includeDone } },
    );
    return data;
  },
};
```

- [ ] **Step 3: Verify typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/iso-docs/types/notes.ts frontend/src/modules/iso-docs/services/notes.ts
git commit -m "feat(iso-docs): add notes types and service client"
```

---

## Task 7: Query keys + hooks

**Files:**
- Modify: `frontend/src/core/hooks/queryKeys.ts`
- Create: `frontend/src/modules/iso-docs/hooks/useIsoDocNotes.ts`

- [ ] **Step 1: Add query keys**

In `frontend/src/core/hooks/queryKeys.ts`, inside the `isoDocs:` object (after `registryYears`):

```ts
    notesByNode: (nodeId: string) =>
      ['iso-docs', 'notes', 'node', nodeId] as const,
    allNotes: (includeDone: boolean) =>
      ['iso-docs', 'notes', 'admin', includeDone] as const,
```

- [ ] **Step 2: Write hooks**

`frontend/src/modules/iso-docs/hooks/useIsoDocNotes.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { isoDocNotesApi } from '../services/notes';
import type { NoteCreate, NoteUpdate } from '../types/notes';

const NOTES_ROOT = ['iso-docs', 'notes'] as const;

export function useNodeNotes(nodeId: string | null) {
  return useQuery({
    queryKey: queryKeys.isoDocs.notesByNode(nodeId ?? ''),
    queryFn: () => isoDocNotesApi.list(nodeId!),
    enabled: !!nodeId,
    refetchOnWindowFocus: false,
  });
}

export function useAllNotes(includeDone: boolean) {
  return useQuery({
    queryKey: queryKeys.isoDocs.allNotes(includeDone),
    queryFn: () => isoDocNotesApi.listAll(includeDone),
    refetchOnWindowFocus: false,
  });
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>): void {
  qc.invalidateQueries({ queryKey: NOTES_ROOT });
}

export function useCreateNote(nodeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NoteCreate) => isoDocNotesApi.create(nodeId, body),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useUpdateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: NoteUpdate }) =>
      isoDocNotesApi.update(id, body),
    onSuccess: () => invalidateAll(qc),
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => isoDocNotesApi.remove(id),
    onSuccess: () => invalidateAll(qc),
  });
}
```

- [ ] **Step 3: Verify typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/core/hooks/queryKeys.ts frontend/src/modules/iso-docs/hooks/useIsoDocNotes.ts
git commit -m "feat(iso-docs): add notes hooks and query keys"
```

---

## Task 8: NotesPanel component

**Files:**
- Create: `frontend/src/modules/iso-docs/components/NotesPanel.tsx`

- [ ] **Step 1: Implement the component**

```tsx
import { useState } from 'react';
import { Check, Trash2 } from 'lucide-react';
import { DocViewer } from '@/shared/components/doc/DocViewer';
import { Button } from '@/shared/components/ui/button';
import { Textarea } from '@/shared/components/ui/textarea';
import { useNodeNotes, useCreateNote, useUpdateNote, useDeleteNote } from '../hooks/useIsoDocNotes';
import type { IsoDocNote } from '../types/notes';

interface NotesPanelProps {
  readonly nodeId: string;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

function NoteItem({
  note,
  onToggleDone,
  onDelete,
}: {
  readonly note: IsoDocNote;
  readonly onToggleDone: (note: IsoDocNote) => void;
  readonly onDelete: (note: IsoDocNote) => void;
}): JSX.Element {
  return (
    <div className={`border rounded p-3 space-y-2 ${note.done ? 'opacity-60' : ''}`}>
      <DocViewer content={note.content} emptyMessage="" />
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>{note.created_by_name ?? 'Unknown'}</span>
        <span>·</span>
        <span>{formatDate(note.created_at)}</span>
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            onClick={() => onToggleDone(note)}
          >
            <Check className={`h-3.5 w-3.5 ${note.done ? 'text-green-600' : ''}`} />
            <span className="ml-1">{note.done ? 'Done' : 'Mark done'}</span>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={() => onDelete(note)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

export function NotesPanel({ nodeId }: NotesPanelProps): JSX.Element {
  const [draft, setDraft] = useState('');
  const { data: notes = [], isLoading } = useNodeNotes(nodeId);
  const createNote = useCreateNote(nodeId);
  const updateNote = useUpdateNote();
  const deleteNote = useDeleteNote();

  const handleAdd = (): void => {
    const content = draft.trim();
    if (!content) return;
    createNote.mutate({ content }, {
      onSuccess: () => setDraft(''),
    });
  };

  const handleToggle = (note: IsoDocNote): void => {
    updateNote.mutate({ id: note.id, body: { done: !note.done } });
  };

  const handleDelete = (note: IsoDocNote): void => {
    if (!globalThis.confirm('Delete this note?')) return;
    deleteNote.mutate(note.id);
  };

  return (
    <div className="border rounded p-4 space-y-3 bg-muted/30">
      <h3 className="text-sm font-semibold">Notes ({notes.length})</h3>
      {isLoading && <p className="text-xs text-muted-foreground">Loading...</p>}
      {!isLoading && notes.length === 0 && (
        <p className="text-xs text-muted-foreground italic">No notes yet.</p>
      )}
      <div className="space-y-2">
        {notes.map((note) => (
          <NoteItem
            key={note.id}
            note={note}
            onToggleDone={handleToggle}
            onDelete={handleDelete}
          />
        ))}
      </div>
      <div className="space-y-2 pt-2 border-t">
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a note. Markdown supported."
          className="min-h-[80px] text-sm"
        />
        <div className="flex justify-end">
          <Button
            size="sm"
            onClick={handleAdd}
            disabled={!draft.trim() || createNote.isPending}
          >
            {createNote.isPending ? 'Adding...' : 'Add note'}
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/iso-docs/components/NotesPanel.tsx
git commit -m "feat(iso-docs): add NotesPanel component"
```

---

## Task 9: Wire NotesPanel into IsoDocs page

**Files:**
- Modify: `frontend/src/modules/iso-docs/pages/IsoDocs.tsx`

- [ ] **Step 1: Add the toggle button + render**

In `IsoDocs.tsx`:

a) Add imports near the top (alongside other component imports):

```ts
import { MessageSquare } from 'lucide-react';
import { NotesPanel } from '../components/NotesPanel';
import { useNodeNotes } from '../hooks/useIsoDocNotes';
```

b) Inside the component (where `useUrlState` is used for other UI state — search for `useUrlState`), add:

```ts
const [notesOpen, setNotesOpen] = useUrlState('notes', '0');
const showNotes = notesOpen === '1' && isEditor;
const { data: nodeNotes = [] } = useNodeNotes(isEditor && selectedNode ? selectedNode.id : null);
const pendingNotesCount = nodeNotes.filter((n) => !n.done).length;
```

c) Locate the action row that contains the existing edit-metadata pencil (search for `MetadataEditDialog` and follow the breadcrumbs back to the toolbar at the top of the node detail). Just before the existing edit/dropdown buttons, render:

```tsx
{isEditor && (
  <Button
    variant="ghost"
    size="sm"
    className="h-8 gap-1"
    onClick={() => setNotesOpen(showNotes ? '0' : '1')}
  >
    <MessageSquare className="h-4 w-4" />
    Notes
    {pendingNotesCount > 0 && (
      <span className="rounded bg-primary text-primary-foreground text-xs px-1.5 py-0.5">
        {pendingNotesCount}
      </span>
    )}
  </Button>
)}
```

d) In each branch that renders content (page / registry / widget), insert the panel between the `MetadataPanel` and the body:

```tsx
{showNotes && selectedNode && <NotesPanel nodeId={selectedNode.id} />}
```

The three relevant branches are around `IsoDocs.tsx:800–836` (`isPage`, `isRegistry`, `isWidget`). All three already render `MetadataPanel`; add `NotesPanel` directly underneath each.

- [ ] **Step 2: Manual smoke test**

Run dev servers (`cd frontend && npm run dev` and the backend already runs with reload). In the browser:
1. Open an ISO doc node as an editor.
2. Click "Notes" — panel appears, badge updates after adding.
3. Add a note → it shows.
4. Mark done → opacity dims.
5. Reload → notes panel state preserved via URL.
6. Delete → confirm prompt, note disappears.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/iso-docs/pages/IsoDocs.tsx
git commit -m "feat(iso-docs): wire NotesPanel into node view"
```

---

## Task 10: Admin notes page

**Files:**
- Create: `frontend/src/modules/iso-docs/pages/IsoNotesAdmin.tsx`

- [ ] **Step 1: Implement the page**

```tsx
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, Trash2, Check, Pencil } from 'lucide-react';
import { useState } from 'react';
import { DocViewer } from '@/shared/components/doc/DocViewer';
import { Button } from '@/shared/components/ui/button';
import { Switch } from '@/shared/components/ui/switch';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { useAllNotes, useUpdateNote, useDeleteNote } from '../hooks/useIsoDocNotes';
import type { AdminIsoDocNote } from '../types/notes';

function NoteRow({ note }: { readonly note: AdminIsoDocNote }): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note.content);
  const updateNote = useUpdateNote();
  const deleteNote = useDeleteNote();

  const handleSave = (): void => {
    updateNote.mutate(
      { id: note.id, body: { content: draft } },
      { onSuccess: () => setEditing(false) },
    );
  };

  return (
    <div className={`border rounded p-3 space-y-2 ${note.done ? 'opacity-60' : ''}`}>
      {editing ? (
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="min-h-[80px] text-sm"
        />
      ) : (
        <DocViewer content={note.content} emptyMessage="" />
      )}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>{note.created_by_name ?? 'Unknown'}</span>
        <span>·</span>
        <span>{new Date(note.created_at).toLocaleDateString('en-GB')}</span>
        <div className="ml-auto flex items-center gap-1">
          {editing ? (
            <>
              <Button size="sm" className="h-7" onClick={handleSave} disabled={updateNote.isPending}>
                Save
              </Button>
              <Button
                size="sm" variant="ghost" className="h-7"
                onClick={() => { setEditing(false); setDraft(note.content); }}
              >
                Cancel
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="ghost" size="icon" className="h-7 w-7"
                onClick={() => setEditing(true)}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost" size="sm" className="h-7 px-2"
                onClick={() => updateNote.mutate({ id: note.id, body: { done: !note.done } })}
              >
                <Check className={`h-3.5 w-3.5 ${note.done ? 'text-green-600' : ''}`} />
                <span className="ml-1">{note.done ? 'Done' : 'Mark done'}</span>
              </Button>
              <Button
                variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive"
                onClick={() => {
                  if (globalThis.confirm('Delete this note?')) deleteNote.mutate(note.id);
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function IsoNotesAdmin(): JSX.Element {
  const [showDone, setShowDone] = useUrlState('done', '0');
  const includeDone = showDone === '1';
  const { data: notes = [], isLoading } = useAllNotes(includeDone);

  const grouped = useMemo(() => {
    const map = new Map<string, { title: string; slug: string | null; items: AdminIsoDocNote[] }>();
    for (const note of notes) {
      const entry = map.get(note.node_id) ?? { title: note.node_title, slug: note.node_slug, items: [] };
      entry.items.push(note);
      map.set(note.node_id, entry);
    }
    return Array.from(map.entries()).sort(([, a], [, b]) => a.title.localeCompare(b.title));
  }, [notes]);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">ISO Notes</h1>
        <div className="flex items-center gap-2">
          <Switch
            id="show-done"
            checked={includeDone}
            onCheckedChange={(checked) => setShowDone(checked ? '1' : '0')}
          />
          <Label htmlFor="show-done" className="text-sm">Show completed</Label>
        </div>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
      {!isLoading && grouped.length === 0 && (
        <p className="text-sm text-muted-foreground italic">No notes to show.</p>
      )}

      <div className="space-y-6">
        {grouped.map(([nodeId, group]) => {
          const pending = group.items.filter((n) => !n.done).length;
          return (
            <section key={nodeId} className="space-y-2">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold">
                  {group.slug ? (
                    <Link to={`/iso/docs?page=${group.slug}`} className="hover:underline inline-flex items-center gap-1">
                      {group.title}
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  ) : (
                    group.title
                  )}
                </h2>
                <span className="text-xs text-muted-foreground">
                  {pending} pending · {group.items.length} total
                </span>
              </div>
              <div className="space-y-2">
                {group.items.map((note) => <NoteRow key={note.id} note={note} />)}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

> If the `Switch` component doesn't exist at `@/shared/components/ui/switch`, install it from shadcn (`npx shadcn@latest add switch`) or fall back to a `<input type="checkbox" />` with a `<label>`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/iso-docs/pages/IsoNotesAdmin.tsx
git commit -m "feat(iso-docs): add admin notes page"
```

---

## Task 11: Admin route + sidebar entry

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: admin sidebar definition (locate during this task)

- [ ] **Step 1: Add the route**

In `frontend/src/App.tsx`, inside `AdminRoutes()`, add (place near the existing `tracker` block, e.g. just below the closing `</Route>` of the `tracker` group):

```tsx
<Route path="iso/notes" element={<IsoNotesAdmin />} />
```

Add the import at the top of `App.tsx`:

```ts
import IsoNotesAdmin from './modules/iso-docs/pages/IsoNotesAdmin';
```

- [ ] **Step 2: Locate the admin sidebar source and add entry**

Find the file that defines the admin sidebar links:

```bash
cd frontend && grep -rn "admin/global-scores\|admin/notifications\|/admin/tracker" src/core/components/ src/core/pages/ | head -20
```

Add a new section/entry pointing to `/admin/iso/notes` titled "ISO" (group) → "Notes". Match the surrounding pattern (icon, label, `to` prop). Use `MessageSquare` icon from lucide-react for consistency with the node-view button.

- [ ] **Step 3: Manual smoke test**

1. Navigate to `/admin/iso/notes` as admin → page renders.
2. Toggle "Show completed" → list updates, URL `?done=1`.
3. Edit a note inline, save → content updates.
4. Mark done → moves out of the default view.
5. Click the node title link → navigates to that ISO doc node.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx <admin sidebar file>
git commit -m "feat(iso-docs): wire admin notes route and sidebar entry"
```

---

## Task 12: Frontend tests for NotesPanel

**Files:**
- Create: `frontend/src/modules/iso-docs/components/__tests__/NotesPanel.test.tsx`

- [ ] **Step 1: Look at an existing component test for the standard pattern**

```bash
cd frontend && ls src/modules/iso-docs/components/__tests__/ 2>/dev/null || find src -path "*__tests__*" -name "*.test.tsx" | head -5
```

Pick one nearby (e.g. `MetadataEditDialog.test.tsx` if it exists) and mirror the React Query / MSW / vitest patterns it uses. Below is a template — adjust the test harness to match the project's existing conventions:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NotesPanel } from '../NotesPanel';
import { isoDocNotesApi } from '../../services/notes';

vi.mock('../../services/notes');

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

describe('NotesPanel', () => {
  it('renders empty state when no notes', async () => {
    vi.mocked(isoDocNotesApi.list).mockResolvedValue([]);
    render(wrap(<NotesPanel nodeId="n1" />));
    await waitFor(() => expect(screen.getByText(/no notes yet/i)).toBeInTheDocument());
  });

  it('creates a note when typing and clicking Add', async () => {
    vi.mocked(isoDocNotesApi.list).mockResolvedValue([]);
    vi.mocked(isoDocNotesApi.create).mockResolvedValue({
      id: 'x', node_id: 'n1', content: 'hello', done: false,
      done_at: null, done_by_id: null, done_by_name: null,
      created_by_id: 'u1', created_by_name: 'Test', created_at: '2026-04-13T00:00:00Z',
      updated_at: '2026-04-13T00:00:00Z',
    });
    render(wrap(<NotesPanel nodeId="n1" />));
    fireEvent.change(screen.getByPlaceholderText(/add a note/i), { target: { value: 'hello' } });
    fireEvent.click(screen.getByRole('button', { name: /add note/i }));
    await waitFor(() =>
      expect(isoDocNotesApi.create).toHaveBeenCalledWith('n1', { content: 'hello' }),
    );
  });
});
```

- [ ] **Step 2: Run tests**

```bash
cd frontend && npm test -- NotesPanel
```

Expected: tests pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/iso-docs/components/__tests__/NotesPanel.test.tsx
git commit -m "test(iso-docs): add NotesPanel tests"
```

---

## Task 13: Final integration check + push

- [ ] **Step 1: Run the full backend test suite for the iso_docs slice**

```bash
cd backend && pytest tests/iso_docs -v
```

Expected: all green.

- [ ] **Step 2: Run frontend typecheck and lint**

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

Expected: no errors.

- [ ] **Step 3: Push to dev**

```bash
git push origin dev
```

---

## Self-Review Notes

- **Spec coverage:** every requirement from the spec is covered:
  - Notes table + cascade delete (Tasks 1–2).
  - Markdown long text (Task 2: `Text` column; frontend renders via `DocViewer`).
  - Hidden behind a button + add/done/delete in node view (Tasks 8–9).
  - Admin page grouped by node, default pending only, edit/delete/done (Tasks 10–11).
  - Editor-only access (`IsoDocsEditor` on every endpoint; `isEditor` gates on the frontend).
- **Type consistency:** `IsoDocNote` matches the backend `NoteResponse`; `AdminIsoDocNote` extends with `node_title` / `node_slug`. Hook names (`useNodeNotes`, `useAllNotes`, `useCreateNote`, `useUpdateNote`, `useDeleteNote`) are consistent across tasks.
- **Pending unknowns flagged inline:**
  - Task 10 notes the `Switch` shadcn component may need to be installed.
  - Task 11 leaves the exact admin sidebar file to be located via grep, since the prior exploration didn't surface a single sidebar definition file.
