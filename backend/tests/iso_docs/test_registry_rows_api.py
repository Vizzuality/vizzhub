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
async def test_update_row_null_clears_optional_field(
    client: AsyncClient, registry_setup: dict
):
    """PATCH with `key: null` for an optional column must clear that field."""
    node_id = registry_setup["node"]["id"]
    create_resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "WithCount", "category": "A", "count": 42}},
    )
    row_id = create_resp.json()["id"]
    assert create_resp.json()["data"]["count"] == 42

    resp = await client.patch(
        f"/api/iso-docs/registries/{node_id}/rows/{row_id}",
        json={"data": {"count": None}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["count"] is None
    assert body["data"]["name"] == "WithCount"
    assert body["data"]["category"] == "A"


@pytest.mark.asyncio
async def test_update_row_null_required_field_rejected(
    client: AsyncClient, registry_setup: dict
):
    """PATCH that nulls a required field must fail validation (422)."""
    node_id = registry_setup["node"]["id"]
    create_resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Keep", "category": "A"}},
    )
    row_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/iso-docs/registries/{node_id}/rows/{row_id}",
        json={"data": {"name": None}},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_row_unsent_keys_preserved(
    client: AsyncClient, registry_setup: dict
):
    """PATCH with a partial data dict must preserve keys NOT in the payload.
    Distinguishes 'not sent' from 'explicitly null' (audit Tier 2 #10)."""
    node_id = registry_setup["node"]["id"]
    create_resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={
            "data": {
                "name": "Original", "category": "A", "count": 5, "active": True,
            },
        },
    )
    row_id = create_resp.json()["id"]

    # Send only `count: null` — name/category/active must survive untouched.
    resp = await client.patch(
        f"/api/iso-docs/registries/{node_id}/rows/{row_id}",
        json={"data": {"count": None}},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["count"] is None
    assert body["name"] == "Original"
    assert body["category"] == "A"
    assert body["active"] is True


@pytest.mark.asyncio
async def test_update_row_empty_data_no_op(
    client: AsyncClient, registry_setup: dict
):
    """PATCH with `{data: {}}` must not change anything.
    Guards against 'empty dict = clear all' misinterpretation."""
    node_id = registry_setup["node"]["id"]
    create_resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Stable", "category": "B", "count": 7}},
    )
    row_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/iso-docs/registries/{node_id}/rows/{row_id}",
        json={"data": {}},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["name"] == "Stable"
    assert body["category"] == "B"
    assert body["count"] == 7


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


@pytest.mark.asyncio
async def test_copy_year(client: AsyncClient, yearly_setup: dict):
    node_id = yearly_setup["node"]["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"year": 2024, "data": {"item": "risk A"}},
    )
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"year": 2024, "data": {"item": "risk B"}},
    )

    resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/copy-year",
        params={"source_year": 2024, "target_year": 2025},
    )
    assert resp.status_code == 200
    assert resp.json()["copied"] == 2

    rows = await client.get(
        f"/api/iso-docs/registries/{node_id}/rows", params={"year": 2025}
    )
    assert len(rows.json()) == 2
    assert rows.json()[0]["data"]["item"] == "risk A"


@pytest.mark.asyncio
async def test_copy_year_target_not_empty(client: AsyncClient, yearly_setup: dict):
    node_id = yearly_setup["node"]["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"year": 2024, "data": {"item": "A"}},
    )
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"year": 2025, "data": {"item": "B"}},
    )
    resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/copy-year",
        params={"source_year": 2024, "target_year": 2025},
    )
    assert resp.status_code == 400
    assert "already has data" in resp.json()["detail"]


COMPUTED_SCHEMA = [
    {"key": "probability", "label": "Probability", "type": "number", "required": True},
    {"key": "impact", "label": "Impact", "type": "number", "required": True},
    {
        "key": "evaluation",
        "label": "Evaluation",
        "type": "computed",
        "formula": {"operation": "multiply", "fields": ["probability", "impact"]},
        "conditional_format": [
            {"min": 1, "max": 2, "color": "#22c55e", "label": "Low"},
            {"min": 3, "max": 4, "color": "#eab308", "label": "Moderate"},
            {"min": 6, "max": 9, "color": "#ef4444", "label": "High"},
        ],
    },
    {"key": "notes", "label": "Notes", "type": "string", "required": False},
]


@pytest_asyncio.fixture
async def computed_setup(client: AsyncClient) -> dict:
    rt_resp = await client.post(
        "/api/iso-docs/registry-types",
        json={"name": "Risk Test", "schema": COMPUTED_SCHEMA},
    )
    rt = rt_resp.json()
    node_resp = await client.post(
        "/api/iso-docs/nodes",
        json={"title": "Risks", "type": "registry", "registry_type_id": rt["id"]},
    )
    return {"type": rt, "node": node_resp.json()}


@pytest.mark.asyncio
async def test_computed_field_in_create_response(
    client: AsyncClient, computed_setup: dict
):
    node_id = computed_setup["node"]["id"]
    resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"probability": 2, "impact": 3}},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["evaluation"] == 6


@pytest.mark.asyncio
async def test_computed_field_in_list_response(
    client: AsyncClient, computed_setup: dict
):
    node_id = computed_setup["node"]["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"probability": 1, "impact": 2}},
    )
    resp = await client.get(f"/api/iso-docs/registries/{node_id}/rows")
    assert resp.status_code == 200
    rows = resp.json()
    assert rows[0]["data"]["evaluation"] == 2


@pytest.mark.asyncio
async def test_computed_field_in_update_response(
    client: AsyncClient, computed_setup: dict
):
    node_id = computed_setup["node"]["id"]
    create_resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"probability": 1, "impact": 1}},
    )
    row_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/iso-docs/registries/{node_id}/rows/{row_id}",
        json={"data": {"impact": 3}},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["evaluation"] == 3


@pytest.mark.asyncio
async def test_computed_field_stripped_from_storage(
    client: AsyncClient, computed_setup: dict
):
    """Sending a computed key in data should not cause validation error."""
    node_id = computed_setup["node"]["id"]
    resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"probability": 2, "impact": 2, "evaluation": 999}},
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["evaluation"] == 4


@pytest.mark.asyncio
async def test_computed_field_in_csv_export(
    client: AsyncClient, computed_setup: dict
):
    node_id = computed_setup["node"]["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"probability": 3, "impact": 3}},
    )
    resp = await client.get(
        f"/api/iso-docs/registries/{node_id}/export", params={"format": "csv"}
    )
    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    assert "Evaluation" in lines[0]
    assert "9" in lines[1]


@pytest.mark.asyncio
async def test_computed_column_ignored_in_csv_import(
    client: AsyncClient, computed_setup: dict
):
    node_id = computed_setup["node"]["id"]
    csv_content = "Probability,Impact,Evaluation,Notes\n2,3,6,test\n"
    import io
    resp = await client.post(
        f"/api/iso-docs/registries/{node_id}/import",
        files={"file": ("data.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    assert resp.json()["imported"] == 1
    rows_resp = await client.get(f"/api/iso-docs/registries/{node_id}/rows")
    row_data = rows_resp.json()[0]["data"]
    assert row_data["evaluation"] == 6
