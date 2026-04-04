"""Tests for ISO docs nodes API."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_tree_empty(client: AsyncClient):
    response = await client.get("/api/iso-docs/tree")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_page_node(client: AsyncClient):
    response = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Access Control Policy", "type": "page"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Access Control Policy"
    assert data["slug"] == "access-control-policy"
    assert data["type"] == "page"
    assert data["parent_id"] is None


@pytest.mark.asyncio
async def test_create_group_node(client: AsyncClient):
    response = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Policies", "type": "group"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "group"
    assert data["slug"] == "policies"


@pytest.mark.asyncio
async def test_create_nested_node(client: AsyncClient):
    group = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Procedures", "type": "group"},
    )
    group_id = group.json()["id"]

    page = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "PR01", "type": "page", "parent_id": group_id},
    )
    assert page.status_code == 201
    assert page.json()["parent_id"] == group_id


@pytest.mark.asyncio
async def test_tree_structure(client: AsyncClient):
    group = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Manual", "type": "group"},
    )
    group_id = group.json()["id"]

    await client.post(
        "/api/iso-docs/nodes",
        json={"title": "IMS Manual", "type": "page", "parent_id": group_id},
    )

    response = await client.get("/api/iso-docs/tree")
    tree = response.json()
    assert len(tree) == 1
    assert tree[0]["title"] == "Manual"
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["title"] == "IMS Manual"


@pytest.mark.asyncio
async def test_update_node_title(client: AsyncClient):
    create = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Old Title", "type": "page"},
    )
    node_id = create.json()["id"]

    response = await client.patch(
        f"/api/iso-docs/nodes/{node_id}",
        json={"title": "New Title"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"
    assert response.json()["slug"] == "new-title"


@pytest.mark.asyncio
async def test_delete_node(client: AsyncClient):
    create = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "To Delete", "type": "page"},
    )
    node_id = create.json()["id"]

    response = await client.delete(f"/api/iso-docs/nodes/{node_id}")
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1


@pytest.mark.asyncio
async def test_delete_group_cascades(client: AsyncClient):
    group = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Group", "type": "group"},
    )
    group_id = group.json()["id"]

    await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Child 1", "type": "page", "parent_id": group_id},
    )
    await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Child 2", "type": "page", "parent_id": group_id},
    )

    response = await client.delete(f"/api/iso-docs/nodes/{group_id}")
    assert response.json()["deleted_count"] == 3


@pytest.mark.asyncio
async def test_reorder_nodes(client: AsyncClient):
    a = await client.post("/api/iso-docs/nodes", json={"title": "A", "type": "page"})
    b = await client.post("/api/iso-docs/nodes", json={"title": "B", "type": "page"})

    response = await client.put(
        "/api/iso-docs/nodes/reorder",
        json={
            "items": [
                {"id": b.json()["id"], "parent_id": None, "position": 0},
                {"id": a.json()["id"], "parent_id": None, "position": 1},
            ]
        },
    )
    assert response.status_code == 200

    tree = await client.get("/api/iso-docs/tree")
    titles = [n["title"] for n in tree.json()]
    # Tree always sorts alphabetically by title
    assert titles == ["A", "B"]


@pytest.mark.asyncio
async def test_duplicate_slug_gets_suffix(client: AsyncClient):
    await client.post("/api/iso-docs/nodes", json={"title": "Policy", "type": "page"})
    r2 = await client.post("/api/iso-docs/nodes", json={"title": "Policy", "type": "page"})
    assert r2.json()["slug"] == "policy-2"
