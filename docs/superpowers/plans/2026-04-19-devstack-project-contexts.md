# DevStack Project Contexts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build DevStack Project Contexts — per-project private `CLAUDE.md` distribution with bidirectional sync (pull-automatic, push-explicit) and LLM-mediated merge. Spec: `docs/superpowers/specs/2026-04-19-devstack-project-contexts-design.md`.

**Architecture:** New table `devstack_project_contexts` (slug ↔ VizzHub project mapping). Backend is a dumb GitHub blob store with optimistic-locked commit push — no merge logic server-side. Three new MCP tools (`list`, `get` with `at_sha`, `update` with `expected_remote_sha`). Push uses the existing command-queue infrastructure with auto-approval in the same DB transaction. LLM does all merge intelligence in the skill.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic (backend), httpx for GitHub API, FastMCP (MCP server), React 18 + TanStack Query + shadcn/ui (frontend), pytest + vitest.

**Key references:**
- Existing pattern for CRUD: `backend/app/modules/devstack/api/entries.py`, `backend/app/modules/devstack/models/entry.py`
- Existing MCP tool file to extend: `mcp_server/tools/devstack.py`
- Command queue: `mcp_server/services/command_service.py` — `CommandService.enqueue()` signature with kw-only args (`module`, `action`, `target`, `payload`, `summary`, `user_id`)
- MCP user context: `mcp_server/data/base.py` — `get_mcp_user()` → `McpUserContext` (has `user_id`, `email`; NO display name → fetch from `UserDB`)
- Frontend sidebar: `frontend/src/core/components/layout/AppSidebar.tsx` — `DEVSTACK_TABS` const
- Permission gating: `usePermission(Action.DEVSTACK_MANAGE)` / `<Can>` — see `CLAUDE.md` §8

---

## Phase 1 — Backend foundation

### Task 1: Config constants

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Locate the Settings class**

Open `backend/app/config.py` and find the `Settings` Pydantic class. Note where existing GitHub-related settings live (there's already a GitHub token setting for the catalog).

- [ ] **Step 2: Add the three new settings**

Add inside the `Settings` class, grouping them near other GitHub/DevStack settings:

```python
    devstack_project_contexts_repo: str = "Vizzuality/project-contexts"
    # Owner/name of the private GitHub repo hosting per-project CLAUDE.md files.
    # Backend must have a GitHub token with contents:read + contents:write on this repo.

    devstack_project_contexts_committer_name: str = "VizzHub Bot"
    devstack_project_contexts_committer_email: str = "bot@vizzuality.com"
    # Committer identity used on every commit pushed by the backend to the
    # project-contexts repo. The author is the proposing dev (from the MCP
    # session JWT); the committer is always this bot identity.
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(devstack): add project-contexts repo + committer config"
```

---

### Task 2: Database model + migration

**Files:**
- Create: `backend/app/modules/devstack/models/project_context.py`
- Modify: `backend/app/modules/devstack/models/__init__.py` (if the module re-exports models; check first)
- Create: `backend/alembic/versions/062_devstack_proj_ctx.py`

- [ ] **Step 1: Write the model**

Create `backend/app/modules/devstack/models/project_context.py`:

```python
"""Project-context model: links a VizzHub project to a folder in the
private `project-contexts` repo holding its CLAUDE.md."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DevstackProjectContextDB(Base):
    """Per-project private CLAUDE.md registration.

    Slug is globally unique and immutable after creation — used as the folder
    name inside the private `project-contexts` monorepo. Project link is
    NOT NULL and RESTRICTs project deletion while a context exists.
    """

    __tablename__ = "devstack_project_contexts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    slug: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Create the migration file**

Create `backend/alembic/versions/062_devstack_proj_ctx.py` (revision ID 22 chars, well under the 32-char limit). Use the down_revision that matches the current head. Run `alembic heads` first to confirm:

```bash
cd backend && alembic heads
```

Expected: prints the current head revision (should be `061_devstack_sec` or later).

Now write the migration (adjust `down_revision` if `alembic heads` showed something different):

```python
"""Add devstack_project_contexts table.

Revision ID: 062_devstack_proj_ctx
Revises: 061_devstack_sec
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "062_devstack_proj_ctx"
down_revision = "061_devstack_sec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devstack_project_contexts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_devstack_project_contexts_slug"),
    )
    op.create_index(
        "ix_devstack_project_contexts_slug",
        "devstack_project_contexts",
        ["slug"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_devstack_project_contexts_slug",
        table_name="devstack_project_contexts",
    )
    op.drop_table("devstack_project_contexts")
```

- [ ] **Step 3: Run migration against local DB**

```bash
cd backend && alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade 061_devstack_sec -> 062_devstack_proj_ctx`.

- [ ] **Step 4: Verify the table was created correctly**

```bash
cd backend && python -c "
import asyncio
from app.database import engine
from sqlalchemy import inspect

async def main():
    async with engine.connect() as conn:
        def _inspect(sync_conn):
            insp = inspect(sync_conn)
            return insp.get_columns('devstack_project_contexts')
        cols = await conn.run_sync(_inspect)
        for c in cols:
            print(c['name'], c['type'], 'NULL' if c['nullable'] else 'NOT NULL')

asyncio.run(main())
"
```

Expected output includes: `id UUID NOT NULL`, `slug VARCHAR(64) NOT NULL`, `project_id UUID NOT NULL`, `description TEXT NULL`, `created_at TIMESTAMP WITH TIME ZONE NOT NULL`, `updated_at TIMESTAMP WITH TIME ZONE NOT NULL`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/devstack/models/project_context.py \
        backend/alembic/versions/062_devstack_proj_ctx.py
git commit -m "feat(devstack): add devstack_project_contexts table"
```

---

### Task 3: CRUD service + tests

**Files:**
- Create: `backend/app/modules/devstack/services/project_context_service.py`
- Create: `backend/tests/modules/devstack/test_project_context_service.py`

- [ ] **Step 1: Write the failing test for list**

Create `backend/tests/modules/devstack/test_project_context_service.py`:

```python
"""Tests for DevstackProjectContextService."""

import pytest
from uuid import uuid4

from app.core.models.project import Project
from app.modules.devstack.models.project_context import DevstackProjectContextDB
from app.modules.devstack.services.project_context_service import (
    DevstackProjectContextService,
    DuplicateSlugError,
    SlugImmutableError,
    ProjectAlreadyLinkedError,
)


@pytest.fixture
async def sample_project(db):
    project = Project(name="Acme Corp")
    db.add(project)
    await db.flush()
    return project


async def test_create_and_list(db, sample_project):
    svc = DevstackProjectContextService(db)
    ctx = await svc.create(
        slug="acme-corp",
        project_id=sample_project.id,
        description="Private notes for Acme",
    )
    assert ctx.slug == "acme-corp"
    assert ctx.project_id == sample_project.id

    listed = await svc.list()
    assert len(listed) == 1
    assert listed[0].slug == "acme-corp"


async def test_create_duplicate_slug_raises(db, sample_project):
    svc = DevstackProjectContextService(db)
    await svc.create(slug="acme-corp", project_id=sample_project.id, description=None)
    with pytest.raises(DuplicateSlugError):
        await svc.create(slug="acme-corp", project_id=sample_project.id, description=None)


async def test_create_project_already_linked_raises(db, sample_project):
    svc = DevstackProjectContextService(db)
    await svc.create(slug="acme-corp", project_id=sample_project.id, description=None)
    with pytest.raises(ProjectAlreadyLinkedError):
        await svc.create(slug="acme-second", project_id=sample_project.id, description=None)


async def test_update_only_description(db, sample_project):
    svc = DevstackProjectContextService(db)
    ctx = await svc.create(slug="acme-corp", project_id=sample_project.id, description="old")
    updated = await svc.update(ctx.id, description="new")
    assert updated.description == "new"
    assert updated.slug == "acme-corp"


async def test_update_rejects_slug_change(db, sample_project):
    """Slug is immutable — the API must not expose a way to change it.
    Calling update with a slug kwarg raises SlugImmutableError."""
    svc = DevstackProjectContextService(db)
    ctx = await svc.create(slug="acme-corp", project_id=sample_project.id, description=None)
    with pytest.raises(SlugImmutableError):
        await svc.update(ctx.id, slug="renamed")


async def test_delete(db, sample_project):
    svc = DevstackProjectContextService(db)
    ctx = await svc.create(slug="acme-corp", project_id=sample_project.id, description=None)
    await svc.delete(ctx.id)
    assert await svc.list() == []


async def test_get_by_slug(db, sample_project):
    svc = DevstackProjectContextService(db)
    await svc.create(slug="acme-corp", project_id=sample_project.id, description=None)
    ctx = await svc.get_by_slug("acme-corp")
    assert ctx is not None
    assert ctx.slug == "acme-corp"
    assert await svc.get_by_slug("missing") is None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && pytest tests/modules/devstack/test_project_context_service.py -v
```

Expected: `ImportError: cannot import name 'DevstackProjectContextService'`.

- [ ] **Step 3: Implement the service**

Create `backend/app/modules/devstack/services/project_context_service.py`:

```python
"""CRUD service for DevstackProjectContextDB.

Domain rules:
- slug is globally unique and immutable after creation.
- project_id is NOT NULL and each project may have at most one context.
- Only `description` is editable via update().
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devstack.models.project_context import DevstackProjectContextDB


class DuplicateSlugError(Exception):
    """Raised when attempting to create a context with an already-used slug."""


class ProjectAlreadyLinkedError(Exception):
    """Raised when the target project already has a linked context."""


class SlugImmutableError(Exception):
    """Raised when an update attempts to change slug or project_id."""


class DevstackProjectContextService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self) -> list[DevstackProjectContextDB]:
        result = await self.db.execute(
            select(DevstackProjectContextDB).order_by(DevstackProjectContextDB.slug)
        )
        return list(result.scalars().all())

    async def get(self, context_id: UUID) -> DevstackProjectContextDB | None:
        return await self.db.get(DevstackProjectContextDB, context_id)

    async def get_by_slug(self, slug: str) -> DevstackProjectContextDB | None:
        result = await self.db.execute(
            select(DevstackProjectContextDB).where(
                DevstackProjectContextDB.slug == slug
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        slug: str,
        project_id: UUID,
        description: str | None,
    ) -> DevstackProjectContextDB:
        if await self.get_by_slug(slug) is not None:
            raise DuplicateSlugError(slug)

        existing = await self.db.execute(
            select(DevstackProjectContextDB).where(
                DevstackProjectContextDB.project_id == project_id
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ProjectAlreadyLinkedError(project_id)

        ctx = DevstackProjectContextDB(
            slug=slug,
            project_id=project_id,
            description=description,
        )
        self.db.add(ctx)
        await self.db.flush()
        return ctx

    async def update(
        self,
        context_id: UUID,
        *,
        description: str | None = None,
        slug: str | None = None,
        project_id: UUID | None = None,
    ) -> DevstackProjectContextDB:
        if slug is not None or project_id is not None:
            raise SlugImmutableError(
                "slug and project_id are immutable after creation"
            )

        ctx = await self.db.get(DevstackProjectContextDB, context_id)
        if ctx is None:
            raise KeyError(context_id)

        ctx.description = description
        await self.db.flush()
        return ctx

    async def delete(self, context_id: UUID) -> None:
        ctx = await self.db.get(DevstackProjectContextDB, context_id)
        if ctx is not None:
            await self.db.delete(ctx)
            await self.db.flush()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/modules/devstack/test_project_context_service.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/devstack/services/project_context_service.py \
        backend/tests/modules/devstack/test_project_context_service.py
git commit -m "feat(devstack): add project-context CRUD service"
```

---

### Task 4: REST API

**Files:**
- Create: `backend/app/modules/devstack/api/project_contexts.py`
- Modify: `backend/app/modules/devstack/router.py`
- Create: `backend/tests/modules/devstack/test_project_contexts_api.py`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/modules/devstack/test_project_contexts_api.py`:

```python
"""Tests for /api/devstack/project-contexts endpoints."""

import pytest
from uuid import uuid4

from app.core.models.project import Project


@pytest.fixture
async def sample_project(db):
    project = Project(name="Acme Corp")
    db.add(project)
    await db.flush()
    return project


async def test_list_empty(client_manager):
    resp = await client_manager.get("/api/devstack/project-contexts")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_and_list(client_manager, sample_project):
    resp = await client_manager.post(
        "/api/devstack/project-contexts",
        json={
            "slug": "acme-corp",
            "project_id": str(sample_project.id),
            "description": "notes",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "acme-corp"
    assert body["project_id"] == str(sample_project.id)
    assert body["project_name"] == "Acme Corp"

    resp = await client_manager.get("/api/devstack/project-contexts")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["project_name"] == "Acme Corp"


async def test_create_invalid_slug_rejected(client_manager, sample_project):
    resp = await client_manager.post(
        "/api/devstack/project-contexts",
        json={
            "slug": "Acme Corp",  # uppercase + space
            "project_id": str(sample_project.id),
            "description": None,
        },
    )
    assert resp.status_code == 422


async def test_create_duplicate_slug_409(client_manager, sample_project):
    body = {
        "slug": "acme-corp",
        "project_id": str(sample_project.id),
        "description": None,
    }
    await client_manager.post("/api/devstack/project-contexts", json=body)

    other_project_resp = await client_manager.post(
        "/api/projects", json={"name": "Other"}
    )
    other_project_id = other_project_resp.json()["id"]
    body["project_id"] = other_project_id
    resp = await client_manager.post("/api/devstack/project-contexts", json=body)
    assert resp.status_code == 409


async def test_update_description(client_manager, sample_project):
    create = await client_manager.post(
        "/api/devstack/project-contexts",
        json={"slug": "acme-corp", "project_id": str(sample_project.id), "description": "old"},
    )
    context_id = create.json()["id"]

    resp = await client_manager.put(
        f"/api/devstack/project-contexts/{context_id}",
        json={"description": "new"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "new"


async def test_update_slug_rejected_400(client_manager, sample_project):
    create = await client_manager.post(
        "/api/devstack/project-contexts",
        json={"slug": "acme-corp", "project_id": str(sample_project.id), "description": None},
    )
    context_id = create.json()["id"]

    resp = await client_manager.put(
        f"/api/devstack/project-contexts/{context_id}",
        json={"slug": "renamed"},
    )
    assert resp.status_code == 400


async def test_delete(client_manager, sample_project):
    create = await client_manager.post(
        "/api/devstack/project-contexts",
        json={"slug": "acme-corp", "project_id": str(sample_project.id), "description": None},
    )
    context_id = create.json()["id"]
    resp = await client_manager.delete(f"/api/devstack/project-contexts/{context_id}")
    assert resp.status_code == 204


async def test_viewer_can_list_but_not_create(client_viewer, sample_project):
    """client_viewer has DEVSTACK_VIEW but not DEVSTACK_MANAGE."""
    resp = await client_viewer.get("/api/devstack/project-contexts")
    assert resp.status_code == 200

    resp = await client_viewer.post(
        "/api/devstack/project-contexts",
        json={"slug": "acme-corp", "project_id": str(sample_project.id), "description": None},
    )
    assert resp.status_code == 403
```

Note: this test file assumes `client_manager` and `client_viewer` fixtures exist (an authenticated test client with DEVSTACK_MANAGE and DEVSTACK_VIEW roles respectively). If they don't, look at existing files in `backend/tests/modules/devstack/` for the canonical fixture name and adapt.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/modules/devstack/test_project_contexts_api.py -v
```

Expected: all fail with 404 (route not registered).

- [ ] **Step 3: Implement the API module**

Create `backend/app/modules/devstack/api/project_contexts.py`:

```python
"""REST API for per-project private CLAUDE.md registrations."""

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.api.deps import DBSession
from app.core.models.project import Project
from app.modules.devstack.api.deps import DevstackManager, DevstackViewer
from app.modules.devstack.models.project_context import DevstackProjectContextDB
from app.modules.devstack.services.project_context_service import (
    DevstackProjectContextService,
    DuplicateSlugError,
    ProjectAlreadyLinkedError,
)

router = APIRouter(prefix="/devstack/project-contexts", tags=["devstack-contexts"])

SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")


class ProjectContextResponse(BaseModel):
    id: UUID
    slug: str
    project_id: UUID
    project_name: str | None
    description: str | None


class ProjectContextCreate(BaseModel):
    slug: Annotated[str, Field(min_length=1, max_length=64)]
    project_id: UUID
    description: str | None = None

    @field_validator("slug")
    @classmethod
    def _slug_shape(cls, v: str) -> str:
        if not SLUG_PATTERN.fullmatch(v):
            raise ValueError("slug must match ^[a-z0-9-]+$")
        return v


class ProjectContextUpdate(BaseModel):
    description: str | None = None
    # slug and project_id are intentionally absent — immutable after creation.
    # Extra keys are rejected via model_config below.
    model_config = {"extra": "forbid"}


def _to_response(
    ctx: DevstackProjectContextDB, project_name: str | None
) -> ProjectContextResponse:
    return ProjectContextResponse(
        id=ctx.id,
        slug=ctx.slug,
        project_id=ctx.project_id,
        project_name=project_name,
        description=ctx.description,
    )


@router.get("", responses={403: {"description": "Not authorized"}})
async def list_project_contexts(
    db: DBSession, user: DevstackViewer
) -> list[ProjectContextResponse]:
    result = await db.execute(
        select(DevstackProjectContextDB, Project.name)
        .join(Project, DevstackProjectContextDB.project_id == Project.id)
        .order_by(DevstackProjectContextDB.slug)
    )
    return [_to_response(ctx, name) for ctx, name in result.all()]


@router.post(
    "",
    status_code=201,
    responses={
        403: {"description": "Not authorized"},
        409: {"description": "Slug already exists or project already linked"},
        422: {"description": "Invalid slug shape"},
    },
)
async def create_project_context(
    body: ProjectContextCreate, db: DBSession, user: DevstackManager
) -> ProjectContextResponse:
    svc = DevstackProjectContextService(db)
    try:
        ctx = await svc.create(
            slug=body.slug,
            project_id=body.project_id,
            description=body.description,
        )
    except DuplicateSlugError:
        raise HTTPException(status_code=409, detail=f"Slug '{body.slug}' already exists")
    except ProjectAlreadyLinkedError:
        raise HTTPException(
            status_code=409,
            detail=f"Project {body.project_id} already has a linked context",
        )

    project = await db.get(Project, body.project_id)
    if project is None:
        raise HTTPException(status_code=422, detail="Project not found")
    return _to_response(ctx, project.name)


@router.get(
    "/{context_id}",
    responses={
        403: {"description": "Not authorized"},
        404: {"description": "Project context not found"},
    },
)
async def get_project_context(
    context_id: UUID, db: DBSession, user: DevstackViewer
) -> ProjectContextResponse:
    svc = DevstackProjectContextService(db)
    ctx = await svc.get(context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Project context not found")
    project = await db.get(Project, ctx.project_id)
    return _to_response(ctx, project.name if project else None)


@router.put(
    "/{context_id}",
    responses={
        400: {"description": "Attempt to change immutable field"},
        403: {"description": "Not authorized"},
        404: {"description": "Project context not found"},
    },
)
async def update_project_context(
    context_id: UUID,
    body: ProjectContextUpdate,
    db: DBSession,
    user: DevstackManager,
) -> ProjectContextResponse:
    # Reject unknown/forbidden fields early — Pydantic forbids extras in the
    # model, so reaching here means body only contains description. Still
    # defence-in-depth against future model drift:
    svc = DevstackProjectContextService(db)
    try:
        ctx = await svc.update(context_id, description=body.description)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project context not found")
    project = await db.get(Project, ctx.project_id)
    return _to_response(ctx, project.name if project else None)


@router.delete(
    "/{context_id}",
    status_code=204,
    responses={
        403: {"description": "Not authorized"},
        404: {"description": "Project context not found"},
    },
)
async def delete_project_context(
    context_id: UUID, db: DBSession, user: DevstackManager
) -> None:
    svc = DevstackProjectContextService(db)
    ctx = await svc.get(context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Project context not found")
    await svc.delete(context_id)
```

- [ ] **Step 4: Register the sub-router**

Modify `backend/app/modules/devstack/router.py`:

```python
"""Devstack module router — aggregates all devstack sub-routers."""

from fastapi import APIRouter

from app.modules.devstack.api import entries as entries_router
from app.modules.devstack.api import project_contexts as project_contexts_router

router = APIRouter()

router.routes.extend(entries_router.router.routes)
router.routes.extend(project_contexts_router.router.routes)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest tests/modules/devstack/test_project_contexts_api.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/devstack/api/project_contexts.py \
        backend/app/modules/devstack/router.py \
        backend/tests/modules/devstack/test_project_contexts_api.py
git commit -m "feat(devstack): REST API for project-contexts CRUD"
```

---

## Phase 2 — GitHub I/O

### Task 5: GitHub blob fetch (HEAD + at_sha)

**Files:**
- Create: `backend/app/modules/devstack/services/project_context_github.py`
- Create: `backend/tests/modules/devstack/test_project_context_github.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/modules/devstack/test_project_context_github.py`:

```python
"""Tests for ProjectContextGitHubClient."""

import base64
import pytest
import respx
import httpx

from app.modules.devstack.services.project_context_github import (
    ProjectContextGitHubClient,
    NotFoundError,
    NoContentError,
)


@pytest.fixture
def client():
    return ProjectContextGitHubClient(
        repo="Vizzuality/project-contexts",
        token="fake-token",
        committer_name="VizzHub Bot",
        committer_email="bot@vizzuality.com",
    )


@respx.mock
async def test_fetch_head_returns_content_and_sha(client):
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/contents/acme-corp/CLAUDE.md"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "abc123",
                "content": base64.b64encode(b"# Acme").decode(),
                "encoding": "base64",
            },
        )
    )
    content, sha = await client.fetch_head("acme-corp")
    assert content == "# Acme"
    assert sha == "abc123"


@respx.mock
async def test_fetch_head_404(client):
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/contents/missing/CLAUDE.md"
    ).mock(return_value=httpx.Response(404))
    with pytest.raises(NotFoundError):
        await client.fetch_head("missing")


@respx.mock
async def test_fetch_at_sha_returns_historical_blob(client):
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/blobs/oldsha"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "oldsha",
                "content": base64.b64encode(b"# Old Acme").decode(),
                "encoding": "base64",
            },
        )
    )
    content = await client.fetch_at_sha("oldsha")
    assert content == "# Old Acme"


@respx.mock
async def test_fetch_at_sha_404(client):
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/blobs/nope"
    ).mock(return_value=httpx.Response(404))
    with pytest.raises(NotFoundError):
        await client.fetch_at_sha("nope")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/modules/devstack/test_project_context_github.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement the client (fetch only for now)**

Create `backend/app/modules/devstack/services/project_context_github.py`:

```python
"""GitHub I/O for per-project CLAUDE.md files in the private monorepo.

Two responsibilities: (1) fetch blobs by HEAD or by explicit SHA, and
(2) push commits via the Git Data API with optimistic locking. No merge
logic — all merge intelligence is LLM-side in the skill.
"""

import base64

import httpx


GITHUB_API = "https://api.github.com"


class NotFoundError(Exception):
    """Slug folder / CLAUDE.md / blob does not exist."""


class NoContentError(Exception):
    """Folder exists but has no CLAUDE.md at HEAD."""


class FetchError(Exception):
    """Generic GitHub API read failure (network, auth, quota)."""


class CommitError(Exception):
    """GitHub rejected the push (write path)."""


class ProjectContextGitHubClient:
    """Thin wrapper around GitHub's REST + Git Data APIs.

    One instance per request — do not share across async tasks without
    care. The httpx.AsyncClient is created per method call for simplicity;
    optimise later if needed.
    """

    def __init__(
        self,
        *,
        repo: str,
        token: str,
        committer_name: str,
        committer_email: str,
    ):
        self.repo = repo
        self.token = token
        self.committer_name = committer_name
        self.committer_email = committer_email

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def fetch_head(self, slug: str) -> tuple[str, str]:
        """Return (content, sha) of `<slug>/CLAUDE.md` at the default branch."""
        url = f"{GITHUB_API}/repos/{self.repo}/contents/{slug}/CLAUDE.md"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers())

        if resp.status_code == 404:
            raise NotFoundError(slug)
        if resp.status_code >= 400:
            raise FetchError(f"GitHub returned {resp.status_code}: {resp.text}")

        data = resp.json()
        if data.get("encoding") != "base64":
            raise FetchError(f"Unexpected encoding: {data.get('encoding')}")
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]

    async def fetch_at_sha(self, blob_sha: str) -> str:
        """Return the content of a specific blob by SHA (immutable in Git)."""
        url = f"{GITHUB_API}/repos/{self.repo}/git/blobs/{blob_sha}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers())

        if resp.status_code == 404:
            raise NotFoundError(blob_sha)
        if resp.status_code >= 400:
            raise FetchError(f"GitHub returned {resp.status_code}: {resp.text}")

        data = resp.json()
        if data.get("encoding") != "base64":
            raise FetchError(f"Unexpected encoding: {data.get('encoding')}")
        return base64.b64decode(data["content"]).decode("utf-8")
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest tests/modules/devstack/test_project_context_github.py -v
```

Expected: 4 tests PASS (fetch_head_* and fetch_at_sha_*).

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/devstack/services/project_context_github.py \
        backend/tests/modules/devstack/test_project_context_github.py
git commit -m "feat(devstack): GitHub client — blob fetch (head + at_sha)"
```

---

### Task 6: GitHub commit push with optimistic lock

**Files:**
- Modify: `backend/app/modules/devstack/services/project_context_github.py`
- Modify: `backend/tests/modules/devstack/test_project_context_github.py`

- [ ] **Step 1: Add failing tests for commit push**

Append to `backend/tests/modules/devstack/test_project_context_github.py`:

```python
@respx.mock
async def test_push_success_returns_new_sha(client):
    # 1. get default branch head
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts"
    ).mock(return_value=httpx.Response(200, json={"default_branch": "main"}))
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/ref/heads/main"
    ).mock(return_value=httpx.Response(200, json={"object": {"sha": "commit-sha-1"}}))
    # 2. verify current blob SHA matches expected
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/contents/acme-corp/CLAUDE.md"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "expected-blob-sha",
                "content": base64.b64encode(b"old").decode(),
                "encoding": "base64",
            },
        )
    )
    # 3. create blob
    respx.post(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/blobs"
    ).mock(return_value=httpx.Response(201, json={"sha": "new-blob-sha"}))
    # 4. get base commit to extract its tree
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/commits/commit-sha-1"
    ).mock(return_value=httpx.Response(200, json={"tree": {"sha": "base-tree-sha"}}))
    # 5. create tree
    respx.post(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/trees"
    ).mock(return_value=httpx.Response(201, json={"sha": "new-tree-sha"}))
    # 6. create commit
    respx.post(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/commits"
    ).mock(return_value=httpx.Response(201, json={"sha": "commit-sha-2"}))
    # 7. update ref
    respx.patch(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/refs/heads/main"
    ).mock(return_value=httpx.Response(200, json={"object": {"sha": "commit-sha-2"}}))

    new_sha = await client.push(
        slug="acme-corp",
        content="new content",
        expected_remote_sha="expected-blob-sha",
        author_name="Miguel",
        author_email="miguel@vizzuality.com",
        message="Update acme-corp/CLAUDE.md via VizzHub (miguel@vizzuality.com)",
    )
    assert new_sha == "new-blob-sha"


@respx.mock
async def test_push_optimistic_lock_fails_when_remote_advanced(client):
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts"
    ).mock(return_value=httpx.Response(200, json={"default_branch": "main"}))
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/ref/heads/main"
    ).mock(return_value=httpx.Response(200, json={"object": {"sha": "commit-sha-1"}}))
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/contents/acme-corp/CLAUDE.md"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "actually-newer-sha",  # remote advanced
                "content": base64.b64encode(b"x").decode(),
                "encoding": "base64",
            },
        )
    )
    from app.modules.devstack.services.project_context_github import OptimisticLockError
    with pytest.raises(OptimisticLockError) as excinfo:
        await client.push(
            slug="acme-corp",
            content="new",
            expected_remote_sha="expected-blob-sha",
            author_name="Miguel",
            author_email="miguel@vizzuality.com",
            message="msg",
        )
    assert excinfo.value.current_sha == "actually-newer-sha"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/modules/devstack/test_project_context_github.py -v
```

Expected: 2 new tests fail with `AttributeError: 'ProjectContextGitHubClient' object has no attribute 'push'`.

- [ ] **Step 3: Implement push**

Add to `backend/app/modules/devstack/services/project_context_github.py`:

```python
class OptimisticLockError(Exception):
    """Remote blob SHA no longer matches the expected value.

    The caller must re-fetch the remote, re-run the LLM-mediated merge,
    and retry with the new expected_remote_sha.
    """

    def __init__(self, current_sha: str):
        super().__init__(f"Remote advanced to {current_sha}")
        self.current_sha = current_sha
```

Then add this method to `ProjectContextGitHubClient`:

```python
    async def push(
        self,
        *,
        slug: str,
        content: str,
        expected_remote_sha: str,
        author_name: str,
        author_email: str,
        message: str,
    ) -> str:
        """Commit a new version of `<slug>/CLAUDE.md` if the remote is still
        at `expected_remote_sha`. Returns the new blob SHA.

        Raises OptimisticLockError if the remote advanced — caller must merge
        against the new head and retry.

        Commit attribution: author = dev (from JWT), committer = bot
        (from config). Preserves `git blame` correctness in the private repo.
        """
        headers = self._headers()
        path = f"{slug}/CLAUDE.md"

        async with httpx.AsyncClient(timeout=30, headers=headers) as http:
            # 1. Discover default branch.
            repo_resp = await http.get(f"{GITHUB_API}/repos/{self.repo}")
            if repo_resp.status_code >= 400:
                raise FetchError(f"repo metadata: {repo_resp.status_code}")
            default_branch = repo_resp.json()["default_branch"]

            # 2. Current ref SHA (parent commit).
            ref_resp = await http.get(
                f"{GITHUB_API}/repos/{self.repo}/git/ref/heads/{default_branch}"
            )
            if ref_resp.status_code >= 400:
                raise FetchError(f"get ref: {ref_resp.status_code}")
            parent_commit_sha = ref_resp.json()["object"]["sha"]

            # 3. Optimistic lock: current blob SHA must match expected.
            contents_resp = await http.get(
                f"{GITHUB_API}/repos/{self.repo}/contents/{path}"
            )
            if contents_resp.status_code == 404:
                raise NotFoundError(slug)
            if contents_resp.status_code >= 400:
                raise FetchError(f"contents: {contents_resp.status_code}")
            current_blob_sha = contents_resp.json()["sha"]
            if current_blob_sha != expected_remote_sha:
                raise OptimisticLockError(current_blob_sha)

            # 4. Create blob.
            blob_resp = await http.post(
                f"{GITHUB_API}/repos/{self.repo}/git/blobs",
                json={
                    "content": base64.b64encode(content.encode("utf-8")).decode(),
                    "encoding": "base64",
                },
            )
            if blob_resp.status_code >= 400:
                raise CommitError(f"create blob: {blob_resp.status_code}")
            new_blob_sha = blob_resp.json()["sha"]

            # 5. Fetch parent commit's tree SHA.
            parent_commit_resp = await http.get(
                f"{GITHUB_API}/repos/{self.repo}/git/commits/{parent_commit_sha}"
            )
            if parent_commit_resp.status_code >= 400:
                raise CommitError(f"get parent commit: {parent_commit_resp.status_code}")
            base_tree_sha = parent_commit_resp.json()["tree"]["sha"]

            # 6. Create tree with the new blob replacing the old one at `path`.
            tree_resp = await http.post(
                f"{GITHUB_API}/repos/{self.repo}/git/trees",
                json={
                    "base_tree": base_tree_sha,
                    "tree": [
                        {
                            "path": path,
                            "mode": "100644",
                            "type": "blob",
                            "sha": new_blob_sha,
                        }
                    ],
                },
            )
            if tree_resp.status_code >= 400:
                raise CommitError(f"create tree: {tree_resp.status_code}")
            new_tree_sha = tree_resp.json()["sha"]

            # 7. Create commit with author=dev, committer=bot.
            commit_resp = await http.post(
                f"{GITHUB_API}/repos/{self.repo}/git/commits",
                json={
                    "message": message,
                    "tree": new_tree_sha,
                    "parents": [parent_commit_sha],
                    "author": {"name": author_name, "email": author_email},
                    "committer": {
                        "name": self.committer_name,
                        "email": self.committer_email,
                    },
                },
            )
            if commit_resp.status_code >= 400:
                raise CommitError(f"create commit: {commit_resp.status_code}")
            new_commit_sha = commit_resp.json()["sha"]

            # 8. Update ref (fast-forward).
            update_ref_resp = await http.patch(
                f"{GITHUB_API}/repos/{self.repo}/git/refs/heads/{default_branch}",
                json={"sha": new_commit_sha, "force": False},
            )
            if update_ref_resp.status_code >= 400:
                raise CommitError(f"update ref: {update_ref_resp.status_code}")

        return new_blob_sha
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest tests/modules/devstack/test_project_context_github.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/devstack/services/project_context_github.py \
        backend/tests/modules/devstack/test_project_context_github.py
git commit -m "feat(devstack): GitHub client — optimistic-locked commit push"
```

---

## Phase 3 — MCP tools

### Task 7: MCP data-layer helpers

**Files:**
- Create: `mcp_server/data/project_contexts.py`
- Create: `mcp_server/tests/test_project_contexts_data.py`

**Context for the engineer:** The MCP data layer is a thin async API over the read-only DB session + external IO. Follow the pattern in `mcp_server/data/devstack.py`. The helpers here DO NOT handle permissions (that's the `@mcp_requires` decorator on the tool) or command-queue (that's the tool too). They just fetch + call GitHub.

- [ ] **Step 1: Add failing tests for data helpers**

Create `mcp_server/tests/test_project_contexts_data.py`:

```python
"""Tests for the MCP project-contexts data layer."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from mcp_server.data import project_contexts as pc_data


async def test_list_returns_slugs_only():
    session = MagicMock()
    session.execute = AsyncMock()
    # Simulate two rows: (slug, description, project_name)
    session.execute.return_value.all.return_value = [
        ("acme-corp", "Acme notes", "Acme Corp"),
        ("gov-x", None, "Gov Project X"),
    ]
    result = await pc_data.list_contexts(session)
    assert result == [
        {"slug": "acme-corp", "description": "Acme notes", "project_name": "Acme Corp"},
        {"slug": "gov-x", "description": None, "project_name": "Gov Project X"},
    ]


async def test_get_uses_fetch_head_when_no_at_sha(monkeypatch):
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value.scalar_one_or_none.return_value = MagicMock(
        slug="acme-corp"
    )

    fake_client = MagicMock()
    fake_client.fetch_head = AsyncMock(return_value=("# Acme", "blob-sha-1"))
    fake_client.fetch_at_sha = AsyncMock()
    monkeypatch.setattr(pc_data, "_build_github_client", lambda: fake_client)

    result = await pc_data.get_context(session, slug="acme-corp", at_sha=None)
    assert result == {
        "target_path": "CLAUDE.md",
        "content": "# Acme",
        "devstack_sha": "blob-sha-1",
        "slug": "acme-corp",
    }
    fake_client.fetch_head.assert_awaited_once_with("acme-corp")
    fake_client.fetch_at_sha.assert_not_called()


async def test_get_uses_fetch_at_sha_when_provided(monkeypatch):
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value.scalar_one_or_none.return_value = MagicMock(
        slug="acme-corp"
    )

    fake_client = MagicMock()
    fake_client.fetch_head = AsyncMock()
    fake_client.fetch_at_sha = AsyncMock(return_value="# Base Acme")
    monkeypatch.setattr(pc_data, "_build_github_client", lambda: fake_client)

    result = await pc_data.get_context(session, slug="acme-corp", at_sha="old-sha")
    assert result == {
        "target_path": "CLAUDE.md",
        "content": "# Base Acme",
        "devstack_sha": "old-sha",
        "slug": "acme-corp",
    }
    fake_client.fetch_at_sha.assert_awaited_once_with("old-sha")


async def test_get_slug_not_registered_raises(monkeypatch):
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(pc_data.ContextNotFoundError):
        await pc_data.get_context(session, slug="missing", at_sha=None)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest mcp_server/tests/test_project_contexts_data.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the data layer**

Create `mcp_server/data/project_contexts.py`:

```python
"""MCP data-layer helpers for DevStack project contexts.

Lightweight read/push helpers; tool-level logic (permissions, command queue,
JSON serialisation) is handled in `mcp_server/tools/devstack.py`.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.models.project import Project
from app.modules.devstack.models.project_context import DevstackProjectContextDB
from app.modules.devstack.services.project_context_github import (
    NotFoundError as GitHubNotFoundError,
    OptimisticLockError,
    ProjectContextGitHubClient,
)


class ContextNotFoundError(Exception):
    """Slug is not registered in VizzHub."""


def _build_github_client() -> ProjectContextGitHubClient:
    return ProjectContextGitHubClient(
        repo=settings.devstack_project_contexts_repo,
        token=settings.devstack_github_token,  # reuse existing catalog token
        committer_name=settings.devstack_project_contexts_committer_name,
        committer_email=settings.devstack_project_contexts_committer_email,
    )


async def list_contexts(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(
            DevstackProjectContextDB.slug,
            DevstackProjectContextDB.description,
            Project.name,
        )
        .join(Project, DevstackProjectContextDB.project_id == Project.id)
        .order_by(DevstackProjectContextDB.slug)
    )
    return [
        {"slug": slug, "description": desc, "project_name": name}
        for slug, desc, name in result.all()
    ]


async def _get_or_raise(
    session: AsyncSession, slug: str
) -> DevstackProjectContextDB:
    result = await session.execute(
        select(DevstackProjectContextDB).where(
            DevstackProjectContextDB.slug == slug
        )
    )
    ctx = result.scalar_one_or_none()
    if ctx is None:
        raise ContextNotFoundError(slug)
    return ctx


async def get_context(
    session: AsyncSession, *, slug: str, at_sha: str | None
) -> dict:
    """Fetch remote CLAUDE.md content, either HEAD or a specific historical blob.

    Returns {target_path, content, devstack_sha, slug}.
    """
    await _get_or_raise(session, slug)
    client = _build_github_client()
    if at_sha is None:
        try:
            content, sha = await client.fetch_head(slug)
        except GitHubNotFoundError:
            raise ContextNotFoundError(f"{slug}/CLAUDE.md not found in repo")
    else:
        try:
            content = await client.fetch_at_sha(at_sha)
        except GitHubNotFoundError:
            raise ContextNotFoundError(f"blob {at_sha}")
        sha = at_sha
    return {
        "target_path": "CLAUDE.md",
        "content": content,
        "devstack_sha": sha,
        "slug": slug,
    }


async def push_context(
    session: AsyncSession,
    *,
    slug: str,
    content: str,
    expected_remote_sha: str,
    author_name: str,
    author_email: str,
) -> dict:
    """Publish new content. Returns one of three shapes:
      {status: "committed", new_sha}
      {status: "up_to_date", remote_sha}
      {status: "conflict", remote_sha}  # optimistic lock failed

    The caller is responsible for creating the auto-approved command-queue
    row (this helper does not touch the queue).
    """
    await _get_or_raise(session, slug)
    client = _build_github_client()

    try:
        current_content, current_sha = await client.fetch_head(slug)
    except GitHubNotFoundError:
        raise ContextNotFoundError(f"{slug}/CLAUDE.md not found in repo")

    if current_content == content:
        return {"status": "up_to_date", "remote_sha": current_sha}

    if current_sha != expected_remote_sha:
        return {"status": "conflict", "remote_sha": current_sha}

    message = (
        f"Update {slug}/CLAUDE.md via VizzHub ({author_email})"
    )
    try:
        new_sha = await client.push(
            slug=slug,
            content=content,
            expected_remote_sha=expected_remote_sha,
            author_name=author_name,
            author_email=author_email,
            message=message,
        )
    except OptimisticLockError as exc:
        # Extremely narrow race window between our own fetch_head and push.
        return {"status": "conflict", "remote_sha": exc.current_sha}

    return {"status": "committed", "new_sha": new_sha}
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest mcp_server/tests/test_project_contexts_data.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/data/project_contexts.py \
        mcp_server/tests/test_project_contexts_data.py
git commit -m "feat(mcp): project-contexts data layer (list/get/push)"
```

---

### Task 8: MCP tools — list + get

**Files:**
- Modify: `mcp_server/tools/devstack.py`
- Create: `mcp_server/tests/test_project_contexts_tools.py`

- [ ] **Step 1: Add failing tool tests**

Create `mcp_server/tests/test_project_contexts_tools.py`:

```python
"""Tests for MCP project-contexts tools."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.tools.devstack import (
    devstack_list_project_contexts,
    devstack_get_project_context,
)


@pytest.fixture(autouse=True)
def set_user():
    """Set a valid MCP user context for all tests."""
    from mcp_server.data.base import McpUserContext, _mcp_user_context
    token = _mcp_user_context.set(
        McpUserContext(
            user_id="00000000-0000-0000-0000-000000000001",
            email="dev@vizzuality.com",
            roles=["user"],
            permissions=["devstack:view"],
        )
    )
    yield
    _mcp_user_context.reset(token)


async def test_list_returns_json_array():
    with patch("mcp_server.tools.devstack.get_read_session") as mock_session_ctx:
        session = MagicMock()
        mock_session_ctx.return_value.__aenter__.return_value = session

        with patch(
            "mcp_server.tools.devstack.project_contexts_data.list_contexts",
            new=AsyncMock(return_value=[{"slug": "acme-corp", "description": None, "project_name": "Acme"}]),
        ):
            out = await devstack_list_project_contexts()

    parsed = json.loads(out)
    assert parsed == [{"slug": "acme-corp", "description": None, "project_name": "Acme"}]


async def test_get_with_at_sha_forwards_param():
    with patch("mcp_server.tools.devstack.get_read_session") as mock_session_ctx:
        mock_session_ctx.return_value.__aenter__.return_value = MagicMock()

        fake_result = {
            "target_path": "CLAUDE.md",
            "content": "# Acme base",
            "devstack_sha": "old-sha",
            "slug": "acme-corp",
        }
        get_mock = AsyncMock(return_value=fake_result)
        with patch(
            "mcp_server.tools.devstack.project_contexts_data.get_context",
            new=get_mock,
        ):
            out = await devstack_get_project_context(
                slug="acme-corp", at_sha="old-sha"
            )

    assert json.loads(out) == fake_result
    # Verify at_sha was forwarded
    call_kwargs = get_mock.await_args.kwargs
    assert call_kwargs["at_sha"] == "old-sha"


async def test_get_unknown_slug_returns_error_json():
    from mcp_server.data.project_contexts import ContextNotFoundError
    with patch("mcp_server.tools.devstack.get_read_session") as mock_session_ctx:
        mock_session_ctx.return_value.__aenter__.return_value = MagicMock()

        with patch(
            "mcp_server.tools.devstack.project_contexts_data.get_context",
            new=AsyncMock(side_effect=ContextNotFoundError("missing")),
        ):
            out = await devstack_get_project_context(slug="missing")

    parsed = json.loads(out)
    assert parsed["code"] == "NOT_FOUND"
    assert "missing" in parsed["error"]
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd backend && pytest mcp_server/tests/test_project_contexts_tools.py -v
```

Expected: ImportError or AttributeError.

- [ ] **Step 3: Add tools to `mcp_server/tools/devstack.py`**

At the top of the file, add imports:

```python
from mcp_server.data import project_contexts as project_contexts_data
from mcp_server.data.project_contexts import ContextNotFoundError
```

After the existing tool definitions (before `register_devstack_tools`), add:

```python
@mcp_requires("devstack:view")
async def devstack_list_project_contexts() -> str:
    """List registered per-project private CLAUDE.md contexts.

    Returns a JSON array of {slug, description, project_name}. Use for
    discovery when the dev doesn't know the slug of the context linked
    to the current project.
    """
    async with get_read_session() as session:
        data = await project_contexts_data.list_contexts(session)
    return json.dumps(data, default=str)


@mcp_requires("devstack:view")
async def devstack_get_project_context(
    slug: str,
    at_sha: str | None = None,
) -> str:
    """Fetch a project's private CLAUDE.md content.

    With `at_sha` omitted, returns the current HEAD content. With `at_sha`,
    returns the content of that specific immutable blob — used by the skill
    to fetch the common-ancestor ("base") version during an LLM-mediated
    merge at session start.

    Returns JSON: {target_path: "CLAUDE.md", content, devstack_sha, slug}.

    Args:
        slug: The registered context slug.
        at_sha: Optional blob SHA to fetch a historical version.
    """
    try:
        async with get_read_session() as session:
            data = await project_contexts_data.get_context(
                session, slug=slug, at_sha=at_sha
            )
    except ContextNotFoundError as exc:
        return json.dumps({"error": str(exc), "code": "NOT_FOUND"})

    return json.dumps(data, default=str)
```

Register them in `register_devstack_tools`:

```python
def register_devstack_tools(server: FastMCP) -> None:
    """Register all DevStack tools on the given MCP server instance."""
    server.tool()(devstack_get_catalog)
    server.tool()(devstack_discover)
    server.tool()(devstack_get_tech_radar)
    server.tool()(devstack_get_installable)
    server.tool()(devstack_list_project_contexts)
    server.tool()(devstack_get_project_context)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest mcp_server/tests/test_project_contexts_tools.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/tools/devstack.py \
        mcp_server/tests/test_project_contexts_tools.py
git commit -m "feat(mcp): list + get project-context tools"
```

---

### Task 9: MCP update tool + command-queue auto-approve

**Files:**
- Modify: `mcp_server/services/command_service.py` (add `enqueue_approved` method)
- Modify: `mcp_server/tools/devstack.py` (add update tool)
- Modify: `mcp_server/tests/test_project_contexts_tools.py` (append update tests)
- Modify: `mcp_server/data/project_contexts.py` (no change — the data helper is already correct)

**Context for the engineer:** The existing command-queue flow creates rows in "pending" status and requires a separate `approve_command` call. For DevStack project-context updates we want the row created *already approved* in the same transaction as the GitHub push — see spec section "Auto-approve details". Add a new service method rather than calling `enqueue` + `approve` back-to-back (which would allow a row to briefly exist as pending in the DB).

Before writing, quickly read `mcp_server/services/command_service.py` end-to-end (it's short) to see how `approve` works today. Note the exact field names on `CommandDB` for approval state (likely `status`, `approved_by`, `approved_at` — verify).

- [ ] **Step 1: Add `enqueue_approved` method to CommandService**

Append to `mcp_server/services/command_service.py`:

```python
    async def enqueue_approved(
        self,
        *,
        module: str,
        action: str,
        target: str | None,
        payload: dict,
        summary: str,
        user_id: UUID,
    ) -> CommandDB:
        """Enqueue a command row that is already in the `approved` state.

        Used by flows where the act of invoking the tool IS the approval —
        the audit record is created after the side-effect has succeeded,
        inside the same DB transaction, so the queue is never inconsistent
        with the external system.

        Do NOT use this for human-in-the-loop commands. The normal `enqueue`
        path remains the default for anything that should wait for explicit
        human approval.
        """
        cmd = CommandDB(
            module=module,
            action=action,
            target=target,
            payload=payload,
            summary=summary,
            requested_by=user_id,
            # The three following field names are the ones currently on
            # CommandDB. Engineer: verify by reading the model; adjust if
            # different. If there is a single `status` enum, set it to
            # "approved". If there are `approved_by` + `approved_at`, set
            # them here too.
            status="approved",
            approved_by=user_id,
            approved_at=func.now(),
        )
        self._session.add(cmd)
        await self._session.flush()
        await self._session.refresh(cmd)
        return cmd
```

If `CommandDB` uses different field names than assumed above, adapt. Import `func` from `sqlalchemy` at top of the file if not already present.

- [ ] **Step 2: Add a test for the new service method**

Create or extend `mcp_server/tests/test_command_service.py` with:

```python
async def test_enqueue_approved_sets_status_immediately(db):
    from mcp_server.services.command_service import CommandService
    from uuid import uuid4

    svc = CommandService(db)
    user_id = uuid4()
    cmd = await svc.enqueue_approved(
        module="devstack",
        action="update_project_context",
        target="acme-corp",
        payload={"sha": "abc123"},
        summary="Update acme-corp CLAUDE.md",
        user_id=user_id,
    )
    assert cmd.status == "approved"
    assert cmd.approved_by == user_id
    assert cmd.approved_at is not None
```

Run:

```bash
cd backend && pytest mcp_server/tests/test_command_service.py::test_enqueue_approved_sets_status_immediately -v
```

Expected: PASS.

- [ ] **Step 3: Add failing test for the update tool**

Append to `mcp_server/tests/test_project_contexts_tools.py`:

```python
async def test_update_committed_creates_approved_command(monkeypatch):
    from mcp_server.tools.devstack import devstack_update_project_context

    # Fake user display-name lookup
    user_db = MagicMock()
    user_db.name = "Miguel Mendoza"
    user_db.email = "miguel@vizzuality.com"

    with patch("mcp_server.tools.devstack.get_write_session") as mock_session_ctx:
        session = MagicMock()
        session.get = AsyncMock(return_value=user_db)
        mock_session_ctx.return_value.__aenter__.return_value = session

        push_mock = AsyncMock(return_value={"status": "committed", "new_sha": "new-sha"})
        monkeypatch.setattr(
            "mcp_server.tools.devstack.project_contexts_data.push_context",
            push_mock,
        )
        enqueue_mock = AsyncMock(return_value=MagicMock(id="cmd-uuid"))
        monkeypatch.setattr(
            "mcp_server.tools.devstack.CommandService.enqueue_approved",
            enqueue_mock,
        )

        out = await devstack_update_project_context(
            slug="acme-corp",
            content="# New content",
            expected_remote_sha="old-sha",
        )

    parsed = json.loads(out)
    assert parsed["status"] == "committed"
    assert parsed["new_sha"] == "new-sha"
    assert parsed["command_id"] == "cmd-uuid"
    # Author passed to push_context is the MCP user
    push_kwargs = push_mock.await_args.kwargs
    assert push_kwargs["author_email"] == "dev@vizzuality.com"


async def test_update_conflict_does_not_enqueue(monkeypatch):
    from mcp_server.tools.devstack import devstack_update_project_context

    user_db = MagicMock()
    user_db.name = "Miguel"
    user_db.email = "miguel@vizzuality.com"

    with patch("mcp_server.tools.devstack.get_write_session") as mock_session_ctx:
        session = MagicMock()
        session.get = AsyncMock(return_value=user_db)
        mock_session_ctx.return_value.__aenter__.return_value = session

        monkeypatch.setattr(
            "mcp_server.tools.devstack.project_contexts_data.push_context",
            AsyncMock(return_value={"status": "conflict", "remote_sha": "newer-sha"}),
        )
        enqueue_mock = AsyncMock()
        monkeypatch.setattr(
            "mcp_server.tools.devstack.CommandService.enqueue_approved",
            enqueue_mock,
        )

        out = await devstack_update_project_context(
            slug="acme-corp", content="# x", expected_remote_sha="stale"
        )

    parsed = json.loads(out)
    assert parsed["status"] == "conflict"
    assert parsed["remote_sha"] == "newer-sha"
    enqueue_mock.assert_not_awaited()
```

Run to confirm failure:

```bash
cd backend && pytest mcp_server/tests/test_project_contexts_tools.py -v
```

Expected: 2 new tests fail with ImportError / AttributeError.

- [ ] **Step 4: Implement the update tool**

Add to `mcp_server/tools/devstack.py` (imports and tool):

```python
from uuid import UUID

from mcp_server.data.base import get_mcp_user, get_write_session
from mcp_server.services.command_service import CommandService
from app.core.models.user import UserDB


@mcp_requires("devstack:view")
async def devstack_update_project_context(
    slug: str,
    content: str,
    expected_remote_sha: str,
) -> str:
    """Publish an update to a project's private CLAUDE.md.

    Only call this when the dev explicitly asks to publish ("publica los
    cambios", "push my CLAUDE.md changes"). The push uses optimistic locking
    against `expected_remote_sha`:
      - If remote still matches → commit with author=<dev>, committer=bot,
        create an auto-approved command-queue entry, return
        {status: "committed", new_sha, command_id}.
      - If remote already equals content → no-op, return
        {status: "up_to_date", remote_sha}.
      - If remote advanced → return {status: "conflict", remote_sha};
        you must re-fetch the new head, re-run the LLM-mediated merge,
        and retry with the new expected_remote_sha.

    Args:
        slug: Registered context slug.
        content: The full new content of CLAUDE.md (not a diff).
        expected_remote_sha: The blob SHA you last synced against. Optimistic
            lock — used to detect concurrent writes.
    """
    user = get_mcp_user()

    async with get_write_session() as session:
        # Fetch the proposing user's display name (author field on commit).
        user_row = await session.get(UserDB, UUID(user.user_id))
        author_name = user_row.name if user_row and user_row.name else user.email
        author_email = user.email

        result = await project_contexts_data.push_context(
            session,
            slug=slug,
            content=content,
            expected_remote_sha=expected_remote_sha,
            author_name=author_name,
            author_email=author_email,
        )

        if result["status"] == "committed":
            cmd_svc = CommandService(session)
            cmd = await cmd_svc.enqueue_approved(
                module="devstack",
                action="update_project_context",
                target=slug,
                payload={
                    "slug": slug,
                    "new_sha": result["new_sha"],
                    # NOTE: do not persist `content` here — it would leak
                    # private CLAUDE.md content into the audit log. The
                    # GitHub commit is the authoritative record of content.
                },
                summary=f"Published update to {slug}/CLAUDE.md",
                user_id=UUID(user.user_id),
            )
            result["command_id"] = str(cmd.id)

    return json.dumps(result, default=str)
```

Register in `register_devstack_tools`:

```python
    server.tool()(devstack_update_project_context)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest mcp_server/tests/test_project_contexts_tools.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp_server/services/command_service.py \
        mcp_server/tests/test_command_service.py \
        mcp_server/tools/devstack.py \
        mcp_server/tests/test_project_contexts_tools.py
git commit -m "feat(mcp): update project-context tool with auto-approved queue row"
```

---

## Phase 4 — Frontend

### Task 10: Frontend types + service + hooks

**Files:**
- Create: `frontend/src/modules/devstack/types/projectContexts.ts`
- Create: `frontend/src/modules/devstack/services/projectContexts.ts`
- Create: `frontend/src/modules/devstack/hooks/useProjectContexts.ts`
- Modify: `frontend/src/core/hooks/queryKeys.ts` (add `devstackProjectContexts` keys)

- [ ] **Step 1: Write types**

Create `frontend/src/modules/devstack/types/projectContexts.ts`:

```typescript
export interface ProjectContext {
  id: string;
  slug: string;
  project_id: string;
  project_name: string | null;
  description: string | null;
}

export interface ProjectContextCreate {
  slug: string;
  project_id: string;
  description: string | null;
}

export interface ProjectContextUpdate {
  description: string | null;
}
```

- [ ] **Step 2: Write service**

Create `frontend/src/modules/devstack/services/projectContexts.ts`:

```typescript
import api from '@/core/services/client';
import type {
  ProjectContext,
  ProjectContextCreate,
  ProjectContextUpdate,
} from '../types/projectContexts';

export const projectContextsApi = {
  list: async (): Promise<ProjectContext[]> => {
    const response = await api.get<ProjectContext[]>(
      '/devstack/project-contexts',
    );
    return response.data;
  },

  get: async (id: string): Promise<ProjectContext> => {
    const response = await api.get<ProjectContext>(
      `/devstack/project-contexts/${id}`,
    );
    return response.data;
  },

  create: async (data: ProjectContextCreate): Promise<ProjectContext> => {
    const response = await api.post<ProjectContext>(
      '/devstack/project-contexts',
      data,
    );
    return response.data;
  },

  update: async (
    id: string,
    data: ProjectContextUpdate,
  ): Promise<ProjectContext> => {
    const response = await api.put<ProjectContext>(
      `/devstack/project-contexts/${id}`,
      data,
    );
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/devstack/project-contexts/${id}`);
  },
};
```

- [ ] **Step 3: Add query keys**

Modify `frontend/src/core/hooks/queryKeys.ts` — add a `devstackProjectContexts` namespace following the existing pattern (look at `devstack` entries for the shape):

```typescript
export const queryKeys = {
  // ... existing keys ...
  devstackProjectContexts: {
    all: ['devstack-project-contexts'] as const,
    list: () => [...queryKeys.devstackProjectContexts.all, 'list'] as const,
    detail: (id: string) =>
      [...queryKeys.devstackProjectContexts.all, 'detail', id] as const,
  },
};
```

- [ ] **Step 4: Write hooks**

Create `frontend/src/modules/devstack/hooks/useProjectContexts.ts`:

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { projectContextsApi } from '../services/projectContexts';
import type {
  ProjectContextCreate,
  ProjectContextUpdate,
} from '../types/projectContexts';

export function useProjectContexts() {
  return useQuery({
    queryKey: queryKeys.devstackProjectContexts.list(),
    queryFn: () => projectContextsApi.list(),
  });
}

export function useProjectContext(id: string) {
  return useQuery({
    queryKey: queryKeys.devstackProjectContexts.detail(id),
    queryFn: () => projectContextsApi.get(id),
    enabled: !!id,
  });
}

export function useCreateProjectContext() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ProjectContextCreate) => projectContextsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.devstackProjectContexts.all,
      });
    },
  });
}

export function useUpdateProjectContext() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ProjectContextUpdate }) =>
      projectContextsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.devstackProjectContexts.all,
      });
    },
  });
}

export function useDeleteProjectContext() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => projectContextsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.devstackProjectContexts.all,
      });
    },
  });
}
```

- [ ] **Step 5: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/modules/devstack/types/projectContexts.ts \
        frontend/src/modules/devstack/services/projectContexts.ts \
        frontend/src/modules/devstack/hooks/useProjectContexts.ts \
        frontend/src/core/hooks/queryKeys.ts
git commit -m "feat(devstack): frontend types + service + hooks for project contexts"
```

---

### Task 11: List page + delete dialog

**Files:**
- Create: `frontend/src/modules/devstack/pages/ProjectContexts.tsx`
- Create: `frontend/src/modules/devstack/pages/ProjectContexts.test.tsx`

- [ ] **Step 1: Write failing test**

Create `frontend/src/modules/devstack/pages/ProjectContexts.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import ProjectContexts from './ProjectContexts';

vi.mock('@/core/permissions', () => ({
  usePermission: vi.fn(() => true),
  Action: { DEVSTACK_MANAGE: 'devstack:manage' },
}));

vi.mock('../hooks/useProjectContexts', () => ({
  useProjectContexts: () => ({
    data: [
      {
        id: '1',
        slug: 'acme-corp',
        project_id: 'p1',
        project_name: 'Acme Corp',
        description: 'Notes',
      },
    ],
    isLoading: false,
  }),
  useDeleteProjectContext: () => ({ mutate: vi.fn(), isPending: false }),
}));

function renderPage() {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProjectContexts />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ProjectContexts page', () => {
  it('renders list of contexts', () => {
    renderPage();
    expect(screen.getByText('acme-corp')).toBeInTheDocument();
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
  });

  it('shows New button when user has DEVSTACK_MANAGE', () => {
    renderPage();
    expect(
      screen.getByRole('button', { name: /new project context/i }),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test (fails: file not found)**

```bash
cd frontend && npx vitest run src/modules/devstack/pages/ProjectContexts.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement the page**

Create `frontend/src/modules/devstack/pages/ProjectContexts.tsx`:

```tsx
import { useState } from 'react';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { usePermission, Action } from '@/core/permissions';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
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
import {
  useProjectContexts,
  useDeleteProjectContext,
} from '../hooks/useProjectContexts';
import { ProjectContextForm } from '../components/ProjectContextForm';
import type { ProjectContext } from '../types/projectContexts';

export default function ProjectContexts(): JSX.Element {
  const canManage = usePermission(Action.DEVSTACK_MANAGE);
  const { data, isLoading } = useProjectContexts();
  const deleteMutation = useDeleteProjectContext();

  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<ProjectContext | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectContext | null>(null);

  const handleDelete = (): void => {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    });
  };

  if (isLoading) return <LoadingSpinner />;

  const contexts = data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Project Contexts</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Per-project private CLAUDE.md files synced via DevStack.
          </p>
        </div>
        {canManage && (
          <Button
            size="sm"
            onClick={() => {
              setEditTarget(null);
              setFormOpen(true);
            }}
          >
            <Plus className="w-4 h-4 mr-1.5" />
            New Project Context
          </Button>
        )}
      </div>

      {contexts.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-muted-foreground">No project contexts yet</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Project</TableHead>
                  <TableHead>Slug</TableHead>
                  <TableHead>Description</TableHead>
                  {canManage && (
                    <TableHead className="w-[100px]">Actions</TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {contexts.map((ctx) => (
                  <TableRow key={ctx.id}>
                    <TableCell className="font-medium">
                      {ctx.project_name ?? '—'}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {ctx.slug}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {ctx.description ?? '—'}
                    </TableCell>
                    {canManage && (
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditTarget(ctx);
                              setFormOpen(true);
                            }}
                          >
                            <Pencil className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => setDeleteTarget(ctx)}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {canManage && formOpen && (
        <ProjectContextForm
          context={editTarget}
          onClose={() => {
            setFormOpen(false);
            setEditTarget(null);
          }}
        />
      )}

      <AlertDialog
        open={canManage && deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete project context?</AlertDialogTitle>
            <AlertDialogDescription>
              This unlinks &quot;{deleteTarget?.slug}&quot; from VizzHub. The
              private CLAUDE.md file in the GitHub repo is not deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault();
                handleDelete();
              }}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
```

Note: `ProjectContextForm` doesn't exist yet — Task 12 creates it. The import will make the test fail until Task 12 is done. To let Task 11 stand on its own, add a placeholder component inline: create `frontend/src/modules/devstack/components/ProjectContextForm.tsx` as an empty stub that accepts the props and renders nothing. It will be filled out in Task 12.

Stub file contents:

```tsx
import type { ProjectContext } from '../types/projectContexts';

interface ProjectContextFormProps {
  readonly context: ProjectContext | null;
  readonly onClose: () => void;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function ProjectContextForm(_props: ProjectContextFormProps): JSX.Element {
  return <></>;
}
```

- [ ] **Step 4: Run tests and type-check**

```bash
cd frontend && npx vitest run src/modules/devstack/pages/ProjectContexts.test.tsx && npx tsc --noEmit
```

Expected: 2 tests PASS; no TS errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/devstack/pages/ProjectContexts.tsx \
        frontend/src/modules/devstack/pages/ProjectContexts.test.tsx \
        frontend/src/modules/devstack/components/ProjectContextForm.tsx
git commit -m "feat(devstack): frontend list page for project contexts"
```

---

### Task 12: Form component (create + edit) + sidebar + routing

**Files:**
- Modify: `frontend/src/modules/devstack/components/ProjectContextForm.tsx` (flesh out the stub)
- Modify: `frontend/src/core/components/layout/AppSidebar.tsx` (add sub-entry)
- Modify: `frontend/src/App.tsx` or router file (add route — confirm the routing file's path before editing)
- Create: `frontend/src/modules/devstack/components/ProjectContextForm.test.tsx`

- [ ] **Step 1: Write failing form test**

Create `frontend/src/modules/devstack/components/ProjectContextForm.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectContextForm } from './ProjectContextForm';

vi.mock('@/core/hooks/useProjects', () => ({
  useProjects: () => ({
    data: { items: [{ id: 'p1', name: 'Acme Corp' }] },
  }),
}));

const createMutate = vi.fn();
vi.mock('../hooks/useProjectContexts', () => ({
  useCreateProjectContext: () => ({ mutate: createMutate, isPending: false }),
  useUpdateProjectContext: () => ({ mutate: vi.fn(), isPending: false }),
}));

function renderForm(props: Parameters<typeof ProjectContextForm>[0]) {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <ProjectContextForm {...props} />
    </QueryClientProvider>,
  );
}

describe('ProjectContextForm', () => {
  it('auto-slugs from project name', () => {
    renderForm({ context: null, onClose: vi.fn() });
    fireEvent.click(screen.getByRole('combobox', { name: /project/i }));
    fireEvent.click(screen.getByText('Acme Corp'));
    const slugInput = screen.getByLabelText(/slug/i) as HTMLInputElement;
    expect(slugInput.value).toBe('acme-corp');
  });

  it('disables slug and project in edit mode', () => {
    renderForm({
      context: {
        id: '1',
        slug: 'existing',
        project_id: 'p1',
        project_name: 'Acme Corp',
        description: null,
      },
      onClose: vi.fn(),
    });
    expect(screen.getByLabelText(/slug/i)).toBeDisabled();
  });

  it('rejects invalid slug shape', () => {
    renderForm({ context: null, onClose: vi.fn() });
    const slugInput = screen.getByLabelText(/slug/i);
    fireEvent.change(slugInput, { target: { value: 'Invalid Slug' } });
    fireEvent.click(screen.getByRole('button', { name: /create/i }));
    expect(screen.getByText(/lowercase letters, digits, hyphens/i)).toBeInTheDocument();
    expect(createMutate).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd frontend && npx vitest run src/modules/devstack/components/ProjectContextForm.test.tsx
```

Expected: FAIL (stub renders nothing).

- [ ] **Step 3: Implement the form**

Replace `frontend/src/modules/devstack/components/ProjectContextForm.tsx` with:

```tsx
import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useProjects } from '@/core/hooks/useProjects';
import {
  useCreateProjectContext,
  useUpdateProjectContext,
} from '../hooks/useProjectContexts';
import type { ProjectContext } from '../types/projectContexts';

interface ProjectContextFormProps {
  readonly context: ProjectContext | null;
  readonly onClose: () => void;
}

const SLUG_REGEX = /^[a-z0-9-]+$/;

function slugify(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // strip diacritics
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function ProjectContextForm({
  context,
  onClose,
}: ProjectContextFormProps): JSX.Element {
  const isEdit = context !== null;
  const { data: projectsData } = useProjects();
  const createMutation = useCreateProjectContext();
  const updateMutation = useUpdateProjectContext();

  const [projectId, setProjectId] = useState(context?.project_id ?? '');
  const [slug, setSlug] = useState(context?.slug ?? '');
  const [description, setDescription] = useState(context?.description ?? '');
  const [error, setError] = useState<string | null>(null);

  const handleProjectSelect = (id: string): void => {
    setProjectId(id);
    if (!isEdit) {
      const project = projectsData?.items.find((p) => p.id === id);
      if (project) setSlug(slugify(project.name));
    }
  };

  const handleSubmit = (): void => {
    setError(null);
    if (!isEdit && !SLUG_REGEX.test(slug)) {
      setError(
        'Slug must contain only lowercase letters, digits, hyphens.',
      );
      return;
    }

    if (isEdit && context) {
      updateMutation.mutate(
        { id: context.id, data: { description: description || null } },
        { onSuccess: onClose },
      );
    } else {
      createMutation.mutate(
        {
          slug,
          project_id: projectId,
          description: description || null,
        },
        { onSuccess: onClose },
      );
    }
  };

  const isPending = createMutation.isPending || updateMutation.isPending;
  const canSubmit = isEdit ? true : Boolean(projectId && slug);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEdit ? 'Edit project context' : 'New project context'}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="project">Project</Label>
            <Select
              value={projectId}
              onValueChange={handleProjectSelect}
              disabled={isEdit}
            >
              <SelectTrigger id="project">
                <SelectValue placeholder="Select a project" />
              </SelectTrigger>
              <SelectContent>
                {(projectsData?.items ?? []).map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="slug">Slug</Label>
            <Input
              id="slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              disabled={isEdit}
              placeholder="acme-corp"
            />
            {isEdit && (
              <p className="text-xs text-muted-foreground">
                Slug is immutable after creation. Delete and recreate to rename.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit || isPending}>
            {isPending ? 'Saving...' : isEdit ? 'Save' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Add sidebar sub-entry**

Modify `frontend/src/core/components/layout/AppSidebar.tsx`:

```typescript
const DEVSTACK_TABS = [
  { to: '/devstack', label: 'Catalog' },
  { to: '/devstack/contexts', label: 'Project Contexts' },
] as const;
```

- [ ] **Step 5: Add route**

Find the router configuration (likely `frontend/src/App.tsx` or a file that imports `BrowserRouter`/`Routes`). Add:

```tsx
import ProjectContexts from '@/modules/devstack/pages/ProjectContexts';

// Within <Routes>, inside the authenticated section:
<Route
  path="/devstack/contexts"
  element={
    <PermissionRoute require={Action.DEVSTACK_VIEW}>
      <ProjectContexts />
    </PermissionRoute>
  }
/>
```

Confirm the existing DevStack catalog route's permission wrapper and copy that shape — `PermissionRoute` + `Action.DEVSTACK_VIEW` is typical.

- [ ] **Step 6: Run tests + typecheck + manual dev check**

```bash
cd frontend && npx vitest run src/modules/devstack && npx tsc --noEmit
```

Expected: all form + page tests PASS; no TS errors.

```bash
cd frontend && npm run dev
```

Navigate to `/devstack/contexts` in the browser, confirm the sidebar shows "Project Contexts" under DevStack, create a context with a real project, edit it (slug disabled), delete it.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/modules/devstack/components/ProjectContextForm.tsx \
        frontend/src/modules/devstack/components/ProjectContextForm.test.tsx \
        frontend/src/core/components/layout/AppSidebar.tsx \
        frontend/src/App.tsx
git commit -m "feat(devstack): project-contexts form + sidebar + route"
```

---

## Phase 5 — Skill

### Task 13: Skill document section

**Files:**
- Modify: `Vizzuality/claude-code-standards` repository — `skills/devstack-sync/SKILL.md` (external repo; the engineer opens it via a local clone or GitHub web UI).

**Context for the engineer:** This is the public, distributable skill. The file lives OUTSIDE this vizzhub repo. Clone `Vizzuality/claude-code-standards`, edit the file in a branch, open a PR there. The section below is a self-contained prose addition to `skills/devstack-sync/SKILL.md` — append it after the existing catalog-sync section.

Do NOT put any private project content in the skill. Only procedure.

- [ ] **Step 1: Clone the skill repo if not already done**

```bash
git clone git@github.com:Vizzuality/claude-code-standards.git ~/work/claude-code-standards
cd ~/work/claude-code-standards
git checkout -b feat/project-contexts-section
```

- [ ] **Step 2: Append the new section to `skills/devstack-sync/SKILL.md`**

Add this block at the end of the file (or after the existing catalog-sync section — match existing heading levels):

````markdown
## Per-project private context (optional)

Some projects distribute their `CLAUDE.md` through DevStack Project Contexts instead of committing it to the public repo (NDA, compliance, etc.). This section only applies when the current project has a DevStack context linked.

### Marker files

In the project root, under `.claude/` (always gitignored by this skill):

- **`.claude/.devstack-context`** — present when the project is linked. Format:
  ```
  slug: acme-corp
  sha: <blob SHA of CLAUDE.md at last successful sync>
  local_hash: <sha256 of ./CLAUDE.md at last successful sync>
  ```
- **`.claude/.devstack-skip`** — present when the dev declared no private context (content irrelevant).

Never present both.

### Session-start procedure (pull-automatic)

1. **Dispatch**:
   - `.devstack-context` present → parse slug/sha/local_hash and continue.
   - `.devstack-skip` present → exit silently.
   - Neither → ask the dev exactly once: *"This project has no DevStack context linked. Is there a private context? Reply with the slug (e.g. `acme-corp`) or `N` to skip."* Create the appropriate marker; if slug, continue with no `sha`/`local_hash` yet.

2. **Fetch remote head**: call `devstack_get_project_context(slug)` (no `at_sha`).
   - `NOT_FOUND` → warn *"The context '<slug>' is no longer registered in VizzHub. Your local `./CLAUDE.md` may be stale. Ask me to unlink this project if it no longer applies."* Do NOT delete the local file.
   - Other error → surface and exit.

3. **First sync** (marker has no `sha`/`local_hash`): write the returned content to `./CLAUDE.md` atomically (tempfile + rename), then update the marker with `sha` + `local_hash`.

4. **Compute state**:
   - `local_changed = sha256(current ./CLAUDE.md) != marker.local_hash`
   - `remote_changed = remote_sha != marker.sha`

5. **Decide action**:

   | local | remote | action |
   |:-:|:-:|---|
   | no | no | silent no-op |
   | no | yes | **Fast-forward pull**: atomic write remote content, update marker. |
   | yes | no | Silent; emit one soft reminder: *"You have unpublished changes to this project's CLAUDE.md. Ask me to publish when you're ready."* |
   | yes | yes | **LLM-mediated merge** (step 6). |

6. **LLM-mediated merge**:
   1. Call `devstack_get_project_context(slug, at_sha=marker.sha)` → `base_content`.
   2. Read local `./CLAUDE.md` → `local_content`.
   3. Summarise for the dev in natural language what changed remotely since `base`, what they changed locally since `base`, and where they overlap. Quote concise snippets; be precise.
   4. Propose a merged version. For non-overlapping edits, state how you're combining (e.g. *"keeping both"*). For overlapping edits, surface the tension explicitly and ask: *"Both of you edited X — team now says Y, you had Z. Which stays?"*
   5. **Wait for explicit approval** (*"aprobado"*, *"go ahead"*, etc.) before writing. The dev may tweak the proposal or ask for the raw three versions pasted into chat.
   6. Once approved, write atomically and update marker: `sha = remote_sha`, `local_hash = sha256(merged_content)`.

7. **Gitignore check**: ensure `CLAUDE.md`, `.claude/.devstack-context`, and `.claude/.devstack-skip` are all listed in the project's root `.gitignore`. Append any missing entries on first sync and tell the dev once.

### Push procedure (explicit, natural language)

Triggered by *"publica los cambios del contexto"*, *"push my CLAUDE.md changes"*, *"sync this context"*, or equivalent. No formal command.

1. Read `./CLAUDE.md` → `local_content`. Read `marker.sha` → `expected_remote_sha`.
2. Call `devstack_update_project_context(slug, local_content, expected_remote_sha)`.
3. Handle the three statuses:
   - `up_to_date` → refresh `marker.local_hash = sha256(local_content)`. Tell the dev: *"Your local content already matches the published version — nothing to publish."*
   - `committed` → update marker `sha = new_sha`, `local_hash = sha256(local_content)`. Tell the dev: *"Published. Commit `<new_sha[:7]>` added to the private repo, attributed to you. Command queue entry: `<command_id>`."*
   - `conflict` → remote advanced mid-flight. Call `devstack_get_project_context(slug)` for the new head, re-run the LLM-mediated merge flow (step 6 above) against the new remote, then retry `devstack_update_project_context` with `expected_remote_sha = <new remote_sha>`.

### Linking / unlinking (natural language)

- *"vincula este proyecto al contexto <slug>"* → delete `.devstack-skip` if present; write `slug: <slug>` to `.devstack-context` (no sha yet); run the session-start pull.
- *"desvincula este proyecto de DevStack"* → delete `./CLAUDE.md` and `.devstack-context`; create `.devstack-skip`.

### Notes

- The public-repo `.gitignore` must list `CLAUDE.md` — do not commit project context content to the project's public git history.
- The `./CLAUDE.md` synced by DevStack composes with the dev's personal `~/.claude/CLAUDE.md` (native Claude Code behaviour). Both apply.
- Editors who prefer working outside Claude can clone `Vizzuality/project-contexts` anywhere and edit `<slug>/CLAUDE.md` directly; teammates pick up the change via drift detection on next session.
- All writes to `./CLAUDE.md` must be tempfile + rename (atomic on POSIX) to avoid truncation if multiple sessions race.
````

- [ ] **Step 3: Open PR against `Vizzuality/claude-code-standards`**

```bash
cd ~/work/claude-code-standards
git add skills/devstack-sync/SKILL.md
git commit -m "feat(devstack-sync): add per-project private context procedure"
git push -u origin feat/project-contexts-section
gh pr create --title "devstack-sync: per-project private context procedure" --body "Adds the prose procedure for pull-automatic, push-explicit sync with LLM-mediated merge for per-project private CLAUDE.md files, matching the vizzhub spec 2026-04-19-devstack-project-contexts-design.md."
```

- [ ] **Step 4: Return PR URL to the user**

Report the PR URL in the task summary so the maintainer of `claude-code-standards` can merge.

---

## Phase 6 — Integration & docs

### Task 14: Update `docs/devstack.md`

**Files:**
- Modify: `docs/devstack.md`

- [ ] **Step 1: Locate and extend**

Open `docs/devstack.md`. Add a new top-level section "Project Contexts" after the existing sections describing the catalog. Contents:

```markdown
## Project Contexts (private CLAUDE.md distribution)

For projects where `CLAUDE.md` cannot be committed to the public repo
(NDA, compliance), DevStack distributes it via a private monorepo and
a bidirectional sync in the `devstack-sync` skill.

### Model

- Table: `devstack_project_contexts` — `slug` (unique), `project_id` (FK, NOT NULL), `description`.
- Private repo: `Vizzuality/project-contexts` (monorepo, one folder per slug).
- Backend token: reuses the existing DevStack GitHub token — needs contents:read + contents:write on the private repo.

### MCP tools

- `devstack_list_project_contexts()` — discovery of slugs.
- `devstack_get_project_context(slug, at_sha=None)` — fetch CLAUDE.md content (HEAD or historical blob).
- `devstack_update_project_context(slug, content, expected_remote_sha)` — optimistic-lock commit push. Auto-approved command-queue row in the same transaction. Commit attributed to the dev (author) with the VizzHub bot as committer.

### Merge strategy

LLM-mediated in the skill, not server-side. On divergence the skill fetches
the common-ancestor blob via `at_sha=base_sha`, presents the three versions
to the dev in prose, proposes a merged version, writes only after explicit
approval. See `docs/superpowers/specs/2026-04-19-devstack-project-contexts-design.md`
for rationale and flows.

### Skill behaviour

Detailed procedure lives in `Vizzuality/claude-code-standards` → `skills/devstack-sync/SKILL.md`. Two marker files in the project root's `.claude/` directory (`.devstack-context` and `.devstack-skip`) drive the state machine.
```

- [ ] **Step 2: Commit**

```bash
git add docs/devstack.md
git commit -m "docs(devstack): document project contexts feature"
```

---

### Task 15: Content-vs-logs integration test

**Files:**
- Create: `backend/tests/integration/test_project_contexts_no_content_in_logs.py`

Rationale: spec requirement — private content must never appear in `structlog` output. This test runs all three MCP tools against mocked GitHub and asserts that distinctive content strings don't appear in captured logs.

- [ ] **Step 1: Write the test**

Create `backend/tests/integration/test_project_contexts_no_content_in_logs.py`:

```python
"""Integration test: private CLAUDE.md content must never appear in logs.

Drives the three MCP tools (list, get, update) through the MCP layer with
mocked GitHub responses containing a distinctive canary string and asserts
the canary does not appear in captured structlog output.
"""

import base64
import pytest
import respx
import httpx
import structlog
from structlog.testing import capture_logs

from mcp_server.tools.devstack import (
    devstack_list_project_contexts,
    devstack_get_project_context,
    devstack_update_project_context,
)

CANARY = "CANARY_PRIVATE_TEXT_9f7e3a1b2c4d"


@pytest.fixture(autouse=True)
def set_user():
    from mcp_server.data.base import McpUserContext, _mcp_user_context
    token = _mcp_user_context.set(
        McpUserContext(
            user_id="00000000-0000-0000-0000-000000000042",
            email="dev@vizzuality.com",
            roles=["user"],
            permissions=["devstack:view"],
        )
    )
    yield
    _mcp_user_context.reset(token)


@pytest.fixture
async def linked_context(db):
    """Insert a context row so the MCP data layer finds it."""
    from app.core.models.project import Project
    from app.modules.devstack.models.project_context import DevstackProjectContextDB

    project = Project(name="Acme")
    db.add(project)
    await db.flush()
    ctx = DevstackProjectContextDB(
        slug="acme-corp",
        project_id=project.id,
        description=None,
    )
    db.add(ctx)
    await db.flush()
    return ctx


@respx.mock
async def test_get_does_not_log_content(linked_context):
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/contents/acme-corp/CLAUDE.md"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "blob-1",
                "content": base64.b64encode(CANARY.encode()).decode(),
                "encoding": "base64",
            },
        )
    )
    with capture_logs() as logs:
        await devstack_get_project_context(slug="acme-corp")

    serialised = repr(logs)
    assert CANARY not in serialised, (
        "Private CLAUDE.md content leaked into structlog output"
    )


@respx.mock
async def test_update_does_not_log_content(linked_context):
    # Mock all the GitHub endpoints used by push
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts"
    ).mock(return_value=httpx.Response(200, json={"default_branch": "main"}))
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/ref/heads/main"
    ).mock(return_value=httpx.Response(200, json={"object": {"sha": "c1"}}))
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/contents/acme-corp/CLAUDE.md"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "expected",
                "content": base64.b64encode(b"old").decode(),
                "encoding": "base64",
            },
        )
    )
    respx.post(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/blobs"
    ).mock(return_value=httpx.Response(201, json={"sha": "new-blob"}))
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/commits/c1"
    ).mock(return_value=httpx.Response(200, json={"tree": {"sha": "t1"}}))
    respx.post(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/trees"
    ).mock(return_value=httpx.Response(201, json={"sha": "new-tree"}))
    respx.post(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/commits"
    ).mock(return_value=httpx.Response(201, json={"sha": "c2"}))
    respx.patch(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/refs/heads/main"
    ).mock(return_value=httpx.Response(200, json={"object": {"sha": "c2"}}))

    with capture_logs() as logs:
        await devstack_update_project_context(
            slug="acme-corp",
            content=CANARY,
            expected_remote_sha="expected",
        )

    serialised = repr(logs)
    assert CANARY not in serialised, (
        "Canary content string leaked into structlog output during push"
    )
```

- [ ] **Step 2: Run test**

```bash
cd backend && pytest tests/integration/test_project_contexts_no_content_in_logs.py -v
```

Expected: both tests PASS. If either fails, the offending log call must be removed (never log `content`, `local_content`, or any body — only `slug`, `sha`, and `status`).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_project_contexts_no_content_in_logs.py
git commit -m "test(devstack): assert private content never appears in structlog"
```

---

## Self-review summary

**Spec coverage:**

| Spec section | Task(s) |
|---|---|
| Data model `DevstackProjectContextDB` | 2 |
| Config constants | 1 |
| Backend CRUD service | 3 |
| REST API (list/create/get/put/delete) | 4 |
| GitHub blob fetch (HEAD + at_sha) | 5 |
| GitHub optimistic-locked commit push | 6 |
| MCP data helpers | 7 |
| MCP tools list + get | 8 |
| MCP tool update + auto-approved command queue | 9 |
| Frontend types/service/hooks | 10 |
| Frontend list page | 11 |
| Frontend form + sidebar + routing | 12 |
| Skill document section | 13 |
| `docs/devstack.md` update | 14 |
| Integration test: content never in logs | 15 |
| Success criterion: unit tests for push/fetch | 5, 6 |
| Success criterion: conversational merge | 13 |
| Success criterion: sidebar sub-entry | 12 |
| Markers logic (`.devstack-context` / `.devstack-skip`) | 13 |

**Type consistency**: `ProjectContext` type (frontend) matches `ProjectContextResponse` shape (backend). `project_context_service.py` methods (`create`, `update`, `delete`, `get_by_slug`, `list`, `get`) used consistently across API and tests. `push_context` return shape (`committed` / `up_to_date` / `conflict`) used identically in `project_contexts.py` data layer, MCP tool, and skill procedure.

**Placeholder scan**: none — every step has complete code or exact commands.

