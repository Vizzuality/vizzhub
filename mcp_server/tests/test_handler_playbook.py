"""Tests for Playbook command handler."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from mcp_server.handlers.playbook import execute


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        email="playbook-test@vizzuality.com",
        name="Playbook Tester",
        first_name="Playbook",
        last_name="Tester",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def playbook_tree(db_session: AsyncSession, test_user: UserDB) -> dict:
    """Create Getting Started group -> Onboarding page + version."""
    group = PlaybookNodeDB(
        title="Getting Started",
        slug="getting-started",
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
        content="# Onboarding\n\nWelcome to the team.",
        version=1,
        created_by_id=test_user.id,
    )
    db_session.add(version)
    await db_session.flush()

    return {"group": group, "page": page}


@pytest.mark.asyncio
async def test_create_article(
    db_session: AsyncSession, test_user: UserDB, playbook_tree: dict,
) -> None:
    result = await execute(
        "create_article", "getting-started", {"title": "First Steps"},
        test_user.id, db_session,
    )

    assert result["title"] == "First Steps"
    assert result["slug"] == "first-steps"
    assert result["node_id"]

    node_result = await db_session.execute(
        select(PlaybookNodeDB).where(PlaybookNodeDB.slug == "first-steps")
    )
    node = node_result.scalar_one()
    assert node.parent_id == playbook_tree["group"].id
    assert node.type == "page"


@pytest.mark.asyncio
async def test_update_article_content(
    db_session: AsyncSession, test_user: UserDB, playbook_tree: dict,
) -> None:
    result = await execute(
        "update_article_content",
        "onboarding",
        {"content": "# Onboarding\n\nUpdated welcome guide."},
        test_user.id,
        db_session,
    )

    assert result["version"] == 2
    assert result["conflict"] is False

    ver_result = await db_session.execute(
        select(PlaybookPageVersionDB)
        .where(
            PlaybookPageVersionDB.node_id == playbook_tree["page"].id,
            PlaybookPageVersionDB.version == 2,
        )
    )
    ver = ver_result.scalar_one()
    assert "Updated welcome guide" in ver.content


@pytest.mark.asyncio
async def test_update_node_title(
    db_session: AsyncSession, test_user: UserDB, playbook_tree: dict,
) -> None:
    result = await execute(
        "update_node",
        "onboarding",
        {"title": "New Hire Onboarding"},
        test_user.id,
        db_session,
    )

    assert result["title"] == "New Hire Onboarding"
    assert result["slug"] == "new-hire-onboarding"
    assert result["node_id"] == str(playbook_tree["page"].id)


@pytest.mark.asyncio
async def test_delete_leaf_node(
    db_session: AsyncSession, test_user: UserDB, playbook_tree: dict,
) -> None:
    result = await execute(
        "delete_node", "onboarding", {}, test_user.id, db_session,
    )

    assert result["ok"] is True

    check = await db_session.execute(
        select(PlaybookNodeDB).where(PlaybookNodeDB.slug == "onboarding")
    )
    assert check.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_node_with_children_rejected(
    db_session: AsyncSession, test_user: UserDB, playbook_tree: dict,
) -> None:
    with pytest.raises(ValueError, match="has children"):
        await execute(
            "delete_node", "getting-started", {}, test_user.id, db_session,
        )


@pytest.mark.asyncio
async def test_unknown_action_raises(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    with pytest.raises(ValueError, match="Unknown playbook action"):
        await execute(
            "nonexistent_action", None, {}, test_user.id, db_session,
        )
