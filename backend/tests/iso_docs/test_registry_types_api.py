"""Tests for registry types API."""

import pytest
import pytest_asyncio
from httpx import AsyncClient

SAMPLE_SCHEMA = [
    {"key": "name", "label": "Name", "type": "string", "required": True},
    {"key": "count", "label": "Count", "type": "number", "required": False},
]


@pytest_asyncio.fixture
async def registry_type(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/iso-docs/registry-types",
        json={
            "name": "Test Register",
            "description": "A test register",
            "is_yearly": False,
            "schema": SAMPLE_SCHEMA,
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_create_registry_type(client: AsyncClient):
    resp = await client.post(
        "/api/iso-docs/registry-types",
        json={
            "name": "Asset Inventory",
            "schema": [{"key": "asset_id", "label": "Asset ID", "type": "string", "required": True}],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Asset Inventory"
    assert data["slug"] == "asset-inventory"
    assert len(data["schema"]) == 1


@pytest.mark.asyncio
async def test_list_registry_types(client: AsyncClient, registry_type: dict):
    resp = await client.get("/api/iso-docs/registry-types")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_registry_type(client: AsyncClient, registry_type: dict):
    resp = await client.get(f"/api/iso-docs/registry-types/{registry_type['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Register"


@pytest.mark.asyncio
async def test_get_registry_type_not_found(client: AsyncClient):
    resp = await client.get(
        "/api/iso-docs/registry-types/00000000-0000-0000-0000-000000000099"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_registry_type(client: AsyncClient, registry_type: dict):
    resp = await client.patch(
        f"/api/iso-docs/registry-types/{registry_type['id']}",
        json={"name": "Updated Register"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Register"
    assert resp.json()["slug"] == "updated-register"


@pytest.mark.asyncio
async def test_update_registry_type_renames_column_and_migrates_row_data(
    client: AsyncClient, registry_type: dict,
):
    """When a column key changes (same type, same position), existing
    registry_rows.data must be migrated so values stay reachable under
    the new key. Regression for the silent label→key rebuild bug."""
    node_resp = await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "Test Node",
            "type": "registry",
            "registry_type_id": registry_type["id"],
        },
    )
    assert node_resp.status_code == 201
    node_id = node_resp.json()["id"]

    row_resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Item A", "count": 5}},
    )
    assert row_resp.status_code == 201
    row_id = row_resp.json()["id"]

    new_schema = [
        {"key": "full_name", "label": "Full Name", "type": "string", "required": True},
        {"key": "count", "label": "Count", "type": "number", "required": False},
    ]
    resp = await client.patch(
        f"/api/iso-docs/registry-types/{registry_type['id']}",
        json={"schema": new_schema},
    )
    assert resp.status_code == 200

    rows = (await client.get(f"/api/iso-docs/registries/{node_id}/rows")).json()
    [migrated] = [r for r in rows if r["id"] == row_id]
    assert migrated["data"] == {"full_name": "Item A", "count": 5}


@pytest.mark.asyncio
async def test_update_registry_type_does_not_migrate_when_types_differ(
    client: AsyncClient, registry_type: dict,
):
    """A column whose key AND type both change is treated as remove+add,
    not rename. Avoids confusing a string column with a date column."""
    node_resp = await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "Test Node 2",
            "type": "registry",
            "registry_type_id": registry_type["id"],
        },
    )
    node_id = node_resp.json()["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Item", "count": 7}},
    )

    new_schema = [
        {"key": "started_on", "label": "Started On", "type": "date", "required": False},
        {"key": "count", "label": "Count", "type": "number", "required": False},
    ]
    resp = await client.patch(
        f"/api/iso-docs/registry-types/{registry_type['id']}",
        json={"schema": new_schema},
    )
    assert resp.status_code == 200

    rows = (await client.get(f"/api/iso-docs/registries/{node_id}/rows")).json()
    row = rows[0]
    assert "started_on" not in row["data"]
    assert "name" in row["data"]
    assert row["data"]["name"] == "Item"


@pytest.mark.asyncio
async def test_update_registry_type_name_only_does_not_touch_rows(
    client: AsyncClient, registry_type: dict,
):
    """PATCHing without a schema field must not run the rename detector."""
    node_resp = await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "Test Node 3",
            "type": "registry",
            "registry_type_id": registry_type["id"],
        },
    )
    node_id = node_resp.json()["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Stay", "count": 1}},
    )

    resp = await client.patch(
        f"/api/iso-docs/registry-types/{registry_type['id']}",
        json={"name": "Renamed Register"},
    )
    assert resp.status_code == 200

    rows = (await client.get(f"/api/iso-docs/registries/{node_id}/rows")).json()
    assert rows[0]["data"] == {"name": "Stay", "count": 1}


@pytest.mark.asyncio
async def test_delete_registry_type(client: AsyncClient, registry_type: dict):
    resp = await client.delete(
        f"/api/iso-docs/registry-types/{registry_type['id']}"
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_registry_type_in_use(client: AsyncClient, registry_type: dict):
    await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "My Registry",
            "type": "registry",
            "registry_type_id": registry_type["id"],
        },
    )
    resp = await client.delete(
        f"/api/iso-docs/registry-types/{registry_type['id']}"
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_duplicate_slug_rejected(client: AsyncClient, registry_type: dict):
    resp = await client.post(
        "/api/iso-docs/registry-types",
        json={
            "name": "Test Register",
            "schema": SAMPLE_SCHEMA,
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_schema_required(client: AsyncClient):
    resp = await client.post(
        "/api/iso-docs/registry-types",
        json={"name": "Empty Schema", "schema": []},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_column_visibility(client: AsyncClient, registry_type: dict):
    type_id = registry_type["id"]
    resp = await client.patch(
        f"/api/iso-docs/registry-types/{type_id}/column-visibility",
        json={"hidden_columns": ["count"]},
    )
    assert resp.status_code == 200
    schema = resp.json()["schema"]
    by_key = {col["key"]: col for col in schema}
    assert by_key["count"].get("hidden") is True
    assert "hidden" not in by_key["name"] or by_key["name"]["hidden"] is False


@pytest.mark.asyncio
async def test_update_column_visibility_unhide(client: AsyncClient, registry_type: dict):
    type_id = registry_type["id"]
    await client.patch(
        f"/api/iso-docs/registry-types/{type_id}/column-visibility",
        json={"hidden_columns": ["name", "count"]},
    )
    resp = await client.patch(
        f"/api/iso-docs/registry-types/{type_id}/column-visibility",
        json={"hidden_columns": []},
    )
    assert resp.status_code == 200
    schema = resp.json()["schema"]
    for col in schema:
        assert "hidden" not in col or col["hidden"] is False


@pytest.mark.asyncio
async def test_update_column_visibility_not_found(client: AsyncClient):
    resp = await client.patch(
        "/api/iso-docs/registry-types/00000000-0000-0000-0000-000000000099/column-visibility",
        json={"hidden_columns": ["name"]},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_column_visibility_ignores_unknown_keys(
    client: AsyncClient, registry_type: dict,
):
    type_id = registry_type["id"]
    resp = await client.patch(
        f"/api/iso-docs/registry-types/{type_id}/column-visibility",
        json={"hidden_columns": ["nonexistent_key"]},
    )
    assert resp.status_code == 200
    schema = resp.json()["schema"]
    for col in schema:
        assert "hidden" not in col or col["hidden"] is False
