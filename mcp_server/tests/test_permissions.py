"""Tests for MCP permission layer."""

import json

import pytest
import pytest_asyncio
from jose import jwt as jose_jwt
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.auth.permissions import mcp_requires
from mcp_server.auth.token_verifier import VizzHubTokenVerifier
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
    IsoDocNoteDB,
    IsoDocVersionDB,
    RegistryTypeDB,
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
    async def test_iso_registries_returns_filtered_list_for_non_editor(
        self, db_session: AsyncSession,
    ) -> None:
        """Audit Tier 1 #4: registry reads no longer require iso_docs:edit.
        Non-editors get a visibility-filtered list (empty here, no registries
        seeded under policies/procedures), not a permission error."""
        user = McpUserContext(
            user_id="u1", email="a@b.com",
            roles=["user"], permissions=["tracker:view", "scorecard:view"],
        )
        async with override_session(db_session):
            async with override_mcp_user(user):
                result = await iso_get_registries()
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert parsed == []

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


@pytest_asyncio.fixture
async def iso_registry_tree(db_session: AsyncSession):
    """ISO tree with registries mounted under both visible and hidden roots.

    Tree:
      policies (group)      <- visible
        +-- visible-reg (registry, type 'visible-register')
      plans (group)         <- hidden from non-editors
        +-- hidden-reg (registry, type 'hidden-register')
    """
    policies = IsoDocNodeDB(title="Policies", slug="policies", type="group", parent_id=None, position=0)
    plans = IsoDocNodeDB(title="Plans", slug="plans", type="group", parent_id=None, position=1)
    db_session.add_all([policies, plans])
    await db_session.flush()

    visible_type = RegistryTypeDB(
        name="Visible Register", slug="visible-register",
        is_yearly=False,
        schema=[{"key": "name", "label": "Name", "type": "string", "required": True}],
    )
    hidden_type = RegistryTypeDB(
        name="Hidden Register", slug="hidden-register",
        is_yearly=False,
        schema=[{"key": "name", "label": "Name", "type": "string", "required": True}],
    )
    db_session.add_all([visible_type, hidden_type])
    await db_session.flush()

    visible_reg = IsoDocNodeDB(
        title="Visible Reg", slug="visible-reg",
        type="registry", parent_id=policies.id, position=0,
        registry_type_id=visible_type.id,
    )
    hidden_reg = IsoDocNodeDB(
        title="Hidden Reg", slug="hidden-reg",
        type="registry", parent_id=plans.id, position=0,
        registry_type_id=hidden_type.id,
    )
    db_session.add_all([visible_reg, hidden_reg])
    await db_session.flush()
    return {
        "visible_node": visible_reg,
        "hidden_node": hidden_reg,
        "visible_type": visible_type,
        "hidden_type": hidden_type,
    }


class TestIsoRegistryVisibility:
    """Audit Tier 1 #4: non-editors only see registries mounted under policies/procedures."""

    REGULAR_USER = McpUserContext(
        user_id="u1", email="user@vizzuality.com",
        roles=["user"], permissions=["tracker:view"],
    )
    ISO_EDITOR = McpUserContext(
        user_id="u2", email="editor@vizzuality.com",
        roles=["iso_docs_editor"], permissions=["iso_docs:edit"],
    )

    @pytest.mark.asyncio
    async def test_editor_sees_all_registry_types(
        self, db_session: AsyncSession, iso_registry_tree,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(self.ISO_EDITOR):
                types = await iso_data.get_registry_types(db_session)
        slugs = {rt.slug for rt, _ in types}
        assert "visible-register" in slugs
        assert "hidden-register" in slugs

    @pytest.mark.asyncio
    async def test_regular_user_sees_only_visible_registry_types(
        self, db_session: AsyncSession, iso_registry_tree,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(self.REGULAR_USER):
                types = await iso_data.get_registry_types(db_session)
        slugs = {rt.slug for rt, _ in types}
        assert "visible-register" in slugs
        assert "hidden-register" not in slugs

    @pytest.mark.asyncio
    async def test_regular_user_cannot_resolve_hidden_registry(
        self, db_session: AsyncSession, iso_registry_tree,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(self.REGULAR_USER):
                with pytest.raises(ValueError, match="not found"):
                    await iso_data.resolve_registry_node(db_session, "hidden-reg")

    @pytest.mark.asyncio
    async def test_regular_user_can_resolve_visible_registry(
        self, db_session: AsyncSession, iso_registry_tree,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(self.REGULAR_USER):
                rt, node_id, slug = await iso_data.resolve_registry_node(
                    db_session, "visible-reg",
                )
        assert slug == "visible-reg"
        assert rt.slug == "visible-register"


class TestIsoNoteVisibility:
    """Audit Tier 1 #4: non-editors only see notes attached to visible nodes."""

    REGULAR_USER = McpUserContext(
        user_id="u1", email="user@vizzuality.com",
        roles=["user"], permissions=["tracker:view"],
    )

    @pytest.mark.asyncio
    async def test_regular_user_cannot_list_notes_on_hidden_node(
        self, db_session: AsyncSession, iso_doc_tree,
    ) -> None:
        db_session.add(IsoDocNoteDB(
            node_id=iso_doc_tree["plan_page"].id,
            content="audit flag on hidden",
            done=False,
        ))
        await db_session.flush()
        async with override_session(db_session):
            async with override_mcp_user(self.REGULAR_USER):
                with pytest.raises(ValueError, match="not found"):
                    await iso_data.get_node_notes(
                        db_session, "bcp-plan", include_done=False,
                    )

    @pytest.mark.asyncio
    async def test_regular_user_pending_notes_excludes_hidden(
        self, db_session: AsyncSession, iso_doc_tree,
    ) -> None:
        db_session.add(IsoDocNoteDB(
            node_id=iso_doc_tree["policy_page"].id,
            content="visible note", done=False,
        ))
        db_session.add(IsoDocNoteDB(
            node_id=iso_doc_tree["plan_page"].id,
            content="hidden note", done=False,
        ))
        await db_session.flush()
        async with override_session(db_session):
            async with override_mcp_user(self.REGULAR_USER):
                notes = await iso_data.get_pending_notes(db_session)
        contents = {n["content"] for n in notes}
        assert "visible note" in contents
        assert "hidden note" not in contents


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
