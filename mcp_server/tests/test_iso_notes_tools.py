"""Tests for MCP ISO note tools."""

import json
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.iso_docs.models import IsoDocNodeDB, IsoDocNoteDB
from mcp_server.data.base import override_session
from mcp_server.server import mcp


@pytest_asyncio.fixture
async def seed_notes(db_session: AsyncSession) -> dict:
    user = UserDB(id=uuid4(), email="auditor@test.com", first_name="Alice", last_name="A")
    db_session.add(user)
    await db_session.flush()

    page = IsoDocNodeDB(title="POL04", slug="pol04", type="page")
    registry = IsoDocNodeDB(title="Opportunities", slug="opportunities", type="registry")
    db_session.add_all([page, registry])
    await db_session.flush()

    pending = IsoDocNoteDB(
        node_id=page.id, content="Check version bump", created_by_id=user.id,
    )
    done = IsoDocNoteDB(
        node_id=page.id, content="Already resolved", created_by_id=user.id, done=True,
    )
    other = IsoDocNoteDB(
        node_id=registry.id, content="Missing 2024 rows", created_by_id=user.id,
    )
    db_session.add_all([pending, done, other])
    await db_session.commit()
    return {"page_slug": page.slug, "registry_slug": registry.slug}


@pytest.mark.asyncio
async def test_list_notes_default_excludes_done(
    db_session: AsyncSession, use_test_db, seed_notes,
) -> None:
    async with override_session(db_session):
        result = await mcp.call_tool("iso_list_notes", {"node_slug": seed_notes["page_slug"]})
    data = json.loads(result[0][0].text)
    assert data["node_slug"] == "pol04"
    assert data["total_notes"] == 1
    assert data["notes"][0]["content"] == "Check version bump"
    assert data["notes"][0]["created_by"] == "Alice A"


@pytest.mark.asyncio
async def test_list_notes_include_done(
    db_session: AsyncSession, use_test_db, seed_notes,
) -> None:
    async with override_session(db_session):
        result = await mcp.call_tool(
            "iso_list_notes",
            {"node_slug": seed_notes["page_slug"], "include_done": True},
        )
    data = json.loads(result[0][0].text)
    assert data["total_notes"] == 2
    contents = {n["content"] for n in data["notes"]}
    assert contents == {"Check version bump", "Already resolved"}


@pytest.mark.asyncio
async def test_list_notes_unknown_slug(
    db_session: AsyncSession, use_test_db,
) -> None:
    async with override_session(db_session):
        result = await mcp.call_tool("iso_list_notes", {"node_slug": "does-not-exist"})
    data = json.loads(result[0][0].text)
    assert "not found" in data["error"].lower()


@pytest.mark.asyncio
async def test_list_pending_notes_aggregates_across_nodes(
    db_session: AsyncSession, use_test_db, seed_notes,
) -> None:
    async with override_session(db_session):
        result = await mcp.call_tool("iso_list_pending_notes", {})
    notes = json.loads(result[0][0].text)
    assert len(notes) == 2
    slugs = {n["node_slug"] for n in notes}
    assert slugs == {"pol04", "opportunities"}
    # Done notes are excluded
    assert all(n["content"] != "Already resolved" for n in notes)
