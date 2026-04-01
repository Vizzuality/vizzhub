"""Tests for registry node creation and tree integration."""

import pytest
import pytest_asyncio
from httpx import AsyncClient

SCHEMA = [{"key": "item", "label": "Item", "type": "string", "required": True}]


@pytest_asyncio.fixture
async def registry_type(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/iso-docs/registry-types",
        json={"name": "Node Test Register", "schema": SCHEMA},
    )
    return resp.json()


@pytest.mark.asyncio
async def test_create_registry_node(client: AsyncClient, registry_type: dict):
    resp = await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "My Registry",
            "type": "registry",
            "registry_type_id": registry_type["id"],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["type"] == "registry"
    assert resp.json()["registry_type_id"] == registry_type["id"]


@pytest.mark.asyncio
async def test_registry_node_requires_type_id(client: AsyncClient):
    resp = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "No Type", "type": "registry"},
    )
    assert resp.status_code == 400
    assert "registry_type_id" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_non_registry_rejects_type_id(client: AsyncClient, registry_type: dict):
    resp = await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "Page With Type",
            "type": "page",
            "registry_type_id": registry_type["id"],
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_tree_includes_registry_type_id(client: AsyncClient, registry_type: dict):
    await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "Registry In Tree",
            "type": "registry",
            "registry_type_id": registry_type["id"],
        },
    )
    resp = await client.get("/api/iso-docs/tree")
    tree = resp.json()
    registry_nodes = [n for n in tree if n["type"] == "registry"]
    assert len(registry_nodes) == 1
    assert registry_nodes[0]["registry_type_id"] == registry_type["id"]


@pytest.mark.asyncio
async def test_invalid_registry_type_id(client: AsyncClient):
    resp = await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "Bad Type",
            "type": "registry",
            "registry_type_id": "00000000-0000-0000-0000-000000000099",
        },
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower()
