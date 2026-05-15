"""API-level tests for playbook node validation.

The tree_service unit tests cover `validate_depth` and `validate_not_circular`
in isolation; these tests ensure those checks are actually wired into the
HTTP layer's create/update/reorder endpoints.
"""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.playbook.models.node import PlaybookNodeDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def debug_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        id=DEBUG_USER_ID,
        email="debug@vizzuality.com",
        first_name="Debug",
        last_name="User",
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _make_chain(db_session: AsyncSession, depth: int) -> list[PlaybookNodeDB]:
    """Create a linear group chain `depth` levels deep, root first."""
    nodes: list[PlaybookNodeDB] = []
    parent_id: UUID | None = None
    for i in range(depth):
        node = PlaybookNodeDB(
            title=f"Level {i}",
            slug=f"level-{i}-{uuid4().hex[:6]}",
            type="group",
            parent_id=parent_id,
            position=0,
            created_by_id=DEBUG_USER_ID,
            updated_by_id=DEBUG_USER_ID,
        )
        db_session.add(node)
        await db_session.flush()
        await db_session.refresh(node)
        nodes.append(node)
        parent_id = node.id
    await db_session.commit()
    return nodes


@pytest.mark.asyncio
async def test_create_node_rejects_when_max_depth_exceeded(
    client: AsyncClient, db_session: AsyncSession, debug_user: UserDB,
) -> None:
    """Creating a child under a 10-deep parent fails with 400."""
    chain = await _make_chain(db_session, depth=10)
    deepest = chain[-1]

    resp = await client.post(
        "/api/playbook/nodes",
        json={"title": "Too Deep", "type": "page", "parent_id": str(deepest.id)},
    )
    assert resp.status_code == 400
    assert "depth" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_node_within_depth_succeeds(
    client: AsyncClient, db_session: AsyncSession, debug_user: UserDB,
) -> None:
    chain = await _make_chain(db_session, depth=3)
    parent = chain[-1]

    resp = await client.post(
        "/api/playbook/nodes",
        json={"title": "OK Page", "type": "page", "parent_id": str(parent.id)},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "OK Page"


@pytest.mark.asyncio
async def test_update_node_rejects_move_under_own_descendant(
    client: AsyncClient, db_session: AsyncSession, debug_user: UserDB,
) -> None:
    """Moving a node under its own descendant must 400."""
    chain = await _make_chain(db_session, depth=3)
    root, _, leaf = chain

    resp = await client.patch(
        f"/api/playbook/nodes/{root.id}",
        json={"parent_id": str(leaf.id)},
    )
    assert resp.status_code == 400
    assert "descendant" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reorder_rejects_cycle(
    client: AsyncClient, db_session: AsyncSession, debug_user: UserDB,
) -> None:
    chain = await _make_chain(db_session, depth=3)
    root, _, leaf = chain

    resp = await client.put(
        "/api/playbook/nodes/reorder",
        json={
            "items": [
                {"id": str(root.id), "parent_id": str(leaf.id), "position": 0},
            ]
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reorder_rejects_max_depth(
    client: AsyncClient, db_session: AsyncSession, debug_user: UserDB,
) -> None:
    """Attaching a node under a depth-10 chain (would make it depth 11) → 400."""
    chain = await _make_chain(db_session, depth=10)
    deepest = chain[-1]

    lone = PlaybookNodeDB(
        title="Lone",
        slug=f"lone-{uuid4().hex[:6]}",
        type="page",
        parent_id=None,
        position=0,
        created_by_id=DEBUG_USER_ID,
        updated_by_id=DEBUG_USER_ID,
    )
    db_session.add(lone)
    await db_session.commit()
    await db_session.refresh(lone)

    resp = await client.put(
        "/api/playbook/nodes/reorder",
        json={
            "items": [
                {"id": str(lone.id), "parent_id": str(deepest.id), "position": 0},
            ]
        },
    )
    assert resp.status_code == 400
    assert "depth" in resp.json()["detail"].lower()
