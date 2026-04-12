"""Integration tests -- MCP write tools + command queue."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.iso_docs.models import (
    IsoDocMetadataDB,
    IsoDocNodeDB,
    IsoDocVersionDB,
    RegistryTypeDB,
)
from mcp_server.data.base import McpUserContext, override_mcp_user, override_session
from mcp_server.server import mcp


@pytest_asyncio.fixture
async def editor_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        email="editor@vizzuality.com",
        name="Editor User",
        first_name="Editor",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
def editor_ctx(editor_user: UserDB) -> McpUserContext:
    return McpUserContext(
        user_id=str(editor_user.id),
        email=editor_user.email,
        roles=["iso_docs_editor"],
        permissions=["*"],
    )


@pytest_asyncio.fixture
async def seeded_iso(db_session: AsyncSession, editor_user: UserDB) -> dict:
    """Create group + page + metadata + version + registry type + node."""
    group = IsoDocNodeDB(
        title="Policies",
        slug="policies",
        type="group",
        position=0,
        created_by_id=editor_user.id,
    )
    db_session.add(group)
    await db_session.flush()
    await db_session.refresh(group)

    page = IsoDocNodeDB(
        title="Security Policy",
        slug="security-policy",
        type="page",
        parent_id=group.id,
        position=0,
        created_by_id=editor_user.id,
    )
    db_session.add(page)
    await db_session.flush()
    await db_session.refresh(page)

    meta = IsoDocMetadataDB(node_id=page.id, code="POL-001", status="draft")
    db_session.add(meta)

    version = IsoDocVersionDB(
        node_id=page.id,
        content="# Security Policy\n\nInitial content.",
        version=1,
        created_by_id=editor_user.id,
    )
    db_session.add(version)

    rt = RegistryTypeDB(
        name="Incident Register",
        slug="incident-register",
        description="Tracks security incidents.",
        is_yearly=False,
        schema=[
            {"key": "number", "label": "Number", "type": "number"},
            {"key": "severity", "label": "Severity", "type": "select",
             "options": ["low", "medium", "high"]},
        ],
    )
    db_session.add(rt)
    await db_session.flush()
    await db_session.refresh(rt)

    reg_node = IsoDocNodeDB(
        title="Incident Register",
        slug="incident-register",
        type="registry",
        position=1,
        registry_type_id=rt.id,
        created_by_id=editor_user.id,
    )
    db_session.add(reg_node)
    await db_session.flush()

    return {
        "group": group,
        "page": page,
        "meta": meta,
        "registry_type": rt,
        "registry_node": reg_node,
    }


@pytest.mark.asyncio
async def test_iso_create_page_enqueue_and_approve(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "Access Control"},
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "queued"
            assert "command_id" in data
            assert "Access Control" in data["summary"]

            approve_result = await mcp.call_tool(
                "approve_command",
                {"command_id": data["command_id"]},
            )
            approve_data = json.loads(approve_result[0][0].text)
            assert approve_data["status"] == "executed"
            assert approve_data["result"]["slug"] == "access-control"
            assert approve_data["result"]["title"] == "Access Control"


@pytest.mark.asyncio
async def test_iso_create_registry_row_enqueue_and_approve(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "iso_create_registry_row",
                {
                    "slug": "incident-register",
                    "data": {"number": 1, "severity": "high"},
                },
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "queued"
            assert "Incident Register" in data["summary"]

            approve_result = await mcp.call_tool(
                "approve_command",
                {"command_id": data["command_id"]},
            )
            approve_data = json.loads(approve_result[0][0].text)
            assert approve_data["status"] == "executed"
            assert approve_data["result"]["data"]["number"] == 1
            assert approve_data["result"]["data"]["severity"] == "high"


@pytest.mark.asyncio
async def test_reject_command(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "Unwanted Page"},
            )
            data = json.loads(result[0][0].text)
            command_id = data["command_id"]

            reject_result = await mcp.call_tool(
                "reject_command",
                {"command_id": command_id},
            )
            reject_data = json.loads(reject_result[0][0].text)
            assert reject_data["status"] == "rejected"
            assert reject_data["command_id"] == command_id


@pytest.mark.asyncio
async def test_get_pending_commands(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "Page One"},
            )
            await mcp.call_tool(
                "iso_delete_node",
                {"slug": "security-policy"},
            )

            result = await mcp.call_tool("get_pending_commands", {})
            data = json.loads(result[0][0].text)
            assert isinstance(data, list)
            assert len(data) == 2
            actions = {cmd["action"] for cmd in data}
            assert "create_page" in actions
            assert "delete_node" in actions


@pytest.mark.asyncio
async def test_permission_denied_for_write_tool(
    db_session: AsyncSession,
    seeded_iso: dict,
) -> None:
    no_perm_ctx = McpUserContext(
        user_id="no-perm-user",
        email="viewer@vizzuality.com",
        roles=["user"],
        permissions=["tracker:view"],
    )
    async with override_session(db_session):
        async with override_mcp_user(no_perm_ctx):
            result = await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "Should Fail"},
            )
            data = json.loads(result[0][0].text)
            assert "error" in data
            assert "Permission denied" in data["error"]
            assert "iso_docs:edit" in data["error"]
