"""Tests for playbook nodes API."""

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_dev_user(db_session: AsyncSession) -> None:
    """Create the dev user so FK constraints on created_by_id pass."""
    from sqlalchemy import select

    result = await db_session.execute(select(UserDB).where(UserDB.id == DEBUG_USER_ID))
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=DEBUG_USER_ID, email="dev@test.com"))
        await db_session.flush()


@pytest.mark.asyncio
async def test_get_tree_empty(client: AsyncClient):
    response = await client.get("/api/playbook/tree")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_page_node(client: AsyncClient):
    response = await client.post(
        "/api/playbook/nodes",
        json={"title": "Welcome", "type": "page"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Welcome"
    assert data["slug"] == "welcome"
    assert data["type"] == "page"
    assert data["parent_id"] is None
    assert data["is_public"] is False


@pytest.mark.asyncio
async def test_create_group_node(client: AsyncClient):
    response = await client.post(
        "/api/playbook/nodes",
        json={"title": "Getting Started", "type": "group"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "group"
    assert data["slug"] == "getting-started"


@pytest.mark.asyncio
async def test_create_nested_node(client: AsyncClient):
    group = await client.post(
        "/api/playbook/nodes",
        json={"title": "Section", "type": "group"},
    )
    group_id = group.json()["id"]

    page = await client.post(
        "/api/playbook/nodes",
        json={"title": "Page", "type": "page", "parent_id": group_id},
    )
    assert page.status_code == 201
    assert page.json()["parent_id"] == group_id


@pytest.mark.asyncio
async def test_get_tree_nested(client: AsyncClient):
    group = await client.post(
        "/api/playbook/nodes",
        json={"title": "Docs", "type": "group"},
    )
    group_id = group.json()["id"]

    await client.post(
        "/api/playbook/nodes",
        json={"title": "Intro", "type": "page", "parent_id": group_id},
    )

    response = await client.get("/api/playbook/tree")
    assert response.status_code == 200
    tree = response.json()
    assert len(tree) == 1
    assert tree[0]["title"] == "Docs"
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["title"] == "Intro"


@pytest.mark.asyncio
async def test_update_node_title(client: AsyncClient):
    create = await client.post(
        "/api/playbook/nodes",
        json={"title": "Old Title", "type": "page"},
    )
    node_id = create.json()["id"]

    response = await client.patch(
        f"/api/playbook/nodes/{node_id}",
        json={"title": "New Title"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"
    assert response.json()["slug"] == "new-title"


@pytest.mark.asyncio
async def test_update_node_is_public(client: AsyncClient):
    create = await client.post(
        "/api/playbook/nodes",
        json={"title": "Public Page", "type": "page"},
    )
    node_id = create.json()["id"]

    response = await client.patch(
        f"/api/playbook/nodes/{node_id}",
        json={"is_public": True},
    )
    assert response.status_code == 200
    assert response.json()["is_public"] is True


@pytest.mark.asyncio
async def test_delete_node(client: AsyncClient):
    create = await client.post(
        "/api/playbook/nodes",
        json={"title": "To Delete", "type": "page"},
    )
    node_id = create.json()["id"]

    response = await client.delete(f"/api/playbook/nodes/{node_id}")
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1


@pytest.mark.asyncio
async def test_delete_group_cascades(client: AsyncClient):
    group = await client.post(
        "/api/playbook/nodes",
        json={"title": "Group", "type": "group"},
    )
    group_id = group.json()["id"]

    await client.post(
        "/api/playbook/nodes",
        json={"title": "Child 1", "type": "page", "parent_id": group_id},
    )
    await client.post(
        "/api/playbook/nodes",
        json={"title": "Child 2", "type": "page", "parent_id": group_id},
    )

    response = await client.delete(f"/api/playbook/nodes/{group_id}")
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 3


@pytest.mark.asyncio
async def test_reorder_nodes(client: AsyncClient):
    a = await client.post("/api/playbook/nodes", json={"title": "A", "type": "page"})
    b = await client.post("/api/playbook/nodes", json={"title": "B", "type": "page"})
    a_id = a.json()["id"]
    b_id = b.json()["id"]

    response = await client.put(
        "/api/playbook/nodes/reorder",
        json={
            "items": [
                {"id": b_id, "parent_id": None, "position": 0},
                {"id": a_id, "parent_id": None, "position": 1},
            ]
        },
    )
    assert response.status_code == 200

    tree = await client.get("/api/playbook/tree")
    titles = [n["title"] for n in tree.json()]
    # Tree always sorts alphabetically by title
    assert titles[0] == "A"
    assert titles[1] == "B"


@pytest.mark.asyncio
async def test_create_node_exceeds_depth(client: AsyncClient):
    parent_id = None
    for i in range(10):
        resp = await client.post(
            "/api/playbook/nodes",
            json={"title": f"Level {i}", "type": "group", "parent_id": parent_id},
        )
        parent_id = resp.json()["id"]

    response = await client.post(
        "/api/playbook/nodes",
        json={"title": "Too Deep", "type": "page", "parent_id": parent_id},
    )
    assert response.status_code == 400
    assert "depth" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_duplicate_slug_gets_suffix(client: AsyncClient):
    await client.post(
        "/api/playbook/nodes",
        json={"title": "Welcome", "type": "page"},
    )
    resp = await client.post(
        "/api/playbook/nodes",
        json={"title": "Welcome", "type": "page"},
    )
    assert resp.status_code == 201
    assert resp.json()["slug"] == "welcome-2"
