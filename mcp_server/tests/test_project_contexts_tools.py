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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
    call_kwargs = get_mock.await_args.kwargs
    assert call_kwargs["at_sha"] == "old-sha"


@pytest.mark.asyncio
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
