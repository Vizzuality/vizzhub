"""Tests for MCP permission layer."""

import json

import pytest

from mcp_server.auth.permissions import mcp_requires
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
