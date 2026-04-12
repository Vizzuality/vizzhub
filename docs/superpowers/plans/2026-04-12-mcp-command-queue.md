# MCP Command Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add write operations to the MCP server via a human-in-the-loop command queue — 12 write tools for ISO docs/registries/Playbook, plus 3 queue management tools.

**Architecture:** Write tools enqueue commands (validated, with human-readable summaries) into a `command_queue` table. Approval triggers execution via module handlers that call backend services directly (TreeService, ContentVersionService, models). REST endpoints expose the queue for future UI.

**Tech Stack:** SQLAlchemy async, FastMCP, Alembic (raw SQL), pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-04-12-mcp-command-queue-design.md`

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `backend/alembic/versions/051_command_queue.py` | Migration: `command_queue` table |
| `mcp_server/models/__init__.py` | Package init |
| `mcp_server/models/command.py` | `CommandDB` SQLAlchemy model |
| `mcp_server/services/__init__.py` | Package init |
| `mcp_server/services/command_service.py` | `enqueue()`, `approve()`, `reject()`, `list_pending()` |
| `mcp_server/handlers/__init__.py` | Package init |
| `mcp_server/handlers/iso_docs.py` | ISO handler: 8 actions (pages, metadata, nodes, registry rows) |
| `mcp_server/handlers/playbook.py` | Playbook handler: 4 actions (articles, nodes) |
| `mcp_server/tools/iso_write.py` | 8 ISO write MCP tools |
| `mcp_server/tools/playbook_write.py` | 4 Playbook write MCP tools |
| `mcp_server/tools/commands.py` | 3 queue management MCP tools |
| `backend/app/core/api/commands.py` | REST endpoints for command queue |
| `mcp_server/tests/test_command_service.py` | Command service unit tests |
| `mcp_server/tests/test_handler_iso_docs.py` | ISO handler tests |
| `mcp_server/tests/test_handler_playbook.py` | Playbook handler tests |
| `mcp_server/tests/test_command_tools.py` | Integration tests: tool → enqueue → approve → DB |
| `backend/tests/modules/core/test_commands_api.py` | REST endpoint tests |

### Modified files

| File | Change |
|---|---|
| `mcp_server/data/base.py` | Add `get_write_session()` context manager |
| `mcp_server/server.py` | Register write tools and command tools |
| `backend/app/main.py` | Mount commands router |

---

### Task 1: Alembic Migration — `command_queue` Table

**Files:**
- Create: `backend/alembic/versions/051_command_queue.py`

- [ ] **Step 1: Write the migration**

```python
"""Add command_queue table for MCP write operations.

Revision ID: 051_cmd_queue
Revises: 050_mcp_state
"""

from alembic import op

revision = "051_cmd_queue"
down_revision = "050_mcp_state"


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS command_queue ("
        "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "  module TEXT NOT NULL,"
        "  action TEXT NOT NULL,"
        "  target TEXT,"
        "  payload JSONB NOT NULL DEFAULT '{}'::jsonb,"
        "  summary TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  requested_by UUID NOT NULL REFERENCES users(id),"
        "  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        "  reviewed_by UUID REFERENCES users(id),"
        "  reviewed_at TIMESTAMPTZ,"
        "  result JSONB,"
        "  error TEXT,"
        "  executed_at TIMESTAMPTZ"
        ")"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_command_queue_status "
        "ON command_queue(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_command_queue_requested_by "
        "ON command_queue(requested_by)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_command_queue_module "
        "ON command_queue(module)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS command_queue")
```

- [ ] **Step 2: Run the migration locally**

Run: `cd backend && alembic upgrade head`
Expected: Migration applies without error.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/051_command_queue.py
git commit -m "feat(mcp): add command_queue table migration"
```

---

### Task 2: CommandDB Model + Write Session

**Files:**
- Create: `mcp_server/models/__init__.py`
- Create: `mcp_server/models/command.py`
- Modify: `mcp_server/data/base.py`

- [ ] **Step 1: Create the model package init**

```python
```

(Empty `__init__.py`)

- [ ] **Step 2: Write the failing test for CommandDB**

Create `mcp_server/tests/test_command_service.py`:

```python
"""Tests for command queue service."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from mcp_server.models.command import CommandDB


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        email="test@vizzuality.com",
        name="Test User",
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_command_model_create(db_session: AsyncSession, test_user: UserDB) -> None:
    cmd = CommandDB(
        module="iso_docs",
        action="create_page",
        target="policies",
        payload={"title": "New Policy"},
        summary='Create page **New Policy** in Policies',
        requested_by=test_user.id,
    )
    db_session.add(cmd)
    await db_session.flush()
    await db_session.refresh(cmd)

    assert cmd.id is not None
    assert cmd.status == "pending"
    assert cmd.requested_at is not None
    assert cmd.reviewed_by is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_command_service.py::test_command_model_create -xvs`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.models'`

- [ ] **Step 4: Write CommandDB model**

Create `mcp_server/models/command.py`:

```python
"""Command queue model for MCP write operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class CommandDB(Base):
    """A queued write command awaiting approval."""

    __tablename__ = "command_queue"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
    )
    requested_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
```

- [ ] **Step 5: Add `get_write_session()` to base.py**

Add to `mcp_server/data/base.py` after the `_backend_read_session_maker` global:

```python
# Writable session maker — only for command queue operations.
_backend_write_session_maker: async_sessionmaker | None = None
```

Add a new function `enable_backend_write_sessions()` after `enable_backend_sessions()`:

```python
def enable_backend_write_sessions() -> None:
    """Create a writable session maker sharing the backend's engine.

    Called during FastAPI lifespan alongside enable_backend_sessions().
    Used exclusively by the command queue for executing approved commands.
    """
    global _backend_write_session_maker
    from app.database import engine  # noqa: PLC0415

    _backend_write_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
```

Add `get_write_session()` after `get_read_session()`:

```python
@asynccontextmanager
async def get_write_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a writable async session. Commits on success, rolls back on error.

    Priority:
    1. Test override (same as read — tests share a single session)
    2. Backend writable session maker (HTTP mode)
    3. Standalone writable engine (stdio mode)
    """
    override = _session_override.get()
    if override is not None:
        yield override
        return

    if _backend_write_session_maker is not None:
        async with _backend_write_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            return

    settings = get_settings()
    write_engine = create_async_engine(settings.database_url, echo=False)
    maker = async_sessionmaker(write_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    await write_engine.dispose()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_command_service.py::test_command_model_create -xvs`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add mcp_server/models/__init__.py mcp_server/models/command.py mcp_server/data/base.py
git commit -m "feat(mcp): add CommandDB model and get_write_session"
```

---

### Task 3: Command Service — enqueue, approve, reject, list

**Files:**
- Create: `mcp_server/services/__init__.py`
- Create: `mcp_server/services/command_service.py`
- Modify: `mcp_server/tests/test_command_service.py`

- [ ] **Step 1: Write failing tests for command service**

Add to `mcp_server/tests/test_command_service.py`:

```python
from uuid import UUID

from mcp_server.services.command_service import CommandService


@pytest.mark.asyncio
async def test_enqueue_creates_pending_command(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    cmd = await svc.enqueue(
        module="iso_docs",
        action="create_page",
        target="policies",
        payload={"title": "New Policy"},
        summary="Create page **New Policy** in Policies",
        user_id=test_user.id,
    )
    assert cmd.status == "pending"
    assert cmd.module == "iso_docs"
    assert cmd.action == "create_page"
    assert cmd.requested_by == test_user.id


@pytest.mark.asyncio
async def test_approve_transitions_to_executed(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    cmd = await svc.enqueue(
        module="iso_docs",
        action="create_page",
        target="policies",
        payload={"title": "New Policy"},
        summary="Create page **New Policy** in Policies",
        user_id=test_user.id,
    )

    async def fake_executor(action, target, payload, user_id, session):
        return {"node_id": "fake-id", "slug": "new-policy"}

    result = await svc.approve(cmd.id, test_user.id, executor=fake_executor)
    assert result.status == "executed"
    assert result.result == {"node_id": "fake-id", "slug": "new-policy"}
    assert result.reviewed_by == test_user.id
    assert result.executed_at is not None


@pytest.mark.asyncio
async def test_approve_failed_execution(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    cmd = await svc.enqueue(
        module="iso_docs",
        action="create_page",
        target="policies",
        payload={"title": "New Policy"},
        summary="Create page **New Policy** in Policies",
        user_id=test_user.id,
    )

    async def failing_executor(action, target, payload, user_id, session):
        raise ValueError("Registry type not found")

    result = await svc.approve(cmd.id, test_user.id, executor=failing_executor)
    assert result.status == "failed"
    assert "Registry type not found" in result.error


@pytest.mark.asyncio
async def test_reject_command(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    cmd = await svc.enqueue(
        module="iso_docs",
        action="create_page",
        target="policies",
        payload={"title": "New Policy"},
        summary="Create page **New Policy** in Policies",
        user_id=test_user.id,
    )
    result = await svc.reject(cmd.id, test_user.id)
    assert result.status == "rejected"
    assert result.reviewed_by == test_user.id


@pytest.mark.asyncio
async def test_approve_non_pending_raises(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    cmd = await svc.enqueue(
        module="iso_docs",
        action="create_page",
        target="policies",
        payload={"title": "X"},
        summary="X",
        user_id=test_user.id,
    )
    await svc.reject(cmd.id, test_user.id)

    with pytest.raises(ValueError, match="not pending"):
        async def noop(a, t, p, u, s):
            return {}
        await svc.approve(cmd.id, test_user.id, executor=noop)


@pytest.mark.asyncio
async def test_list_pending_filters_by_user(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    other = UserDB(email="other@vizzuality.com", name="Other")
    db_session.add(other)
    await db_session.flush()

    svc = CommandService(db_session)
    await svc.enqueue(
        module="iso_docs", action="create_page", target=None,
        payload={}, summary="User cmd", user_id=test_user.id,
    )
    await svc.enqueue(
        module="playbook", action="create_article", target=None,
        payload={}, summary="Other cmd", user_id=other.id,
    )

    mine = await svc.list_pending(user_id=test_user.id)
    assert len(mine) == 1
    assert mine[0].summary == "User cmd"

    all_pending = await svc.list_pending()
    assert len(all_pending) == 2


@pytest.mark.asyncio
async def test_list_pending_filters_by_module(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    svc = CommandService(db_session)
    await svc.enqueue(
        module="iso_docs", action="create_page", target=None,
        payload={}, summary="ISO cmd", user_id=test_user.id,
    )
    await svc.enqueue(
        module="playbook", action="create_article", target=None,
        payload={}, summary="PB cmd", user_id=test_user.id,
    )

    iso_only = await svc.list_pending(module="iso_docs")
    assert len(iso_only) == 1
    assert iso_only[0].module == "iso_docs"


@pytest.mark.asyncio
async def test_approve_nonexistent_raises(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    from uuid import uuid4

    svc = CommandService(db_session)
    with pytest.raises(ValueError, match="not found"):
        async def noop(a, t, p, u, s):
            return {}
        await svc.approve(uuid4(), test_user.id, executor=noop)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_command_service.py -xvs`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.services'`

- [ ] **Step 3: Create services package and implement CommandService**

Create `mcp_server/services/__init__.py` (empty).

Create `mcp_server/services/command_service.py`:

```python
"""Command queue service — enqueue, approve, reject, list."""

from __future__ import annotations

from collections.abc import Callable, Awaitable
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.models.command import CommandDB

# Type alias for the executor callback used during approval.
Executor = Callable[
    [str, str | None, dict, UUID, AsyncSession],
    Awaitable[dict],
]


class CommandService:
    """Manages the lifecycle of queued commands."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(
        self,
        *,
        module: str,
        action: str,
        target: str | None,
        payload: dict,
        summary: str,
        user_id: UUID,
    ) -> CommandDB:
        """Create a pending command in the queue."""
        cmd = CommandDB(
            module=module,
            action=action,
            target=target,
            payload=payload,
            summary=summary,
            requested_by=user_id,
        )
        self._session.add(cmd)
        await self._session.flush()
        await self._session.refresh(cmd)
        return cmd

    async def approve(
        self,
        command_id: UUID,
        reviewer_id: UUID,
        *,
        executor: Executor,
    ) -> CommandDB:
        """Approve and execute a pending command.

        The executor callback performs the actual write operation.
        On success, status becomes 'executed'. On failure, 'failed'.
        """
        cmd = await self._get_command(command_id)
        if cmd.status != "pending":
            raise ValueError(f"Command {command_id} is not pending (status={cmd.status})")

        now = datetime.now(timezone.utc)
        cmd.status = "approved"
        cmd.reviewed_by = reviewer_id
        cmd.reviewed_at = now

        try:
            result = await executor(
                cmd.action, cmd.target, cmd.payload, cmd.requested_by, self._session,
            )
            cmd.status = "executed"
            cmd.result = result
            cmd.executed_at = datetime.now(timezone.utc)
        except Exception as exc:
            cmd.status = "failed"
            cmd.error = str(exc)

        await self._session.flush()
        await self._session.refresh(cmd)
        return cmd

    async def reject(self, command_id: UUID, reviewer_id: UUID) -> CommandDB:
        """Reject a pending command."""
        cmd = await self._get_command(command_id)
        if cmd.status != "pending":
            raise ValueError(f"Command {command_id} is not pending (status={cmd.status})")

        cmd.status = "rejected"
        cmd.reviewed_by = reviewer_id
        cmd.reviewed_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(cmd)
        return cmd

    async def list_pending(
        self,
        *,
        user_id: UUID | None = None,
        module: str | None = None,
    ) -> list[CommandDB]:
        """List pending commands, optionally filtered by user and/or module."""
        stmt = (
            select(CommandDB)
            .where(CommandDB.status == "pending")
            .order_by(CommandDB.requested_at)
        )
        if user_id is not None:
            stmt = stmt.where(CommandDB.requested_by == user_id)
        if module is not None:
            stmt = stmt.where(CommandDB.module == module)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_command(self, command_id: UUID) -> CommandDB:
        """Public accessor — raises ValueError if not found."""
        return await self._get_command(command_id)

    async def _get_command(self, command_id: UUID) -> CommandDB:
        result = await self._session.execute(
            select(CommandDB).where(CommandDB.id == command_id)
        )
        cmd = result.scalar_one_or_none()
        if cmd is None:
            raise ValueError(f"Command {command_id} not found")
        return cmd
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_command_service.py -xvs`
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/services/__init__.py mcp_server/services/command_service.py mcp_server/tests/test_command_service.py
git commit -m "feat(mcp): add CommandService with enqueue/approve/reject/list"
```

---

### Task 4: ISO Docs Handler

**Files:**
- Create: `mcp_server/handlers/__init__.py`
- Create: `mcp_server/handlers/iso_docs.py`
- Create: `mcp_server/tests/test_handler_iso_docs.py`

- [ ] **Step 1: Write failing tests for ISO handler**

Create `mcp_server/tests/test_handler_iso_docs.py`:

```python
"""Tests for ISO docs command handler."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.models.user import UserDB
from app.modules.iso_docs.models import (
    IsoDocMetadataDB,
    IsoDocNodeDB,
    IsoDocVersionDB,
    RegistryRowDB,
    RegistryTypeDB,
)


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        email="editor@vizzuality.com",
        name="Editor",
        first_name="Editor",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def iso_tree(db_session: AsyncSession) -> dict:
    """Seed a basic ISO doc tree: group → page with metadata + version."""
    group = IsoDocNodeDB(
        title="Policies", slug="policies", type="group",
    )
    db_session.add(group)
    await db_session.flush()

    page = IsoDocNodeDB(
        title="Security Policy", slug="security-policy",
        type="page", parent_id=group.id,
    )
    db_session.add(page)
    await db_session.flush()

    meta = IsoDocMetadataDB(node_id=page.id, classification="internal_use")
    db_session.add(meta)

    version = IsoDocVersionDB(
        node_id=page.id, version=1,
        content="# Security Policy\n\nOriginal content.",
    )
    db_session.add(version)
    await db_session.flush()

    return {"group": group, "page": page, "meta": meta}


@pytest_asyncio.fixture
async def registry_setup(db_session: AsyncSession) -> dict:
    """Seed a registry type + node for row CRUD tests."""
    rt = RegistryTypeDB(
        name="Incident Register", slug="incident-register",
        description="Security incidents", is_yearly=True,
        schema=[
            {"key": "number", "label": "Number", "type": "string", "required": True},
            {"key": "severity", "label": "Severity", "type": "select",
             "options": ["Critical", "High", "Medium", "Low"]},
        ],
    )
    db_session.add(rt)
    await db_session.flush()

    node = IsoDocNodeDB(
        title="Incident Register", slug="incident-register",
        type="registry", registry_type_id=rt.id,
    )
    db_session.add(node)
    await db_session.flush()

    meta = IsoDocMetadataDB(node_id=node.id)
    db_session.add(meta)

    row = RegistryRowDB(
        node_id=node.id, year=2026, row_index=0,
        data={"number": "INC-001", "severity": "High"},
    )
    db_session.add(row)
    await db_session.flush()

    return {"rt": rt, "node": node, "row": row}


@pytest.mark.asyncio
async def test_create_page(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    from mcp_server.handlers.iso_docs import execute

    result = await execute(
        "create_page", "policies", {"title": "Data Retention Policy"},
        test_user.id, db_session,
    )
    assert "slug" in result
    assert result["title"] == "Data Retention Policy"

    from sqlalchemy import select
    node = (await db_session.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.slug == result["slug"])
    )).scalar_one()
    assert node.parent_id == iso_tree["group"].id
    assert node.type == "page"


@pytest.mark.asyncio
async def test_update_page_content(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    from mcp_server.handlers.iso_docs import execute

    result = await execute(
        "update_page_content", "security-policy",
        {"content": "# Security Policy\n\nUpdated content with new section."},
        test_user.id, db_session,
    )
    assert result["version"] == 2
    assert result["conflict"] is False


@pytest.mark.asyncio
async def test_update_metadata(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    from mcp_server.handlers.iso_docs import execute

    result = await execute(
        "update_metadata", "security-policy",
        {"status": "approved", "code": "POL-001"},
        test_user.id, db_session,
    )
    assert result["status"] == "approved"
    assert result["code"] == "POL-001"


@pytest.mark.asyncio
async def test_update_node_title(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    from mcp_server.handlers.iso_docs import execute

    result = await execute(
        "update_node", "security-policy",
        {"title": "Information Security Policy"},
        test_user.id, db_session,
    )
    assert result["title"] == "Information Security Policy"
    assert "information-security-policy" in result["slug"]


@pytest.mark.asyncio
async def test_update_node_move(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    from mcp_server.handlers.iso_docs import execute

    new_group = IsoDocNodeDB(title="Procedures", slug="procedures", type="group")
    db_session.add(new_group)
    await db_session.flush()

    result = await execute(
        "update_node", "security-policy",
        {"parent_slug": "procedures"},
        test_user.id, db_session,
    )
    assert result["parent_id"] == str(new_group.id)


@pytest.mark.asyncio
async def test_delete_leaf_node(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    from mcp_server.handlers.iso_docs import execute

    result = await execute(
        "delete_node", "security-policy", {},
        test_user.id, db_session,
    )
    assert result["ok"] is True

    from sqlalchemy import select
    node = (await db_session.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.slug == "security-policy")
    )).scalar_one_or_none()
    assert node is None


@pytest.mark.asyncio
async def test_delete_node_with_children_rejected(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    from mcp_server.handlers.iso_docs import execute

    with pytest.raises(ValueError, match="has children"):
        await execute(
            "delete_node", "policies", {},
            test_user.id, db_session,
        )


@pytest.mark.asyncio
async def test_create_registry_row(
    db_session: AsyncSession, test_user: UserDB, registry_setup: dict,
) -> None:
    from mcp_server.handlers.iso_docs import execute

    result = await execute(
        "create_registry_row", "incident-register",
        {"year": 2026, "data": {"number": "INC-002", "severity": "Medium"}},
        test_user.id, db_session,
    )
    assert result["data"]["number"] == "INC-002"
    assert "row_id" in result


@pytest.mark.asyncio
async def test_update_registry_row(
    db_session: AsyncSession, test_user: UserDB, registry_setup: dict,
) -> None:
    from mcp_server.handlers.iso_docs import execute

    row_id = str(registry_setup["row"].id)
    result = await execute(
        "update_registry_row", "incident-register",
        {"row_id": row_id, "data": {"severity": "Critical"}},
        test_user.id, db_session,
    )
    assert result["data"]["severity"] == "Critical"
    assert result["data"]["number"] == "INC-001"


@pytest.mark.asyncio
async def test_delete_registry_row(
    db_session: AsyncSession, test_user: UserDB, registry_setup: dict,
) -> None:
    from mcp_server.handlers.iso_docs import execute

    row_id = str(registry_setup["row"].id)
    result = await execute(
        "delete_registry_row", "incident-register",
        {"row_id": row_id},
        test_user.id, db_session,
    )
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_unknown_action_raises(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    from mcp_server.handlers.iso_docs import execute

    with pytest.raises(ValueError, match="Unknown action"):
        await execute("nonexistent", None, {}, test_user.id, db_session)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_handler_iso_docs.py -xvs`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.handlers'`

- [ ] **Step 3: Create handlers package and implement ISO docs handler**

Create `mcp_server/handlers/__init__.py` (empty).

Create `mcp_server/handlers/iso_docs.py`:

```python
"""ISO docs + registries command handler.

Dispatches write actions to the appropriate backend services.
Each action receives (target, payload, user_id, session) and returns
a result dict. Raises ValueError on validation failures.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.core.services.content_version_service import ContentVersionService
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.models.registry_type import RegistryTypeDB
from app.modules.iso_docs.services.registry_service import (
    get_next_row_index,
    strip_computed_keys,
    validate_row_data,
)
from app.modules.iso_docs.services.tree_service import (
    ensure_unique_slug,
    generate_slug,
    get_next_position,
    validate_depth,
    validate_not_circular,
)

logger = structlog.get_logger()

_versions = ContentVersionService(
    model_class=IsoDocVersionDB,
    entity_fk_field="node_id",
)

MODULE = "iso_docs"


async def execute(
    action: str,
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    """Dispatch an ISO docs action. Raises ValueError on failure."""
    handler = _ACTIONS.get(action)
    if handler is None:
        raise ValueError(f"Unknown action: {action}")
    return await handler(target, payload, user_id, session)


async def _resolve_node_by_slug(
    session: AsyncSession, slug: str, expected_type: str | None = None,
) -> IsoDocNodeDB:
    result = await session.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.slug == slug)
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise ValueError(f"Node '{slug}' not found")
    if expected_type and node.type != expected_type:
        raise ValueError(f"Node '{slug}' is type '{node.type}', expected '{expected_type}'")
    return node


async def _get_user_display_name(session: AsyncSession, user_id: UUID) -> str:
    result = await session.execute(
        select(UserDB.first_name, UserDB.last_name, UserDB.name, UserDB.email)
        .where(UserDB.id == user_id)
    )
    row = result.first()
    if row is None:
        return "Unknown"
    parts = [row.first_name, row.last_name]
    full = " ".join(p for p in parts if p)
    return full or row.name or row.email.split("@")[0]


# --- Page actions ---

async def _create_page(
    target: str | None, payload: dict, user_id: UUID, session: AsyncSession,
) -> dict:
    parent = await _resolve_node_by_slug(session, target, expected_type="group")
    title = payload["title"]

    if not await validate_depth(session, parent.id):
        raise ValueError("Maximum tree depth exceeded (10 levels)")

    slug = generate_slug(title)
    slug = await ensure_unique_slug(session, slug)
    position = await get_next_position(session, parent.id)

    node = IsoDocNodeDB(
        title=title, slug=slug, type="page",
        parent_id=parent.id, position=position,
        created_by_id=user_id, updated_by_id=user_id,
    )
    session.add(node)
    await session.flush()
    await session.refresh(node)

    session.add(IsoDocMetadataDB(node_id=node.id))
    await session.flush()

    logger.info("mcp_iso_page_created", node_id=str(node.id), title=title)
    return {"node_id": str(node.id), "slug": node.slug, "title": node.title}


async def _update_page_content(
    target: str | None, payload: dict, user_id: UUID, session: AsyncSession,
) -> dict:
    node = await _resolve_node_by_slug(session, target, expected_type="page")
    content = payload["content"]

    new_version, conflict = await _versions.save_version(
        session, entity_id=node.id, content=content,
        user_id=user_id, expected_version=payload.get("expected_version"),
    )

    h1_title = _extract_h1(content)
    if h1_title and h1_title != node.title:
        node.title = h1_title
        node.slug = await ensure_unique_slug(
            session, generate_slug(h1_title), exclude_id=node.id,
        )
        node.updated_by_id = user_id
        await session.flush()

    logger.info("mcp_iso_page_updated", node_id=str(node.id), version=new_version)
    return {"node_id": str(node.id), "version": new_version, "conflict": conflict}


async def _update_metadata(
    target: str | None, payload: dict, user_id: UUID, session: AsyncSession,
) -> dict:
    node = await _resolve_node_by_slug(session, target)

    result = await session.execute(
        select(IsoDocMetadataDB).where(IsoDocMetadataDB.node_id == node.id)
    )
    meta = result.scalar_one_or_none()

    if payload.get("changelog"):
        display_name = await _get_user_display_name(session, user_id)
        for entry in payload["changelog"]:
            if not entry.get("author") or entry["author"] == "system":
                entry["author"] = display_name

    if meta:
        for field, value in payload.items():
            setattr(meta, field, value)
    else:
        meta = IsoDocMetadataDB(node_id=node.id, **payload)
        session.add(meta)

    await session.flush()
    await session.refresh(meta)

    logger.info("mcp_iso_metadata_updated", node_id=str(node.id))
    return {
        "node_id": str(node.id),
        "code": meta.code,
        "status": meta.status,
        "classification": meta.classification,
        "standard": meta.standard,
        "clauses": meta.clauses,
        "guidance": meta.guidance,
        "changelog": meta.changelog,
    }


# --- Node actions ---

async def _update_node(
    target: str | None, payload: dict, user_id: UUID, session: AsyncSession,
) -> dict:
    node = await _resolve_node_by_slug(session, target)

    if "parent_slug" in payload:
        parent = await _resolve_node_by_slug(session, payload["parent_slug"], "group")
        if not await validate_not_circular(session, node.id, parent.id):
            raise ValueError("Cannot move node under its own descendant")
        if not await validate_depth(session, parent.id):
            raise ValueError("Maximum tree depth exceeded (10 levels)")
        node.parent_id = parent.id

    if "title" in payload and payload["title"] != node.title:
        node.title = payload["title"]
        node.slug = await ensure_unique_slug(
            session, generate_slug(payload["title"]), exclude_id=node.id,
        )

    node.updated_by_id = user_id
    await session.flush()
    await session.refresh(node)

    logger.info("mcp_iso_node_updated", node_id=str(node.id))
    return {
        "node_id": str(node.id),
        "slug": node.slug,
        "title": node.title,
        "parent_id": str(node.parent_id) if node.parent_id else None,
    }


async def _delete_node(
    target: str | None, payload: dict, user_id: UUID, session: AsyncSession,
) -> dict:
    node = await _resolve_node_by_slug(session, target)

    children_count = await session.execute(
        select(sa_func.count()).select_from(IsoDocNodeDB).where(
            IsoDocNodeDB.parent_id == node.id
        )
    )
    if children_count.scalar_one() > 0:
        raise ValueError(
            f"Node '{target}' has children. Delete children first."
        )

    await session.delete(node)
    await session.flush()

    logger.info("mcp_iso_node_deleted", node_id=str(node.id))
    return {"ok": True}


# --- Registry row actions ---

async def _resolve_registry(session: AsyncSession, slug: str):
    """Resolve registry slug to (node, registry_type, schema)."""
    result = await session.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.slug == slug)
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise ValueError(f"Registry node '{slug}' not found")

    if not node.registry_type_id:
        raise ValueError(f"Node '{slug}' is not a registry")

    rt_result = await session.execute(
        select(RegistryTypeDB).where(RegistryTypeDB.id == node.registry_type_id)
    )
    rt = rt_result.scalar_one_or_none()
    if rt is None:
        raise ValueError(f"Registry type for '{slug}' not found")

    return node, rt, rt.schema or []


async def _create_registry_row(
    target: str | None, payload: dict, user_id: UUID, session: AsyncSession,
) -> dict:
    node, rt, schema = await _resolve_registry(session, target)
    year = payload.get("year")
    data = payload["data"]

    if rt.is_yearly and year is None:
        raise ValueError("Year is required for yearly registries")

    clean_data = strip_computed_keys(schema, data) if schema else data
    if schema:
        errors = validate_row_data(schema, clean_data)
        if errors:
            raise ValueError(f"Validation errors: {'; '.join(errors)}")

    row_index = await get_next_row_index(session, node.id, year)
    row = RegistryRowDB(
        node_id=node.id, year=year, row_index=row_index,
        data=clean_data,
        created_by_id=user_id, updated_by_id=user_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)

    logger.info("mcp_registry_row_created", node_id=str(node.id), row_id=str(row.id))
    return {"row_id": str(row.id), "data": row.data, "year": row.year}


async def _update_registry_row(
    target: str | None, payload: dict, user_id: UUID, session: AsyncSession,
) -> dict:
    node, rt, schema = await _resolve_registry(session, target)
    row_id = UUID(payload["row_id"])

    result = await session.execute(
        select(RegistryRowDB).where(
            RegistryRowDB.id == row_id, RegistryRowDB.node_id == node.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"Row {row_id} not found in registry '{target}'")

    clean_update = strip_computed_keys(schema, payload["data"]) if schema else payload["data"]
    merged = {**row.data, **clean_update}
    if schema:
        errors = validate_row_data(schema, merged)
        if errors:
            raise ValueError(f"Validation errors: {'; '.join(errors)}")

    row.data = merged
    row.updated_by_id = user_id
    await session.flush()
    await session.refresh(row)

    logger.info("mcp_registry_row_updated", node_id=str(node.id), row_id=str(row.id))
    return {"row_id": str(row.id), "data": row.data}


async def _delete_registry_row(
    target: str | None, payload: dict, user_id: UUID, session: AsyncSession,
) -> dict:
    node, _, _ = await _resolve_registry(session, target)
    row_id = UUID(payload["row_id"])

    result = await session.execute(
        select(RegistryRowDB).where(
            RegistryRowDB.id == row_id, RegistryRowDB.node_id == node.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"Row {row_id} not found in registry '{target}'")

    await session.delete(row)
    await session.flush()

    logger.info("mcp_registry_row_deleted", node_id=str(node.id), row_id=str(row_id))
    return {"ok": True}


# --- Helpers ---

def _extract_h1(content: str) -> str | None:
    """Extract H1 title from markdown content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped and not stripped.startswith("#"):
            break
    return None


# --- Action dispatch table ---

_ACTIONS = {
    "create_page": _create_page,
    "update_page_content": _update_page_content,
    "update_metadata": _update_metadata,
    "update_node": _update_node,
    "delete_node": _delete_node,
    "create_registry_row": _create_registry_row,
    "update_registry_row": _update_registry_row,
    "delete_registry_row": _delete_registry_row,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_handler_iso_docs.py -xvs`
Expected: All 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/handlers/__init__.py mcp_server/handlers/iso_docs.py mcp_server/tests/test_handler_iso_docs.py
git commit -m "feat(mcp): add ISO docs command handler with 8 actions"
```

---

### Task 5: Playbook Handler

**Files:**
- Create: `mcp_server/handlers/playbook.py`
- Create: `mcp_server/tests/test_handler_playbook.py`

- [ ] **Step 1: Write failing tests for Playbook handler**

Create `mcp_server/tests/test_handler_playbook.py`:

```python
"""Tests for Playbook command handler."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        email="editor@vizzuality.com",
        name="Editor",
        first_name="Editor",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def playbook_tree(db_session: AsyncSession) -> dict:
    """Seed a basic Playbook tree: group → article."""
    group = PlaybookNodeDB(
        title="Getting Started", slug="getting-started", type="group",
    )
    db_session.add(group)
    await db_session.flush()

    article = PlaybookNodeDB(
        title="Onboarding", slug="onboarding",
        type="page", parent_id=group.id,
    )
    db_session.add(article)
    await db_session.flush()

    version = PlaybookPageVersionDB(
        node_id=article.id, version=1,
        content="# Onboarding\n\nWelcome to Vizzuality.",
    )
    db_session.add(version)
    await db_session.flush()

    return {"group": group, "article": article}


@pytest.mark.asyncio
async def test_create_article(
    db_session: AsyncSession, test_user: UserDB, playbook_tree: dict,
) -> None:
    from mcp_server.handlers.playbook import execute

    result = await execute(
        "create_article", "getting-started", {"title": "Dev Setup Guide"},
        test_user.id, db_session,
    )
    assert "slug" in result
    assert result["title"] == "Dev Setup Guide"

    from sqlalchemy import select
    node = (await db_session.execute(
        select(PlaybookNodeDB).where(PlaybookNodeDB.slug == result["slug"])
    )).scalar_one()
    assert node.parent_id == playbook_tree["group"].id
    assert node.type == "page"


@pytest.mark.asyncio
async def test_update_article_content(
    db_session: AsyncSession, test_user: UserDB, playbook_tree: dict,
) -> None:
    from mcp_server.handlers.playbook import execute

    result = await execute(
        "update_article_content", "onboarding",
        {"content": "# Onboarding\n\nUpdated welcome guide.\n\n## Tools"},
        test_user.id, db_session,
    )
    assert result["version"] == 2
    assert result["conflict"] is False


@pytest.mark.asyncio
async def test_update_node_title(
    db_session: AsyncSession, test_user: UserDB, playbook_tree: dict,
) -> None:
    from mcp_server.handlers.playbook import execute

    result = await execute(
        "update_node", "onboarding",
        {"title": "Welcome Guide"},
        test_user.id, db_session,
    )
    assert result["title"] == "Welcome Guide"
    assert "welcome-guide" in result["slug"]


@pytest.mark.asyncio
async def test_delete_leaf_node(
    db_session: AsyncSession, test_user: UserDB, playbook_tree: dict,
) -> None:
    from mcp_server.handlers.playbook import execute

    result = await execute(
        "delete_node", "onboarding", {},
        test_user.id, db_session,
    )
    assert result["ok"] is True

    from sqlalchemy import select
    node = (await db_session.execute(
        select(PlaybookNodeDB).where(PlaybookNodeDB.slug == "onboarding")
    )).scalar_one_or_none()
    assert node is None


@pytest.mark.asyncio
async def test_delete_node_with_children_rejected(
    db_session: AsyncSession, test_user: UserDB, playbook_tree: dict,
) -> None:
    from mcp_server.handlers.playbook import execute

    with pytest.raises(ValueError, match="has children"):
        await execute(
            "delete_node", "getting-started", {},
            test_user.id, db_session,
        )


@pytest.mark.asyncio
async def test_unknown_action_raises(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    from mcp_server.handlers.playbook import execute

    with pytest.raises(ValueError, match="Unknown action"):
        await execute("nonexistent", None, {}, test_user.id, db_session)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_handler_playbook.py -xvs`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.handlers.playbook'`

- [ ] **Step 3: Implement Playbook handler**

Create `mcp_server/handlers/playbook.py`:

```python
"""Playbook command handler.

Dispatches write actions for playbook articles and nodes.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.content_version_service import ContentVersionService
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.modules.playbook.services.tree_service import (
    ensure_unique_slug,
    generate_slug,
    get_next_position,
    validate_depth,
    validate_not_circular,
)

logger = structlog.get_logger()

_versions = ContentVersionService(
    model_class=PlaybookPageVersionDB,
    entity_fk_field="node_id",
)

MODULE = "playbook"


async def execute(
    action: str,
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    """Dispatch a playbook action. Raises ValueError on failure."""
    handler = _ACTIONS.get(action)
    if handler is None:
        raise ValueError(f"Unknown action: {action}")
    return await handler(target, payload, user_id, session)


async def _resolve_node_by_slug(
    session: AsyncSession, slug: str, expected_type: str | None = None,
) -> PlaybookNodeDB:
    result = await session.execute(
        select(PlaybookNodeDB).where(PlaybookNodeDB.slug == slug)
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise ValueError(f"Node '{slug}' not found")
    if expected_type and node.type != expected_type:
        raise ValueError(f"Node '{slug}' is type '{node.type}', expected '{expected_type}'")
    return node


async def _create_article(
    target: str | None, payload: dict, user_id: UUID, session: AsyncSession,
) -> dict:
    parent = await _resolve_node_by_slug(session, target, expected_type="group")
    title = payload["title"]

    if not await validate_depth(session, parent.id):
        raise ValueError("Maximum tree depth exceeded (10 levels)")

    slug = generate_slug(title)
    slug = await ensure_unique_slug(session, slug)
    position = await get_next_position(session, parent.id)

    node = PlaybookNodeDB(
        title=title, slug=slug, type="page",
        parent_id=parent.id, position=position,
        created_by_id=user_id, updated_by_id=user_id,
    )
    session.add(node)
    await session.flush()
    await session.refresh(node)

    logger.info("mcp_playbook_article_created", node_id=str(node.id), title=title)
    return {"node_id": str(node.id), "slug": node.slug, "title": node.title}


async def _update_article_content(
    target: str | None, payload: dict, user_id: UUID, session: AsyncSession,
) -> dict:
    node = await _resolve_node_by_slug(session, target, expected_type="page")
    content = payload["content"]

    new_version, conflict = await _versions.save_version(
        session, entity_id=node.id, content=content,
        user_id=user_id, expected_version=payload.get("expected_version"),
    )

    h1_title = _extract_h1(content)
    if h1_title and h1_title != node.title:
        node.title = h1_title
        node.slug = await ensure_unique_slug(
            session, generate_slug(h1_title), exclude_id=node.id,
        )
        node.updated_by_id = user_id
        await session.flush()

    logger.info("mcp_playbook_article_updated", node_id=str(node.id), version=new_version)
    return {"node_id": str(node.id), "version": new_version, "conflict": conflict}


async def _update_node(
    target: str | None, payload: dict, user_id: UUID, session: AsyncSession,
) -> dict:
    node = await _resolve_node_by_slug(session, target)

    if "parent_slug" in payload:
        parent = await _resolve_node_by_slug(session, payload["parent_slug"], "group")
        if not await validate_not_circular(session, node.id, parent.id):
            raise ValueError("Cannot move node under its own descendant")
        if not await validate_depth(session, parent.id):
            raise ValueError("Maximum tree depth exceeded (10 levels)")
        node.parent_id = parent.id

    if "title" in payload and payload["title"] != node.title:
        node.title = payload["title"]
        node.slug = await ensure_unique_slug(
            session, generate_slug(payload["title"]), exclude_id=node.id,
        )

    node.updated_by_id = user_id
    await session.flush()
    await session.refresh(node)

    logger.info("mcp_playbook_node_updated", node_id=str(node.id))
    return {
        "node_id": str(node.id),
        "slug": node.slug,
        "title": node.title,
        "parent_id": str(node.parent_id) if node.parent_id else None,
    }


async def _delete_node(
    target: str | None, payload: dict, user_id: UUID, session: AsyncSession,
) -> dict:
    node = await _resolve_node_by_slug(session, target)

    children_count = await session.execute(
        select(sa_func.count()).select_from(PlaybookNodeDB).where(
            PlaybookNodeDB.parent_id == node.id
        )
    )
    if children_count.scalar_one() > 0:
        raise ValueError(
            f"Node '{target}' has children. Delete children first."
        )

    await session.delete(node)
    await session.flush()

    logger.info("mcp_playbook_node_deleted", node_id=str(node.id))
    return {"ok": True}


def _extract_h1(content: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped and not stripped.startswith("#"):
            break
    return None


_ACTIONS = {
    "create_article": _create_article,
    "update_article_content": _update_article_content,
    "update_node": _update_node,
    "delete_node": _delete_node,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_handler_playbook.py -xvs`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/handlers/playbook.py mcp_server/tests/test_handler_playbook.py
git commit -m "feat(mcp): add Playbook command handler with 4 actions"
```

---

### Task 6: Summary Generation

Summary generation happens at enqueue time inside each write tool. This task adds the summary helpers that the tools will use.

**Files:**
- Create: `mcp_server/services/summary.py`
- Create: `mcp_server/tests/test_summary.py`

- [ ] **Step 1: Write failing tests for summary generation**

Create `mcp_server/tests/test_summary.py`:

```python
"""Tests for command summary generation."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.iso_docs.models.registry_type import RegistryTypeDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.playbook.models.node import PlaybookNodeDB


@pytest_asyncio.fixture
async def iso_tree(db_session: AsyncSession) -> dict:
    group = IsoDocNodeDB(title="Policies", slug="policies", type="group")
    db_session.add(group)
    await db_session.flush()
    page = IsoDocNodeDB(
        title="Security Policy", slug="security-policy",
        type="page", parent_id=group.id,
    )
    db_session.add(page)
    await db_session.flush()
    meta = IsoDocMetadataDB(
        node_id=page.id, classification="internal_use", status="draft",
    )
    db_session.add(meta)
    version = IsoDocVersionDB(
        node_id=page.id, version=1, content="# Security Policy\n\nContent.",
    )
    db_session.add(version)
    await db_session.flush()
    return {"group": group, "page": page}


@pytest_asyncio.fixture
async def registry_setup(db_session: AsyncSession) -> dict:
    rt = RegistryTypeDB(
        name="Incident Register", slug="incident-register",
        description="Incidents", is_yearly=True,
        schema=[
            {"key": "number", "label": "Number", "type": "string", "required": True},
            {"key": "severity", "label": "Severity", "type": "select",
             "options": ["Critical", "High", "Medium", "Low"]},
        ],
    )
    db_session.add(rt)
    await db_session.flush()
    node = IsoDocNodeDB(
        title="Incident Register", slug="incident-register",
        type="registry", registry_type_id=rt.id,
    )
    db_session.add(node)
    await db_session.flush()
    row = RegistryRowDB(
        node_id=node.id, year=2026, row_index=0,
        data={"number": "INC-001", "severity": "High"},
    )
    db_session.add(row)
    await db_session.flush()
    return {"rt": rt, "node": node, "row": row}


@pytest.mark.asyncio
async def test_summary_create_page(db_session: AsyncSession, iso_tree: dict) -> None:
    from mcp_server.services.summary import generate_summary

    s = await generate_summary(
        db_session, "iso_docs", "create_page", "policies", {"title": "Data Retention"},
    )
    assert "Data Retention" in s
    assert "Policies" in s


@pytest.mark.asyncio
async def test_summary_update_page_content(db_session: AsyncSession, iso_tree: dict) -> None:
    from mcp_server.services.summary import generate_summary

    s = await generate_summary(
        db_session, "iso_docs", "update_page_content", "security-policy",
        {"content": "new content"},
    )
    assert "Security Policy" in s
    assert "v1" in s or "v2" in s


@pytest.mark.asyncio
async def test_summary_update_metadata_diff(db_session: AsyncSession, iso_tree: dict) -> None:
    from mcp_server.services.summary import generate_summary

    s = await generate_summary(
        db_session, "iso_docs", "update_metadata", "security-policy",
        {"status": "approved", "code": "POL-001"},
    )
    assert "Security Policy" in s
    assert "status" in s.lower()


@pytest.mark.asyncio
async def test_summary_create_registry_row(
    db_session: AsyncSession, registry_setup: dict,
) -> None:
    from mcp_server.services.summary import generate_summary

    s = await generate_summary(
        db_session, "iso_docs", "create_registry_row", "incident-register",
        {"year": 2026, "data": {"number": "INC-002", "severity": "Medium"}},
    )
    assert "Incident Register" in s
    assert "INC-002" in s


@pytest.mark.asyncio
async def test_summary_update_registry_row_uses_labels(
    db_session: AsyncSession, registry_setup: dict,
) -> None:
    from mcp_server.services.summary import generate_summary

    s = await generate_summary(
        db_session, "iso_docs", "update_registry_row", "incident-register",
        {"row_id": str(registry_setup["row"].id), "data": {"severity": "Critical"}},
    )
    assert "Incident Register" in s
    assert "Severity" in s or "severity" in s


@pytest.mark.asyncio
async def test_summary_delete_node(db_session: AsyncSession, iso_tree: dict) -> None:
    from mcp_server.services.summary import generate_summary

    s = await generate_summary(
        db_session, "iso_docs", "delete_node", "security-policy", {},
    )
    assert "Security Policy" in s
    assert "Delete" in s or "delete" in s


@pytest.mark.asyncio
async def test_summary_playbook_create(db_session: AsyncSession) -> None:
    from mcp_server.services.summary import generate_summary

    group = PlaybookNodeDB(title="Guides", slug="guides", type="group")
    db_session.add(group)
    await db_session.flush()

    s = await generate_summary(
        db_session, "playbook", "create_article", "guides", {"title": "Setup Guide"},
    )
    assert "Setup Guide" in s
    assert "Guides" in s
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_summary.py -xvs`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement summary generation**

Create `mcp_server/services/summary.py`:

```python
"""Human-readable summary generation for command queue entries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.content_version_service import ContentVersionService
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.models.registry_type import RegistryTypeDB
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB

_iso_versions = ContentVersionService(IsoDocVersionDB, "node_id")
_pb_versions = ContentVersionService(PlaybookPageVersionDB, "node_id")


async def generate_summary(
    session: AsyncSession,
    module: str,
    action: str,
    target: str | None,
    payload: dict,
) -> str:
    """Generate a human-readable summary for a command."""
    key = (module, action)
    generator = _GENERATORS.get(key)
    if generator is None:
        return f"{action} on {target or module}"
    return await generator(session, target, payload)


# --- ISO Docs summaries ---

async def _iso_node_title(session: AsyncSession, slug: str) -> str:
    result = await session.execute(
        select(IsoDocNodeDB.title).where(IsoDocNodeDB.slug == slug)
    )
    return result.scalar_one_or_none() or slug


async def _iso_parent_title(session: AsyncSession, slug: str) -> str:
    result = await session.execute(
        select(IsoDocNodeDB.title, IsoDocNodeDB.id)
        .where(IsoDocNodeDB.slug == slug)
    )
    row = result.first()
    if row is None:
        return slug
    return row.title


async def _sum_create_page(session, target, payload):
    parent_title = await _iso_parent_title(session, target)
    title = payload.get("title", "Untitled")
    return f"Create page **{title}** in {parent_title}"


async def _sum_update_page_content(session, target, payload):
    title = await _iso_node_title(session, target)
    node = (await session.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.slug == target)
    )).scalar_one_or_none()
    if node:
        latest = await _iso_versions.get_latest(session, entity_id=node.id)
        v = latest.version if latest else 0
        return f"Update content of **{title}** (v{v} → v{v + 1})"
    return f"Update content of **{title}**"


async def _sum_update_metadata(session, target, payload):
    title = await _iso_node_title(session, target)
    fields = list(payload.keys())
    field_str = ", ".join(fields[:3])
    if len(fields) > 3:
        field_str += f" (+{len(fields) - 3} more)"
    return f"Update metadata of **{title}**: {field_str}"


async def _sum_update_node(session, target, payload):
    title = await _iso_node_title(session, target)
    parts = []
    if "title" in payload:
        parts.append(f"Rename **{title}** → **{payload['title']}**")
    if "parent_slug" in payload:
        parent_title = await _iso_parent_title(session, payload["parent_slug"])
        parts.append(f"Move **{title}** to {parent_title}")
    return "; ".join(parts) if parts else f"Update **{title}**"


async def _sum_delete_node(session, target, payload):
    title = await _iso_node_title(session, target)
    return f"Delete **{title}**"


async def _sum_create_registry_row(session, target, payload):
    title = await _iso_node_title(session, target)
    data_str = _format_row_data(session, target, payload.get("data", {}))
    return f"Create row in **{title}**: {data_str}"


def _format_row_data(session, target, data: dict) -> str:
    """Format row data as key: value pairs, truncated."""
    items = [f"{k}: {v}" for k, v in list(data.items())[:3]]
    return ", ".join(items) if items else "(empty)"


async def _sum_update_registry_row(session, target, payload):
    title = await _iso_node_title(session, target)
    data = payload.get("data", {})
    changes = ", ".join(f"{k}: {v}" for k, v in list(data.items())[:3])
    return f"Update row in **{title}**: {changes}"


async def _sum_delete_registry_row(session, target, payload):
    title = await _iso_node_title(session, target)
    return f"Delete row from **{title}**"


# --- Playbook summaries ---

async def _pb_node_title(session: AsyncSession, slug: str) -> str:
    result = await session.execute(
        select(PlaybookNodeDB.title).where(PlaybookNodeDB.slug == slug)
    )
    return result.scalar_one_or_none() or slug


async def _sum_pb_create_article(session, target, payload):
    parent_title = await _pb_node_title(session, target)
    title = payload.get("title", "Untitled")
    return f"Create article **{title}** in {parent_title}"


async def _sum_pb_update_content(session, target, payload):
    title = await _pb_node_title(session, target)
    node = (await session.execute(
        select(PlaybookNodeDB).where(PlaybookNodeDB.slug == target)
    )).scalar_one_or_none()
    if node:
        latest = await _pb_versions.get_latest(session, entity_id=node.id)
        v = latest.version if latest else 0
        return f"Update content of **{title}** (v{v} → v{v + 1})"
    return f"Update content of **{title}**"


async def _sum_pb_update_node(session, target, payload):
    title = await _pb_node_title(session, target)
    parts = []
    if "title" in payload:
        parts.append(f"Rename **{title}** → **{payload['title']}**")
    if "parent_slug" in payload:
        parent_title = await _pb_node_title(session, payload["parent_slug"])
        parts.append(f"Move **{title}** to {parent_title}")
    return "; ".join(parts) if parts else f"Update **{title}**"


async def _sum_pb_delete_node(session, target, payload):
    title = await _pb_node_title(session, target)
    return f"Delete **{title}**"


# --- Generator dispatch ---

_GENERATORS = {
    ("iso_docs", "create_page"): _sum_create_page,
    ("iso_docs", "update_page_content"): _sum_update_page_content,
    ("iso_docs", "update_metadata"): _sum_update_metadata,
    ("iso_docs", "update_node"): _sum_update_node,
    ("iso_docs", "delete_node"): _sum_delete_node,
    ("iso_docs", "create_registry_row"): _sum_create_registry_row,
    ("iso_docs", "update_registry_row"): _sum_update_registry_row,
    ("iso_docs", "delete_registry_row"): _sum_delete_registry_row,
    ("playbook", "create_article"): _sum_pb_create_article,
    ("playbook", "update_article_content"): _sum_pb_update_content,
    ("playbook", "update_node"): _sum_pb_update_node,
    ("playbook", "delete_node"): _sum_pb_delete_node,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_summary.py -xvs`
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/services/summary.py mcp_server/tests/test_summary.py
git commit -m "feat(mcp): add human-readable summary generation for commands"
```

---

### Task 7: ISO Write Tools (8 MCP tools)

**Files:**
- Create: `mcp_server/tools/iso_write.py`
- Modify: `mcp_server/server.py`

- [ ] **Step 1: Write failing integration test**

Create `mcp_server/tests/test_command_tools.py`:

```python
"""Integration tests — MCP write tools + command queue."""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.iso_docs.models import (
    IsoDocMetadataDB,
    IsoDocNodeDB,
    IsoDocVersionDB,
    RegistryRowDB,
    RegistryTypeDB,
)
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from mcp_server.data.base import McpUserContext, override_mcp_user, override_session
from mcp_server.server import mcp


@pytest_asyncio.fixture
async def editor_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        email="editor@vizzuality.com",
        name="Editor",
        first_name="Test",
        last_name="Editor",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def editor_ctx(editor_user: UserDB) -> McpUserContext:
    return McpUserContext(
        user_id=str(editor_user.id),
        email=editor_user.email,
        roles=["admin"],
        permissions=["*"],
    )


@pytest_asyncio.fixture
async def seeded_iso(db_session: AsyncSession) -> dict:
    group = IsoDocNodeDB(title="Policies", slug="policies", type="group")
    db_session.add(group)
    await db_session.flush()

    page = IsoDocNodeDB(
        title="Security Policy", slug="security-policy",
        type="page", parent_id=group.id,
    )
    db_session.add(page)
    await db_session.flush()

    db_session.add(IsoDocMetadataDB(node_id=page.id))
    db_session.add(IsoDocVersionDB(
        node_id=page.id, version=1,
        content="# Security Policy\n\nContent.",
    ))

    rt = RegistryTypeDB(
        name="Incident Register", slug="incident-register",
        description="Incidents", is_yearly=True,
        schema=[
            {"key": "number", "label": "Number", "type": "string", "required": True},
            {"key": "severity", "label": "Severity", "type": "select",
             "options": ["Critical", "High", "Medium", "Low"]},
        ],
    )
    db_session.add(rt)
    await db_session.flush()

    reg_node = IsoDocNodeDB(
        title="Incident Register", slug="incident-register",
        type="registry", registry_type_id=rt.id,
    )
    db_session.add(reg_node)
    await db_session.flush()
    db_session.add(IsoDocMetadataDB(node_id=reg_node.id))

    await db_session.commit()
    return {"group": group, "page": page, "rt": rt, "reg_node": reg_node}


@pytest.mark.asyncio
async def test_iso_create_page_enqueue_and_approve(
    db_session: AsyncSession, editor_user: UserDB, editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "Data Retention Policy"},
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "queued"
            command_id = data["command_id"]

            result = await mcp.call_tool(
                "approve_command", {"command_id": command_id},
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "executed"
            assert "slug" in data["result"]


@pytest.mark.asyncio
async def test_iso_create_registry_row_enqueue_and_approve(
    db_session: AsyncSession, editor_user: UserDB, editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "iso_create_registry_row",
                {"slug": "incident-register", "year": 2026,
                 "data": {"number": "INC-001", "severity": "High"}},
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "queued"
            assert "INC-001" in data["summary"]

            result = await mcp.call_tool(
                "approve_command", {"command_id": data["command_id"]},
            )
            approved = json.loads(result[0][0].text)
            assert approved["status"] == "executed"
            assert approved["result"]["data"]["number"] == "INC-001"


@pytest.mark.asyncio
async def test_reject_command(
    db_session: AsyncSession, editor_user: UserDB, editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "Draft Policy"},
            )
            data = json.loads(result[0][0].text)

            result = await mcp.call_tool(
                "reject_command", {"command_id": data["command_id"]},
            )
            rejected = json.loads(result[0][0].text)
            assert rejected["status"] == "rejected"


@pytest.mark.asyncio
async def test_get_pending_commands(
    db_session: AsyncSession, editor_user: UserDB, editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "Policy A"},
            )
            await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "Policy B"},
            )

            result = await mcp.call_tool(
                "get_pending_commands", {},
            )
            data = json.loads(result[0][0].text)
            assert len(data) == 2


@pytest.mark.asyncio
async def test_permission_denied_for_write_tool(
    db_session: AsyncSession, editor_user: UserDB, seeded_iso: dict,
) -> None:
    read_only_ctx = McpUserContext(
        user_id=str(editor_user.id),
        email=editor_user.email,
        roles=["user"],
        permissions=["tracker:view"],
    )
    async with override_session(db_session):
        async with override_mcp_user(read_only_ctx):
            result = await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "Blocked"},
            )
            data = json.loads(result[0][0].text)
            assert "error" in data
            assert "Permission denied" in data["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_command_tools.py::test_iso_create_page_enqueue_and_approve -xvs`
Expected: FAIL — tool `iso_create_page` not registered.

- [ ] **Step 3: Implement ISO write tools**

Create `mcp_server/tools/iso_write.py`:

```python
"""ISO docs + registries write tools — enqueue commands for approval."""

from __future__ import annotations

import json
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from mcp_server.auth.permissions import mcp_requires
from mcp_server.data.base import get_mcp_user, get_write_session
from mcp_server.handlers import iso_docs as iso_handler
from mcp_server.models.command import CommandDB
from mcp_server.services.command_service import CommandService
from mcp_server.services.summary import generate_summary

_MODULE = "iso_docs"


def _to_json(data: object) -> str:
    return json.dumps(data, indent=2, default=str)


async def _enqueue_iso(action: str, target: str | None, payload: dict) -> str:
    """Common enqueue logic for ISO write tools."""
    user = get_mcp_user()
    user_id = UUID(user.user_id)

    async with get_write_session() as session:
        summary = await generate_summary(session, _MODULE, action, target, payload)
        svc = CommandService(session)
        cmd = await svc.enqueue(
            module=_MODULE, action=action, target=target,
            payload=payload, summary=summary, user_id=user_id,
        )
        return _to_json({
            "status": "queued",
            "command_id": str(cmd.id),
            "summary": cmd.summary,
            "message": f"Command queued. Use approve_command('{cmd.id}') to execute.",
        })


@mcp_requires("iso_docs:edit")
async def iso_create_page(parent_slug: str, title: str) -> str:
    """Create a new ISO doc page under the specified parent group.

    Does NOT execute immediately — creates a pending command.
    Use approve_command() to execute after review.

    Args:
        parent_slug: Slug of the parent group node (e.g. "policies")
        title: Title for the new page
    """
    return await _enqueue_iso("create_page", parent_slug, {"title": title})


@mcp_requires("iso_docs:edit")
async def iso_update_page_content(slug: str, content: str) -> str:
    """Update the markdown content of an ISO doc page (creates new version).

    Does NOT execute immediately — creates a pending command.
    Use approve_command() to execute after review.

    Args:
        slug: Page slug (e.g. "security-policy")
        content: Full markdown content (include # H1 title as first line)
    """
    return await _enqueue_iso("update_page_content", slug, {"content": content})


@mcp_requires("iso_docs:edit")
async def iso_update_page_metadata(
    slug: str,
    code: str | None = None,
    standard: list[str] | None = None,
    clauses: list[str] | None = None,
    classification: str | None = None,
    status: str | None = None,
    document_date: str | None = None,
    original_filename: str | None = None,
    guidance: str | None = None,
    changelog: list[dict] | None = None,
) -> str:
    """Update metadata fields of an ISO doc page.

    Does NOT execute immediately — creates a pending command.
    Only fields provided will be updated (partial update).

    Args:
        slug: Page slug
        code: Document code (max 50 chars, e.g. "POL-001")
        standard: List of standards (e.g. ["ISO 27001", "ISO 9001"])
        clauses: List of clause references (e.g. ["5.2", "A.5.1"])
        classification: "internal_use" or "confidential"
        status: "draft", "approved", or "under_review"
        document_date: Date string (YYYY-MM-DD)
        original_filename: Original filename if imported
        guidance: Guidance text
        changelog: List of {version, date, author, description} entries
    """
    payload = {}
    for key, val in [
        ("code", code), ("standard", standard), ("clauses", clauses),
        ("classification", classification), ("status", status),
        ("document_date", document_date), ("original_filename", original_filename),
        ("guidance", guidance), ("changelog", changelog),
    ]:
        if val is not None:
            payload[key] = val
    return await _enqueue_iso("update_metadata", slug, payload)


@mcp_requires("iso_docs:edit")
async def iso_update_node(
    slug: str,
    title: str | None = None,
    parent_slug: str | None = None,
) -> str:
    """Rename or move an ISO doc node (page or group).

    Does NOT execute immediately — creates a pending command.

    Args:
        slug: Node slug to update
        title: New title (optional)
        parent_slug: Slug of the new parent group to move under (optional)
    """
    payload = {}
    if title is not None:
        payload["title"] = title
    if parent_slug is not None:
        payload["parent_slug"] = parent_slug
    return await _enqueue_iso("update_node", slug, payload)


@mcp_requires("iso_docs:edit")
async def iso_delete_node(slug: str) -> str:
    """Delete an ISO doc node (leaf nodes only — no children allowed).

    Does NOT execute immediately — creates a pending command.

    Args:
        slug: Slug of the node to delete
    """
    return await _enqueue_iso("delete_node", slug, {})


@mcp_requires("iso_docs:edit")
async def iso_create_registry_row(
    slug: str, data: dict, year: int | None = None,
) -> str:
    """Create a new row in an ISO registry.

    Does NOT execute immediately — creates a pending command.

    Args:
        slug: Registry slug (e.g. "incident-register")
        data: Row data as key-value pairs matching the registry schema
        year: Year for yearly registries (required if registry is yearly)
    """
    payload: dict = {"data": data}
    if year is not None:
        payload["year"] = year
    return await _enqueue_iso("create_registry_row", slug, payload)


@mcp_requires("iso_docs:edit")
async def iso_update_registry_row(
    slug: str, row_id: str, data: dict,
) -> str:
    """Update an existing row in an ISO registry.

    Does NOT execute immediately — creates a pending command.
    Only provided fields are updated (merged with existing data).

    Args:
        slug: Registry slug
        row_id: UUID of the row to update
        data: Fields to update as key-value pairs
    """
    return await _enqueue_iso(
        "update_registry_row", slug, {"row_id": row_id, "data": data},
    )


@mcp_requires("iso_docs:edit")
async def iso_delete_registry_row(slug: str, row_id: str) -> str:
    """Delete a row from an ISO registry.

    Does NOT execute immediately — creates a pending command.

    Args:
        slug: Registry slug
        row_id: UUID of the row to delete
    """
    return await _enqueue_iso("delete_registry_row", slug, {"row_id": row_id})


def register_iso_write_tools(server: FastMCP) -> None:
    """Register all ISO write tools on the MCP server."""
    server.tool()(iso_create_page)
    server.tool()(iso_update_page_content)
    server.tool()(iso_update_page_metadata)
    server.tool()(iso_update_node)
    server.tool()(iso_delete_node)
    server.tool()(iso_create_registry_row)
    server.tool()(iso_update_registry_row)
    server.tool()(iso_delete_registry_row)
```

- [ ] **Step 4: Implement command management tools**

Create `mcp_server/tools/commands.py`:

```python
"""Command queue management tools — list, approve, reject."""

from __future__ import annotations

import json
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from mcp_server.data.base import get_mcp_user, get_write_session
from mcp_server.handlers import iso_docs as iso_handler
from mcp_server.handlers import playbook as playbook_handler
from mcp_server.services.command_service import CommandService

_HANDLERS = {
    "iso_docs": iso_handler.execute,
    "playbook": playbook_handler.execute,
}

_MODULE_PERMISSIONS = {
    "iso_docs": "iso_docs:edit",
    "playbook": "playbook:edit",
}


def _to_json(data: object) -> str:
    return json.dumps(data, indent=2, default=str)


async def get_pending_commands(module: str | None = None) -> str:
    """List your pending commands awaiting approval.

    Args:
        module: Filter by module ("iso_docs" or "playbook"). Omit for all.
    """
    user = get_mcp_user()
    user_id = UUID(user.user_id)

    async with get_write_session() as session:
        svc = CommandService(session)
        commands = await svc.list_pending(user_id=user_id, module=module)
        return _to_json([
            {
                "command_id": str(cmd.id),
                "module": cmd.module,
                "action": cmd.action,
                "summary": cmd.summary,
                "requested_at": cmd.requested_at,
            }
            for cmd in commands
        ])


async def approve_command(command_id: str) -> str:
    """Approve and execute a pending command.

    This executes the queued operation. Only call after user has reviewed
    and explicitly confirmed the command.

    Args:
        command_id: UUID of the command to approve
    """
    user = get_mcp_user()
    reviewer_id = UUID(user.user_id)
    cmd_uuid = UUID(command_id)

    async with get_write_session() as session:
        svc = CommandService(session)
        cmd = await svc.get_command(cmd_uuid)

        required_perm = _MODULE_PERMISSIONS.get(cmd.module)
        if required_perm and not user.has_permission(required_perm):
            return _to_json({
                "error": f"Permission denied: requires {required_perm}",
            })

        executor = _HANDLERS.get(cmd.module)
        if executor is None:
            return _to_json({"error": f"No handler for module '{cmd.module}'"})

        result = await svc.approve(cmd_uuid, reviewer_id, executor=executor)

        if result.status == "executed":
            return _to_json({
                "status": "executed",
                "command_id": str(result.id),
                "result": result.result,
            })
        else:
            return _to_json({
                "status": "failed",
                "command_id": str(result.id),
                "error": result.error,
            })


async def reject_command(command_id: str) -> str:
    """Reject a pending command. The operation will not be executed.

    Args:
        command_id: UUID of the command to reject
    """
    user = get_mcp_user()
    reviewer_id = UUID(user.user_id)
    cmd_uuid = UUID(command_id)

    async with get_write_session() as session:
        svc = CommandService(session)
        cmd = await svc.get_command(cmd_uuid)

        required_perm = _MODULE_PERMISSIONS.get(cmd.module)
        if required_perm and not user.has_permission(required_perm):
            return _to_json({
                "error": f"Permission denied: requires {required_perm}",
            })

        result = await svc.reject(cmd_uuid, reviewer_id)
        return _to_json({
            "status": "rejected",
            "command_id": str(result.id),
        })


def register_command_tools(server: FastMCP) -> None:
    """Register command queue management tools."""
    server.tool()(get_pending_commands)
    server.tool()(approve_command)
    server.tool()(reject_command)
```

- [ ] **Step 5: Register tools in server.py**

Add imports and registration calls to `mcp_server/server.py`. After the existing `register_*_tools` imports, add:

```python
from mcp_server.tools.iso_write import register_iso_write_tools
from mcp_server.tools.commands import register_command_tools
```

In `create_mcp_server()`, after the existing `register_*_tools(instance)` calls, add:

```python
    register_iso_write_tools(instance)
    register_command_tools(instance)
```

- [ ] **Step 6: Run integration tests**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_command_tools.py -xvs`
Expected: All 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add mcp_server/tools/iso_write.py mcp_server/tools/commands.py mcp_server/server.py mcp_server/tests/test_command_tools.py
git commit -m "feat(mcp): add ISO write tools and command management tools"
```

---

### Task 8: Playbook Write Tools (4 MCP tools)

**Files:**
- Create: `mcp_server/tools/playbook_write.py`
- Modify: `mcp_server/server.py`
- Modify: `mcp_server/tests/test_command_tools.py`

- [ ] **Step 1: Add Playbook integration tests**

Append to `mcp_server/tests/test_command_tools.py`:

```python
@pytest_asyncio.fixture
async def seeded_playbook(db_session: AsyncSession) -> dict:
    group = PlaybookNodeDB(title="Guides", slug="guides", type="group")
    db_session.add(group)
    await db_session.flush()

    article = PlaybookNodeDB(
        title="Onboarding", slug="onboarding",
        type="page", parent_id=group.id,
    )
    db_session.add(article)
    await db_session.flush()

    db_session.add(PlaybookPageVersionDB(
        node_id=article.id, version=1,
        content="# Onboarding\n\nWelcome.",
    ))
    await db_session.commit()
    return {"group": group, "article": article}


@pytest.mark.asyncio
async def test_playbook_create_article_enqueue_and_approve(
    db_session: AsyncSession, editor_user: UserDB, editor_ctx: McpUserContext,
    seeded_playbook: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "playbook_create_article",
                {"parent_slug": "guides", "title": "Dev Setup"},
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "queued"

            result = await mcp.call_tool(
                "approve_command", {"command_id": data["command_id"]},
            )
            approved = json.loads(result[0][0].text)
            assert approved["status"] == "executed"
            assert "slug" in approved["result"]


@pytest.mark.asyncio
async def test_playbook_update_article_content(
    db_session: AsyncSession, editor_user: UserDB, editor_ctx: McpUserContext,
    seeded_playbook: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "playbook_update_article_content",
                {"slug": "onboarding", "content": "# Onboarding\n\nUpdated guide."},
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "queued"

            result = await mcp.call_tool(
                "approve_command", {"command_id": data["command_id"]},
            )
            approved = json.loads(result[0][0].text)
            assert approved["status"] == "executed"
            assert approved["result"]["version"] == 2
```

- [ ] **Step 2: Implement Playbook write tools**

Create `mcp_server/tools/playbook_write.py`:

```python
"""Playbook write tools — enqueue commands for approval."""

from __future__ import annotations

import json
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from mcp_server.auth.permissions import mcp_requires
from mcp_server.data.base import get_mcp_user, get_write_session
from mcp_server.services.command_service import CommandService
from mcp_server.services.summary import generate_summary

_MODULE = "playbook"


def _to_json(data: object) -> str:
    return json.dumps(data, indent=2, default=str)


async def _enqueue_playbook(action: str, target: str | None, payload: dict) -> str:
    user = get_mcp_user()
    user_id = UUID(user.user_id)

    async with get_write_session() as session:
        summary = await generate_summary(session, _MODULE, action, target, payload)
        svc = CommandService(session)
        cmd = await svc.enqueue(
            module=_MODULE, action=action, target=target,
            payload=payload, summary=summary, user_id=user_id,
        )
        return _to_json({
            "status": "queued",
            "command_id": str(cmd.id),
            "summary": cmd.summary,
            "message": f"Command queued. Use approve_command('{cmd.id}') to execute.",
        })


@mcp_requires("playbook:edit")
async def playbook_create_article(parent_slug: str, title: str) -> str:
    """Create a new Playbook article under the specified parent group.

    Does NOT execute immediately — creates a pending command.
    Use approve_command() to execute after review.

    Args:
        parent_slug: Slug of the parent group (e.g. "getting-started")
        title: Title for the new article
    """
    return await _enqueue_playbook("create_article", parent_slug, {"title": title})


@mcp_requires("playbook:edit")
async def playbook_update_article_content(slug: str, content: str) -> str:
    """Update the markdown content of a Playbook article (creates new version).

    Does NOT execute immediately — creates a pending command.

    Args:
        slug: Article slug
        content: Full markdown content (include # H1 title as first line)
    """
    return await _enqueue_playbook("update_article_content", slug, {"content": content})


@mcp_requires("playbook:edit")
async def playbook_update_node(
    slug: str,
    title: str | None = None,
    parent_slug: str | None = None,
) -> str:
    """Rename or move a Playbook node (article or group).

    Does NOT execute immediately — creates a pending command.

    Args:
        slug: Node slug to update
        title: New title (optional)
        parent_slug: Slug of new parent group to move under (optional)
    """
    payload = {}
    if title is not None:
        payload["title"] = title
    if parent_slug is not None:
        payload["parent_slug"] = parent_slug
    return await _enqueue_playbook("update_node", slug, payload)


@mcp_requires("playbook:edit")
async def playbook_delete_node(slug: str) -> str:
    """Delete a Playbook node (leaf nodes only — no children allowed).

    Does NOT execute immediately — creates a pending command.

    Args:
        slug: Slug of the node to delete
    """
    return await _enqueue_playbook("delete_node", slug, {})


def register_playbook_write_tools(server: FastMCP) -> None:
    """Register all Playbook write tools."""
    server.tool()(playbook_create_article)
    server.tool()(playbook_update_article_content)
    server.tool()(playbook_update_node)
    server.tool()(playbook_delete_node)
```

- [ ] **Step 3: Register in server.py**

Add import:
```python
from mcp_server.tools.playbook_write import register_playbook_write_tools
```

Add call in `create_mcp_server()`:
```python
    register_playbook_write_tools(instance)
```

- [ ] **Step 4: Run all integration tests**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/test_command_tools.py -xvs`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/tools/playbook_write.py mcp_server/server.py mcp_server/tests/test_command_tools.py
git commit -m "feat(mcp): add Playbook write tools"
```

---

### Task 9: REST API Endpoints

**Files:**
- Create: `backend/app/core/api/commands.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/modules/core/test_commands_api.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/modules/core/test_commands_api.py`:

```python
"""Tests for command queue REST API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.main import app
from mcp_server.models.command import CommandDB


@pytest.fixture
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.mark.asyncio
async def test_list_commands_empty(admin_headers: dict) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/commands", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_commands_with_status_filter(
    db_session: AsyncSession, admin_user: UserDB, admin_headers: dict,
) -> None:
    cmd = CommandDB(
        module="iso_docs", action="create_page", target="policies",
        payload={"title": "Test"}, summary="Create page **Test** in Policies",
        requested_by=admin_user.id,
    )
    db_session.add(cmd)
    await db_session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/commands", params={"status": "pending"},
            headers=admin_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["summary"] == "Create page **Test** in Policies"
```

Note: This test depends on existing backend test fixtures (`admin_token`, `admin_user`, `db_session`). If these don't exist exactly, adapt to the project's existing fixture pattern in `backend/tests/conftest.py`.

- [ ] **Step 2: Implement REST endpoints**

Create `backend/app/core/api/commands.py`:

```python
"""Command queue REST API — list, approve, reject pending commands."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from mcp_server.models.command import CommandDB

logger = structlog.get_logger()

router = APIRouter(tags=["commands"])


@router.get("/commands")
async def list_commands(
    db: DBSession,
    user: CurrentUser,
    status: Annotated[str | None, Query()] = None,
    module: Annotated[str | None, Query()] = None,
) -> list[dict]:
    """List commands visible to the current user."""
    stmt = select(CommandDB).order_by(CommandDB.requested_at.desc())
    if status:
        stmt = stmt.where(CommandDB.status == status)
    if module:
        stmt = stmt.where(CommandDB.module == module)

    result = await db.execute(stmt)
    commands = result.scalars().all()

    return [
        {
            "id": str(cmd.id),
            "module": cmd.module,
            "action": cmd.action,
            "target": cmd.target,
            "summary": cmd.summary,
            "status": cmd.status,
            "requested_by": str(cmd.requested_by),
            "requested_at": cmd.requested_at.isoformat() if cmd.requested_at else None,
            "reviewed_by": str(cmd.reviewed_by) if cmd.reviewed_by else None,
            "reviewed_at": cmd.reviewed_at.isoformat() if cmd.reviewed_at else None,
            "result": cmd.result,
            "error": cmd.error,
        }
        for cmd in commands
    ]


@router.post(
    "/commands/{command_id}/approve",
    responses={
        404: {"description": "Command not found"},
        400: {"description": "Command is not pending"},
    },
)
async def approve_command(
    command_id: UUID, db: DBSession, user: CurrentUser,
) -> dict:
    """Approve and execute a pending command."""
    from mcp_server.handlers import iso_docs as iso_handler
    from mcp_server.handlers import playbook as playbook_handler
    from mcp_server.services.command_service import CommandService

    handlers = {
        "iso_docs": iso_handler.execute,
        "playbook": playbook_handler.execute,
    }

    svc = CommandService(db)
    try:
        cmd = await svc.get_command(command_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Command not found")

    executor = handlers.get(cmd.module)
    if executor is None:
        raise HTTPException(status_code=400, detail=f"No handler for module '{cmd.module}'")

    try:
        result = await svc.approve(
            command_id, UUID(user.user_id), executor=executor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    logger.info("command_approved", command_id=str(command_id), status=result.status)
    return {"status": result.status, "result": result.result, "error": result.error}


@router.post(
    "/commands/{command_id}/reject",
    responses={
        404: {"description": "Command not found"},
        400: {"description": "Command is not pending"},
    },
)
async def reject_command(
    command_id: UUID, db: DBSession, user: CurrentUser,
) -> dict:
    """Reject a pending command."""
    from mcp_server.services.command_service import CommandService

    svc = CommandService(db)
    try:
        result = await svc.reject(command_id, UUID(user.user_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    logger.info("command_rejected", command_id=str(command_id))
    return {"status": result.status}
```

- [ ] **Step 3: Mount router in main.py**

Add to `backend/app/main.py` imports:
```python
from app.core.api import commands as commands_router
```

Add after the existing `include_router` calls:
```python
app.include_router(commands_router.router, prefix="/api")
```

- [ ] **Step 4: Run tests**

Run: `cd /Volumes/Work/Dev/vizzhub/backend && python -m pytest tests/modules/core/test_commands_api.py -xvs`
Expected: Tests pass (adapt fixtures as needed to match existing test setup).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/api/commands.py backend/app/main.py backend/tests/modules/core/test_commands_api.py
git commit -m "feat(api): add REST endpoints for command queue"
```

---

### Task 10: Wire `enable_backend_write_sessions()` in Lifespan

**Files:**
- Modify: `backend/app/main.py` (lifespan function)

- [ ] **Step 1: Find the lifespan function and add the call**

In `backend/app/main.py`, find the lifespan context manager (where `enable_backend_sessions()` is called) and add `enable_backend_write_sessions()` alongside it:

```python
from mcp_server.data.base import enable_backend_sessions, enable_backend_write_sessions
```

Inside the lifespan, after `enable_backend_sessions()`:
```python
enable_backend_write_sessions()
```

- [ ] **Step 2: Verify the app starts**

Run: `cd /Volumes/Work/Dev/vizzhub/backend && python run_server.py`
Expected: Server starts without errors. Check logs for no import failures.

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(mcp): wire enable_backend_write_sessions in lifespan"
```

---

### Task 11: Run Full Test Suite

- [ ] **Step 1: Run MCP tests**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/ -v`
Expected: All tests pass, including existing read-only tests unchanged.

- [ ] **Step 2: Run backend tests**

Run: `cd /Volumes/Work/Dev/vizzhub/backend && pytest -v`
Expected: All tests pass, including new command API tests.

- [ ] **Step 3: Verify no write tools appear in read-only test**

The existing `test_no_write_tools_registered` in `mcp_server/tests/test_integration.py:124` checks that no `create/update/delete` tools exist. This test needs updating since we now intentionally have write tools.

Update the test to check that write tools ARE registered:

```python
@pytest.mark.asyncio
async def test_write_tools_registered(db_session, seeded_db) -> None:
    """Phase 3B: write tools should be registered."""
    async with override_session(db_session):
        tools = await mcp.list_tools()
    names = [t.name for t in tools]
    assert "iso_create_page" in names
    assert "approve_command" in names
    assert "playbook_create_article" in names
```

- [ ] **Step 4: Run full suite again**

Run: `cd /Volumes/Work/Dev/vizzhub && python -m pytest mcp_server/tests/ -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/tests/test_integration.py
git commit -m "test(mcp): update integration test for write tools"
```

---

### Task 12: Update Documentation

**Files:**
- Modify: `docs/mcp.md`

- [ ] **Step 1: Add command queue section to mcp.md**

Add a new section after the existing tools documentation:

```markdown
## Write Operations (Command Queue)

All write operations go through a human-in-the-loop command queue. Tools enqueue
commands that require explicit approval before execution.

### ISO Docs Write Tools (8)

| Tool | Description |
|---|---|
| `iso_create_page` | Create a new page under a group |
| `iso_update_page_content` | Update page markdown content (versioned) |
| `iso_update_page_metadata` | Update metadata fields (partial update) |
| `iso_update_node` | Rename or move a node |
| `iso_delete_node` | Delete a leaf node (no children) |
| `iso_create_registry_row` | Add a row to a registry |
| `iso_update_registry_row` | Update fields in a registry row |
| `iso_delete_registry_row` | Delete a registry row |

### Playbook Write Tools (4)

| Tool | Description |
|---|---|
| `playbook_create_article` | Create a new article under a group |
| `playbook_update_article_content` | Update article markdown content (versioned) |
| `playbook_update_node` | Rename or move a node |
| `playbook_delete_node` | Delete a leaf node (no children) |

### Queue Management Tools (3)

| Tool | Description |
|---|---|
| `get_pending_commands` | List your pending commands |
| `approve_command` | Approve and execute a command |
| `reject_command` | Reject a command |

### Flow

1. Claude calls a write tool → command is enqueued with `status: queued`
2. Claude presents the summary to the user for review
3. User confirms → Claude calls `approve_command` → command executes
4. User declines → Claude calls `reject_command` → command is discarded

### REST API

Commands are also accessible via REST for future UI integration:

- `GET /api/commands?status=pending&module=iso_docs`
- `POST /api/commands/{id}/approve`
- `POST /api/commands/{id}/reject`
```

- [ ] **Step 2: Commit**

```bash
git add docs/mcp.md
git commit -m "docs(mcp): add command queue documentation"
```
