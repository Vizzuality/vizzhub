"""End-to-end integration tests — seed DB, call MCP tools, verify responses."""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models import (
    IsoDocMetadataDB,
    IsoDocNodeDB,
    IsoDocVersionDB,
    RegistryRowDB,
    RegistryTypeDB,
)
from mcp_server.data.base import override_session
from mcp_server.server import mcp


@pytest_asyncio.fixture
async def seeded_db(db_session: AsyncSession) -> None:
    """Seed DB with a registry and a document for integration testing."""
    # Registry type + node + rows
    rt = RegistryTypeDB(
        name="Incident Register",
        slug="incident-register",
        description="Security incidents",
        is_yearly=True,
        schema=[
            {"key": "number", "label": "Number", "type": "string", "required": True},
            {"key": "severity", "label": "Severity", "type": "select",
             "options": ["Critical", "High", "Medium", "Low"]},
        ],
    )
    db_session.add(rt)
    await db_session.flush()

    node = IsoDocNodeDB(
        title="Incident Register",
        slug="incident-register",
        type="registry",
        registry_type_id=rt.id,
    )
    db_session.add(node)
    await db_session.flush()

    db_session.add(RegistryRowDB(
        node_id=node.id, year=2026, row_index=0,
        data={"number": "INC-001", "severity": "High"},
    ))

    # Parent group + document page + metadata + version
    group = IsoDocNodeDB(
        title="Policies", slug="policies", type="group",
    )
    db_session.add(group)
    await db_session.flush()

    page = IsoDocNodeDB(
        title="Security Policy",
        slug="security-policy",
        type="page",
        parent_id=group.id,
    )
    db_session.add(page)
    await db_session.flush()

    db_session.add(IsoDocMetadataDB(
        node_id=page.id, doc_version="1.0",
    ))
    db_session.add(IsoDocVersionDB(
        node_id=page.id, version=1,
        content="## 1. Purpose\n\nEstablishes encryption and remote access controls.",
    ))

    await db_session.commit()


@pytest.mark.asyncio
async def test_list_registries_then_get_rows(db_session, seeded_db) -> None:
    """Full flow: discover registries → fetch rows."""
    async with override_session(db_session):
        result = await mcp.call_tool("iso_get_registries", {})
        registries = json.loads(result[0][0].text)
        assert len(registries) >= 1

        slug = registries[0]["slug"]
        result = await mcp.call_tool(
            "iso_get_registry_rows", {"slug": slug, "year": 2026},
        )
        data = json.loads(result[0][0].text)
        assert data["total_rows"] >= 1
        assert data["rows"][0]["data"]["number"] == "INC-001"


@pytest.mark.asyncio
async def test_search_then_read_document(db_session, seeded_db) -> None:
    """Full flow: search docs → read matching document."""
    async with override_session(db_session):
        result = await mcp.call_tool(
            "iso_search_documents", {"query": "encryption remote"},
        )
        results = json.loads(result[0][0].text)
        assert len(results) >= 1
        slug = results[0]["slug"]

        result = await mcp.call_tool("iso_get_document", {"slug": slug})
        doc = json.loads(result[0][0].text)
        assert "encryption" in doc["content"].lower()


@pytest.mark.asyncio
async def test_list_documents_filtered(db_session, seeded_db) -> None:
    async with override_session(db_session):
        result = await mcp.call_tool(
            "iso_get_documents", {"category": "Policies"},
        )
        docs = json.loads(result[0][0].text)
        assert len(docs) >= 1
        assert all(d["category"] == "Policies" for d in docs)


@pytest.mark.asyncio
async def test_no_write_tools_registered(db_session, seeded_db) -> None:
    """Phase 1 is read-only: no create/update/delete tools should exist."""
    async with override_session(db_session):
        tools = await mcp.list_tools()
    names = [t.name for t in tools]
    write_tools = [n for n in names if "create" in n or "update" in n or "delete" in n]
    assert write_tools == [], f"Unexpected write tools found: {write_tools}"
