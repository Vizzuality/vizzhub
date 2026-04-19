"""Tests for the MCP project-contexts data layer."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.data import project_contexts as pc_data


@pytest.mark.asyncio
async def test_list_returns_slugs_only():
    rows = [
        ("acme-corp", "Acme notes", "Acme Corp"),
        ("gov-x", None, "Gov Project X"),
    ]
    db_result = MagicMock()
    db_result.all = MagicMock(return_value=rows)
    session = MagicMock()
    session.execute = AsyncMock(return_value=db_result)
    result = await pc_data.list_contexts(session)
    assert result == [
        {"slug": "acme-corp", "description": "Acme notes", "project_name": "Acme Corp"},
        {"slug": "gov-x", "description": None, "project_name": "Gov Project X"},
    ]


@pytest.mark.asyncio
async def test_get_uses_fetch_head_when_no_at_sha(monkeypatch):
    ctx_record = MagicMock(slug="acme-corp")
    db_result = MagicMock()
    db_result.scalar_one_or_none = MagicMock(return_value=ctx_record)
    session = MagicMock()
    session.execute = AsyncMock(return_value=db_result)

    fake_client = MagicMock()
    fake_client.fetch_head = AsyncMock(return_value=("# Acme", "blob-sha-1"))
    fake_client.fetch_at_sha = AsyncMock()
    monkeypatch.setattr(pc_data, "_build_github_client", lambda token: fake_client)

    with patch.object(
        pc_data.IntegrationTokenService, "get_token", new=AsyncMock(return_value="tok")
    ):
        result = await pc_data.get_context(session, slug="acme-corp", at_sha=None)

    assert result == {
        "target_path": "CLAUDE.md",
        "content": "# Acme",
        "devstack_sha": "blob-sha-1",
        "slug": "acme-corp",
    }
    fake_client.fetch_head.assert_awaited_once_with("acme-corp")
    fake_client.fetch_at_sha.assert_not_called()


@pytest.mark.asyncio
async def test_get_uses_fetch_at_sha_when_provided(monkeypatch):
    ctx_record = MagicMock(slug="acme-corp")
    db_result = MagicMock()
    db_result.scalar_one_or_none = MagicMock(return_value=ctx_record)
    session = MagicMock()
    session.execute = AsyncMock(return_value=db_result)

    fake_client = MagicMock()
    fake_client.fetch_head = AsyncMock()
    fake_client.fetch_at_sha = AsyncMock(return_value="# Base Acme")
    monkeypatch.setattr(pc_data, "_build_github_client", lambda token: fake_client)

    with patch.object(
        pc_data.IntegrationTokenService, "get_token", new=AsyncMock(return_value="tok")
    ):
        result = await pc_data.get_context(session, slug="acme-corp", at_sha="old-sha")

    assert result == {
        "target_path": "CLAUDE.md",
        "content": "# Base Acme",
        "devstack_sha": "old-sha",
        "slug": "acme-corp",
    }
    fake_client.fetch_at_sha.assert_awaited_once_with("old-sha")


@pytest.mark.asyncio
async def test_get_slug_not_registered_raises():
    db_result = MagicMock()
    db_result.scalar_one_or_none = MagicMock(return_value=None)
    session = MagicMock()
    session.execute = AsyncMock(return_value=db_result)

    with pytest.raises(pc_data.ContextNotFoundError):
        await pc_data.get_context(session, slug="missing", at_sha=None)
