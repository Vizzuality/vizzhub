"""Tests for registry rows API."""

import pytest
import pytest_asyncio
from httpx import AsyncClient

SCHEMA = [
    {"key": "name", "label": "Name", "type": "string", "required": True},
    {"key": "category", "label": "Category", "type": "select", "required": True, "options": ["A", "B", "C"]},
    {"key": "count", "label": "Count", "type": "number", "required": False},
    {"key": "active", "label": "Active", "type": "boolean", "required": False},
    {"key": "start_date", "label": "Start Date", "type": "date", "required": False},
]


@pytest_asyncio.fixture
async def registry_setup(client: AsyncClient) -> dict:
    """Create registry type + registry node."""
    rt_resp = await client.post(
        "/api/iso-docs/registry-types",
        json={"name": "Test Rows Register", "schema": SCHEMA},
    )
    rt = rt_resp.json()

    node_resp = await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "My Registry",
            "type": "registry",
            "registry_type_id": rt["id"],
        },
    )
    node = node_resp.json()
    return {"type": rt, "node": node}


@pytest_asyncio.fixture
async def yearly_setup(client: AsyncClient) -> dict:
    """Create yearly registry type + node."""
    rt_resp = await client.post(
        "/api/iso-docs/registry-types",
        json={
            "name": "Yearly Register",
            "is_yearly": True,
            "schema": [{"key": "item", "label": "Item", "type": "string", "required": True}],
        },
    )
    rt = rt_resp.json()

    node_resp = await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "Yearly Node",
            "type": "registry",
            "registry_type_id": rt["id"],
        },
    )
    node = node_resp.json()
    return {"type": rt, "node": node}


@pytest.mark.asyncio
async def test_create_row(client: AsyncClient, registry_setup: dict):
    node_id = registry_setup["node"]["id"]
    resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Item 1", "category": "A"}},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["data"]["name"] == "Item 1"
    assert data["row_index"] == 0


@pytest.mark.asyncio
async def test_create_row_validation_required(client: AsyncClient, registry_setup: dict):
    node_id = registry_setup["node"]["id"]
    resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"count": 5}},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_row_validation_select(client: AsyncClient, registry_setup: dict):
    node_id = registry_setup["node"]["id"]
    resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "X", "category": "INVALID"}},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_row_validation_unknown_field(client: AsyncClient, registry_setup: dict):
    node_id = registry_setup["node"]["id"]
    resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "X", "category": "A", "unknown_field": "val"}},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_rows(client: AsyncClient, registry_setup: dict):
    node_id = registry_setup["node"]["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Item 1", "category": "A"}},
    )
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Item 2", "category": "B"}},
    )

    resp = await client.get(f"/api/iso-docs/registries/{node_id}/rows")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 2
    assert rows[0]["row_index"] == 0
    assert rows[1]["row_index"] == 1


@pytest.mark.asyncio
async def test_update_row(client: AsyncClient, registry_setup: dict):
    node_id = registry_setup["node"]["id"]
    create_resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Original", "category": "A"}},
    )
    row_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/iso-docs/registries/{node_id}/rows/{row_id}",
        json={"data": {"name": "Updated"}},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Updated"
    assert resp.json()["data"]["category"] == "A"


@pytest.mark.asyncio
async def test_delete_row(client: AsyncClient, registry_setup: dict):
    node_id = registry_setup["node"]["id"]
    create_resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "To Delete", "category": "A"}},
    )
    row_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/iso-docs/registries/{node_id}/rows/{row_id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reorder_rows(client: AsyncClient, registry_setup: dict):
    node_id = registry_setup["node"]["id"]
    r1 = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "First", "category": "A"}},
    )
    r2 = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Second", "category": "B"}},
    )

    resp = await client.put(
        f"/api/iso-docs/registries/{node_id}/rows/reorder",
        json={"row_ids": [r2.json()["id"], r1.json()["id"]]},
    )
    assert resp.status_code == 200

    rows = (await client.get(f"/api/iso-docs/registries/{node_id}/rows")).json()
    assert rows[0]["data"]["name"] == "Second"
    assert rows[1]["data"]["name"] == "First"


@pytest.mark.asyncio
async def test_yearly_requires_year(client: AsyncClient, yearly_setup: dict):
    node_id = yearly_setup["node"]["id"]
    resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"item": "Test"}},
    )
    assert resp.status_code == 400
    assert "year" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_yearly_filter_by_year(client: AsyncClient, yearly_setup: dict):
    node_id = yearly_setup["node"]["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"year": 2025, "data": {"item": "2025 item"}},
    )
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"year": 2026, "data": {"item": "2026 item"}},
    )

    resp_2025 = await client.get(f"/api/iso-docs/registries/{node_id}/rows?year=2025")
    assert len(resp_2025.json()) == 1
    assert resp_2025.json()[0]["data"]["item"] == "2025 item"

    resp_all = await client.get(f"/api/iso-docs/registries/{node_id}/rows")
    assert len(resp_all.json()) == 2


@pytest.mark.asyncio
async def test_export_xlsx(client: AsyncClient, registry_setup: dict):
    node_id = registry_setup["node"]["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Export Test", "category": "A"}},
    )

    resp = await client.get(f"/api/iso-docs/registries/{node_id}/export")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient, registry_setup: dict):
    node_id = registry_setup["node"]["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "CSV Test", "category": "B", "count": 42, "active": True}},
    )

    resp = await client.get(f"/api/iso-docs/registries/{node_id}/export?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    lines = resp.text.strip().split("\n")
    assert len(lines) == 2
    assert "CSV Test" in lines[1]


@pytest.mark.asyncio
async def test_import_csv_roundtrip(client: AsyncClient, registry_setup: dict):
    node_id = registry_setup["node"]["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Row 1", "category": "A", "count": 10, "active": True, "start_date": "2025-01-15"}},
    )
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Row 2", "category": "B", "count": 20, "active": False}},
    )

    export_resp = await client.get(f"/api/iso-docs/registries/{node_id}/export?format=csv")
    assert export_resp.status_code == 200
    csv_content = export_resp.text

    import_resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/import",
        files={"file": ("test.csv", csv_content.encode(), "text/csv")},
    )
    assert import_resp.status_code == 200, import_resp.text
    assert import_resp.json()["imported"] == 2

    rows_resp = await client.get(f"/api/iso-docs/registries/{node_id}/rows")
    rows = rows_resp.json()
    assert len(rows) == 2
    assert rows[0]["data"]["name"] == "Row 1"
    assert rows[0]["data"]["count"] == 10
    assert rows[0]["data"]["active"] is True
    assert rows[0]["data"]["start_date"] == "2025-01-15"
    assert rows[1]["data"]["name"] == "Row 2"
    assert rows[1]["data"]["count"] == 20


@pytest.mark.asyncio
async def test_list_years(client: AsyncClient, yearly_setup: dict):
    node_id = yearly_setup["node"]["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"year": 2024, "data": {"item": "old"}},
    )
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"year": 2024, "data": {"item": "old2"}},
    )
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"year": 2026, "data": {"item": "new"}},
    )

    resp = await client.get(f"/api/iso-docs/registries/{node_id}/years")
    assert resp.status_code == 200
    years = resp.json()
    assert years == [2026, 2024]


@pytest.mark.asyncio
async def test_list_years_empty(client: AsyncClient, yearly_setup: dict):
    node_id = yearly_setup["node"]["id"]
    resp = await client.get(f"/api/iso-docs/registries/{node_id}/years")
    assert resp.status_code == 200
    assert resp.json() == []
