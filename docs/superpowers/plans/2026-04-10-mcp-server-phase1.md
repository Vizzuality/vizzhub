# MCP Server Phase 1 — Read-Only ISO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only MCP server that exposes ISO registries and documents to Claude Code and Claude Desktop via stdio transport.

**Architecture:** Separate `mcp_server/` package at the repo root. Data layer with read-only PostgreSQL sessions imports backend models directly. Tools are thin wrappers using the FastMCP decorator API. No auth for local-only Phase 1.

**Tech Stack:** Python MCP SDK (`mcp`), SQLAlchemy async, PostgreSQL `tsvector`/GIN for full-text search, pytest + `anyio` for testing.

**Spec:** `docs/superpowers/specs/2026-04-10-mcp-server-phase1-design.md`

---

### Task 1: Project Scaffolding

**Files:**
- Create: `mcp_server/__init__.py`
- Create: `mcp_server/__main__.py`
- Create: `mcp_server/server.py`
- Create: `mcp_server/config.py`
- Create: `mcp_server/data/__init__.py`
- Create: `mcp_server/data/base.py`
- Create: `mcp_server/data/iso.py` (empty)
- Create: `mcp_server/tools/__init__.py`
- Create: `mcp_server/tools/iso.py` (empty)
- Create: `mcp_server/tests/__init__.py`
- Create: `mcp_server/tests/conftest.py`
- Create: `requirements-mcp.txt`
- Modify: `.dockerignore`

- [ ] **Step 1: Create `requirements-mcp.txt`**

```
mcp>=1.12.0
```

- [ ] **Step 2: Install the MCP SDK**

Run: `pip install -r requirements-mcp.txt`
Expected: Successful installation of the `mcp` package.

- [ ] **Step 3: Create `mcp_server/config.py`**

```python
"""MCP server configuration — reads from environment variables."""

import os


class MCPSettings:
    """Settings for the VizzHub MCP server."""

    def __init__(self) -> None:
        self.database_url: str = os.environ["DATABASE_URL"]
        self.mcp_user_email: str = os.environ.get(
            "MCP_USER_EMAIL", "unknown@vizzuality.com"
        )


_settings: MCPSettings | None = None


def get_settings() -> MCPSettings:
    global _settings
    if _settings is None:
        _settings = MCPSettings()
    return _settings
```

- [ ] **Step 4: Create `mcp_server/data/base.py`**

Read-only session factory. This engine rejects any INSERT/UPDATE/DELETE at the PostgreSQL connection level. Includes a `ContextVar`-based override for tests so tools use the test DB session instead of creating their own.

```python
"""Read-only database session factory for MCP server."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from contextvars import ContextVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mcp_server.config import get_settings

_engine = None
_session_maker = None

# Test override: when set, get_read_session() uses this session
# instead of creating one from the engine.
_session_override: ContextVar[AsyncSession | None] = ContextVar(
    "_session_override", default=None
)


def _get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_maker
    if _session_maker is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            execution_options={"postgresql_readonly": True},
            echo=False,
        )
        _session_maker = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False,
        )
    return _session_maker


def reset_engine() -> None:
    """Reset cached engine and session maker. Used in tests."""
    global _engine, _session_maker
    _engine = None
    _session_maker = None


@asynccontextmanager
async def get_read_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a read-only async session. Never commits.

    If a session override is set (via tests), yields that instead.
    """
    override = _session_override.get()
    if override is not None:
        yield override
        return

    maker = _get_session_maker()
    async with maker() as session:
        yield session


@asynccontextmanager
async def override_session(session: AsyncSession):
    """Context manager to override the read session for testing.

    Usage in tests:
        async with override_session(db_session):
            result = await client.call_tool("iso_get_registries", {})
    """
    token = _session_override.set(session)
    try:
        yield
    finally:
        _session_override.reset(token)
```

- [ ] **Step 5: Create `mcp_server/server.py`**

Minimal server that will be wired up in later tasks.

```python
"""MCP server definition — registers tools from each module."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "VizzHub",
    instructions=(
        "VizzHub is Vizzuality's internal operations hub. "
        "Use the ISO tools to query compliance registries and documents. "
        "Registry slugs are listed by iso_get_registries. "
        "Document content can be searched with iso_search_documents."
    ),
)
```

- [ ] **Step 6: Create `mcp_server/__main__.py`**

```python
"""Entrypoint: python -m mcp_server"""

from mcp_server.server import mcp


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Create empty module files**

Create these as empty files (or with a single docstring):

`mcp_server/__init__.py`:
```python
```

`mcp_server/data/__init__.py`:
```python
```

`mcp_server/data/iso.py`:
```python
"""ISO data access — registry types, rows, documents, search."""
```

`mcp_server/tools/__init__.py`:
```python
```

`mcp_server/tools/iso.py`:
```python
"""ISO MCP tools — registered on the FastMCP server."""
```

`mcp_server/tests/__init__.py`:
```python
```

- [ ] **Step 8: Create `mcp_server/tests/conftest.py`**

Reuses the backend's test DB setup. `PYTHONPATH` must include `backend/` when running tests.

```python
"""Shared test fixtures for MCP server tests."""

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret-key-for-testing")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard_test",
)

from collections.abc import AsyncGenerator
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base

_TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(autouse=True)
def _mock_encryption_key():
    with patch("app.core.token_encryption.get_settings") as mock:
        mock.return_value.oauth_encryption_key = _TEST_ENCRYPTION_KEY
        yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def use_test_db(db_session: AsyncSession):
    """Ensure all MCP tools use the test DB session via override."""
    from mcp_server.data.base import override_session

    async with override_session(db_session):
        yield
```

- [ ] **Step 9: Add `mcp_server/` to `.dockerignore`**

Append to `.dockerignore`:

```
mcp_server/
requirements-mcp.txt
```

- [ ] **Step 10: Verify the scaffold imports**

Run: `PYTHONPATH=backend DATABASE_URL=postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard python -c "from mcp_server.server import mcp; print(mcp.name)"`
Expected: `VizzHub`

- [ ] **Step 10b: Verify the stdio entrypoint resolves**

Run: `PYTHONPATH=backend DATABASE_URL=postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard timeout 2 python -m mcp_server 2>&1 || true`
Expected: Process starts and waits for stdio input (no import errors, no crashes). The `timeout` kills it after 2 seconds since it blocks waiting for input. Verify there are no error messages in the output.

- [ ] **Step 11: Commit**

```bash
git add mcp_server/ requirements-mcp.txt .dockerignore
git commit -m "feat(mcp): scaffold MCP server package with read-only data layer"
```

---

### Task 2: Data Layer — Registry Types

**Files:**
- Modify: `mcp_server/data/iso.py`
- Create: `mcp_server/tests/test_iso_data.py`

- [ ] **Step 1: Write the failing test for `get_registry_types`**

```python
"""Tests for mcp_server.data.iso — registry queries."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models import RegistryTypeDB


@pytest_asyncio.fixture
async def seed_registry_types(db_session: AsyncSession) -> list[RegistryTypeDB]:
    rt1 = RegistryTypeDB(
        name="Incident Register",
        slug="incident-register",
        description="Security incidents per ISO 27001 A.16",
        is_yearly=True,
        schema=[
            {"key": "number", "label": "Number", "type": "string", "required": True},
            {"key": "date", "label": "Date", "type": "date"},
            {"key": "severity", "label": "Severity", "type": "select",
             "options": ["Critical", "High", "Medium", "Low"]},
        ],
    )
    rt2 = RegistryTypeDB(
        name="Risk Treatment Plan",
        slug="risk-treatment-plan",
        description="Risk treatment actions per ISO 27001 6.1.3",
        is_yearly=False,
        schema=[
            {"key": "risk", "label": "Risk", "type": "string", "required": True},
            {"key": "treatment", "label": "Treatment", "type": "string"},
        ],
    )
    db_session.add_all([rt1, rt2])
    await db_session.commit()
    return [rt1, rt2]


@pytest.mark.anyio
async def test_get_registry_types_returns_all(
    db_session: AsyncSession, seed_registry_types: list[RegistryTypeDB],
) -> None:
    from mcp_server.data.iso import get_registry_types

    result = await get_registry_types(db_session)
    assert len(result) == 2
    slugs = [rt.slug for rt in result]
    assert "incident-register" in slugs
    assert "risk-treatment-plan" in slugs


@pytest.mark.anyio
async def test_get_registry_types_ordered_by_name(
    db_session: AsyncSession, seed_registry_types: list[RegistryTypeDB],
) -> None:
    from mcp_server.data.iso import get_registry_types

    result = await get_registry_types(db_session)
    names = [rt.name for rt in result]
    assert names == sorted(names)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py::test_get_registry_types_returns_all -v`
Expected: FAIL — `ImportError: cannot import name 'get_registry_types'`

- [ ] **Step 3: Implement `get_registry_types` in `mcp_server/data/iso.py`**

```python
"""ISO data access — registry types, rows, documents, search."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models import RegistryTypeDB


async def get_registry_types(session: AsyncSession) -> list[RegistryTypeDB]:
    """Return all registry types ordered by name."""
    result = await session.execute(
        select(RegistryTypeDB).order_by(RegistryTypeDB.name)
    )
    return list(result.scalars().all())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py -v -k "registry_types"`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add mcp_server/data/iso.py mcp_server/tests/test_iso_data.py
git commit -m "feat(mcp): add get_registry_types data layer query"
```

---

### Task 3: Data Layer — Resolve Registry Node + Get Registry Rows

**Files:**
- Modify: `mcp_server/data/iso.py`
- Modify: `mcp_server/tests/test_iso_data.py`

- [ ] **Step 1: Write the failing test for `resolve_registry_node`**

Add to `mcp_server/tests/test_iso_data.py`:

```python
from app.modules.iso_docs.models import IsoDocNodeDB, RegistryRowDB


@pytest_asyncio.fixture
async def seed_registry_with_rows(
    db_session: AsyncSession, seed_registry_types: list[RegistryTypeDB],
) -> dict:
    rt = seed_registry_types[0]  # incident-register, is_yearly=True
    node = IsoDocNodeDB(
        title="Incident Register",
        slug="incident-register",
        type="registry",
        registry_type_id=rt.id,
    )
    db_session.add(node)
    await db_session.flush()

    rows = [
        RegistryRowDB(
            node_id=node.id, year=2026, row_index=0,
            data={"number": "INC-001", "date": "2026-01-15", "severity": "High"},
        ),
        RegistryRowDB(
            node_id=node.id, year=2026, row_index=1,
            data={"number": "INC-002", "date": "2026-03-22", "severity": "Low"},
        ),
        RegistryRowDB(
            node_id=node.id, year=2025, row_index=0,
            data={"number": "INC-003", "date": "2025-11-01", "severity": "Medium"},
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    return {"registry_type": rt, "node": node, "rows": rows}


@pytest.mark.anyio
async def test_resolve_registry_node_found(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import resolve_registry_node

    rt, node_id = await resolve_registry_node(db_session, "incident-register")
    assert rt.slug == "incident-register"
    assert node_id == seed_registry_with_rows["node"].id


@pytest.mark.anyio
async def test_resolve_registry_node_not_found(db_session: AsyncSession) -> None:
    from mcp_server.data.iso import resolve_registry_node

    with pytest.raises(ValueError, match="not found"):
        await resolve_registry_node(db_session, "nonexistent-slug")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py -v -k "resolve_registry_node"`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `resolve_registry_node`**

Add to `mcp_server/data/iso.py`:

```python
from uuid import UUID

from sqlalchemy import and_

from app.modules.iso_docs.models import IsoDocNodeDB


async def resolve_registry_node(
    session: AsyncSession, slug: str,
) -> tuple[RegistryTypeDB, UUID]:
    """Resolve a registry type slug to (RegistryTypeDB, node_id).

    ISO registries live as nodes in the ISO document tree (iso_doc_nodes),
    each linked to a registry_type that defines the schema. This function
    encapsulates the JOIN between the two tables.

    Raises ValueError if the slug does not match any registry type or
    no node is linked to that registry type.
    """
    result = await session.execute(
        select(RegistryTypeDB, IsoDocNodeDB.id).join(
            IsoDocNodeDB,
            and_(
                IsoDocNodeDB.registry_type_id == RegistryTypeDB.id,
                IsoDocNodeDB.type == "registry",
            ),
        ).where(RegistryTypeDB.slug == slug)
    )
    row = result.first()
    if row is None:
        raise ValueError(f"Registry '{slug}' not found")
    return row[0], row[1]
```

- [ ] **Step 4: Run resolve tests to verify they pass**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py -v -k "resolve_registry_node"`
Expected: 2 tests PASS

- [ ] **Step 5: Write the failing test for `get_registry_rows`**

Add to `mcp_server/tests/test_iso_data.py`:

```python
from datetime import date


@pytest.mark.anyio
async def test_get_registry_rows_filters_by_year(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import get_registry_rows

    node_id = seed_registry_with_rows["node"].id
    rows = await get_registry_rows(db_session, node_id, year=2026)
    assert len(rows) == 2
    numbers = [r.data["number"] for r in rows]
    assert "INC-001" in numbers
    assert "INC-002" in numbers


@pytest.mark.anyio
async def test_get_registry_rows_all_years(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import get_registry_rows

    node_id = seed_registry_with_rows["node"].id
    rows = await get_registry_rows(db_session, node_id, year=None)
    assert len(rows) == 3


@pytest.mark.anyio
async def test_get_registry_rows_ordered_by_index(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import get_registry_rows

    node_id = seed_registry_with_rows["node"].id
    rows = await get_registry_rows(db_session, node_id, year=2026)
    indices = [r.row_index for r in rows]
    assert indices == sorted(indices)
```

- [ ] **Step 6: Run test to verify it fails**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py -v -k "get_registry_rows"`
Expected: FAIL — `ImportError`

- [ ] **Step 7: Implement `get_registry_rows`**

Add to `mcp_server/data/iso.py`:

```python
from app.modules.iso_docs.models import RegistryRowDB


async def get_registry_rows(
    session: AsyncSession, node_id: UUID, year: int | None,
) -> list[RegistryRowDB]:
    """Return registry rows for a node, optionally filtered by year."""
    stmt = (
        select(RegistryRowDB)
        .where(RegistryRowDB.node_id == node_id)
        .order_by(RegistryRowDB.row_index)
    )
    if year is not None:
        stmt = stmt.where(RegistryRowDB.year == year)
    result = await session.execute(stmt)
    return list(result.scalars().all())
```

- [ ] **Step 8: Run all Task 3 tests**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py -v -k "resolve or get_registry_rows"`
Expected: 5 tests PASS

- [ ] **Step 9: Commit**

```bash
git add mcp_server/data/iso.py mcp_server/tests/test_iso_data.py
git commit -m "feat(mcp): add resolve_registry_node and get_registry_rows"
```

---

### Task 4: Data Layer — Documents

**Files:**
- Modify: `mcp_server/data/iso.py`
- Modify: `mcp_server/tests/test_iso_data.py`

- [ ] **Step 1: Write the failing test for `get_documents`**

Add to `mcp_server/tests/test_iso_data.py`:

```python
from app.modules.iso_docs.models import IsoDocVersionDB, IsoDocMetadataDB


@pytest_asyncio.fixture
async def seed_documents(db_session: AsyncSession) -> list[IsoDocNodeDB]:
    page1 = IsoDocNodeDB(
        title="Information Security Policy",
        slug="information-security-policy",
        type="page",
    )
    page2 = IsoDocNodeDB(
        title="Access Control Procedure",
        slug="access-control-procedure",
        type="page",
    )
    group = IsoDocNodeDB(
        title="Policies Group",
        slug="policies",
        type="group",
    )
    db_session.add_all([page1, page2, group])
    await db_session.flush()

    meta1 = IsoDocMetadataDB(
        node_id=page1.id,
        category="policy",
        doc_version="2.1",
    )
    meta2 = IsoDocMetadataDB(
        node_id=page2.id,
        category="procedure",
        doc_version="1.0",
    )
    db_session.add_all([meta1, meta2])

    v1 = IsoDocVersionDB(
        node_id=page1.id, version=1,
        content="## 1. Purpose\n\nThis policy establishes information security controls.",
    )
    v2 = IsoDocVersionDB(
        node_id=page1.id, version=2,
        content="## 1. Purpose\n\nThis policy establishes information security controls.\n\n## 2. Scope\n\nApplies to all employees and remote access.",
    )
    v3 = IsoDocVersionDB(
        node_id=page2.id, version=1,
        content="## 1. Overview\n\nAccess control procedure for VPN and encryption.",
    )
    db_session.add_all([v1, v2, v3])
    await db_session.commit()
    return [page1, page2]


@pytest.mark.anyio
async def test_get_documents_returns_pages_only(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import get_documents

    docs = await get_documents(db_session)
    assert len(docs) == 2
    slugs = [d["slug"] for d in docs]
    assert "information-security-policy" in slugs
    assert "policies" not in slugs  # group excluded


@pytest.mark.anyio
async def test_get_documents_filters_by_category(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import get_documents

    docs = await get_documents(db_session, category="policy")
    assert len(docs) == 1
    assert docs[0]["slug"] == "information-security-policy"


@pytest.mark.anyio
async def test_get_documents_filters_by_title(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import get_documents

    docs = await get_documents(db_session, title_search="Access")
    assert len(docs) == 1
    assert docs[0]["slug"] == "access-control-procedure"


@pytest.mark.anyio
async def test_get_documents_includes_latest_version_metadata(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import get_documents

    docs = await get_documents(db_session)
    policy = next(d for d in docs if d["slug"] == "information-security-policy")
    assert policy["doc_version"] == "2.1"
    assert policy["category"] == "policy"
    assert "summary" in policy
    assert "Purpose" in policy["summary"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py -v -k "get_documents"`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `get_documents`**

Add to `mcp_server/data/iso.py`:

```python
from sqlalchemy import func as sa_func
from sqlalchemy.orm import aliased

from app.modules.iso_docs.models import IsoDocVersionDB, IsoDocMetadataDB

# Subquery for latest version number per node
_latest_version_sq = (
    select(
        IsoDocVersionDB.node_id,
        sa_func.max(IsoDocVersionDB.version).label("max_version"),
    )
    .group_by(IsoDocVersionDB.node_id)
    .subquery()
)

_SUMMARY_LENGTH = 200


async def get_documents(
    session: AsyncSession,
    category: str | None = None,
    title_search: str | None = None,
) -> list[dict]:
    """Return ISO documents (page nodes) with metadata and content summary."""
    stmt = (
        select(
            IsoDocNodeDB.slug,
            IsoDocNodeDB.title,
            IsoDocMetadataDB.category,
            IsoDocMetadataDB.doc_version,
            IsoDocVersionDB.created_at.label("last_updated"),
            sa_func.left(IsoDocVersionDB.content, _SUMMARY_LENGTH).label("summary"),
        )
        .join(IsoDocMetadataDB, IsoDocMetadataDB.node_id == IsoDocNodeDB.id)
        .join(
            _latest_version_sq,
            _latest_version_sq.c.node_id == IsoDocNodeDB.id,
        )
        .join(
            IsoDocVersionDB,
            and_(
                IsoDocVersionDB.node_id == IsoDocNodeDB.id,
                IsoDocVersionDB.version == _latest_version_sq.c.max_version,
            ),
        )
        .where(IsoDocNodeDB.type == "page")
        .order_by(IsoDocNodeDB.title)
    )
    if category is not None:
        stmt = stmt.where(IsoDocMetadataDB.category == category)
    if title_search is not None:
        stmt = stmt.where(IsoDocNodeDB.title.ilike(f"%{title_search}%"))

    result = await session.execute(stmt)
    return [row._asdict() for row in result.all()]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py -v -k "get_documents"`
Expected: 4 tests PASS

- [ ] **Step 5: Write the failing test for `get_document`**

Add to `mcp_server/tests/test_iso_data.py`:

```python
@pytest.mark.anyio
async def test_get_document_returns_latest_content(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import get_document

    doc = await get_document(db_session, "information-security-policy")
    assert doc["slug"] == "information-security-policy"
    assert doc["doc_version"] == "2.1"
    assert "## 2. Scope" in doc["content"]  # only in version 2


@pytest.mark.anyio
async def test_get_document_not_found(db_session: AsyncSession) -> None:
    from mcp_server.data.iso import get_document

    with pytest.raises(ValueError, match="not found"):
        await get_document(db_session, "nonexistent-doc")
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py -v -k "test_get_document"`
Expected: FAIL — `ImportError`

- [ ] **Step 7: Implement `get_document`**

Add to `mcp_server/data/iso.py`:

```python
async def get_document(session: AsyncSession, slug: str) -> dict:
    """Return full content of a single ISO document by slug.

    Raises ValueError if slug not found.
    """
    stmt = (
        select(
            IsoDocNodeDB.slug,
            IsoDocNodeDB.title,
            IsoDocMetadataDB.category,
            IsoDocMetadataDB.doc_version,
            IsoDocVersionDB.content,
        )
        .join(IsoDocMetadataDB, IsoDocMetadataDB.node_id == IsoDocNodeDB.id)
        .join(
            _latest_version_sq,
            _latest_version_sq.c.node_id == IsoDocNodeDB.id,
        )
        .join(
            IsoDocVersionDB,
            and_(
                IsoDocVersionDB.node_id == IsoDocNodeDB.id,
                IsoDocVersionDB.version == _latest_version_sq.c.max_version,
            ),
        )
        .where(IsoDocNodeDB.type == "page")
        .where(IsoDocNodeDB.slug == slug)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        raise ValueError(f"Document '{slug}' not found")
    return row._asdict()
```

- [ ] **Step 8: Run all Task 4 tests**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py -v -k "get_document"`
Expected: 6 tests PASS

- [ ] **Step 9: Commit**

```bash
git add mcp_server/data/iso.py mcp_server/tests/test_iso_data.py
git commit -m "feat(mcp): add get_documents and get_document data layer"
```

---

### Task 5: Alembic Migration — tsvector + GIN Index

**Files:**
- Create: `backend/alembic/versions/mcp_fts_gin_idx.py`
- Modify: `backend/app/modules/iso_docs/models/page_version.py`

- [ ] **Step 1: Add `search_vector` column to the SQLAlchemy model**

Edit `backend/app/modules/iso_docs/models/page_version.py` — add the generated column so the model stays in sync with the DB and `Base.metadata.create_all` creates it in test DBs:

```python
from sqlalchemy import Column, Computed
from sqlalchemy.dialects.postgresql import TSVECTOR

# Add after the existing columns, before the class ends:
search_vector = Column(
    TSVECTOR,
    Computed("to_tsvector('english', coalesce(content, ''))", persisted=True),
)
```

- [ ] **Step 2: Generate the migration stub**

Run: `pushd backend > /dev/null && alembic revision -m "add tsvector and GIN index for iso doc search" && popd > /dev/null`

Note the generated filename.

- [ ] **Step 2: Write the migration**

Edit the generated file — replace the `upgrade` and `downgrade` functions:

```python
"""add tsvector and GIN index for iso doc search"""

from alembic import op


def upgrade() -> None:
    op.execute(
        "ALTER TABLE iso_doc_versions "
        "ADD COLUMN IF NOT EXISTS search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_iso_doc_versions_search_vector "
        "ON iso_doc_versions USING gin(search_vector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_iso_doc_versions_search_vector")
    op.execute("ALTER TABLE iso_doc_versions DROP COLUMN IF EXISTS search_vector")
```

- [ ] **Step 3: Run the migration locally**

Run: `pushd backend > /dev/null && alembic upgrade head && popd > /dev/null`
Expected: Migration applies successfully.

- [ ] **Step 4: Verify the column and index exist**

Run: `psql -d scorecard -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'iso_doc_versions' AND column_name = 'search_vector';"`
Expected: One row with `data_type = tsvector`.

Run: `psql -d scorecard -c "SELECT indexname FROM pg_indexes WHERE tablename = 'iso_doc_versions' AND indexname = 'ix_iso_doc_versions_search_vector';"`
Expected: One row.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/ backend/app/modules/iso_docs/models/page_version.py
git commit -m "feat(mcp): add tsvector column and GIN index for ISO doc full-text search"
```

---

### Task 6: Data Layer — Document Search

**Prerequisite:** Task 5 must be complete. The `search_vector` generated column must exist in both the Alembic migration AND the `IsoDocVersionDB` SQLAlchemy model (added in Task 5 Step 1). This ensures `Base.metadata.create_all` creates the column in the test DB. Verify before starting:

Run: `python -c "from app.modules.iso_docs.models.page_version import IsoDocVersionDB; print([c.key for c in IsoDocVersionDB.__table__.columns])"`
Expected: Output includes `search_vector`.

**Files:**
- Modify: `mcp_server/data/iso.py`
- Modify: `mcp_server/tests/test_iso_data.py`

- [ ] **Step 1: Write the failing test for `search_documents`**

Add to `mcp_server/tests/test_iso_data.py`:

```python
@pytest.mark.anyio
async def test_search_documents_finds_matching_content(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import search_documents

    results = await search_documents(db_session, "encryption VPN")
    assert len(results) >= 1
    slugs = [r["slug"] for r in results]
    assert "access-control-procedure" in slugs


@pytest.mark.anyio
async def test_search_documents_returns_snippets(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import search_documents

    results = await search_documents(db_session, "remote access")
    assert len(results) >= 1
    result = results[0]
    assert "snippet" in result
    assert "rank" in result
    assert "slug" in result
    assert "title" in result


@pytest.mark.anyio
async def test_search_documents_only_latest_version(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import search_documents

    # "Scope" only exists in version 2 of the security policy
    results = await search_documents(db_session, "Scope employees")
    assert len(results) >= 1
    assert results[0]["slug"] == "information-security-policy"


@pytest.mark.anyio
async def test_search_documents_no_results(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import search_documents

    results = await search_documents(db_session, "xyznonexistent")
    assert results == []


@pytest.mark.anyio
async def test_search_documents_extracts_section_heading(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import search_documents

    results = await search_documents(db_session, "employees remote")
    matching = [r for r in results if r["slug"] == "information-security-policy"]
    if matching:
        # Section should be "## 2. Scope" (nearest heading before match)
        assert matching[0]["section"] is None or "Scope" in matching[0]["section"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py -v -k "search_documents"`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement `search_documents`**

Add to `mcp_server/data/iso.py`:

```python
import re
from sqlalchemy import text, literal_column


def _extract_section_heading(content: str, snippet: str) -> str | None:
    """Find the nearest preceding markdown heading for a snippet.

    Searches for the snippet text (stripped of highlight tags) in the
    full content, then walks backwards to find the nearest ## heading.
    Returns None if no heading is found.
    """
    clean_snippet = re.sub(r"<b>|</b>", "", snippet).strip()
    # Use the first substantial fragment of the snippet for matching
    fragment = clean_snippet[:60]
    pos = content.find(fragment)
    if pos < 0:
        return None
    # Walk backwards from match position to find nearest heading
    preceding = content[:pos]
    headings = re.findall(r"^(#{1,3}\s+.+)$", preceding, re.MULTILINE)
    return headings[-1] if headings else None


async def search_documents(
    session: AsyncSession, query: str,
) -> list[dict]:
    """Full-text search across ISO document content.

    Uses the search_vector generated column (GIN-indexed) on
    iso_doc_versions. Only searches the latest version of each document.
    Returns results ordered by rank (ts_rank).
    """
    stmt = text("""
        WITH latest_versions AS (
            SELECT DISTINCT ON (v.node_id)
                v.node_id, v.content, v.search_vector, v.version
            FROM iso_doc_versions v
            ORDER BY v.node_id, v.version DESC
        )
        SELECT
            n.slug,
            n.title,
            lv.content,
            ts_headline('english', lv.content, plainto_tsquery('english', :query),
                'StartSel=<b>, StopSel=</b>, MaxWords=50, MinWords=20'
            ) AS snippet,
            ts_rank(lv.search_vector, plainto_tsquery('english', :query)) AS rank
        FROM latest_versions lv
        JOIN iso_doc_nodes n ON n.id = lv.node_id
        WHERE n.type = 'page'
          AND lv.search_vector @@ plainto_tsquery('english', :query)
        ORDER BY rank DESC
    """)
    result = await session.execute(stmt, {"query": query})
    rows = result.all()
    return [
        {
            "slug": row.slug,
            "title": row.title,
            "section": _extract_section_heading(row.content, row.snippet),
            "snippet": row.snippet,
            "rank": float(row.rank),
        }
        for row in rows
    ]
```

- [ ] **Step 4: Run all search tests**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_data.py -v -k "search_documents"`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add mcp_server/data/iso.py mcp_server/tests/test_iso_data.py
git commit -m "feat(mcp): add search_documents with full-text search and section extraction"
```

---

### Task 7: MCP Tools — Registries

**Files:**
- Modify: `mcp_server/tools/iso.py`
- Modify: `mcp_server/server.py`
- Create: `mcp_server/tests/test_iso_tools.py`

- [ ] **Step 0: Verify MCP SDK test client API**

The SDK's test client API may vary by version. Verify before writing tests:

Run: `python -c "from mcp.server.fastmcp import FastMCP; f = FastMCP('test'); print([m for m in dir(f) if 'test' in m.lower() or 'client' in m.lower()])"`

Use the output to determine the correct in-process client pattern. The expected pattern is `mcp.test_client()`, but fall back to `mcp.client.Client` with memory streams if needed. Update the fixture below accordingly.

- [ ] **Step 1: Write the failing test for `iso_get_registries` tool**

```python
"""Tests for MCP ISO tools — tool response formatting."""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models import RegistryTypeDB
from mcp_server.server import mcp


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def seed_tool_registry(db_session: AsyncSession) -> None:
    rt = RegistryTypeDB(
        name="Test Register",
        slug="test-register",
        description="A test registry",
        is_yearly=False,
        schema=[{"key": "name", "label": "Name", "type": "string"}],
    )
    db_session.add(rt)
    await db_session.commit()


@pytest_asyncio.fixture
async def client(seed_tool_registry, use_test_db):
    """In-process MCP client. Uses session override for test DB."""
    async with mcp.test_client() as c:
        yield c


@pytest.mark.anyio
async def test_iso_get_registries_is_listed(client) -> None:
    tools = await client.list_tools()
    names = [t.name for t in tools.tools]
    assert "iso_get_registries" in names


@pytest.mark.anyio
async def test_iso_get_registries_returns_json(client) -> None:
    result = await client.call_tool("iso_get_registries", {})
    assert result.content
    text = result.content[0].text
    data = json.loads(text)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["slug"] == "test-register"
```

Note: The `use_test_db` fixture (from conftest) activates the session override so tools use the test DB. The `seed_tool_registry` fixture creates minimal data for validation.

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_tools.py -v -k "iso_get_registries"`
Expected: FAIL — tool not found or import error

- [ ] **Step 3: Implement `iso_get_registries` tool**

Edit `mcp_server/tools/iso.py`:

```python
"""ISO MCP tools — registered on the FastMCP server."""

from __future__ import annotations

import json
from datetime import date

from mcp_server.data.base import get_read_session
from mcp_server.data import iso as iso_data
from mcp_server.server import mcp

from app.modules.iso_docs.services.registry_service import compute_row_fields


@mcp.tool()
async def iso_get_registries() -> str:
    """List all ISO registry types with their column schemas.

    Returns a JSON array of registry types. Each entry includes the slug
    (used as identifier in other tools), name, description, whether it
    uses yearly grouping, and the full column schema.
    """
    async with get_read_session() as session:
        types = await iso_data.get_registry_types(session)
    return json.dumps(
        [
            {
                "slug": rt.slug,
                "name": rt.name,
                "description": rt.description,
                "is_yearly": rt.is_yearly,
                "columns": rt.schema,
            }
            for rt in types
        ],
        indent=2,
        default=str,
    )
```

- [ ] **Step 4: Import tools in server.py**

Edit `mcp_server/server.py` — add at the bottom, after the `mcp` definition:

```python
import mcp_server.tools.iso  # noqa: F401 — registers tools on mcp
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_tools.py -v -k "iso_get_registries"`
Expected: 2 tests PASS

- [ ] **Step 6: Write the failing test for `iso_get_registry_rows`**

Add to `mcp_server/tests/test_iso_tools.py`:

```python
@pytest.mark.anyio
async def test_iso_get_registry_rows_is_listed(client) -> None:
    tools = await client.list_tools()
    names = [t.name for t in tools.tools]
    assert "iso_get_registry_rows" in names


@pytest.mark.anyio
async def test_iso_get_registry_rows_invalid_slug(client) -> None:
    result = await client.call_tool(
        "iso_get_registry_rows", {"slug": "nonexistent"}
    )
    text = result.content[0].text
    assert "not found" in text.lower()
```

- [ ] **Step 7: Implement `iso_get_registry_rows` tool**

Add to `mcp_server/tools/iso.py`:

```python
@mcp.tool()
async def iso_get_registry_rows(slug: str, year: int | None = None) -> str:
    """Get all rows from an ISO registry by its slug.

    Args:
        slug: Registry type slug (from iso_get_registries).
        year: Optional year filter for yearly registries. Defaults to
              current year if the registry uses yearly grouping.

    Returns JSON with registry metadata, column schema, and all rows
    with computed fields populated.
    """
    async with get_read_session() as session:
        try:
            rt, node_id = await iso_data.resolve_registry_node(session, slug)
        except ValueError as e:
            return json.dumps({"error": str(e)})

        effective_year = year
        if effective_year is None and rt.is_yearly:
            effective_year = date.today().year

        rows = await iso_data.get_registry_rows(session, node_id, effective_year)

    return json.dumps(
        {
            "registry": rt.name,
            "slug": rt.slug,
            "year": effective_year,
            "total_rows": len(rows),
            "columns": rt.schema,
            "rows": [
                {
                    "id": str(row.id),
                    "row_index": row.row_index,
                    "data": compute_row_fields(rt.schema, row.data),
                }
                for row in rows
            ],
        },
        indent=2,
        default=str,
    )
```

- [ ] **Step 8: Run all Task 7 tests**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_tools.py -v`
Expected: 4 tests PASS

- [ ] **Step 9: Commit**

```bash
git add mcp_server/tools/iso.py mcp_server/server.py mcp_server/tests/test_iso_tools.py
git commit -m "feat(mcp): add iso_get_registries and iso_get_registry_rows tools"
```

---

### Task 8: MCP Tools — Documents

**Files:**
- Modify: `mcp_server/tools/iso.py`
- Modify: `mcp_server/tests/test_iso_tools.py`

- [ ] **Step 1: Write failing tests for document tools**

Add to `mcp_server/tests/test_iso_tools.py`:

```python
@pytest.mark.anyio
async def test_iso_get_documents_is_listed(client) -> None:
    tools = await client.list_tools()
    names = [t.name for t in tools.tools]
    assert "iso_get_documents" in names


@pytest.mark.anyio
async def test_iso_get_document_is_listed(client) -> None:
    tools = await client.list_tools()
    names = [t.name for t in tools.tools]
    assert "iso_get_document" in names


@pytest.mark.anyio
async def test_iso_search_documents_is_listed(client) -> None:
    tools = await client.list_tools()
    names = [t.name for t in tools.tools]
    assert "iso_search_documents" in names


@pytest.mark.anyio
async def test_iso_get_document_not_found(client) -> None:
    result = await client.call_tool(
        "iso_get_document", {"slug": "nonexistent"}
    )
    text = result.content[0].text
    assert "not found" in text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_tools.py -v -k "iso_get_document"`
Expected: FAIL — tools not registered

- [ ] **Step 3: Implement all three document tools**

Add to `mcp_server/tools/iso.py`:

```python
@mcp.tool()
async def iso_get_documents(
    category: str | None = None, search: str | None = None,
) -> str:
    """List ISO documents (policies, procedures, plans) with metadata.

    Args:
        category: Filter by category (policy, procedure, plan, record, etc.).
        search: Filter by title (substring match). For full-text content
                search, use iso_search_documents instead.

    Returns JSON array of documents with slug, title, category,
    version, and a summary of the content.
    """
    async with get_read_session() as session:
        docs = await iso_data.get_documents(
            session, category=category, title_search=search,
        )
    return json.dumps(docs, indent=2, default=str)


@mcp.tool()
async def iso_get_document(slug: str) -> str:
    """Get the full content of a single ISO document by slug.

    Args:
        slug: Document slug (from iso_get_documents).

    Returns JSON with title, category, version, and the full
    markdown content of the document.
    """
    async with get_read_session() as session:
        try:
            doc = await iso_data.get_document(session, slug)
        except ValueError as e:
            return json.dumps({"error": str(e)})
    return json.dumps(doc, indent=2, default=str)


@mcp.tool()
async def iso_search_documents(query: str) -> str:
    """Full-text search across ISO document content.

    Args:
        query: Search terms (e.g. "encryption remote access").

    Returns JSON array of matching documents with snippet, section
    heading, and rank. Rank is a PostgreSQL ts_rank value useful
    only for ordering — it is not a normalized 0-1 score.
    """
    async with get_read_session() as session:
        results = await iso_data.search_documents(session, query)
    return json.dumps(results, indent=2, default=str)
```

- [ ] **Step 4: Run all tool tests**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_iso_tools.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add mcp_server/tools/iso.py mcp_server/tests/test_iso_tools.py
git commit -m "feat(mcp): add iso_get_documents, iso_get_document, iso_search_documents tools"
```

---

### Task 9: Integration Tests

**Files:**
- Create: `mcp_server/tests/test_integration.py`

- [ ] **Step 1: Write integration tests**

These tests seed data and call tools through the MCP Client, validating the full stack.

```python
"""End-to-end integration tests — seed DB, call MCP tools, verify responses."""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models import (
    IsoDocNodeDB,
    IsoDocMetadataDB,
    IsoDocVersionDB,
    RegistryRowDB,
    RegistryTypeDB,
)
from mcp_server.server import mcp


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def seeded_db(db_session: AsyncSession) -> None:
    """Seed DB with a registry and a document for integration testing."""
    # Registry type + node + rows
    rt = RegistryTypeDB(
        name="Incident Register",
        slug="incident-register",
        description="Security incidents",
        is_yearly=True,
        schema=[
            {"key": "number", "label": "Number", "type": "string", "required": True},
            {"key": "severity", "label": "Severity", "type": "select",
             "options": ["Critical", "High", "Medium", "Low"]},
        ],
    )
    db_session.add(rt)
    await db_session.flush()

    node = IsoDocNodeDB(
        title="Incident Register",
        slug="incident-register",
        type="registry",
        registry_type_id=rt.id,
    )
    db_session.add(node)
    await db_session.flush()

    db_session.add(RegistryRowDB(
        node_id=node.id, year=2026, row_index=0,
        data={"number": "INC-001", "severity": "High"},
    ))

    # Document page + metadata + version
    page = IsoDocNodeDB(
        title="Security Policy",
        slug="security-policy",
        type="page",
    )
    db_session.add(page)
    await db_session.flush()

    db_session.add(IsoDocMetadataDB(
        node_id=page.id, category="policy", doc_version="1.0",
    ))
    db_session.add(IsoDocVersionDB(
        node_id=page.id, version=1,
        content="## 1. Purpose\n\nEstablishes encryption and remote access controls.",
    ))

    await db_session.commit()


@pytest_asyncio.fixture
async def client(seeded_db, use_test_db):
    """In-process MCP client with seeded test data and session override."""
    async with mcp.test_client() as c:
        yield c


@pytest.mark.anyio
async def test_list_registries_then_get_rows(client) -> None:
    """Full flow: discover registries → fetch rows."""
    result = await client.call_tool("iso_get_registries", {})
    registries = json.loads(result.content[0].text)
    assert len(registries) >= 1

    slug = registries[0]["slug"]
    result = await client.call_tool(
        "iso_get_registry_rows", {"slug": slug, "year": 2026},
    )
    data = json.loads(result.content[0].text)
    assert data["total_rows"] >= 1
    assert data["rows"][0]["data"]["number"] == "INC-001"


@pytest.mark.anyio
async def test_search_then_read_document(client) -> None:
    """Full flow: search docs → read matching document."""
    result = await client.call_tool(
        "iso_search_documents", {"query": "encryption remote"},
    )
    results = json.loads(result.content[0].text)
    assert len(results) >= 1
    slug = results[0]["slug"]

    result = await client.call_tool("iso_get_document", {"slug": slug})
    doc = json.loads(result.content[0].text)
    assert "encryption" in doc["content"].lower()


@pytest.mark.anyio
async def test_list_documents_filtered(client) -> None:
    result = await client.call_tool(
        "iso_get_documents", {"category": "policy"},
    )
    docs = json.loads(result.content[0].text)
    assert len(docs) >= 1
    assert all(d["category"] == "policy" for d in docs)


@pytest.mark.anyio
async def test_no_write_tools_registered(client) -> None:
    """Phase 1 is read-only: no create/update/delete tools should exist."""
    tools = await client.list_tools()
    names = [t.name for t in tools.tools]
    write_tools = [n for n in names if "create" in n or "update" in n or "delete" in n]
    assert write_tools == [], f"Unexpected write tools found: {write_tools}"
```

- [ ] **Step 2: Run integration tests**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_integration.py -v`
Expected: 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add mcp_server/tests/test_integration.py
git commit -m "test(mcp): add end-to-end integration tests for ISO tools"
```

---

### Task 10: Configuration + Smoke Test

**Files:**
- Create: `.mcp.json.example`
- Modify: `.dockerignore` (verify)

- [ ] **Step 1: Create `.mcp.json.example`**

```json
{
  "mcpServers": {
    "vizzhub": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/vizzhub",
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/dbname",
        "MCP_USER_EMAIL": "you@vizzuality.com",
        "PYTHONPATH": "/path/to/vizzhub/backend"
      }
    }
  }
}
```

- [ ] **Step 2: Configure your local `.mcp.json`**

Copy `.mcp.json.example` and fill in real values. Add the `vizzhub` entry alongside the existing `shadcn`, `sonarqube`, and `sentry` servers.

- [ ] **Step 3: Run all tests**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/ -v`
Expected: All tests PASS.

- [ ] **Step 4: Manual smoke test — Claude Code**

Start a new Claude Code session. Verify the VizzHub MCP server connects successfully. Then test:

1. Ask: "What ISO registries do we have?" → Should list all registry types with descriptions.
2. Ask: "How many security incidents in 2026?" → Should query the incident register and count.
3. Ask: "What does our security policy say about remote access?" → Should search docs, read relevant section, answer.
4. Ask: "Add a new row to the incident register" → Should get a clear message that write operations are not available (no write tools exist, so Claude should say it can't do that).

- [ ] **Step 5: Manual smoke test — Claude Desktop**

Configure `claude_desktop_config.json` with the vizzhub MCP server (using the venv Python path). Repeat smoke test #1 to verify it connects and returns data.

- [ ] **Step 6: Commit**

```bash
git add .mcp.json.example
git commit -m "docs(mcp): add .mcp.json.example with Claude Code and Desktop config"
```

- [ ] **Step 7: Final commit — all tests green**

Run full test suite to confirm nothing is broken:

```bash
PYTHONPATH=backend:. pytest mcp_server/tests/ -v
pushd backend > /dev/null && pytest tests/ -x -q && popd > /dev/null
```

Expected: All MCP tests PASS, all backend tests PASS.
