"""Tests for MCP permission layer."""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.auth.permissions import mcp_requires
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
