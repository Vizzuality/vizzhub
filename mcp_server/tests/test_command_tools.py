"""Integration tests -- MCP write tools + command queue."""

from __future__ import annotations

import json
from datetime import date

import pytest
import pytest_asyncio
from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.iso_docs.models import (
    IsoDocMetadataDB,
    IsoDocNodeDB,
    IsoDocVersionDB,
    RegistryTypeDB,
)
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
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
async def test_iso_update_page_metadata_changelog_missing_version(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    """Changelog entries without a version must be rejected before queuing."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            with pytest.raises(ToolError, match="version"):
                await mcp.call_tool(
                    "iso_update_page_metadata",
                    {
                        "slug": "security-policy",
                        "changelog": [
                            {
                                "date": "2026-04-13",
                                "author": "Editor User",
                                "description": "Initial draft",
                            },
                        ],
                    },
                )


@pytest.mark.asyncio
async def test_iso_update_page_metadata_changelog_valid(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    """Changelog entries with all four required fields are queued successfully."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "iso_update_page_metadata",
                {
                    "slug": "security-policy",
                    "changelog": [
                        {
                            "version": "1.0",
                            "date": "2026-04-13",
                            "author": "Editor User",
                            "description": "Initial draft",
                        },
                    ],
                },
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "queued"
            assert "command_id" in data


@pytest.mark.asyncio
async def test_iso_update_page_metadata_classification_invalid_rejected_at_queue_time(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    """`internal` is not a valid classification (the enum is `internal_use`)."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            with pytest.raises(ToolError):
                await mcp.call_tool(
                    "iso_update_page_metadata",
                    {"slug": "security-policy", "classification": "internal"},
                )


@pytest.mark.asyncio
async def test_iso_update_page_metadata_status_invalid_rejected_at_queue_time(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    """`obsolete` is not a real status; only draft/approved/under_review exist."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            with pytest.raises(ToolError):
                await mcp.call_tool(
                    "iso_update_page_metadata",
                    {"slug": "security-policy", "status": "obsolete"},
                )


@pytest.mark.asyncio
async def test_iso_update_page_metadata_document_date_invalid_format_rejected(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    """Malformed date string fails at queue time, not at approve."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            with pytest.raises(ToolError):
                await mcp.call_tool(
                    "iso_update_page_metadata",
                    {"slug": "security-policy", "document_date": "not-a-date"},
                )


@pytest.mark.asyncio
async def test_iso_update_page_metadata_document_date_iso_string_round_trip(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    """ISO date string travels through the JSONB queue and lands as a Date in DB."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "iso_update_page_metadata",
                {"slug": "security-policy", "document_date": "2026-04-27"},
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "queued"

            approve_result = await mcp.call_tool(
                "approve_command",
                {"command_id": data["command_id"]},
            )
            approve_data = json.loads(approve_result[0][0].text)
            assert approve_data["status"] == "executed"

    meta_row = await db_session.execute(
        select(IsoDocMetadataDB).where(
            IsoDocMetadataDB.node_id == seeded_iso["page"].id
        )
    )
    meta = meta_row.scalar_one()
    assert meta.document_date == date(2026, 4, 27)


@pytest.mark.asyncio
async def test_iso_patch_page_content_enqueue_and_approve(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    """Patch applies search-replace operations and creates a new version."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "iso_patch_page_content",
                {
                    "slug": "security-policy",
                    "operations": [
                        {
                            "search": "Initial content.",
                            "replace": "Updated content with patches.",
                            "description": "update intro paragraph",
                        },
                    ],
                },
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "queued"
            assert "command_id" in data
            assert "Patch" in data["summary"]
            assert "Security Policy" in data["summary"]

            approve_result = await mcp.call_tool(
                "approve_command",
                {"command_id": data["command_id"]},
            )
            approve_data = json.loads(approve_result[0][0].text)
            assert approve_data["status"] == "executed"
            assert approve_data["result"]["version"] == 2
            assert approve_data["result"]["operations_applied"] == 1


@pytest.mark.asyncio
async def test_iso_patch_page_content_search_not_found(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    """Patch fails at execution if search text is not found."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "iso_patch_page_content",
                {
                    "slug": "security-policy",
                    "operations": [
                        {
                            "search": "text that does not exist",
                            "replace": "replacement",
                        },
                    ],
                },
            )
            data = json.loads(result[0][0].text)
            command_id = data["command_id"]

            approve_result = await mcp.call_tool(
                "approve_command",
                {"command_id": command_id},
            )
            approve_data = json.loads(approve_result[0][0].text)
            assert approve_data["status"] == "failed"
            assert "not found" in approve_data["error"]


@pytest_asyncio.fixture
async def page_with_duplicate_text(
    db_session: AsyncSession, seeded_iso: dict, editor_user: UserDB,
) -> dict:
    """Add a version with duplicate text for ambiguous match testing."""
    page = seeded_iso["page"]
    version = IsoDocVersionDB(
        node_id=page.id,
        content="# Security Policy\n\nRule one.\n\nRule one.",
        version=2,
        created_by_id=editor_user.id,
    )
    db_session.add(version)
    await db_session.flush()
    return seeded_iso


@pytest.mark.asyncio
async def test_iso_patch_page_content_ambiguous_match(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    page_with_duplicate_text: dict,
) -> None:
    """Patch fails at execution if search text matches more than once."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "iso_patch_page_content",
                {
                    "slug": "security-policy",
                    "operations": [
                        {"search": "Rule one.", "replace": "Rule two."},
                    ],
                },
            )
            data = json.loads(result[0][0].text)

            approve_result = await mcp.call_tool(
                "approve_command",
                {"command_id": data["command_id"]},
            )
            approve_data = json.loads(approve_result[0][0].text)
            assert approve_data["status"] == "failed"
            assert "found 2 times" in approve_data["error"]


@pytest.mark.asyncio
async def test_iso_patch_page_content_multiple_operations(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    """Multiple patch operations are applied sequentially."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "iso_patch_page_content",
                {
                    "slug": "security-policy",
                    "operations": [
                        {
                            "search": "# Security Policy",
                            "replace": "# Security Policy v2",
                        },
                        {
                            "search": "Initial content.",
                            "replace": "Revised content.",
                        },
                    ],
                },
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "queued"

            approve_result = await mcp.call_tool(
                "approve_command",
                {"command_id": data["command_id"]},
            )
            approve_data = json.loads(approve_result[0][0].text)
            assert approve_data["status"] == "executed"
            assert approve_data["result"]["version"] == 2
            assert approve_data["result"]["operations_applied"] == 2


@pytest.mark.asyncio
async def test_iso_patch_page_content_empty_search_rejected(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    """Empty search string is rejected by Pydantic validation."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            with pytest.raises(ToolError, match="search"):
                await mcp.call_tool(
                    "iso_patch_page_content",
                    {
                        "slug": "security-policy",
                        "operations": [
                            {"search": "", "replace": "something"},
                        ],
                    },
                )


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
async def test_approve_all_executes_every_pending_command(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    """approve_all iterates pending commands and executes each."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "Page A"},
            )
            await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "Page B"},
            )
            await mcp.call_tool(
                "iso_create_registry_row",
                {
                    "slug": "incident-register",
                    "data": {"number": 1, "severity": "low"},
                },
            )

            result = await mcp.call_tool("approve_all", {})
            data = json.loads(result[0][0].text)
            assert data["total"] == 3
            assert data["executed"] == 3
            assert data["failed"] == 0
            assert data["permission_denied"] == 0
            assert len(data["results"]) == 3
            assert {r["status"] for r in data["results"]} == {"executed"}

            pending = await mcp.call_tool("get_pending_commands", {})
            assert json.loads(pending[0][0].text) == []


@pytest.mark.asyncio
async def test_approve_all_reports_failures_and_continues(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    """A failing executor marks one command failed but others still run."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            await mcp.call_tool(
                "iso_patch_page_content",
                {
                    "slug": "security-policy",
                    "operations": [
                        {"search": "does not exist", "replace": "x"},
                    ],
                },
            )
            await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "Valid Page"},
            )

            result = await mcp.call_tool("approve_all", {})
            data = json.loads(result[0][0].text)
            assert data["total"] == 2
            assert data["executed"] == 1
            assert data["failed"] == 1
            statuses = {r["status"] for r in data["results"]}
            assert statuses == {"executed", "failed"}


@pytest.mark.asyncio
async def test_approve_all_with_module_filter(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
    seeded_playbook: dict,
) -> None:
    """module filter approves only matching commands, leaves others pending."""
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            await mcp.call_tool(
                "iso_create_page",
                {"parent_slug": "policies", "title": "ISO Page"},
            )
            await mcp.call_tool(
                "playbook_create_article",
                {"parent_slug": "guides", "title": "Playbook Article"},
            )

            result = await mcp.call_tool("approve_all", {"module": "iso_docs"})
            data = json.loads(result[0][0].text)
            assert data["total"] == 1
            assert data["executed"] == 1

            pending = await mcp.call_tool("get_pending_commands", {})
            pending_data = json.loads(pending[0][0].text)
            assert len(pending_data) == 1
            assert pending_data[0]["module"] == "playbook"


@pytest.mark.asyncio
async def test_approve_all_empty_queue(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_iso: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool("approve_all", {})
            data = json.loads(result[0][0].text)
            assert data["total"] == 0
            assert data["executed"] == 0
            assert data["results"] == []


@pytest_asyncio.fixture
async def seeded_playbook(db_session: AsyncSession, editor_user: UserDB) -> dict:
    """Create group + article + page version for playbook tests."""
    group = PlaybookNodeDB(
        title="Guides",
        slug="guides",
        type="group",
        position=0,
        created_by_id=editor_user.id,
    )
    db_session.add(group)
    await db_session.flush()
    await db_session.refresh(group)

    article = PlaybookNodeDB(
        title="Onboarding",
        slug="onboarding",
        type="page",
        parent_id=group.id,
        position=0,
        created_by_id=editor_user.id,
    )
    db_session.add(article)
    await db_session.flush()
    await db_session.refresh(article)

    version = PlaybookPageVersionDB(
        node_id=article.id,
        content="# Onboarding\n\nWelcome to the team.",
        version=1,
        created_by_id=editor_user.id,
    )
    db_session.add(version)
    await db_session.flush()

    return {"group": group, "article": article, "version": version}


@pytest.mark.asyncio
async def test_playbook_create_article_enqueue_and_approve(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_playbook: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "playbook_create_article",
                {"parent_slug": "guides", "title": "Dev Setup"},
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "queued"
            assert "command_id" in data
            assert "Dev Setup" in data["summary"]

            approve_result = await mcp.call_tool(
                "approve_command",
                {"command_id": data["command_id"]},
            )
            approve_data = json.loads(approve_result[0][0].text)
            assert approve_data["status"] == "executed"
            assert approve_data["result"]["slug"] == "dev-setup"
            assert approve_data["result"]["title"] == "Dev Setup"


@pytest.mark.asyncio
async def test_playbook_update_article_content(
    db_session: AsyncSession,
    editor_ctx: McpUserContext,
    seeded_playbook: dict,
) -> None:
    async with override_session(db_session):
        async with override_mcp_user(editor_ctx):
            result = await mcp.call_tool(
                "playbook_update_article_content",
                {
                    "slug": "onboarding",
                    "content": "# Onboarding\n\nUpdated content.",
                },
            )
            data = json.loads(result[0][0].text)
            assert data["status"] == "queued"

            approve_result = await mcp.call_tool(
                "approve_command",
                {"command_id": data["command_id"]},
            )
            approve_data = json.loads(approve_result[0][0].text)
            assert approve_data["status"] == "executed"
            assert approve_data["result"]["version"] == 2


@pytest.mark.asyncio
async def test_permission_denied_for_write_tool(
    db_session: AsyncSession,
    seeded_iso: dict,
) -> None:
    from mcp.server.fastmcp.exceptions import ToolError

    no_perm_ctx = McpUserContext(
        user_id="no-perm-user",
        email="viewer@vizzuality.com",
        roles=["user"],
        permissions=["tracker:view"],
    )
    async with override_session(db_session):
        async with override_mcp_user(no_perm_ctx):
            with pytest.raises(ToolError, match="requires iso_docs:edit"):
                await mcp.call_tool(
                    "iso_create_page",
                    {"parent_slug": "policies", "title": "Should Fail"},
                )
