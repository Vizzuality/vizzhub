"""Tests for ISO docs notes API."""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def page_node(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "POL04 Access Control", "type": "page"},
    )
    return response.json()


@pytest_asyncio.fixture
async def group_node(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Opportunity Register", "type": "group"},
    )
    return response.json()


@pytest.mark.asyncio
async def test_create_note(client: AsyncClient, page_node: dict):
    response = await client.post(
        f"/api/iso-docs/nodes/{page_node['id']}/notes",
        json={"content": "Auditor flagged inconsistent versions"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "Auditor flagged inconsistent versions"
    assert data["done"] is False
    assert data["node_id"] == page_node["id"]
    assert data["created_by_id"] is not None


@pytest.mark.asyncio
async def test_list_notes_for_node(client: AsyncClient, page_node: dict):
    for content in ["first", "second", "third"]:
        await client.post(
            f"/api/iso-docs/nodes/{page_node['id']}/notes",
            json={"content": content},
        )
    response = await client.get(f"/api/iso-docs/nodes/{page_node['id']}/notes")
    assert response.status_code == 200
    notes = response.json()
    assert len(notes) == 3
    contents = {n["content"] for n in notes}
    assert contents == {"first", "second", "third"}


@pytest.mark.asyncio
async def test_patch_note_content(client: AsyncClient, page_node: dict):
    created = (
        await client.post(
            f"/api/iso-docs/nodes/{page_node['id']}/notes",
            json={"content": "draft"},
        )
    ).json()
    response = await client.patch(
        f"/api/iso-docs/notes/{created['id']}",
        json={"content": "edited"},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "edited"


@pytest.mark.asyncio
async def test_patch_note_done_sets_metadata(client: AsyncClient, page_node: dict):
    created = (
        await client.post(
            f"/api/iso-docs/nodes/{page_node['id']}/notes",
            json={"content": "x"},
        )
    ).json()

    done = (
        await client.patch(
            f"/api/iso-docs/notes/{created['id']}",
            json={"done": True},
        )
    ).json()
    assert done["done"] is True
    assert done["done_at"] is not None
    assert done["done_by_id"] is not None

    reopened = (
        await client.patch(
            f"/api/iso-docs/notes/{created['id']}",
            json={"done": False},
        )
    ).json()
    assert reopened["done"] is False
    assert reopened["done_at"] is None
    assert reopened["done_by_id"] is None


@pytest.mark.asyncio
async def test_delete_note(client: AsyncClient, page_node: dict):
    created = (
        await client.post(
            f"/api/iso-docs/nodes/{page_node['id']}/notes",
            json={"content": "x"},
        )
    ).json()
    response = await client.delete(f"/api/iso-docs/notes/{created['id']}")
    assert response.status_code == 204
    listing = (await client.get(f"/api/iso-docs/nodes/{page_node['id']}/notes")).json()
    assert listing == []


@pytest.mark.asyncio
async def test_node_cascade_deletes_notes(client: AsyncClient, page_node: dict):
    await client.post(
        f"/api/iso-docs/nodes/{page_node['id']}/notes",
        json={"content": "x"},
    )
    await client.delete(f"/api/iso-docs/nodes/{page_node['id']}")
    response = await client.get(f"/api/iso-docs/nodes/{page_node['id']}/notes")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_list_default_excludes_done(
    client: AsyncClient, page_node: dict, group_node: dict
):
    pending = (
        await client.post(
            f"/api/iso-docs/nodes/{page_node['id']}/notes",
            json={"content": "pending"},
        )
    ).json()
    done_note = (
        await client.post(
            f"/api/iso-docs/nodes/{group_node['id']}/notes",
            json={"content": "done"},
        )
    ).json()
    await client.patch(f"/api/iso-docs/notes/{done_note['id']}", json={"done": True})

    response = await client.get("/api/iso-docs/notes")
    assert response.status_code == 200
    items = response.json()
    ids = {n["id"] for n in items}
    assert pending["id"] in ids
    assert done_note["id"] not in ids
    assert all("node_title" in n and "node_slug" in n for n in items)


@pytest.mark.asyncio
async def test_admin_list_include_done(client: AsyncClient, page_node: dict):
    note = (
        await client.post(
            f"/api/iso-docs/nodes/{page_node['id']}/notes",
            json={"content": "x"},
        )
    ).json()
    await client.patch(f"/api/iso-docs/notes/{note['id']}", json={"done": True})
    response = await client.get("/api/iso-docs/notes?include_done=true")
    assert response.status_code == 200
    ids = {n["id"] for n in response.json()}
    assert note["id"] in ids


@pytest.mark.asyncio
async def test_patch_404_for_unknown_note(client: AsyncClient):
    response = await client.patch(
        "/api/iso-docs/notes/00000000-0000-0000-0000-000000000000",
        json={"content": "x"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_404_for_unknown_node(client: AsyncClient):
    response = await client.post(
        "/api/iso-docs/nodes/00000000-0000-0000-0000-000000000000/notes",
        json={"content": "x"},
    )
    assert response.status_code == 404
