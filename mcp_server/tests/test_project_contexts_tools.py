"""Tests for MCP project-contexts tools."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.tools.devstack import (
    devstack_get_project_context,
    devstack_update_project_context,
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


@pytest.mark.asyncio
async def test_update_committed_creates_approved_command(monkeypatch):
    user_db = MagicMock()
    user_db.name = "Miguel Mendoza"
    user_db.email = "miguel@vizzuality.com"

    with patch("mcp_server.tools.devstack.get_write_session") as mock_session_ctx:
        session = MagicMock()
        session.get = AsyncMock(return_value=user_db)
        mock_session_ctx.return_value.__aenter__.return_value = session

        push_mock = AsyncMock(return_value={"status": "committed", "new_sha": "new-sha"})
        monkeypatch.setattr(
            "mcp_server.tools.devstack.project_contexts_data.push_context",
            push_mock,
        )
        enqueue_mock = AsyncMock(return_value=MagicMock(id="cmd-uuid"))
        monkeypatch.setattr(
            "mcp_server.tools.devstack.CommandService.enqueue_approved",
            enqueue_mock,
        )

        out = await devstack_update_project_context(
            slug="acme-corp",
            content="# New content",
            expected_remote_sha="old-sha",
        )

    parsed = json.loads(out)
    assert parsed["status"] == "committed"
    assert parsed["new_sha"] == "new-sha"
    assert parsed["command_id"] == "cmd-uuid"
    push_kwargs = push_mock.await_args.kwargs
    assert push_kwargs["author_email"] == "dev@vizzuality.com"


@pytest.mark.asyncio
async def test_update_conflict_does_not_enqueue(monkeypatch):
    user_db = MagicMock()
    user_db.name = "Miguel"
    user_db.email = "miguel@vizzuality.com"

    with patch("mcp_server.tools.devstack.get_write_session") as mock_session_ctx:
        session = MagicMock()
        session.get = AsyncMock(return_value=user_db)
        mock_session_ctx.return_value.__aenter__.return_value = session

        monkeypatch.setattr(
            "mcp_server.tools.devstack.project_contexts_data.push_context",
            AsyncMock(return_value={"status": "conflict", "remote_sha": "newer-sha"}),
        )
        enqueue_mock = AsyncMock()
        monkeypatch.setattr(
            "mcp_server.tools.devstack.CommandService.enqueue_approved",
            enqueue_mock,
        )

        out = await devstack_update_project_context(
            slug="acme-corp", content="# x", expected_remote_sha="stale"
        )

    parsed = json.loads(out)
    assert parsed["status"] == "conflict"
    assert parsed["remote_sha"] == "newer-sha"
    enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_up_to_date_does_not_enqueue(monkeypatch):
    """When the remote content already matches, no command row should be
    created — up_to_date is a semantic no-op, not just a write-skip like
    conflict."""
    from mcp_server.tools.devstack import devstack_update_project_context

    user_db = MagicMock()
    user_db.name = "Miguel"
    user_db.email = "miguel@vizzuality.com"

    with patch("mcp_server.tools.devstack.get_write_session") as mock_session_ctx:
        session = MagicMock()
        session.get = AsyncMock(return_value=user_db)
        mock_session_ctx.return_value.__aenter__.return_value = session

        monkeypatch.setattr(
            "mcp_server.tools.devstack.project_contexts_data.push_context",
            AsyncMock(return_value={"status": "up_to_date", "remote_sha": "same-sha"}),
        )
        enqueue_mock = AsyncMock()
        monkeypatch.setattr(
            "mcp_server.tools.devstack.CommandService.enqueue_approved",
            enqueue_mock,
        )

        out = await devstack_update_project_context(
            slug="acme-corp", content="# same", expected_remote_sha="same-sha"
        )

    parsed = json.loads(out)
    assert parsed["status"] == "up_to_date"
    assert parsed["remote_sha"] == "same-sha"
    assert "command_id" not in parsed
    enqueue_mock.assert_not_awaited()
