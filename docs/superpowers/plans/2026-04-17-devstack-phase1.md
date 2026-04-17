# DevStack Module — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the DevStack module (backend + MCP + frontend) so VizzHub can manage a catalog of Claude Code artifacts (skills, commands, agents, configs, plugins) and distribute them to developers via MCP + a local sync skill.

**Architecture:** New backend module `devstack` with two tables (`devstack_entries`, `devstack_user_prefs`), CRUD API (admin-only for entries, user-scoped for prefs), two MCP tools (`devstack_get_catalog`, `devstack_update_sync_status`), and a frontend module with Catalog (admin) and My Environment (all users) pages.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, FastMCP, React, React Query, shadcn/ui, TypeScript.

**Spec:** `docs/devstack.md`

---

### Task 1: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/057_devstack.py`

- [ ] **Step 1: Write migration**

```python
"""Create devstack_entries and devstack_user_prefs tables.

Revision ID: 057_devstack
Revises: 056_report_estimated_true
"""

from alembic import op

revision = "057_devstack"
down_revision = "056_report_estimated_true"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS devstack_entries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            description TEXT NOT NULL,
            type VARCHAR(20) NOT NULL,
            install_method VARCHAR(20) NOT NULL,
            url TEXT,
            package VARCHAR(200),
            package_version VARCHAR(50),
            required BOOLEAN NOT NULL DEFAULT false,
            origin VARCHAR(20) NOT NULL DEFAULT 'internal',
            tech JSONB DEFAULT '[]'::jsonb,
            active BOOLEAN NOT NULL DEFAULT true,
            created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            updated_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_devstack_entries_name UNIQUE (name),
            CONSTRAINT ck_devstack_entries_type
                CHECK (type IN ('skill', 'command', 'plugin', 'config', 'agent')),
            CONSTRAINT ck_devstack_entries_install_method
                CHECK (install_method IN ('github', 'npm')),
            CONSTRAINT ck_devstack_entries_origin
                CHECK (origin IN ('internal', 'external')),
            CONSTRAINT ck_devstack_entries_url_required
                CHECK (install_method != 'github' OR url IS NOT NULL),
            CONSTRAINT ck_devstack_entries_package_required
                CHECK (install_method != 'npm' OR package IS NOT NULL)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS devstack_user_prefs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            entry_id UUID NOT NULL REFERENCES devstack_entries(id) ON DELETE CASCADE,
            enabled BOOLEAN NOT NULL DEFAULT false,
            last_synced_sha VARCHAR(40),
            last_synced_at TIMESTAMPTZ,
            CONSTRAINT uq_devstack_user_prefs_user_entry
                UNIQUE (user_id, entry_id)
        )
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_devstack_user_prefs_user_id"
        " ON devstack_user_prefs (user_id)"
    )

    op.execute(
        "INSERT INTO roles (id, name)"
        " VALUES (gen_random_uuid(), 'devstack_manager')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM roles WHERE name = 'devstack_manager'")
    op.execute("DROP TABLE IF EXISTS devstack_user_prefs")
    op.execute("DROP TABLE IF EXISTS devstack_entries")
```

- [ ] **Step 2: Run migration and verify**

Run: `cd backend && alembic upgrade head`
Expected: Tables created, no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/057_devstack.py
git commit -m "feat(devstack): add migration for entries and user_prefs tables"
```

---

### Task 2: Backend Models

**Files:**
- Create: `backend/app/modules/devstack/__init__.py`
- Create: `backend/app/modules/devstack/models/__init__.py`
- Create: `backend/app/modules/devstack/models/entry.py`
- Create: `backend/app/modules/devstack/models/user_pref.py`

- [ ] **Step 1: Create module directory and models**

`backend/app/modules/devstack/__init__.py` — empty file.

`backend/app/modules/devstack/models/entry.py`:

```python
"""DevStack catalog entry — a distributable Claude Code artifact."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class DevstackEntryDB(Base):
    __tablename__ = "devstack_entries"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    install_method: Mapped[str] = mapped_column(String(20), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    package: Mapped[str | None] = mapped_column(String(200), nullable=True)
    package_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    origin: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="internal"
    )
    tech: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`backend/app/modules/devstack/models/user_pref.py`:

```python
"""DevStack user preference — opt-in + sync state per entry."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class DevstackUserPrefDB(Base):
    __tablename__ = "devstack_user_prefs"
    __table_args__ = (
        UniqueConstraint("user_id", "entry_id", name="uq_devstack_user_prefs_user_entry"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    entry_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("devstack_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_synced_sha: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

`backend/app/modules/devstack/models/__init__.py`:

```python
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.models.user_pref import DevstackUserPrefDB

__all__ = ["DevstackEntryDB", "DevstackUserPrefDB"]
```

- [ ] **Step 2: Verify models load**

Run: `cd backend && python -c "from app.modules.devstack.models import DevstackEntryDB, DevstackUserPrefDB; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/devstack/
git commit -m "feat(devstack): add SQLAlchemy models for entries and user_prefs"
```

---

### Task 3: Pydantic Schemas + Constants

**Files:**
- Create: `backend/app/modules/devstack/constants.py`
- Create: `backend/app/modules/devstack/schemas.py`

- [ ] **Step 1: Write constants**

`backend/app/modules/devstack/constants.py`:

```python
"""Enum constants for the devstack module."""

from enum import StrEnum


class EntryType(StrEnum):
    SKILL = "skill"
    COMMAND = "command"
    PLUGIN = "plugin"
    CONFIG = "config"
    AGENT = "agent"


class InstallMethod(StrEnum):
    GITHUB = "github"
    NPM = "npm"


class EntryOrigin(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
```

- [ ] **Step 2: Write schemas**

`backend/app/modules/devstack/schemas.py`:

```python
"""Pydantic schemas for the devstack module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.devstack.constants import EntryOrigin, EntryType, InstallMethod


class EntryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    type: EntryType
    install_method: InstallMethod
    url: str | None = None
    package: str | None = Field(None, max_length=200)
    package_version: str | None = Field(None, max_length=50)
    required: bool = False
    origin: EntryOrigin = EntryOrigin.INTERNAL
    tech: list[str] = Field(default_factory=list)
    active: bool = True


class EntryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, min_length=1)
    type: EntryType | None = None
    install_method: InstallMethod | None = None
    url: str | None = None
    package: str | None = Field(None, max_length=200)
    package_version: str | None = Field(None, max_length=50)
    required: bool | None = None
    origin: EntryOrigin | None = None
    tech: list[str] | None = None
    active: bool | None = None


class EntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    type: str
    install_method: str
    url: str | None = None
    package: str | None = None
    package_version: str | None = None
    required: bool
    origin: str
    tech: list[str]
    active: bool
    created_at: datetime
    updated_at: datetime


class UserPrefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entry_id: UUID
    enabled: bool
    last_synced_sha: str | None = None
    last_synced_at: datetime | None = None


class UserPrefUpdate(BaseModel):
    enabled: bool
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/devstack/constants.py backend/app/modules/devstack/schemas.py
git commit -m "feat(devstack): add Pydantic schemas and constants"
```

---

### Task 4: Backend Permissions

**Files:**
- Modify: `backend/app/core/permissions/actions.py:28-29` (add devstack actions)

- [ ] **Step 1: Add permission actions**

Add after the `EVENTS_MANAGE` line in `backend/app/core/permissions/actions.py`:

```python
    DEVSTACK_VIEW = "devstack:view"
    DEVSTACK_MANAGE = "devstack:manage"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/permissions/actions.py
git commit -m "feat(devstack): add RBAC permission actions"
```

---

### Task 5: Backend API — CRUD Endpoints

**Files:**
- Create: `backend/app/modules/devstack/api/__init__.py`
- Create: `backend/app/modules/devstack/api/deps.py`
- Create: `backend/app/modules/devstack/api/entries.py`
- Create: `backend/app/modules/devstack/api/prefs.py`

- [ ] **Step 1: Write dependencies**

`backend/app/modules/devstack/api/__init__.py` — empty file.

`backend/app/modules/devstack/api/deps.py`:

```python
"""DevStack API dependencies."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.modules.devstack.models.entry import DevstackEntryDB

DevstackViewer = Annotated[
    TokenData, Depends(require_permission(Action.DEVSTACK_VIEW))
]
DevstackManager = Annotated[
    TokenData, Depends(require_permission(Action.DEVSTACK_MANAGE))
]


async def get_entry_or_404(
    db: AsyncSession, entry_id: UUID
) -> DevstackEntryDB:
    result = await db.execute(
        select(DevstackEntryDB).where(DevstackEntryDB.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry
```

- [ ] **Step 2: Write entries CRUD**

`backend/app/modules/devstack/api/entries.py`:

```python
"""DevStack catalog entries — admin CRUD."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.api.deps import DBSession
from app.modules.devstack.api.deps import (
    DevstackManager,
    DevstackViewer,
    get_entry_or_404,
)
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.schemas import EntryCreate, EntryResponse, EntryUpdate

logger = structlog.get_logger()
router = APIRouter()


@router.get("")
async def list_entries(
    db: DBSession,
    user: DevstackViewer,
    type: str | None = None,
    required: bool | None = None,
    active: bool | None = None,
) -> dict:
    query = select(DevstackEntryDB).order_by(DevstackEntryDB.name)
    count_query = select(func.count()).select_from(DevstackEntryDB)

    if type is not None:
        query = query.where(DevstackEntryDB.type == type)
        count_query = count_query.where(DevstackEntryDB.type == type)
    if required is not None:
        query = query.where(DevstackEntryDB.required == required)
        count_query = count_query.where(DevstackEntryDB.required == required)
    if active is not None:
        query = query.where(DevstackEntryDB.active == active)
        count_query = count_query.where(DevstackEntryDB.active == active)

    result = await db.execute(query)
    total_result = await db.execute(count_query)
    items = result.scalars().all()
    total = total_result.scalar_one()

    return {
        "items": [EntryResponse.model_validate(e) for e in items],
        "total": total,
    }


@router.get("/{entry_id}")
async def get_entry(
    entry_id: UUID, db: DBSession, user: DevstackViewer
) -> EntryResponse:
    entry = await get_entry_or_404(db, entry_id)
    return EntryResponse.model_validate(entry)


@router.post("", status_code=201, responses={409: {"description": "Name conflict"}})
async def create_entry(
    body: EntryCreate, db: DBSession, user: DevstackManager
) -> EntryResponse:
    existing = await db.execute(
        select(DevstackEntryDB).where(DevstackEntryDB.name == body.name)
    )
    if existing.scalar_one_or_none() is not None:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Entry name already exists")

    entry = DevstackEntryDB(
        **body.model_dump(), created_by_id=user.user_id
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    logger.info("devstack_entry_created", entry_id=str(entry.id), name=entry.name)
    return EntryResponse.model_validate(entry)


@router.put("/{entry_id}")
async def update_entry(
    entry_id: UUID,
    body: EntryUpdate,
    db: DBSession,
    user: DevstackManager,
) -> EntryResponse:
    entry = await get_entry_or_404(db, entry_id)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(entry, field, value)
    entry.updated_by_id = user.user_id
    await db.commit()
    await db.refresh(entry)
    logger.info("devstack_entry_updated", entry_id=str(entry_id))
    return EntryResponse.model_validate(entry)


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: UUID, db: DBSession, user: DevstackManager
) -> None:
    entry = await get_entry_or_404(db, entry_id)
    await db.delete(entry)
    await db.commit()
    logger.info("devstack_entry_deleted", entry_id=str(entry_id), name=entry.name)
```

- [ ] **Step 3: Write user preferences endpoint**

`backend/app/modules/devstack/api/prefs.py`:

```python
"""DevStack user preferences — opt-in/opt-out for optional entries."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.api.deps import DBSession
from app.core.auth import CurrentUser
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.models.user_pref import DevstackUserPrefDB
from app.modules.devstack.schemas import UserPrefResponse, UserPrefUpdate

logger = structlog.get_logger()
router = APIRouter()


@router.get("/me/prefs")
async def list_my_prefs(
    db: DBSession, user: CurrentUser
) -> list[UserPrefResponse]:
    result = await db.execute(
        select(DevstackUserPrefDB).where(
            DevstackUserPrefDB.user_id == user.user_id
        )
    )
    prefs = result.scalars().all()
    return [UserPrefResponse.model_validate(p) for p in prefs]


@router.put("/me/prefs/{entry_id}")
async def update_my_pref(
    entry_id: UUID,
    body: UserPrefUpdate,
    db: DBSession,
    user: CurrentUser,
) -> UserPrefResponse:
    entry = await db.execute(
        select(DevstackEntryDB).where(DevstackEntryDB.id == entry_id)
    )
    if entry.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    result = await db.execute(
        select(DevstackUserPrefDB).where(
            DevstackUserPrefDB.user_id == user.user_id,
            DevstackUserPrefDB.entry_id == entry_id,
        )
    )
    pref = result.scalar_one_or_none()

    if pref is None:
        pref = DevstackUserPrefDB(
            user_id=user.user_id, entry_id=entry_id, enabled=body.enabled
        )
        db.add(pref)
    else:
        pref.enabled = body.enabled

    await db.commit()
    await db.refresh(pref)
    logger.info(
        "devstack_pref_updated",
        user_id=str(user.user_id),
        entry_id=str(entry_id),
        enabled=body.enabled,
    )
    return UserPrefResponse.model_validate(pref)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/devstack/api/
git commit -m "feat(devstack): add CRUD API for entries and user preferences"
```

---

### Task 6: Router + Mount

**Files:**
- Create: `backend/app/modules/devstack/router.py`
- Create: `backend/app/modules/devstack/public.py`
- Modify: `backend/app/main.py` (add router mount)

- [ ] **Step 1: Write router**

`backend/app/modules/devstack/router.py`:

```python
"""DevStack module router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.modules.devstack.api import entries as entries_router
from app.modules.devstack.api import prefs as prefs_router

router = APIRouter()

router.include_router(prefs_router.router, tags=["devstack:prefs"])
router.routes.extend(entries_router.router.routes)
```

`backend/app/modules/devstack/public.py`:

```python
"""DevStack public interface for cross-module imports."""

from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.models.user_pref import DevstackUserPrefDB

__all__ = ["DevstackEntryDB", "DevstackUserPrefDB"]
```

- [ ] **Step 2: Mount in main.py**

Add the import and `include_router` call in `backend/app/main.py`, following the existing pattern near the other module mounts:

```python
from app.modules.devstack.router import router as devstack_router
```

```python
app.include_router(devstack_router, prefix="/api/devstack", tags=["devstack"])
```

- [ ] **Step 3: Verify server starts**

Run: `cd backend && python -c "from app.main import app; print('Routes OK')"`
Expected: `Routes OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/devstack/router.py backend/app/modules/devstack/public.py backend/app/main.py
git commit -m "feat(devstack): mount module router in main app"
```

---

### Task 7: Backend Tests

**Files:**
- Create: `backend/tests/modules/devstack/__init__.py`
- Create: `backend/tests/modules/devstack/test_devstack_api.py`

- [ ] **Step 1: Write tests**

`backend/tests/modules/devstack/__init__.py` — empty file.

`backend/tests/modules/devstack/test_devstack_api.py`:

```python
"""Tests for devstack module API endpoints."""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def debug_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        id=DEBUG_USER_ID,
        email="debug@vizzuality.com",
        first_name="Debug",
        last_name="User",
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _entry_payload(**overrides) -> dict:
    base = {
        "name": "test-skill",
        "description": "A test skill for Claude Code",
        "type": "skill",
        "install_method": "github",
        "url": "https://github.com/Vizzuality/devstack/test-skill.md",
        "required": True,
        "origin": "internal",
        "tech": ["python"],
        "active": True,
    }
    base.update(overrides)
    return base


class TestEntryList:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/api/devstack")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_with_filters(self, client: AsyncClient):
        await client.post("/api/devstack", json=_entry_payload())
        await client.post(
            "/api/devstack",
            json=_entry_payload(
                name="optional-cmd",
                type="command",
                required=False,
            ),
        )

        resp = await client.get("/api/devstack?type=skill")
        assert resp.json()["total"] == 1

        resp = await client.get("/api/devstack?required=false")
        assert resp.json()["total"] == 1


class TestEntryCRUD:
    @pytest.mark.asyncio
    async def test_create(self, client: AsyncClient):
        resp = await client.post("/api/devstack", json=_entry_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-skill"
        assert data["type"] == "skill"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_duplicate_name(self, client: AsyncClient):
        await client.post("/api/devstack", json=_entry_payload())
        resp = await client.post("/api/devstack", json=_entry_payload())
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_get_detail(self, client: AsyncClient):
        create_resp = await client.post("/api/devstack", json=_entry_payload())
        entry_id = create_resp.json()["id"]
        resp = await client.get(f"/api/devstack/{entry_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-skill"

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get(f"/api/devstack/{uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update(self, client: AsyncClient):
        create_resp = await client.post("/api/devstack", json=_entry_payload())
        entry_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/devstack/{entry_id}",
            json={"description": "Updated description"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_delete(self, client: AsyncClient):
        create_resp = await client.post("/api/devstack", json=_entry_payload())
        entry_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/devstack/{entry_id}")
        assert resp.status_code == 204

        get_resp = await client.get(f"/api/devstack/{entry_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_npm_requires_package(self, client: AsyncClient):
        payload = _entry_payload(
            name="npm-plugin",
            install_method="npm",
            url=None,
            package="@vizzuality/claude-plugin",
        )
        resp = await client.post("/api/devstack", json=payload)
        assert resp.status_code == 201


class TestUserPrefs:
    @pytest.mark.asyncio
    async def test_list_prefs_empty(self, client: AsyncClient):
        resp = await client.get("/api/devstack/me/prefs")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_opt_in(self, client: AsyncClient):
        create_resp = await client.post("/api/devstack", json=_entry_payload())
        entry_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/devstack/me/prefs/{entry_id}",
            json={"enabled": True},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    @pytest.mark.asyncio
    async def test_opt_out(self, client: AsyncClient):
        create_resp = await client.post("/api/devstack", json=_entry_payload())
        entry_id = create_resp.json()["id"]

        await client.put(
            f"/api/devstack/me/prefs/{entry_id}",
            json={"enabled": True},
        )
        resp = await client.put(
            f"/api/devstack/me/prefs/{entry_id}",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    @pytest.mark.asyncio
    async def test_pref_for_nonexistent_entry(self, client: AsyncClient):
        resp = await client.put(
            f"/api/devstack/me/prefs/{uuid4()}",
            json={"enabled": True},
        )
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests**

Run: `cd backend && pytest tests/modules/devstack/ -v`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/modules/devstack/
git commit -m "test(devstack): add API tests for entries CRUD and user prefs"
```

---

### Task 8: MCP Data Layer

**Files:**
- Create: `mcp_server/data/devstack.py`

- [ ] **Step 1: Write data access functions**

```python
"""DevStack data access for MCP tools."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.models.user_pref import DevstackUserPrefDB


async def get_catalog_for_user(
    session: AsyncSession, user_id: UUID
) -> list[dict]:
    """Return active entries the user should install.

    Includes all required entries + optional entries the user has opted in to.
    """
    entries_q = select(DevstackEntryDB).where(DevstackEntryDB.active.is_(True))
    result = await session.execute(entries_q)
    entries = result.scalars().all()

    prefs_q = select(DevstackUserPrefDB).where(
        DevstackUserPrefDB.user_id == user_id
    )
    prefs_result = await session.execute(prefs_q)
    prefs_by_entry = {p.entry_id: p for p in prefs_result.scalars().all()}

    catalog = []
    for entry in entries:
        pref = prefs_by_entry.get(entry.id)
        if not entry.required and (pref is None or not pref.enabled):
            continue
        catalog.append({
            "name": entry.name,
            "description": entry.description,
            "type": entry.type,
            "install_method": entry.install_method,
            "url": entry.url,
            "package": entry.package,
            "package_version": entry.package_version,
            "origin": entry.origin,
            "tech": entry.tech,
            "last_synced_sha": pref.last_synced_sha if pref else None,
        })
    return catalog


async def update_sync_status(
    session: AsyncSession,
    user_id: UUID,
    entry_name: str,
    sha: str,
) -> bool:
    """Update last_synced_sha for a user's entry. Returns True if found."""
    entry_q = select(DevstackEntryDB).where(DevstackEntryDB.name == entry_name)
    entry_result = await session.execute(entry_q)
    entry = entry_result.scalar_one_or_none()
    if entry is None:
        return False

    pref_q = select(DevstackUserPrefDB).where(
        and_(
            DevstackUserPrefDB.user_id == user_id,
            DevstackUserPrefDB.entry_id == entry.id,
        )
    )
    pref_result = await session.execute(pref_q)
    pref = pref_result.scalar_one_or_none()

    if pref is None:
        pref = DevstackUserPrefDB(
            user_id=user_id,
            entry_id=entry.id,
            enabled=entry.required,
        )
        session.add(pref)

    pref.last_synced_sha = sha
    pref.last_synced_at = datetime.now(timezone.utc)
    return True
```

- [ ] **Step 2: Commit**

```bash
git add mcp_server/data/devstack.py
git commit -m "feat(devstack): add MCP data layer for catalog and sync status"
```

---

### Task 9: MCP Tools + Registration

**Files:**
- Create: `mcp_server/tools/devstack.py`
- Modify: `mcp_server/server.py` (register tools)

- [ ] **Step 1: Write MCP tools**

`mcp_server/tools/devstack.py`:

```python
"""DevStack MCP tools — catalog read + sync status write."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from mcp_server.auth.permissions import mcp_requires
from mcp_server.data import devstack as devstack_data
from mcp_server.data.base import get_mcp_user, get_read_session, get_write_session


def _to_json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


@mcp_requires("devstack:view")
async def devstack_get_catalog() -> str:
    """Get the DevStack catalog filtered for the current user.

    Returns all active entries the user should install: required entries
    for everyone + optional entries the user has opted in to. Each entry
    includes the GitHub URL or npm package name, plus the SHA of the
    last successful sync (null if never synced).

    Use this to sync the local Claude Code environment.
    """
    user = get_mcp_user()
    async with get_read_session() as session:
        catalog = await devstack_data.get_catalog_for_user(
            session, UUID(user.user_id)
        )
    return _to_json(catalog)


@mcp_requires("devstack:view")
async def devstack_update_sync_status(entry_name: str, sha: str) -> str:
    """Record a successful sync for a catalog entry.

    Called by the devstack-sync skill after installing or updating an
    artifact locally. Updates the last_synced_sha so future syncs can
    skip unchanged entries.

    Args:
        entry_name: The name of the synced catalog entry.
        sha: The GitHub commit SHA of the synced content.
    """
    user = get_mcp_user()
    async with get_write_session() as session:
        found = await devstack_data.update_sync_status(
            session, UUID(user.user_id), entry_name, sha
        )
    if not found:
        return _to_json({"error": f"Entry '{entry_name}' not found"})
    return _to_json({"status": "ok", "entry": entry_name, "sha": sha})


def register_devstack_tools(server: FastMCP) -> None:
    """Register all DevStack tools on the MCP server instance."""
    server.tool()(devstack_get_catalog)
    server.tool()(devstack_update_sync_status)
```

- [ ] **Step 2: Register in server.py**

Add to `mcp_server/server.py` inside `create_mcp_server()`, after the existing tool registrations:

```python
    from mcp_server.tools.devstack import register_devstack_tools  # noqa: PLC0415
    register_devstack_tools(instance)
```

Also update the `_INSTRUCTIONS` string to add DevStack to the module table:

```
| DevStack | name (string) | devstack_ |
```

- [ ] **Step 3: Verify MCP server loads**

Run: `cd backend && python -c "from mcp_server.server import create_mcp_server; s = create_mcp_server(); print('MCP OK')"`
Expected: `MCP OK`

- [ ] **Step 4: Commit**

```bash
git add mcp_server/tools/devstack.py mcp_server/server.py
git commit -m "feat(devstack): add MCP tools for catalog read and sync status"
```

---

### Task 10: MCP Tests

**Files:**
- Create: `backend/tests/mcp/test_devstack_tools.py`

- [ ] **Step 1: Write MCP tool tests**

```python
"""Tests for DevStack MCP tools."""

import json
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.models.user_pref import DevstackUserPrefDB
from mcp_server.data.base import McpUserContext, override_mcp_user, override_session
from mcp_server.tools.devstack import devstack_get_catalog, devstack_update_sync_status

TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000099")


@pytest_asyncio.fixture(autouse=True)
async def test_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        id=TEST_USER_ID,
        email="dev@vizzuality.com",
        first_name="Dev",
        last_name="User",
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def required_entry(db_session: AsyncSession) -> DevstackEntryDB:
    entry = DevstackEntryDB(
        name="org-skill",
        description="Required org skill",
        type="skill",
        install_method="github",
        url="https://github.com/Vizzuality/devstack/org-skill.md",
        required=True,
        origin="internal",
        tech=["python"],
        active=True,
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


@pytest_asyncio.fixture
async def optional_entry(db_session: AsyncSession) -> DevstackEntryDB:
    entry = DevstackEntryDB(
        name="react-skill",
        description="Optional React skill",
        type="skill",
        install_method="github",
        url="https://github.com/Vizzuality/devstack/react-skill.md",
        required=False,
        origin="internal",
        tech=["react"],
        active=True,
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


USER_CTX = McpUserContext(
    user_id=str(TEST_USER_ID),
    email="dev@vizzuality.com",
    roles=["user"],
    permissions=["devstack:view"],
)


class TestGetCatalog:
    @pytest.mark.asyncio
    async def test_returns_required_entries(
        self, db_session: AsyncSession, required_entry: DevstackEntryDB
    ):
        async with override_session(db_session), override_mcp_user(USER_CTX):
            result = json.loads(await devstack_get_catalog())
        assert len(result) == 1
        assert result[0]["name"] == "org-skill"

    @pytest.mark.asyncio
    async def test_excludes_optional_not_opted_in(
        self,
        db_session: AsyncSession,
        required_entry: DevstackEntryDB,
        optional_entry: DevstackEntryDB,
    ):
        async with override_session(db_session), override_mcp_user(USER_CTX):
            result = json.loads(await devstack_get_catalog())
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_includes_opted_in_optional(
        self,
        db_session: AsyncSession,
        required_entry: DevstackEntryDB,
        optional_entry: DevstackEntryDB,
    ):
        pref = DevstackUserPrefDB(
            user_id=TEST_USER_ID,
            entry_id=optional_entry.id,
            enabled=True,
        )
        db_session.add(pref)
        await db_session.commit()

        async with override_session(db_session), override_mcp_user(USER_CTX):
            result = json.loads(await devstack_get_catalog())
        assert len(result) == 2
        names = {e["name"] for e in result}
        assert names == {"org-skill", "react-skill"}


class TestUpdateSyncStatus:
    @pytest.mark.asyncio
    async def test_update_creates_pref_if_missing(
        self, db_session: AsyncSession, required_entry: DevstackEntryDB
    ):
        async with override_session(db_session), override_mcp_user(USER_CTX):
            result = json.loads(
                await devstack_update_sync_status("org-skill", "abc123")
            )
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_update_nonexistent_entry(self, db_session: AsyncSession):
        async with override_session(db_session), override_mcp_user(USER_CTX):
            result = json.loads(
                await devstack_update_sync_status("no-such-entry", "abc")
            )
        assert "error" in result
```

- [ ] **Step 2: Run tests**

Run: `cd backend && pytest tests/mcp/test_devstack_tools.py -v`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/mcp/test_devstack_tools.py
git commit -m "test(devstack): add MCP tool tests for catalog and sync status"
```

---

### Task 11: Frontend Types + Service + Query Keys

**Files:**
- Create: `frontend/src/modules/devstack/types/devstack.ts`
- Create: `frontend/src/modules/devstack/services/devstack.ts`
- Modify: `frontend/src/core/hooks/queryKeys.ts` (add devstack keys)

- [ ] **Step 1: Write types**

`frontend/src/modules/devstack/types/devstack.ts`:

```typescript
export const ENTRY_TYPES = [
  'skill', 'command', 'plugin', 'config', 'agent',
] as const;
export type EntryType = typeof ENTRY_TYPES[number];

export const INSTALL_METHODS = ['github', 'npm'] as const;
export type InstallMethod = typeof INSTALL_METHODS[number];

export const ENTRY_ORIGINS = ['internal', 'external'] as const;
export type EntryOrigin = typeof ENTRY_ORIGINS[number];

export interface DevstackEntry {
  id: string;
  name: string;
  description: string;
  type: EntryType;
  install_method: InstallMethod;
  url: string | null;
  package: string | null;
  package_version: string | null;
  required: boolean;
  origin: EntryOrigin;
  tech: string[];
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DevstackEntryCreate {
  name: string;
  description: string;
  type: EntryType;
  install_method: InstallMethod;
  url?: string | null;
  package?: string | null;
  package_version?: string | null;
  required: boolean;
  origin: EntryOrigin;
  tech: string[];
  active: boolean;
}

export type DevstackEntryUpdate = Partial<DevstackEntryCreate>;

export interface DevstackEntryListResponse {
  items: DevstackEntry[];
  total: number;
}

export interface DevstackEntryListParams {
  type?: string;
  required?: boolean;
  active?: boolean;
}

export interface UserPref {
  entry_id: string;
  enabled: boolean;
  last_synced_sha: string | null;
  last_synced_at: string | null;
}
```

- [ ] **Step 2: Write service**

`frontend/src/modules/devstack/services/devstack.ts`:

```typescript
import api from '@/core/services/client';
import type {
  DevstackEntry,
  DevstackEntryCreate,
  DevstackEntryListParams,
  DevstackEntryListResponse,
  DevstackEntryUpdate,
  UserPref,
} from '../types/devstack';

export const devstackApi = {
  list: async (params: DevstackEntryListParams = {}): Promise<DevstackEntryListResponse> => {
    const response = await api.get<DevstackEntryListResponse>('/devstack', { params });
    return response.data;
  },

  get: async (id: string): Promise<DevstackEntry> => {
    const response = await api.get<DevstackEntry>(`/devstack/${id}`);
    return response.data;
  },

  create: async (data: DevstackEntryCreate): Promise<DevstackEntry> => {
    const response = await api.post<DevstackEntry>('/devstack', data);
    return response.data;
  },

  update: async (id: string, data: DevstackEntryUpdate): Promise<DevstackEntry> => {
    const response = await api.put<DevstackEntry>(`/devstack/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/devstack/${id}`);
  },

  listMyPrefs: async (): Promise<UserPref[]> => {
    const response = await api.get<UserPref[]>('/devstack/me/prefs');
    return response.data;
  },

  updateMyPref: async (entryId: string, enabled: boolean): Promise<UserPref> => {
    const response = await api.put<UserPref>(`/devstack/me/prefs/${entryId}`, {
      enabled,
    });
    return response.data;
  },
};
```

- [ ] **Step 3: Add query keys**

Add to `frontend/src/core/hooks/queryKeys.ts` after the `events` block:

```typescript
  devstack: {
    all: ['devstack'] as const,
    list: (params: Record<string, unknown>) => ['devstack', 'list', params] as const,
    detail: (id: string) => ['devstack', id] as const,
    myPrefs: ['devstack', 'my-prefs'] as const,
  },
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/devstack/ frontend/src/core/hooks/queryKeys.ts
git commit -m "feat(devstack): add frontend types, service, and query keys"
```

---

### Task 12: Frontend Hooks

**Files:**
- Create: `frontend/src/modules/devstack/hooks/useDevstack.ts`

- [ ] **Step 1: Write hooks**

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { devstackApi } from '../services/devstack';
import type {
  DevstackEntryCreate,
  DevstackEntryListParams,
  DevstackEntryUpdate,
} from '../types/devstack';

export function useDevstackEntries(params: DevstackEntryListParams = {}) {
  return useQuery({
    queryKey: queryKeys.devstack.list(params as unknown as Record<string, unknown>),
    queryFn: () => devstackApi.list(params),
  });
}

export function useDevstackEntry(id: string) {
  return useQuery({
    queryKey: queryKeys.devstack.detail(id),
    queryFn: () => devstackApi.get(id),
    enabled: !!id,
  });
}

export function useCreateDevstackEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: DevstackEntryCreate) => devstackApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.devstack.all });
    },
  });
}

export function useUpdateDevstackEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DevstackEntryUpdate }) =>
      devstackApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.devstack.all });
    },
  });
}

export function useDeleteDevstackEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => devstackApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.devstack.all });
    },
  });
}

export function useMyDevstackPrefs() {
  return useQuery({
    queryKey: queryKeys.devstack.myPrefs,
    queryFn: () => devstackApi.listMyPrefs(),
  });
}

export function useUpdateMyDevstackPref() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entryId, enabled }: { entryId: string; enabled: boolean }) =>
      devstackApi.updateMyPref(entryId, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.devstack.myPrefs });
    },
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/devstack/hooks/
git commit -m "feat(devstack): add React Query hooks"
```

---

### Task 13: Frontend Permissions

**Files:**
- Modify: `frontend/src/core/permissions/constants.ts` (add devstack actions)

- [ ] **Step 1: Add permissions**

Add after the `EVENTS_MANAGE` line in `frontend/src/core/permissions/constants.ts`:

```typescript
  DEVSTACK_VIEW: 'devstack:view',
  DEVSTACK_MANAGE: 'devstack:manage',
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/core/permissions/constants.ts
git commit -m "feat(devstack): add frontend permission constants"
```

---

### Task 14: Catalog Page (Admin)

**Files:**
- Create: `frontend/src/modules/devstack/pages/Catalog.tsx`
- Create: `frontend/src/modules/devstack/components/EntryForm.tsx`

- [ ] **Step 1: Write Catalog page**

`frontend/src/modules/devstack/pages/Catalog.tsx`:

```typescript
import { useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { usePermission, Action } from '@/core/permissions';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
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
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useDevstackEntries, useDeleteDevstackEntry } from '../hooks/useDevstack';
import { EntryForm } from '../components/EntryForm';
import { ENTRY_TYPES } from '../types/devstack';

const ALL_FILTER = '__all__';

export default function Catalog(): JSX.Element {
  const canManage = usePermission(Action.DEVSTACK_MANAGE);
  const [typeFilter, setTypeFilter] = useState(ALL_FILTER);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const params = typeFilter !== ALL_FILTER ? { type: typeFilter } : {};
  const { data, isLoading } = useDevstackEntries(params);
  const deleteEntry = useDeleteDevstackEntry();

  const handleDelete = (): void => {
    if (!deleteId) return;
    deleteEntry.mutate(deleteId, {
      onSettled: () => setDeleteId(null),
    });
  };

  if (isLoading) return <LoadingSpinner className="min-h-[200px]" />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">DevStack Catalog</h1>
        <div className="flex items-center gap-3">
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_FILTER}>All types</SelectItem>
              {ENTRY_TYPES.map((t) => (
                <SelectItem key={t} value={t}>{t}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {canManage && (
            <Button size="sm" onClick={() => setSelectedId('new')}>
              <Plus className="mr-1 h-4 w-4" />
              Add Entry
            </Button>
          )}
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Method</TableHead>
            <TableHead>Required</TableHead>
            <TableHead>Origin</TableHead>
            <TableHead>Active</TableHead>
            {canManage && <TableHead className="w-[80px]" />}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data?.items.map((entry) => (
            <TableRow key={entry.id}>
              <TableCell className="font-medium">{entry.name}</TableCell>
              <TableCell>
                <Badge variant="outline">{entry.type}</Badge>
              </TableCell>
              <TableCell>{entry.install_method}</TableCell>
              <TableCell>
                {entry.required ? (
                  <span className="inline-block w-2 h-2 rounded-full shrink-0 bg-green-500" />
                ) : (
                  <span className="inline-block w-2 h-2 rounded-full shrink-0 bg-muted-foreground/40" />
                )}
              </TableCell>
              <TableCell>{entry.origin}</TableCell>
              <TableCell>
                {entry.active ? (
                  <span className="inline-block w-2 h-2 rounded-full shrink-0 bg-green-500" />
                ) : (
                  <span className="inline-block w-2 h-2 rounded-full shrink-0 bg-red-500" />
                )}
              </TableCell>
              {canManage && (
                <TableCell>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => setSelectedId(entry.id)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive"
                      onClick={() => setDeleteId(entry.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
              )}
            </TableRow>
          ))}
          {data?.items.length === 0 && (
            <TableRow>
              <TableCell colSpan={canManage ? 7 : 6} className="text-center text-muted-foreground py-8">
                No entries yet.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {selectedId && (
        <EntryForm
          entryId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete entry?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove the entry from the catalog. Existing local
              installations will become orphans on next sync.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
```

- [ ] **Step 2: Write EntryForm component**

`frontend/src/modules/devstack/components/EntryForm.tsx`:

```typescript
import { useEffect, useState } from 'react';
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
import { Switch } from '@/shared/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  useDevstackEntry,
  useCreateDevstackEntry,
  useUpdateDevstackEntry,
} from '../hooks/useDevstack';
import {
  ENTRY_TYPES,
  INSTALL_METHODS,
  ENTRY_ORIGINS,
  type DevstackEntryCreate,
} from '../types/devstack';

interface EntryFormProps {
  readonly entryId: string;
  readonly onClose: () => void;
}

const INITIAL: DevstackEntryCreate = {
  name: '',
  description: '',
  type: 'skill',
  install_method: 'github',
  url: '',
  package: null,
  package_version: null,
  required: false,
  origin: 'internal',
  tech: [],
  active: true,
};

export function EntryForm({ entryId, onClose }: EntryFormProps): JSX.Element {
  const isNew = entryId === 'new';
  const { data: existing } = useDevstackEntry(isNew ? '' : entryId);
  const create = useCreateDevstackEntry();
  const update = useUpdateDevstackEntry();

  const [form, setForm] = useState<DevstackEntryCreate>(INITIAL);
  const [techInput, setTechInput] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (existing && !isNew) {
      setForm({
        name: existing.name,
        description: existing.description,
        type: existing.type,
        install_method: existing.install_method,
        url: existing.url,
        package: existing.package,
        package_version: existing.package_version,
        required: existing.required,
        origin: existing.origin,
        tech: existing.tech,
        active: existing.active,
      });
      setTechInput(existing.tech.join(', '));
    }
  }, [existing, isNew]);

  const handleSubmit = (): void => {
    setError(null);
    if (!form.name.trim()) {
      setError('Name is required');
      return;
    }
    const payload: DevstackEntryCreate = {
      ...form,
      tech: techInput
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
    };

    const onError = (err: unknown): void => {
      const msg =
        err instanceof Error ? err.message : 'Failed to save entry';
      setError(msg);
    };

    if (isNew) {
      create.mutate(payload, { onSuccess: onClose, onError });
    } else {
      update.mutate({ id: entryId, data: payload }, { onSuccess: onClose, onError });
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isNew ? 'New Entry' : 'Edit Entry'}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="space-y-1.5">
            <Label>Name</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="my-skill"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Description</Label>
            <Textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={2}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Type</Label>
              <Select
                value={form.type}
                onValueChange={(v) => setForm({ ...form, type: v as typeof form.type })}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ENTRY_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>Install Method</Label>
              <Select
                value={form.install_method}
                onValueChange={(v) =>
                  setForm({ ...form, install_method: v as typeof form.install_method })
                }
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {INSTALL_METHODS.map((m) => (
                    <SelectItem key={m} value={m}>{m}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {form.install_method === 'github' && (
            <div className="space-y-1.5">
              <Label>GitHub URL</Label>
              <Input
                value={form.url ?? ''}
                onChange={(e) => setForm({ ...form, url: e.target.value || null })}
                placeholder="https://github.com/Vizzuality/devstack/skills/my-skill.md"
              />
            </div>
          )}

          {form.install_method === 'npm' && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Package</Label>
                <Input
                  value={form.package ?? ''}
                  onChange={(e) => setForm({ ...form, package: e.target.value || null })}
                  placeholder="@vizzuality/plugin"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Version</Label>
                <Input
                  value={form.package_version ?? ''}
                  onChange={(e) =>
                    setForm({ ...form, package_version: e.target.value || null })
                  }
                  placeholder="1.0.0"
                />
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Origin</Label>
              <Select
                value={form.origin}
                onValueChange={(v) =>
                  setForm({ ...form, origin: v as typeof form.origin })
                }
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ENTRY_ORIGINS.map((o) => (
                    <SelectItem key={o} value={o}>{o}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>Tech tags (comma-separated)</Label>
              <Input
                value={techInput}
                onChange={(e) => setTechInput(e.target.value)}
                placeholder="python, fastapi"
              />
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Switch
                checked={form.required}
                onCheckedChange={(v) => setForm({ ...form, required: v })}
              />
              <Label>Required</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={form.active}
                onCheckedChange={(v) => setForm({ ...form, active: v })}
              />
              <Label>Active</Label>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            disabled={create.isPending || update.isPending}
          >
            {isNew ? 'Create' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/devstack/pages/ frontend/src/modules/devstack/components/
git commit -m "feat(devstack): add Catalog page and EntryForm component"
```

---

### Task 15: My Environment Page

**Files:**
- Create: `frontend/src/modules/devstack/pages/MyEnvironment.tsx`

- [ ] **Step 1: Write My Environment page**

```typescript
import { Switch } from '@/shared/components/ui/switch';
import { Badge } from '@/shared/components/ui/badge';
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
  useDevstackEntries,
  useMyDevstackPrefs,
  useUpdateMyDevstackPref,
} from '../hooks/useDevstack';
import type { UserPref } from '../types/devstack';

export default function MyEnvironment(): JSX.Element {
  const { data: entriesData, isLoading: entriesLoading } = useDevstackEntries({ active: true });
  const { data: prefs, isLoading: prefsLoading } = useMyDevstackPrefs();
  const updatePref = useUpdateMyDevstackPref();

  if (entriesLoading || prefsLoading) {
    return <LoadingSpinner className="min-h-[200px]" />;
  }

  const prefMap = new Map<string, UserPref>();
  prefs?.forEach((p) => prefMap.set(p.entry_id, p));

  const entries = entriesData?.items ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">My Environment</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage which DevStack artifacts are installed on your machine.
        </p>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Enabled</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Last Synced</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map((entry) => {
            const pref = prefMap.get(entry.id);
            const isEnabled = entry.required || (pref?.enabled ?? false);
            const syncedAt = pref?.last_synced_at;

            return (
              <TableRow key={entry.id}>
                <TableCell>
                  {entry.required ? (
                    <Switch checked disabled title="Required for all" />
                  ) : (
                    <Switch
                      checked={isEnabled}
                      onCheckedChange={(enabled) =>
                        updatePref.mutate({ entryId: entry.id, enabled })
                      }
                    />
                  )}
                </TableCell>
                <TableCell className="font-medium">{entry.name}</TableCell>
                <TableCell>
                  <Badge variant="outline">{entry.type}</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground max-w-[300px] truncate">
                  {entry.description}
                </TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {syncedAt
                    ? new Date(syncedAt).toLocaleDateString()
                    : 'Never'}
                </TableCell>
              </TableRow>
            );
          })}
          {entries.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                No entries in the catalog yet.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/devstack/pages/MyEnvironment.tsx
git commit -m "feat(devstack): add My Environment page with opt-in toggles"
```

---

### Task 16: Routing + Sidebar Navigation

**Files:**
- Modify: `frontend/src/App.tsx` (add routes)
- Modify: `frontend/src/core/components/layout/AppSidebar.tsx` (add nav)

- [ ] **Step 1: Add routes to App.tsx**

Add import at the top:

```typescript
import DevstackCatalog from './modules/devstack/pages/Catalog';
import DevstackMyEnv from './modules/devstack/pages/MyEnvironment';
```

Add routes inside the `<AppLayout>` `<Route>` children, near the events routes:

```tsx
<Route path="/devstack" element={<DevstackCatalog />} />
<Route path="/devstack/me" element={<DevstackMyEnv />} />
```

- [ ] **Step 2: Add sidebar navigation**

In `frontend/src/core/components/layout/AppSidebar.tsx`, add the tabs constant near the other tab definitions:

```typescript
const DEVSTACK_TABS = [
  { to: '/devstack', label: 'Catalog' },
  { to: '/devstack/me', label: 'My Environment' },
] as const;
```

Add a `CollapsibleMenuItem` in the sidebar menu, using an appropriate icon (e.g. `Blocks` from lucide-react):

```tsx
<CollapsibleMenuItem
  icon={Blocks}
  label="DevStack"
  isActive={isActive('/devstack')}
  items={DEVSTACK_TABS}
/>
```

- [ ] **Step 3: Start dev server and verify**

Run: `cd frontend && npm run dev`
Navigate to `http://localhost:5173/devstack` — Catalog page should render.
Navigate to `http://localhost:5173/devstack/me` — My Environment page should render.
Verify sidebar shows "DevStack" with both tabs.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/core/components/layout/AppSidebar.tsx
git commit -m "feat(devstack): add routing and sidebar navigation"
```

---

### Task 17: End-to-End Verification

- [ ] **Step 1: Run backend tests**

Run: `cd backend && pytest tests/modules/devstack/ tests/mcp/test_devstack_tools.py -v`
Expected: All tests pass.

- [ ] **Step 2: Run frontend type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 3: Test full flow in browser**

1. Start backend: `cd backend && python run_server.py`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to `/devstack` — create an entry (name: "test-skill", type: skill, method: github, url: any, required: true)
4. Verify it appears in the table
5. Navigate to `/devstack/me` — verify the entry shows with a disabled switch (required)
6. Go back to catalog, create an optional entry
7. Navigate to `/devstack/me` — toggle the opt-in switch, verify it works

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix(devstack): address issues found in e2e verification"
```
