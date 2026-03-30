"""Tests for ISO docs metadata API."""

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


@pytest.mark.asyncio
async def test_get_metadata_not_found(client: AsyncClient, page_node: dict):
    response = await client.get(
        f"/api/iso-docs/pages/{page_node['id']}/metadata"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_metadata(client: AsyncClient, page_node: dict):
    node_id = page_node["id"]

    response = await client.put(
        f"/api/iso-docs/pages/{node_id}/metadata",
        json={
            "code": "POL04",
            "standard": ["ISO 27001:2022"],
            "clauses": ["A.5.15", "A.5.18"],
            "category": "policy",
            "doc_version": "1.1",
            "status": "approved",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "POL04"
    assert data["standard"] == ["ISO 27001:2022"]
    assert data["clauses"] == ["A.5.15", "A.5.18"]
    assert data["category"] == "policy"
    assert data["status"] == "approved"
    assert data["doc_version"] == "1.1"


@pytest.mark.asyncio
async def test_update_metadata(client: AsyncClient, page_node: dict):
    node_id = page_node["id"]

    await client.put(
        f"/api/iso-docs/pages/{node_id}/metadata",
        json={"code": "POL04", "status": "draft"},
    )

    response = await client.put(
        f"/api/iso-docs/pages/{node_id}/metadata",
        json={"status": "approved"},
    )
    assert response.json()["status"] == "approved"
    assert response.json()["code"] == "POL04"


@pytest.mark.asyncio
async def test_metadata_with_changelog(client: AsyncClient, page_node: dict):
    node_id = page_node["id"]

    response = await client.put(
        f"/api/iso-docs/pages/{node_id}/metadata",
        json={
            "changelog": [
                {
                    "version": "1.0",
                    "date": "2024-09-02",
                    "author": "ISMS Manager",
                    "description": "Initial release",
                },
                {
                    "version": "1.1",
                    "date": "2025-01-30",
                    "author": "Miguel Mendoza",
                    "description": "Review",
                },
            ],
        },
    )
    assert response.status_code == 200
    changelog = response.json()["changelog"]
    assert len(changelog) == 2
    assert changelog[0]["version"] == "1.0"


@pytest.mark.asyncio
async def test_search_by_category(client: AsyncClient):
    p1 = await client.post(
        "/api/iso-docs/nodes", json={"title": "Policy A", "type": "page"}
    )
    p2 = await client.post(
        "/api/iso-docs/nodes", json={"title": "Procedure B", "type": "page"}
    )

    await client.put(
        f"/api/iso-docs/pages/{p1.json()['id']}/metadata",
        json={"category": "policy"},
    )
    await client.put(
        f"/api/iso-docs/pages/{p2.json()['id']}/metadata",
        json={"category": "procedure"},
    )

    response = await client.get("/api/iso-docs/metadata/search?category=policy")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["title"] == "Policy A"


@pytest.mark.asyncio
async def test_search_by_standard(client: AsyncClient):
    p1 = await client.post(
        "/api/iso-docs/nodes", json={"title": "Doc 27001", "type": "page"}
    )
    await client.put(
        f"/api/iso-docs/pages/{p1.json()['id']}/metadata",
        json={"standard": ["ISO 27001:2022"]},
    )

    response = await client.get(
        "/api/iso-docs/metadata/search?standard=ISO 27001:2022"
    )
    results = response.json()
    assert len(results) == 1
    assert results[0]["title"] == "Doc 27001"


@pytest.mark.asyncio
async def test_search_by_clause(client: AsyncClient):
    p1 = await client.post(
        "/api/iso-docs/nodes", json={"title": "Doc A515", "type": "page"}
    )
    await client.put(
        f"/api/iso-docs/pages/{p1.json()['id']}/metadata",
        json={"clauses": ["A.5.15", "A.5.18"]},
    )

    response = await client.get("/api/iso-docs/metadata/search?clause=A.5.15")
    results = response.json()
    assert len(results) == 1
    assert results[0]["title"] == "Doc A515"
