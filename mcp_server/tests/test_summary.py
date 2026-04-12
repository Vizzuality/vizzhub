"""Tests for human-readable summary generation."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.models.registry_type import RegistryTypeDB
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from mcp_server.services.summary import generate_summary


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        email="summary-test@vizzuality.com",
        name="Summary Tester",
        first_name="Summary",
        last_name="Tester",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def iso_tree(db_session: AsyncSession, test_user: UserDB) -> dict:
    """Create Policies group -> Security Policy page + metadata + version."""
    group = IsoDocNodeDB(
        title="Policies",
        slug="policies",
        type="group",
        position=0,
        created_by_id=test_user.id,
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
        created_by_id=test_user.id,
    )
    db_session.add(page)
    await db_session.flush()
    await db_session.refresh(page)

    meta = IsoDocMetadataDB(node_id=page.id, code="POL-001", status="draft")
    db_session.add(meta)
    await db_session.flush()

    version = IsoDocVersionDB(
        node_id=page.id,
        content="# Security Policy\n\nInitial content.",
        version=1,
        created_by_id=test_user.id,
    )
    db_session.add(version)
    await db_session.flush()

    return {"group": group, "page": page, "meta": meta}


@pytest_asyncio.fixture
async def registry_setup(
    db_session: AsyncSession, test_user: UserDB,
) -> dict:
    """Create Incident Register type + registry node + sample row."""
    rt = RegistryTypeDB(
        name="Incident Register",
        slug="incident-register",
        is_yearly=False,
        schema=[
            {"key": "number", "label": "Number", "type": "number"},
            {"key": "severity", "label": "Severity", "type": "select"},
        ],
    )
    db_session.add(rt)
    await db_session.flush()
    await db_session.refresh(rt)

    node = IsoDocNodeDB(
        title="Incident Register",
        slug="incident-register",
        type="registry",
        position=0,
        registry_type_id=rt.id,
        created_by_id=test_user.id,
    )
    db_session.add(node)
    await db_session.flush()
    await db_session.refresh(node)

    row = RegistryRowDB(
        node_id=node.id,
        row_index=0,
        data={"number": 1, "severity": "low"},
        created_by_id=test_user.id,
    )
    db_session.add(row)
    await db_session.flush()
    await db_session.refresh(row)

    return {"rt": rt, "node": node, "row": row}


# ---------------------------------------------------------------------------
# ISO Docs summaries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_create_page(
    db_session: AsyncSession, iso_tree: dict,
) -> None:
    summary = await generate_summary(
        db_session,
        module="iso_docs",
        action="create_page",
        target="policies",
        payload={"title": "Data Retention Policy"},
    )
    assert "Data Retention Policy" in summary
    assert "Policies" in summary
    assert summary == "Create page **Data Retention Policy** in Policies"


@pytest.mark.asyncio
async def test_summary_update_page_content(
    db_session: AsyncSession, iso_tree: dict,
) -> None:
    summary = await generate_summary(
        db_session,
        module="iso_docs",
        action="update_page_content",
        target="security-policy",
        payload={"content": "# Security Policy\n\nUpdated."},
    )
    assert "Security Policy" in summary
    assert "v1" in summary
    assert "v2" in summary
    assert summary == "Update content of **Security Policy** (v1 \u2192 v2)"


@pytest.mark.asyncio
async def test_summary_update_metadata_diff(
    db_session: AsyncSession, iso_tree: dict,
) -> None:
    summary = await generate_summary(
        db_session,
        module="iso_docs",
        action="update_metadata",
        target="security-policy",
        payload={"status": "approved", "code": "POL-002"},
    )
    assert "Security Policy" in summary
    assert "status" in summary
    assert "code" in summary


@pytest.mark.asyncio
async def test_summary_update_metadata_truncates_fields(
    db_session: AsyncSession, iso_tree: dict,
) -> None:
    summary = await generate_summary(
        db_session,
        module="iso_docs",
        action="update_metadata",
        target="security-policy",
        payload={
            "status": "approved",
            "code": "POL-002",
            "classification": "confidential",
            "guidance": "Updated guidance",
        },
    )
    assert "+1 more" in summary


@pytest.mark.asyncio
async def test_summary_delete_node(
    db_session: AsyncSession, iso_tree: dict,
) -> None:
    summary = await generate_summary(
        db_session,
        module="iso_docs",
        action="delete_node",
        target="security-policy",
        payload={},
    )
    assert "Delete" in summary
    assert "Security Policy" in summary
    assert summary == "Delete **Security Policy**"


@pytest.mark.asyncio
async def test_summary_update_node_rename(
    db_session: AsyncSession, iso_tree: dict,
) -> None:
    summary = await generate_summary(
        db_session,
        module="iso_docs",
        action="update_node",
        target="security-policy",
        payload={"title": "Information Security Policy"},
    )
    assert "Rename" in summary
    assert "Security Policy" in summary
    assert "Information Security Policy" in summary


@pytest.mark.asyncio
async def test_summary_update_node_move(
    db_session: AsyncSession, iso_tree: dict, test_user: UserDB,
) -> None:
    standards = IsoDocNodeDB(
        title="Standards",
        slug="standards",
        type="group",
        position=1,
        created_by_id=test_user.id,
    )
    db_session.add(standards)
    await db_session.flush()

    summary = await generate_summary(
        db_session,
        module="iso_docs",
        action="update_node",
        target="security-policy",
        payload={"parent_slug": "standards"},
    )
    assert "Move" in summary
    assert "Standards" in summary


# ---------------------------------------------------------------------------
# Registry summaries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_create_registry_row(
    db_session: AsyncSession, registry_setup: dict,
) -> None:
    summary = await generate_summary(
        db_session,
        module="iso_docs",
        action="create_registry_row",
        target="incident-register",
        payload={"data": {"number": 2, "severity": "high"}},
    )
    assert "Incident Register" in summary
    assert "number=2" in summary
    assert "severity=high" in summary
    assert summary.startswith("Create row in **Incident Register**")


@pytest.mark.asyncio
async def test_summary_update_registry_row_uses_labels(
    db_session: AsyncSession, registry_setup: dict,
) -> None:
    summary = await generate_summary(
        db_session,
        module="iso_docs",
        action="update_registry_row",
        target="incident-register",
        payload={
            "row_id": str(registry_setup["row"].id),
            "data": {"severity": "medium"},
        },
    )
    assert "Incident Register" in summary
    assert "severity" in summary
    assert summary.startswith("Update row in **Incident Register**")


@pytest.mark.asyncio
async def test_summary_delete_registry_row(
    db_session: AsyncSession, registry_setup: dict,
) -> None:
    summary = await generate_summary(
        db_session,
        module="iso_docs",
        action="delete_registry_row",
        target="incident-register",
        payload={"row_id": str(registry_setup["row"].id)},
    )
    assert summary == "Delete row from **Incident Register**"


# ---------------------------------------------------------------------------
# Playbook summaries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_playbook_create(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    group = PlaybookNodeDB(
        title="Getting Started",
        slug="getting-started",
        type="group",
        position=0,
        created_by_id=test_user.id,
    )
    db_session.add(group)
    await db_session.flush()

    summary = await generate_summary(
        db_session,
        module="playbook",
        action="create_article",
        target="getting-started",
        payload={"title": "First Steps"},
    )
    assert "First Steps" in summary
    assert "Getting Started" in summary
    assert summary == "Create article **First Steps** in Getting Started"


@pytest.mark.asyncio
async def test_summary_playbook_update_content(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    group = PlaybookNodeDB(
        title="Guides",
        slug="guides",
        type="group",
        position=0,
        created_by_id=test_user.id,
    )
    db_session.add(group)
    await db_session.flush()
    await db_session.refresh(group)

    page = PlaybookNodeDB(
        title="Onboarding",
        slug="onboarding",
        type="page",
        parent_id=group.id,
        position=0,
        created_by_id=test_user.id,
    )
    db_session.add(page)
    await db_session.flush()
    await db_session.refresh(page)

    version = PlaybookPageVersionDB(
        node_id=page.id,
        content="# Onboarding\n\nWelcome.",
        version=1,
        created_by_id=test_user.id,
    )
    db_session.add(version)
    await db_session.flush()

    summary = await generate_summary(
        db_session,
        module="playbook",
        action="update_article_content",
        target="onboarding",
        payload={"content": "# Onboarding\n\nUpdated."},
    )
    assert "Onboarding" in summary
    assert "v1" in summary
    assert "v2" in summary


@pytest.mark.asyncio
async def test_summary_playbook_delete(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    page = PlaybookNodeDB(
        title="Old Guide",
        slug="old-guide",
        type="page",
        position=0,
        created_by_id=test_user.id,
    )
    db_session.add(page)
    await db_session.flush()

    summary = await generate_summary(
        db_session,
        module="playbook",
        action="delete_node",
        target="old-guide",
        payload={},
    )
    assert summary == "Delete **Old Guide**"


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_unknown_action_fallback(
    db_session: AsyncSession,
) -> None:
    summary = await generate_summary(
        db_session,
        module="iso_docs",
        action="some_future_action",
        target="target-slug",
        payload={},
    )
    assert summary == "some_future_action on target-slug"


@pytest.mark.asyncio
async def test_summary_unknown_action_no_target(
    db_session: AsyncSession,
) -> None:
    summary = await generate_summary(
        db_session,
        module="tracker",
        action="update_budget",
        target=None,
        payload={},
    )
    assert summary == "update_budget on tracker"
