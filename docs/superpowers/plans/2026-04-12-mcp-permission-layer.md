# MCP Permission Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Propagate JWT user identity to all MCP tools and enforce module-level access control + ISO document visibility filtering.

**Architecture:** `McpUserContext` ContextVar set by `TokenVerifier` (HTTP) or at startup (stdio). `@mcp_requires` decorator gates tools by permission string. ISO doc queries filter results for non-editors.

**Tech Stack:** Python 3.11, SQLAlchemy async, MCP SDK (FastMCP), pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-04-12-mcp-permission-layer-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `mcp_server/data/base.py` | Modify | McpUserContext dataclass, ContextVar, helpers |
| `mcp_server/auth/permissions.py` | Create | `mcp_requires()` decorator |
| `mcp_server/auth/token_verifier.py` | Modify | Set ContextVar after JWT decode |
| `mcp_server/__main__.py` | Modify | Set FULL_ACCESS for stdio mode |
| `mcp_server/tools/tracker.py` | Modify | Add `@mcp_requires("tracker:view")` |
| `mcp_server/tools/scorecard.py` | Modify | Add `@mcp_requires("scorecard:view")` |
| `mcp_server/tools/capacity.py` | Modify | Add `@mcp_requires("tracker:view")` |
| `mcp_server/tools/iso.py` | Modify | Add `@mcp_requires("iso_docs:edit")` to registry tools |
| `mcp_server/data/iso.py` | Modify | Visibility filtering for doc queries |
| `mcp_server/tests/conftest.py` | Modify | Default FULL_ACCESS in `use_test_db` fixture |
| `mcp_server/tests/test_permissions.py` | Create | Gating + filtering tests |

---

### Task 1: McpUserContext dataclass + helpers

**Files:**
- Modify: `mcp_server/data/base.py`
- Create: `mcp_server/tests/test_permissions.py`

- [ ] **Step 1: Write tests for McpUserContext and helpers**

Create `mcp_server/tests/test_permissions.py`:

```python
"""Tests for MCP permission layer."""

import pytest

from mcp_server.data.base import (
    FULL_ACCESS,
    McpUserContext,
    get_mcp_user,
    override_mcp_user,
    set_mcp_user,
)


class TestMcpUserContext:
    def test_has_permission_specific(self) -> None:
        ctx = McpUserContext(
            user_id="u1", email="a@b.com",
            roles=["user"], permissions=["tracker:view"],
        )
        assert ctx.has_permission("tracker:view") is True
        assert ctx.has_permission("scorecard:view") is False

    def test_has_permission_wildcard(self) -> None:
        ctx = McpUserContext(
            user_id="u1", email="a@b.com",
            roles=["admin"], permissions=["*"],
        )
        assert ctx.has_permission("tracker:view") is True
        assert ctx.has_permission("anything:at_all") is True

    def test_full_access_is_admin(self) -> None:
        assert FULL_ACCESS.has_permission("tracker:view") is True
        assert FULL_ACCESS.has_permission("iso_docs:edit") is True


class TestMcpUserHelpers:
    def test_get_mcp_user_raises_when_not_set(self) -> None:
        with pytest.raises(RuntimeError, match="MCP user context not set"):
            get_mcp_user()

    @pytest.mark.asyncio
    async def test_set_and_get_round_trip(self) -> None:
        ctx = McpUserContext(
            user_id="u1", email="a@b.com",
            roles=["user"], permissions=["tracker:view"],
        )
        set_mcp_user(ctx)
        try:
            assert get_mcp_user() is ctx
        finally:
            set_mcp_user(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_override_mcp_user_restores(self) -> None:
        outer = McpUserContext(
            user_id="outer", email="o@b.com", roles=[], permissions=[],
        )
        inner = McpUserContext(
            user_id="inner", email="i@b.com", roles=[], permissions=["*"],
        )
        set_mcp_user(outer)
        try:
            async with override_mcp_user(inner):
                assert get_mcp_user().user_id == "inner"
            assert get_mcp_user().user_id == "outer"
        finally:
            set_mcp_user(None)  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_permissions.py::TestMcpUserContext -v --no-header 2>&1 | tail -5`

Expected: ImportError — `McpUserContext` does not exist yet.

- [ ] **Step 3: Implement McpUserContext + helpers in base.py**

Add to the top of `mcp_server/data/base.py` (after existing imports):

```python
from dataclasses import dataclass, field
```

Add after the `_session_override` ContextVar definition (around line 23):

```python
@dataclass(frozen=True)
class McpUserContext:
    """Identity + permissions of the current MCP caller."""

    user_id: str
    email: str
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)

    def has_permission(self, action: str) -> bool:
        return "*" in self.permissions or action in self.permissions


FULL_ACCESS = McpUserContext(
    user_id="stdio",
    email="local",
    roles=["admin"],
    permissions=["*"],
)

_mcp_user_context: ContextVar[McpUserContext | None] = ContextVar(
    "_mcp_user_context", default=None,
)


def get_mcp_user() -> McpUserContext:
    """Return the current MCP user context. Raises if not set."""
    ctx = _mcp_user_context.get()
    if ctx is None:
        raise RuntimeError("MCP user context not set")
    return ctx


def set_mcp_user(ctx: McpUserContext) -> None:
    """Set the MCP user context for the current async task."""
    _mcp_user_context.set(ctx)


@asynccontextmanager
async def override_mcp_user(ctx: McpUserContext):
    """Override the MCP user context for testing."""
    token = _mcp_user_context.set(ctx)
    try:
        yield
    finally:
        _mcp_user_context.reset(token)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_permissions.py -v --no-header 2>&1 | tail -10`

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/data/base.py mcp_server/tests/test_permissions.py
git commit -m "feat(mcp): add McpUserContext dataclass and ContextVar helpers"
```

---

### Task 2: Update test fixtures for backward compatibility

**Files:**
- Modify: `mcp_server/tests/conftest.py`

Existing tool tests use `use_test_db` which only overrides the DB session. After we add `@mcp_requires` decorators (Task 4), those tests will fail because no user context is set. We fix this proactively.

- [ ] **Step 1: Update `use_test_db` fixture to set FULL_ACCESS**

In `mcp_server/tests/conftest.py`, change the `use_test_db` fixture:

```python
@pytest_asyncio.fixture
async def use_test_db(db_session: AsyncSession):
    """Ensure all MCP tools use the test DB session and have admin context."""
    from mcp_server.data.base import FULL_ACCESS, override_mcp_user, override_session

    async with override_session(db_session):
        async with override_mcp_user(FULL_ACCESS):
            yield
```

- [ ] **Step 2: Run existing MCP tests to verify nothing breaks**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/ -v --no-header 2>&1 | tail -5`

Expected: All ~163 existing tests PASS.

- [ ] **Step 3: Commit**

```bash
git add mcp_server/tests/conftest.py
git commit -m "test(mcp): set FULL_ACCESS user context in use_test_db fixture"
```

---

### Task 3: mcp_requires decorator

**Files:**
- Create: `mcp_server/auth/permissions.py`
- Modify: `mcp_server/tests/test_permissions.py`

- [ ] **Step 1: Write tests for the decorator**

Add to `mcp_server/tests/test_permissions.py`:

```python
import json

from mcp_server.auth.permissions import mcp_requires


class TestMcpRequires:
    @pytest.mark.asyncio
    async def test_blocks_without_permission(self) -> None:
        @mcp_requires("tracker:view")
        async def my_tool() -> str:
            return '{"data": "ok"}'

        user = McpUserContext(
            user_id="u1", email="a@b.com",
            roles=["user"], permissions=["scorecard:view"],
        )
        async with override_mcp_user(user):
            result = await my_tool()

        parsed = json.loads(result)
        assert "error" in parsed
        assert "tracker:view" in parsed["error"]

    @pytest.mark.asyncio
    async def test_allows_with_permission(self) -> None:
        @mcp_requires("tracker:view")
        async def my_tool() -> str:
            return '{"data": "ok"}'

        user = McpUserContext(
            user_id="u1", email="a@b.com",
            roles=["user"], permissions=["tracker:view"],
        )
        async with override_mcp_user(user):
            result = await my_tool()

        assert json.loads(result) == {"data": "ok"}

    @pytest.mark.asyncio
    async def test_allows_wildcard(self) -> None:
        @mcp_requires("tracker:view")
        async def my_tool() -> str:
            return '{"data": "ok"}'

        async with override_mcp_user(FULL_ACCESS):
            result = await my_tool()

        assert json.loads(result) == {"data": "ok"}

    def test_preserves_function_metadata(self) -> None:
        @mcp_requires("tracker:view")
        async def my_tool() -> str:
            """Tool docstring."""
            return '{"data": "ok"}'

        assert my_tool.__name__ == "my_tool"
        assert my_tool.__doc__ == "Tool docstring."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_permissions.py::TestMcpRequires -v --no-header 2>&1 | tail -5`

Expected: ImportError — `mcp_server.auth.permissions` does not exist.

- [ ] **Step 3: Create the permissions module**

Create `mcp_server/auth/permissions.py`:

```python
"""Permission enforcement for MCP tools."""

from __future__ import annotations

import functools
import json

from mcp_server.data.base import get_mcp_user


def mcp_requires(permission: str):
    """Decorator that gates an MCP tool behind a permission check.

    Returns a JSON error string if the user lacks the permission.
    Uses functools.wraps to preserve function metadata for FastMCP
    schema introspection (inspect.signature follows __wrapped__).
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            user = get_mcp_user()
            if not user.has_permission(permission):
                return json.dumps({
                    "error": f"Permission denied: requires {permission}",
                    "user": user.email,
                })
            return await fn(*args, **kwargs)
        return wrapper
    return decorator
```

Ensure `mcp_server/auth/__init__.py` exists (it should already — check and create if missing).

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_permissions.py -v --no-header 2>&1 | tail -10`

Expected: All 9 tests PASS (5 from Task 1 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add mcp_server/auth/permissions.py mcp_server/tests/test_permissions.py
git commit -m "feat(mcp): add mcp_requires permission decorator"
```

---

### Task 4: Apply gating decorators to tool files

**Files:**
- Modify: `mcp_server/tools/tracker.py`
- Modify: `mcp_server/tools/scorecard.py`
- Modify: `mcp_server/tools/capacity.py`
- Modify: `mcp_server/tools/iso.py`

- [ ] **Step 1: Add decorator to tracker tools**

In `mcp_server/tools/tracker.py`, add import:

```python
from mcp_server.auth.permissions import mcp_requires
```

Add `@mcp_requires("tracker:view")` above each tool function:

```python
@mcp_requires("tracker:view")
async def tracker_get_projects(...) -> str:

@mcp_requires("tracker:view")
async def tracker_get_project_detail(...) -> str:

@mcp_requires("tracker:view")
async def tracker_get_project_time(...) -> str:

@mcp_requires("tracker:view")
async def tracker_get_project_invoices(...) -> str:

@mcp_requires("tracker:view")
async def tracker_get_project_progress(...) -> str:

@mcp_requires("tracker:view")
async def tracker_get_periods(...) -> str:

@mcp_requires("tracker:view")
async def tracker_get_user_jira_issues(...) -> str:
```

- [ ] **Step 2: Add decorator to scorecard tools**

In `mcp_server/tools/scorecard.py`, add import:

```python
from mcp_server.auth.permissions import mcp_requires
```

Add `@mcp_requires("scorecard:view")` above each tool function:

```python
@mcp_requires("scorecard:view")
async def scorecard_get_project_scores(...) -> str:

@mcp_requires("scorecard:view")
async def scorecard_get_project_scorecard(...) -> str:

@mcp_requires("scorecard:view")
async def scorecard_get_project_history(...) -> str:

@mcp_requires("scorecard:view")
async def scorecard_get_global_metrics(...) -> str:
```

- [ ] **Step 3: Add decorator to capacity tools**

In `mcp_server/tools/capacity.py`, add import:

```python
from mcp_server.auth.permissions import mcp_requires
```

Add `@mcp_requires("tracker:view")` above each tool function:

```python
@mcp_requires("tracker:view")
async def capacity_get_insights(...) -> str:

@mcp_requires("tracker:view")
async def capacity_get_fa_detail(...) -> str:

@mcp_requires("tracker:view")
async def capacity_get_user_detail(...) -> str:

@mcp_requires("tracker:view")
async def capacity_get_allocation(...) -> str:
```

- [ ] **Step 4: Add decorator to ISO registry tools only**

In `mcp_server/tools/iso.py`, add import:

```python
from mcp_server.auth.permissions import mcp_requires
```

Add `@mcp_requires("iso_docs:edit")` to **registry tools only** (not document tools):

```python
@mcp_requires("iso_docs:edit")
async def iso_get_registries() -> str:

@mcp_requires("iso_docs:edit")
async def iso_get_registry_rows(slug: str, year: int | None = None) -> str:
```

Do NOT decorate `iso_get_documents`, `iso_get_document`, or `iso_search_documents` — those use data-level filtering (Task 6).

- [ ] **Step 5: Run full MCP test suite**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/ -v --no-header 2>&1 | tail -10`

Expected: All tests PASS. The `use_test_db` fixture sets `FULL_ACCESS`, so all gated tools still work in existing tests.

- [ ] **Step 6: Commit**

```bash
git add mcp_server/tools/tracker.py mcp_server/tools/scorecard.py mcp_server/tools/capacity.py mcp_server/tools/iso.py
git commit -m "feat(mcp): gate tools with @mcp_requires permission decorator"
```

---

### Task 5: Add gating integration tests

**Files:**
- Modify: `mcp_server/tests/test_permissions.py`

- [ ] **Step 1: Write integration tests for tool gating**

Add to `mcp_server/tests/test_permissions.py`:

```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.data.base import override_session
from mcp_server.tools.tracker import tracker_get_projects
from mcp_server.tools.scorecard import scorecard_get_project_scores
from mcp_server.tools.capacity import capacity_get_insights
from mcp_server.tools.iso import iso_get_registries


class TestToolGating:
    """Verify real tools enforce permissions."""

    @pytest.mark.asyncio
    async def test_tracker_blocked_without_permission(self) -> None:
        user = McpUserContext(
            user_id="u1", email="a@b.com", roles=[], permissions=[],
        )
        async with override_mcp_user(user):
            result = await tracker_get_projects()
        assert "Permission denied" in result
        assert "tracker:view" in result

    @pytest.mark.asyncio
    async def test_scorecard_blocked_without_permission(self) -> None:
        user = McpUserContext(
            user_id="u1", email="a@b.com",
            roles=[], permissions=["tracker:view"],
        )
        async with override_mcp_user(user):
            result = await scorecard_get_project_scores()
        assert "Permission denied" in result
        assert "scorecard:view" in result

    @pytest.mark.asyncio
    async def test_capacity_uses_tracker_view(self) -> None:
        user = McpUserContext(
            user_id="u1", email="a@b.com",
            roles=[], permissions=["scorecard:view"],
        )
        async with override_mcp_user(user):
            result = await capacity_get_insights()
        assert "Permission denied" in result

    @pytest.mark.asyncio
    async def test_iso_registries_blocked_without_iso_edit(self) -> None:
        user = McpUserContext(
            user_id="u1", email="a@b.com",
            roles=["user"], permissions=["tracker:view", "scorecard:view"],
        )
        async with override_mcp_user(user):
            result = await iso_get_registries()
        assert "Permission denied" in result
        assert "iso_docs:edit" in result

    @pytest.mark.asyncio
    async def test_iso_registries_allowed_for_editor(
        self, db_session: AsyncSession,
    ) -> None:
        user = McpUserContext(
            user_id="u1", email="a@b.com",
            roles=["iso_docs_editor"], permissions=["iso_docs:edit"],
        )
        async with override_session(db_session):
            async with override_mcp_user(user):
                result = await iso_get_registries()
        parsed = json.loads(result)
        assert isinstance(parsed, list)
```

- [ ] **Step 2: Run gating integration tests**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_permissions.py::TestToolGating -v --no-header 2>&1 | tail -10`

Expected: 5 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add mcp_server/tests/test_permissions.py
git commit -m "test(mcp): add tool gating integration tests"
```

---

### Task 6: ISO data-level filtering

**Files:**
- Modify: `mcp_server/data/iso.py`
- Modify: `mcp_server/tests/test_permissions.py`

- [ ] **Step 1: Write tests for ISO document visibility filtering**

Add to `mcp_server/tests/test_permissions.py`:

```python
from mcp_server.data.base import override_session
from mcp_server.data import iso as iso_data

from app.modules.iso_docs.models import (
    IsoDocMetadataDB,
    IsoDocNodeDB,
    IsoDocVersionDB,
)


@pytest_asyncio.fixture
async def iso_doc_tree(db_session: AsyncSession):
    """Create a minimal ISO doc tree for visibility tests.

    Tree:
      policies (group, root)        ← visible to all
        └── data-protection (page)
      procedures (group, root)      ← visible to all
        └── access-review (page)
      plans (group, root)           ← hidden from non-editors
        └── bcp-plan (page)
    """
    policies_group = IsoDocNodeDB(
        title="Policies", slug="policies", type="group", parent_id=None, position=0,
    )
    procedures_group = IsoDocNodeDB(
        title="Procedures", slug="procedures", type="group", parent_id=None, position=1,
    )
    plans_group = IsoDocNodeDB(
        title="Plans", slug="plans", type="group", parent_id=None, position=2,
    )
    db_session.add_all([policies_group, procedures_group, plans_group])
    await db_session.flush()

    policy_page = IsoDocNodeDB(
        title="Data Protection Policy", slug="data-protection",
        type="page", parent_id=policies_group.id, position=0,
    )
    procedure_page = IsoDocNodeDB(
        title="Access Review Procedure", slug="access-review",
        type="page", parent_id=procedures_group.id, position=0,
    )
    plan_page = IsoDocNodeDB(
        title="Business Continuity Plan", slug="bcp-plan",
        type="page", parent_id=plans_group.id, position=0,
    )
    db_session.add_all([policy_page, procedure_page, plan_page])
    await db_session.flush()

    for page, cat, content in [
        (policy_page, "policy", "Data protection encryption guidelines for remote access"),
        (procedure_page, "procedure", "Quarterly access review process and checklists"),
        (plan_page, "plan", "Business continuity and disaster recovery encryption procedures"),
    ]:
        db_session.add(IsoDocMetadataDB(
            node_id=page.id, category=cat, doc_version="1.0",
        ))
        db_session.add(IsoDocVersionDB(
            node_id=page.id, content=content, version=1,
        ))

    await db_session.flush()
    return {
        "policy_page": policy_page,
        "procedure_page": procedure_page,
        "plan_page": plan_page,
    }


class TestIsoDocVisibility:
    """Verify non-editors only see policies + procedures."""

    REGULAR_USER = McpUserContext(
        user_id="u1", email="user@vizzuality.com",
        roles=["user"], permissions=["tracker:view", "scorecard:view"],
    )
    ISO_EDITOR = McpUserContext(
        user_id="u2", email="editor@vizzuality.com",
        roles=["iso_docs_editor"], permissions=["iso_docs:edit"],
    )

    @pytest.mark.asyncio
    async def test_editor_sees_all_documents(
        self, db_session: AsyncSession, iso_doc_tree,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(self.ISO_EDITOR):
                docs = await iso_data.get_documents(db_session)
        slugs = {d["slug"] for d in docs}
        assert "data-protection" in slugs
        assert "access-review" in slugs
        assert "bcp-plan" in slugs

    @pytest.mark.asyncio
    async def test_regular_user_sees_only_policies_procedures(
        self, db_session: AsyncSession, iso_doc_tree,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(self.REGULAR_USER):
                docs = await iso_data.get_documents(db_session)
        slugs = {d["slug"] for d in docs}
        assert "data-protection" in slugs
        assert "access-review" in slugs
        assert "bcp-plan" not in slugs

    @pytest.mark.asyncio
    async def test_regular_user_cannot_get_hidden_document(
        self, db_session: AsyncSession, iso_doc_tree,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(self.REGULAR_USER):
                with pytest.raises(ValueError, match="not found"):
                    await iso_data.get_document(db_session, "bcp-plan")

    @pytest.mark.asyncio
    async def test_regular_user_can_get_visible_document(
        self, db_session: AsyncSession, iso_doc_tree,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(self.REGULAR_USER):
                doc = await iso_data.get_document(db_session, "data-protection")
        assert doc["slug"] == "data-protection"

    @pytest.mark.asyncio
    async def test_regular_user_search_filters_results(
        self, db_session: AsyncSession, iso_doc_tree,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(self.REGULAR_USER):
                results = await iso_data.search_documents(db_session, "encryption")
        slugs = {r["slug"] for r in results}
        assert "data-protection" in slugs
        assert "bcp-plan" not in slugs

    @pytest.mark.asyncio
    async def test_editor_search_sees_all(
        self, db_session: AsyncSession, iso_doc_tree,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(self.ISO_EDITOR):
                results = await iso_data.search_documents(db_session, "encryption")
        slugs = {r["slug"] for r in results}
        assert "data-protection" in slugs
        assert "bcp-plan" in slugs
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_permissions.py::TestIsoDocVisibility -v --no-header 2>&1 | tail -10`

Expected: FAIL — `get_documents` does not filter yet.

- [ ] **Step 3: Implement visibility filtering in iso.py**

In `mcp_server/data/iso.py`, add imports at the top (note: `text` is already imported from sqlalchemy):

```python
from app.modules.iso_docs.api.deps import USER_VISIBLE_ROOT_SLUGS
from mcp_server.data.base import get_mcp_user
```

Add a helper function after the `_SUMMARY_LENGTH` constant:

```python
async def _get_visible_node_ids(session: AsyncSession) -> set[UUID] | None:
    """Return IDs of nodes visible to the current user, or None if no filter needed."""
    user = get_mcp_user()
    if user.has_permission("iso_docs:edit"):
        return None

    result = await session.execute(
        text("""
            WITH RECURSIVE visible_tree AS (
                SELECT id FROM iso_doc_nodes
                WHERE slug = ANY(:slugs) AND parent_id IS NULL
                UNION ALL
                SELECT n.id FROM iso_doc_nodes n
                INNER JOIN visible_tree vt ON n.parent_id = vt.id
            )
            SELECT id FROM visible_tree
        """),
        {"slugs": list(USER_VISIBLE_ROOT_SLUGS)},
    )
    return {row[0] for row in result.all()}
```

- [ ] **Step 4: Add filtering to get_documents()**

In `mcp_server/data/iso.py`, modify `get_documents`:

```python
async def get_documents(
    session: AsyncSession,
    category: str | None = None,
    title_search: str | None = None,
) -> list[dict]:
    """Return ISO documents (page nodes) with metadata and content summary."""
    visible_ids = await _get_visible_node_ids(session)

    stmt = _doc_base_query(
        IsoDocVersionDB.created_at.label("last_updated"),
        sa_func.left(IsoDocVersionDB.content, _SUMMARY_LENGTH).label("summary"),
    ).order_by(IsoDocNodeDB.title)

    if visible_ids is not None:
        stmt = stmt.where(IsoDocNodeDB.id.in_(visible_ids))
    if category is not None:
        stmt = stmt.where(IsoDocMetadataDB.category == category)
    if title_search is not None:
        stmt = stmt.where(IsoDocNodeDB.title.ilike(f"%{title_search}%"))

    result = await session.execute(stmt)
    return [row._asdict() for row in result.all()]
```

- [ ] **Step 5: Add filtering to get_document()**

In `mcp_server/data/iso.py`, modify `get_document`:

```python
async def get_document(session: AsyncSession, slug: str) -> dict:
    """Return full content of a single ISO document by slug.

    Raises ValueError if slug not found or not visible to current user.
    """
    visible_ids = await _get_visible_node_ids(session)

    stmt = _doc_base_query(
        IsoDocVersionDB.content,
    ).where(IsoDocNodeDB.slug == slug)

    if visible_ids is not None:
        stmt = stmt.where(IsoDocNodeDB.id.in_(visible_ids))

    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        raise ValueError(f"Document '{slug}' not found")
    return row._asdict()
```

- [ ] **Step 6: Add filtering to search_documents()**

In `mcp_server/data/iso.py`, modify `search_documents`:

```python
async def search_documents(
    session: AsyncSession, query: str,
) -> list[dict]:
    """Full-text search across ISO document content.

    Respects user visibility: non-editors only see results from
    documents under policies and procedures root groups.
    """
    visible_ids = await _get_visible_node_ids(session)

    visibility_filter = ""
    params: dict = {"query": query}
    if visible_ids is not None:
        visibility_filter = "AND n.id = ANY(:visible_ids)"
        params["visible_ids"] = list(visible_ids)

    stmt = text(f"""
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
          {visibility_filter}
        ORDER BY rank DESC
    """)
    result = await session.execute(stmt, params)
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

Note: the `visibility_filter` variable is a safe SQL fragment (not user input) injected via f-string. The actual UUIDs go through parameter binding (`:visible_ids`).

- [ ] **Step 7: Run visibility tests**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_permissions.py::TestIsoDocVisibility -v --no-header 2>&1 | tail -10`

Expected: 6 tests PASS.

- [ ] **Step 8: Run full MCP test suite to check for regressions**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/ -v --no-header 2>&1 | tail -10`

Expected: All tests PASS.

- [ ] **Step 9: Commit**

```bash
git add mcp_server/data/iso.py mcp_server/tests/test_permissions.py
git commit -m "feat(mcp): add ISO document visibility filtering for non-editors"
```

---

### Task 7: TokenVerifier sets user context

**Files:**
- Modify: `mcp_server/auth/token_verifier.py`
- Modify: `mcp_server/tests/test_permissions.py`

- [ ] **Step 1: Write test for token verifier context injection**

Add to `mcp_server/tests/test_permissions.py`:

```python
from mcp_server.auth.token_verifier import VizzHubTokenVerifier
from jose import jwt as jose_jwt


class TestTokenVerifierSetsContext:
    SECRET = "test-secret-key-for-testing-only"

    def _make_jwt(self, **extra_claims) -> str:
        payload = {
            "sub": "user-uuid-123",
            "email": "test@vizzuality.com",
            "client_id": "test-client",
            "roles": ["user", "iso_docs_editor"],
            "permissions": ["tracker:view", "scorecard:view", "iso_docs:edit"],
            "scopes": ["read"],
            "iss": "vizzhub",
            "aud": "vizzhub-mcp",
            "exp": 9999999999,
            "iat": 1700000000,
            **extra_claims,
        }
        return jose_jwt.encode(payload, self.SECRET, algorithm="HS256")

    @pytest.mark.asyncio
    async def test_verify_token_sets_mcp_user_context(self) -> None:
        verifier = VizzHubTokenVerifier(secret_key=self.SECRET)
        token_str = self._make_jwt()

        access_token = await verifier.verify_token(token_str)

        assert access_token is not None
        user = get_mcp_user()
        assert user.user_id == "user-uuid-123"
        assert user.email == "test@vizzuality.com"
        assert "user" in user.roles
        assert "iso_docs_editor" in user.roles
        assert user.has_permission("tracker:view")
        assert user.has_permission("iso_docs:edit")

    @pytest.mark.asyncio
    async def test_failed_verification_does_not_set_context(self) -> None:
        verifier = VizzHubTokenVerifier(secret_key=self.SECRET)

        result = await verifier.verify_token("invalid-jwt-token")

        assert result is None
        with pytest.raises(RuntimeError):
            get_mcp_user()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_permissions.py::TestTokenVerifierSetsContext -v --no-header 2>&1 | tail -5`

Expected: FAIL — `get_mcp_user()` raises because `verify_token` doesn't set context yet.

- [ ] **Step 3: Modify token_verifier.py to set context**

Update `mcp_server/auth/token_verifier.py`:

```python
"""JWT token verification for the VizzHub MCP server."""

from __future__ import annotations

import asyncio

from jose import JWTError, jwt
from mcp.server.auth.provider import AccessToken

from mcp_server.data.base import McpUserContext, set_mcp_user


class VizzHubTokenVerifier:
    """Verify MCP access tokens (JWTs signed with the backend's shared secret).

    On success, also sets the McpUserContext ContextVar so that downstream
    tools and data functions can access user identity and permissions.
    """

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        audience: str = "vizzhub-mcp",
        issuer: str = "vizzhub",
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._audience = audience
        self._issuer = issuer

    async def verify_token(self, token: str) -> AccessToken | None:
        """Decode and validate *token*, returning an ``AccessToken`` on success."""
        try:
            payload = await asyncio.to_thread(
                jwt.decode, token, self._secret_key,
                algorithms=[self._algorithm],
                audience=self._audience, issuer=self._issuer,
            )
            set_mcp_user(McpUserContext(
                user_id=payload.get("sub", "unknown"),
                email=payload.get("email", ""),
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
            ))
            return AccessToken(
                token=token,
                client_id=payload.get("client_id", "unknown"),
                scopes=payload.get("scopes", []),
                expires_at=payload.get("exp"),
            )
        except JWTError:
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_permissions.py::TestTokenVerifierSetsContext -v --no-header 2>&1 | tail -5`

Expected: 2 tests PASS.

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/ -v --no-header 2>&1 | tail -5`

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp_server/auth/token_verifier.py mcp_server/tests/test_permissions.py
git commit -m "feat(mcp): set McpUserContext from JWT claims in TokenVerifier"
```

---

### Task 8: stdio mode sets FULL_ACCESS

**Files:**
- Modify: `mcp_server/__main__.py`

- [ ] **Step 1: Update __main__.py to set FULL_ACCESS**

```python
"""Entrypoint: python -m mcp_server"""

from mcp_server.data.base import FULL_ACCESS, set_mcp_user
from mcp_server.server import mcp


def main() -> None:
    set_mcp_user(FULL_ACCESS)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `PYTHONPATH=backend:. python -c "from mcp_server.__main__ import main; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add mcp_server/__main__.py
git commit -m "feat(mcp): set FULL_ACCESS user context in stdio mode"
```

---

### Task 9: Final verification

- [ ] **Step 1: Run full MCP test suite**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/ -v 2>&1 | tail -20`

Expected: All tests pass, including the new permission tests.

- [ ] **Step 2: Run backend tests to check no regressions**

Run: `cd /Volumes/Work/Dev/vizzhub/backend && pytest tests/ -x -q 2>&1 | tail -5`

Expected: All backend tests pass.

- [ ] **Step 3: Count new tests**

Run: `PYTHONPATH=backend:. pytest mcp_server/tests/test_permissions.py -v --no-header 2>&1 | grep -c PASSED`

Expected: ~17 tests (5 context + 4 decorator + 5 gating + 6 ISO visibility + 2 token verifier - some may vary based on search_vector behavior in test DB).

- [ ] **Step 4: Final commit if any loose changes**

```bash
git status
```

If clean, no action needed.
