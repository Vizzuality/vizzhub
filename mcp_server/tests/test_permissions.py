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
