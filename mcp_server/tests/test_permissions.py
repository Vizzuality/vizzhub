"""Tests for MCP permission layer."""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.auth.permissions import mcp_requires
from mcp_server.data import iso as iso_data
from mcp_server.data.base import (
    FULL_ACCESS,
    McpUserContext,
    get_mcp_user,
    override_mcp_user,
    override_session,
    set_mcp_user,
)
from mcp_server.tools.tracker import tracker_get_projects
from mcp_server.tools.scorecard import scorecard_get_project_scores
from mcp_server.tools.capacity import capacity_get_insights
from mcp_server.tools.iso import iso_get_registries

from app.modules.iso_docs.models import (
    IsoDocMetadataDB,
    IsoDocNodeDB,
    IsoDocVersionDB,
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


@pytest_asyncio.fixture
async def iso_doc_tree(db_session: AsyncSession):
    """Create a minimal ISO doc tree for visibility tests.

    Tree:
      policies (group, root)        <- visible to all
        +-- data-protection (page)
      procedures (group, root)      <- visible to all
        +-- access-review (page)
      plans (group, root)           <- hidden from non-editors
        +-- bcp-plan (page)
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
