"""Tests for MCP Playbook tools — tool response formatting via call_tool."""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from mcp_server.data.base import override_session
from mcp_server.server import create_mcp_server


def _parse_tool_result(result) -> dict | list:
    content_blocks = result[0]
    return json.loads(content_blocks[0].text)


@pytest_asyncio.fixture
async def seed_playbook(db_session: AsyncSession) -> dict:
    """Seed a playbook with groups and pages."""
    group = PlaybookNodeDB(
        title="Engineering",
        slug="engineering",
        type="group",
        position=0,
        is_public=True,
    )
    db_session.add(group)
    await db_session.flush()

    page1 = PlaybookNodeDB(
        title="Onboarding Guide",
        slug="onboarding-guide",
        type="page",
        parent_id=group.id,
        position=0,
        is_public=True,
    )
    page2 = PlaybookNodeDB(
        title="Code Review Process",
        slug="code-review-process",
        type="page",
        parent_id=group.id,
        position=1,
        is_public=False,
    )
    db_session.add_all([page1, page2])
    await db_session.flush()

    db_session.add(PlaybookPageVersionDB(
        node_id=page1.id,
        content="# Onboarding\n\nWelcome to Vizzuality! This guide covers the first week setup.",
        version=1,
    ))
    db_session.add(PlaybookPageVersionDB(
        node_id=page1.id,
        content="# Onboarding\n\nWelcome to Vizzuality! This guide covers the first two weeks of setup and training.",
        version=2,
    ))
    db_session.add(PlaybookPageVersionDB(
        node_id=page2.id,
        content="# Code Review\n\nAll PRs require at least one approval before merging.",
        version=1,
    ))
    await db_session.commit()

    return {
        "group_id": str(group.id),
        "page1_slug": "onboarding-guide",
        "page2_slug": "code-review-process",
    }


@pytest.mark.asyncio
async def test_playbook_get_tree(db_session, seed_playbook) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("playbook_get_tree", {})
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    assert len(data) == 1
    group = data[0]
    assert group["title"] == "Engineering"
    assert group["type"] == "group"
    assert len(group["children"]) == 2


@pytest.mark.asyncio
async def test_playbook_get_article(db_session, seed_playbook) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "playbook_get_article",
            {"slug": seed_playbook["page1_slug"]},
        )
    data = _parse_tool_result(result)
    assert data["title"] == "Onboarding Guide"
    assert data["version"] == 2  # Latest version
    assert "two weeks" in data["content"]
    assert data["is_public"] is True


@pytest.mark.asyncio
async def test_playbook_get_article_not_found(db_session, seed_playbook) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "playbook_get_article",
            {"slug": "nonexistent-page"},
        )
    data = _parse_tool_result(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_playbook_search_articles(db_session, seed_playbook) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "playbook_search_articles",
            {"query": "onboarding"},
        )
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["title"] == "Onboarding Guide"


@pytest.mark.asyncio
async def test_playbook_search_articles_content(db_session, seed_playbook) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "playbook_search_articles",
            {"query": "approval"},
        )
    data = _parse_tool_result(result)
    assert len(data) == 1
    assert data[0]["title"] == "Code Review Process"


@pytest.mark.asyncio
async def test_playbook_search_articles_no_results(db_session, seed_playbook) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "playbook_search_articles",
            {"query": "nonexistent-term-xyz"},
        )
    data = _parse_tool_result(result)
    assert data == []
