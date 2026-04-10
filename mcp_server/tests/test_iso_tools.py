"""Tests for MCP ISO tools — tool response formatting."""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models import RegistryTypeDB, IsoDocNodeDB, RegistryRowDB
from mcp_server.data.base import override_session
from mcp_server.server import mcp


@pytest_asyncio.fixture
async def seed_tool_registry(db_session: AsyncSession) -> None:
    rt = RegistryTypeDB(
        name="Test Register",
        slug="test-register",
        description="A test registry",
        is_yearly=False,
        schema=[{"key": "name", "label": "Name", "type": "string"}],
    )
    db_session.add(rt)
    await db_session.flush()

    node = IsoDocNodeDB(
        title="Test Register",
        slug="test-register",
        type="registry",
        registry_type_id=rt.id,
    )
    db_session.add(node)
    await db_session.flush()

    db_session.add(RegistryRowDB(
        node_id=node.id, year=None, row_index=0,
        data={"name": "Test Row"},
    ))
    await db_session.commit()


@pytest.mark.asyncio
async def test_iso_get_registries_is_listed(db_session, seed_tool_registry) -> None:
    async with override_session(db_session):
        tools = await mcp.list_tools()
    names = [t.name for t in tools]
    assert "iso_get_registries" in names


@pytest.mark.asyncio
async def test_iso_get_registries_returns_json(db_session, seed_tool_registry) -> None:
    async with override_session(db_session):
        result = await mcp.call_tool("iso_get_registries", {})
    # call_tool returns (unstructured_content, structured_content); unstructured is a list of ContentBlock
    content_blocks = result[0]
    text = content_blocks[0].text
    data = json.loads(text)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["slug"] == "test-register"


@pytest.mark.asyncio
async def test_iso_get_registry_rows_is_listed(db_session, seed_tool_registry) -> None:
    async with override_session(db_session):
        tools = await mcp.list_tools()
    names = [t.name for t in tools]
    assert "iso_get_registry_rows" in names


@pytest.mark.asyncio
async def test_iso_get_registry_rows_returns_data(db_session, seed_tool_registry) -> None:
    async with override_session(db_session):
        result = await mcp.call_tool("iso_get_registry_rows", {"slug": "test-register"})
    content_blocks = result[0]
    data = json.loads(content_blocks[0].text)
    assert data["total_rows"] == 1
    assert data["rows"][0]["data"]["name"] == "Test Row"


@pytest.mark.asyncio
async def test_iso_get_registry_rows_invalid_slug(db_session, seed_tool_registry) -> None:
    async with override_session(db_session):
        result = await mcp.call_tool("iso_get_registry_rows", {"slug": "nonexistent"})
    content_blocks = result[0]
    text = content_blocks[0].text
    assert "not found" in text.lower()
