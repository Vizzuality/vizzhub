"""Tests for ISO docs pages and versions API."""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def page_node(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Test Page", "type": "page"},
    )
    return response.json()


@pytest.mark.asyncio
async def test_get_page_empty(client: AsyncClient, page_node: dict):
    response = await client.get(f"/api/iso-docs/pages/{page_node['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == ""
    assert data["version"] == 0


@pytest.mark.asyncio
async def test_save_and_get_page(client: AsyncClient, page_node: dict):
    node_id = page_node["id"]

    save = await client.put(
        f"/api/iso-docs/pages/{node_id}",
        json={"content": "# Hello\n\nWorld", "expected_version": 0},
    )
    assert save.status_code == 200
    assert save.json()["version"] == 1
    assert save.json()["conflict"] is False

    get = await client.get(f"/api/iso-docs/pages/{node_id}")
    assert get.json()["content"] == "# Hello\n\nWorld"
    assert get.json()["version"] == 1


@pytest.mark.asyncio
async def test_save_detects_conflict(client: AsyncClient, page_node: dict):
    node_id = page_node["id"]

    await client.put(
        f"/api/iso-docs/pages/{node_id}",
        json={"content": "v1", "expected_version": 0},
    )
    await client.put(
        f"/api/iso-docs/pages/{node_id}",
        json={"content": "v2", "expected_version": 1},
    )

    save = await client.put(
        f"/api/iso-docs/pages/{node_id}",
        json={"content": "v3 from stale client", "expected_version": 1},
    )
    assert save.json()["version"] == 3
    assert save.json()["conflict"] is True


@pytest.mark.asyncio
async def test_save_syncs_title_from_h1(client: AsyncClient, page_node: dict):
    node_id = page_node["id"]

    await client.put(
        f"/api/iso-docs/pages/{node_id}",
        json={"content": "# Updated Title\n\nContent", "expected_version": 0},
    )

    tree = await client.get("/api/iso-docs/tree")
    titles = [n["title"] for n in tree.json()]
    assert "Updated Title" in titles


@pytest.mark.asyncio
async def test_list_versions(client: AsyncClient, page_node: dict):
    node_id = page_node["id"]

    await client.put(
        f"/api/iso-docs/pages/{node_id}",
        json={"content": "v1", "expected_version": 0},
    )
    await client.put(
        f"/api/iso-docs/pages/{node_id}",
        json={"content": "v2 with more lines\nline2", "expected_version": 1},
    )

    response = await client.get(f"/api/iso-docs/pages/{node_id}/versions")
    assert response.status_code == 200
    versions = response.json()
    assert len(versions) == 2
    assert versions[0]["version"] == 2
    assert versions[1]["version"] == 1


@pytest.mark.asyncio
async def test_get_specific_version(client: AsyncClient, page_node: dict):
    node_id = page_node["id"]

    await client.put(
        f"/api/iso-docs/pages/{node_id}",
        json={"content": "first", "expected_version": 0},
    )
    await client.put(
        f"/api/iso-docs/pages/{node_id}",
        json={"content": "second", "expected_version": 1},
    )

    response = await client.get(f"/api/iso-docs/pages/{node_id}/versions/1")
    assert response.status_code == 200
    assert response.json()["content"] == "first"


@pytest.mark.asyncio
async def test_get_page_rejects_group(client: AsyncClient):
    group = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Group", "type": "group"},
    )
    response = await client.get(f"/api/iso-docs/pages/{group.json()['id']}")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_search_pages_by_title(client: AsyncClient, page_node: dict):
    await client.put(
        f"/api/iso-docs/pages/{page_node['id']}",
        json={"content": "Some content", "expected_version": 0},
    )

    response = await client.get("/api/iso-docs/pages/search", params={"q": "Test Page"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert any(r["node_id"] == page_node["id"] for r in results)


@pytest.mark.asyncio
async def test_search_pages_by_content(client: AsyncClient, page_node: dict):
    await client.put(
        f"/api/iso-docs/pages/{page_node['id']}",
        json={"content": "# Title\n\nUnique keyword xylophone here", "expected_version": 0},
    )

    response = await client.get("/api/iso-docs/pages/search", params={"q": "xylophone"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["node_id"] == page_node["id"]
    assert "xylophone" in results[0]["snippet"]


@pytest.mark.asyncio
async def test_search_pages_min_length(client: AsyncClient):
    response = await client.get("/api/iso-docs/pages/search", params={"q": "a"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_search_pages_no_results(client: AsyncClient):
    response = await client.get("/api/iso-docs/pages/search", params={"q": "zznonexistent"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_search_includes_registry_nodes(client: AsyncClient):
    """Registry nodes should appear in search results by title."""
    rt = await client.post(
        "/api/iso-docs/registry-types",
        json={"name": "Search Test", "schema": [{"key": "a", "label": "A", "type": "string"}]},
    )
    node = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Zebra Registry", "type": "registry", "registry_type_id": rt.json()["id"]},
    )
    assert node.status_code == 201

    search = await client.get("/api/iso-docs/pages/search", params={"q": "Zebra"})
    assert search.status_code == 200
    results = search.json()
    assert len(results) == 1
    assert results[0]["title"] == "Zebra Registry"
