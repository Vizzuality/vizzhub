"""Tests for ISO docs command handler."""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.models.registry_type import RegistryTypeDB
from mcp_server.handlers.iso_docs import execute


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        email="handler-test@vizzuality.com",
        name="Handler Tester",
        first_name="Handler",
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
            {"key": "severity", "label": "Severity", "type": "select", "options": ["low", "medium", "high"]},
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


@pytest.mark.asyncio
async def test_create_page(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    result = await execute(
        "create_page", "policies", {"title": "Access Control"},
        test_user.id, db_session,
    )

    assert result["title"] == "Access Control"
    assert result["slug"] == "access-control"
    assert result["node_id"]

    node_result = await db_session.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.slug == "access-control")
    )
    node = node_result.scalar_one()
    assert node.parent_id == iso_tree["group"].id
    assert node.type == "page"


@pytest.mark.asyncio
async def test_update_page_content(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    result = await execute(
        "update_page_content",
        "security-policy",
        {"content": "# Security Policy\n\nUpdated content."},
        test_user.id,
        db_session,
    )

    assert result["version"] == 2
    assert result["conflict"] is False

    ver_result = await db_session.execute(
        select(IsoDocVersionDB)
        .where(
            IsoDocVersionDB.node_id == iso_tree["page"].id,
            IsoDocVersionDB.version == 2,
        )
    )
    ver = ver_result.scalar_one()
    assert "Updated content" in ver.content


@pytest.mark.asyncio
async def test_update_metadata(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    result = await execute(
        "update_metadata",
        "security-policy",
        {"status": "approved", "code": "POL-002"},
        test_user.id,
        db_session,
    )

    assert result["status"] == "approved"
    assert result["code"] == "POL-002"

    meta_result = await db_session.execute(
        select(IsoDocMetadataDB).where(
            IsoDocMetadataDB.node_id == iso_tree["page"].id
        )
    )
    meta = meta_result.scalar_one()
    assert meta.status == "approved"
    assert meta.code == "POL-002"


@pytest.mark.asyncio
async def test_update_node_title(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    result = await execute(
        "update_node",
        "security-policy",
        {"title": "Information Security Policy"},
        test_user.id,
        db_session,
    )

    assert result["title"] == "Information Security Policy"
    assert result["slug"] == "information-security-policy"
    assert result["node_id"] == str(iso_tree["page"].id)


@pytest.mark.asyncio
async def test_update_node_move(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    new_group = IsoDocNodeDB(
        title="Standards",
        slug="standards",
        type="group",
        position=1,
        created_by_id=test_user.id,
    )
    db_session.add(new_group)
    await db_session.flush()
    await db_session.refresh(new_group)

    result = await execute(
        "update_node",
        "security-policy",
        {"parent_slug": "standards"},
        test_user.id,
        db_session,
    )

    assert result["parent_id"] == str(new_group.id)


@pytest.mark.asyncio
async def test_delete_leaf_node(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    result = await execute(
        "delete_node", "security-policy", {}, test_user.id, db_session,
    )

    assert result["ok"] is True

    check = await db_session.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.slug == "security-policy")
    )
    assert check.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_node_with_children_rejected(
    db_session: AsyncSession, test_user: UserDB, iso_tree: dict,
) -> None:
    with pytest.raises(ValueError, match="has children"):
        await execute(
            "delete_node", "policies", {}, test_user.id, db_session,
        )


@pytest.mark.asyncio
async def test_create_registry_row(
    db_session: AsyncSession,
    test_user: UserDB,
    registry_setup: dict,
) -> None:
    result = await execute(
        "create_registry_row",
        "incident-register",
        {"data": {"number": 2, "severity": "high"}},
        test_user.id,
        db_session,
    )

    assert result["row_id"]
    assert result["data"]["number"] == 2
    assert result["data"]["severity"] == "high"


@pytest.mark.asyncio
async def test_update_registry_row(
    db_session: AsyncSession,
    test_user: UserDB,
    registry_setup: dict,
) -> None:
    row = registry_setup["row"]
    result = await execute(
        "update_registry_row",
        "incident-register",
        {"row_id": str(row.id), "data": {"severity": "medium"}},
        test_user.id,
        db_session,
    )

    assert result["data"]["severity"] == "medium"
    assert result["data"]["number"] == 1


@pytest.mark.asyncio
async def test_delete_registry_row(
    db_session: AsyncSession,
    test_user: UserDB,
    registry_setup: dict,
) -> None:
    row = registry_setup["row"]
    result = await execute(
        "delete_registry_row",
        "incident-register",
        {"row_id": str(row.id)},
        test_user.id,
        db_session,
    )

    assert result["ok"] is True

    check = await db_session.execute(
        select(RegistryRowDB).where(RegistryRowDB.id == row.id)
    )
    assert check.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_unknown_action_raises(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    with pytest.raises(ValueError, match="Unknown ISO docs action"):
        await execute(
            "nonexistent_action", None, {}, test_user.id, db_session,
        )
