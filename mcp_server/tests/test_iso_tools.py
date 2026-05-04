"""Tests for MCP ISO tools — tool response formatting."""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models import RegistryTypeDB, IsoDocNodeDB, RegistryRowDB, IsoDocVersionDB, IsoDocMetadataDB
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


@pytest_asyncio.fixture
async def seed_registry_with_divergent_slugs(db_session: AsyncSession) -> None:
    """Registry whose node slug differs from its registry type slug — the
    real-world case that surfaced the bug (e.g. 'Audit Plan & Results')."""
    rt = RegistryTypeDB(
        name="Audit Plan & Results",
        slug="audit-plan-&-results",
        description="Annual audit plan",
        is_yearly=False,
        schema=[{"key": "title", "label": "Title", "type": "string"}],
    )
    db_session.add(rt)
    await db_session.flush()
    node = IsoDocNodeDB(
        title="Audit Plan & Results",
        slug="audit-plan-results",
        type="registry",
        registry_type_id=rt.id,
    )
    db_session.add(node)
    await db_session.flush()
    db_session.add(RegistryRowDB(
        node_id=node.id, year=None, row_index=0,
        data={"title": "Internal audit"},
    ))
    await db_session.commit()


@pytest.mark.asyncio
async def test_iso_get_registries_returns_node_slug_as_canonical(
    db_session, seed_registry_with_divergent_slugs,
) -> None:
    """Regression: iso_get_registries must surface the node slug as `slug`
    (canonical, accepted by write tools) and the type slug as `type_slug`."""
    async with override_session(db_session):
        result = await mcp.call_tool("iso_get_registries", {})
    data = json.loads(result[0][0].text)
    entry = next(r for r in data if r["name"] == "Audit Plan & Results")
    assert entry["slug"] == "audit-plan-results"
    assert entry["type_slug"] == "audit-plan-&-results"


@pytest.mark.asyncio
async def test_iso_get_registry_rows_accepts_node_slug(
    db_session, seed_registry_with_divergent_slugs,
) -> None:
    """The slug returned by iso_get_registries must round-trip through
    iso_get_registry_rows."""
    async with override_session(db_session):
        result = await mcp.call_tool(
            "iso_get_registry_rows", {"slug": "audit-plan-results"},
        )
    data = json.loads(result[0][0].text)
    assert data["slug"] == "audit-plan-results"
    assert data["type_slug"] == "audit-plan-&-results"
    assert data["total_rows"] == 1


@pytest.mark.asyncio
async def test_iso_get_registry_rows_accepts_type_slug_for_compat(
    db_session, seed_registry_with_divergent_slugs,
) -> None:
    """Legacy callers that have the registry type slug must keep working."""
    async with override_session(db_session):
        result = await mcp.call_tool(
            "iso_get_registry_rows", {"slug": "audit-plan-&-results"},
        )
    data = json.loads(result[0][0].text)
    assert data["slug"] == "audit-plan-results"
    assert data["total_rows"] == 1


@pytest_asyncio.fixture
async def seed_tool_documents(db_session: AsyncSession) -> None:
    page = IsoDocNodeDB(
        title="Test Policy",
        slug="test-policy",
        type="page",
    )
    db_session.add(page)
    await db_session.flush()

    db_session.add(IsoDocMetadataDB(
        node_id=page.id, category="policy", doc_version="1.0",
    ))
    db_session.add(IsoDocVersionDB(
        node_id=page.id, version=1,
        content="## Purpose\n\nThis policy covers encryption and remote access.",
    ))
    await db_session.commit()


@pytest.mark.asyncio
async def test_iso_get_document_not_found(db_session, seed_tool_documents) -> None:
    async with override_session(db_session):
        result = await mcp.call_tool("iso_get_document", {"slug": "nonexistent"})
    content_blocks = result[0]
    text = content_blocks[0].text
    assert "not found" in text.lower()


@pytest.mark.asyncio
async def test_iso_get_documents_returns_data(db_session, seed_tool_documents) -> None:
    async with override_session(db_session):
        result = await mcp.call_tool("iso_get_documents", {})
    content_blocks = result[0]
    docs = json.loads(content_blocks[0].text)
    assert len(docs) >= 1
    assert docs[0]["slug"] == "test-policy"


@pytest.mark.asyncio
async def test_iso_search_documents_returns_results(db_session, seed_tool_documents) -> None:
    async with override_session(db_session):
        result = await mcp.call_tool("iso_search_documents", {"query": "encryption"})
    content_blocks = result[0]
    results = json.loads(content_blocks[0].text)
    assert len(results) >= 1
    assert results[0]["slug"] == "test-policy"
