"""Tests for registry types API."""

from collections.abc import AsyncGenerator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from app.core.api.deps import get_db
from app.core.auth import TokenData, get_current_user
from app.main import app

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
async def test_update_registry_type_renames_multiple_columns_in_one_call(
    client: AsyncClient, registry_type: dict,
):
    """Two columns renamed in a single PATCH: BOTH renames must migrate.
    Audit Tier 2 #10 — schema-rename drift risk on multi-rename."""
    node_resp = await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "Multi Rename Node",
            "type": "registry",
            "registry_type_id": registry_type["id"],
        },
    )
    node_id = node_resp.json()["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Hello", "count": 99}},
    )

    new_schema = [
        {"key": "label", "label": "Label", "type": "string", "required": True},
        {"key": "quantity", "label": "Quantity", "type": "number", "required": False},
    ]
    resp = await client.patch(
        f"/api/iso-docs/registry-types/{registry_type['id']}",
        json={"schema": new_schema},
    )
    assert resp.status_code == 200

    rows = (await client.get(f"/api/iso-docs/registries/{node_id}/rows")).json()
    assert rows[0]["data"] == {"label": "Hello", "quantity": 99}


@pytest.mark.asyncio
async def test_update_registry_type_rename_with_no_row_data_is_safe(
    client: AsyncClient, registry_type: dict,
):
    """Renaming a column that no row carries must be a clean no-op on data,
    even though the rename detector fires. Audit Tier 2 #10."""
    node_resp = await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "Empty Node",
            "type": "registry",
            "registry_type_id": registry_type["id"],
        },
    )
    node_id = node_resp.json()["id"]
    # No rows.

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
    assert rows == []


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
async def test_delete_registry_type_blocked_emits_audit_log(
    client: AsyncClient, registry_type: dict, caplog,
):
    """Compliance: blocked deletion must leave an audit trail (Major #6)."""
    await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "Audited Registry",
            "type": "registry",
            "registry_type_id": registry_type["id"],
        },
    )
    with caplog.at_level("INFO"):
        resp = await client.delete(
            f"/api/iso-docs/registry-types/{registry_type['id']}"
        )
    assert resp.status_code == 409
    blocked = [r for r in caplog.records if "iso_registry_type_delete_blocked" in r.message]
    assert blocked, "expected iso_registry_type_delete_blocked log on 409"


@pytest.mark.asyncio
async def test_rename_emits_keys_renamed_audit_log(
    client: AsyncClient, registry_type: dict, caplog,
):
    """Compliance: cross-row JSONB rename must log type_slug, registries
    affected, rows rewritten, and actor (Major #5)."""
    node_resp = await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "Auditable Node",
            "type": "registry",
            "registry_type_id": registry_type["id"],
        },
    )
    node_id = node_resp.json()["id"]
    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={"data": {"name": "Audit Item", "count": 3}},
    )

    new_schema = [
        {"key": "full_name", "label": "Full Name", "type": "string", "required": True},
        {"key": "count", "label": "Count", "type": "number", "required": False},
    ]
    with caplog.at_level("INFO"):
        resp = await client.patch(
            f"/api/iso-docs/registry-types/{registry_type['id']}",
            json={"schema": new_schema},
        )
    assert resp.status_code == 200

    renamed = [r for r in caplog.records if "iso_registry_keys_renamed" in r.message]
    assert renamed, "expected iso_registry_keys_renamed log on rename"


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


# --- Visibility-gating tests (audit Tier 1 #3) -------------------------------
# Non-editor users may only see registry-types that are attached to a node
# under USER_VISIBLE_ROOT_SLUGS (`policies`, `procedures`). The schemas of
# ISMS / legal registries are otherwise exposed as information disclosure.

EDITOR_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
REGULAR_USER_ID = UUID("00000000-0000-0000-0000-000000000002")

EDITOR_TOKEN = TokenData(
    user_id=str(EDITOR_USER_ID),
    email="editor@test.com",
    roles=["user", "iso_docs_editor"],
    permissions=["iso_docs:edit"],
)

REGULAR_TOKEN = TokenData(
    user_id=str(REGULAR_USER_ID),
    email="user@test.com",
    roles=["user"],
    permissions=["scorecard:view"],
)


def _override_user(token: TokenData):
    async def _get_user() -> TokenData:
        return token
    return _get_user


@pytest_asyncio.fixture
async def _override_db_for_visibility(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def visibility_setup(_override_db_for_visibility):
    """Build: a registry-type attached under `policies` (visible), and another
    free-floating registry-type (hidden from regular users)."""
    app.dependency_overrides[get_current_user] = _override_user(EDITOR_TOKEN)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        # Visible type: lives under `policies` root group.
        visible_type = (await c.post(
            "/api/iso-docs/registry-types",
            json={"name": "Visible Register", "schema": SAMPLE_SCHEMA},
        )).json()
        policies = (await c.post(
            "/api/iso-docs/nodes",
            json={"title": "Policies", "type": "group"},
        )).json()
        await c.post(
            "/api/iso-docs/nodes",
            json={
                "title": "Visible Reg Node",
                "type": "registry",
                "parent_id": policies["id"],
                "registry_type_id": visible_type["id"],
            },
        )
        # Hidden type: never attached to any node.
        hidden_type = (await c.post(
            "/api/iso-docs/registry-types",
            json={"name": "Hidden Register", "schema": SAMPLE_SCHEMA},
        )).json()
    return {"visible": visible_type, "hidden": hidden_type}


async def _client_as(token: TokenData) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_current_user] = _override_user(token)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_editor_lists_all_registry_types(visibility_setup: dict):
    async for c in _client_as(EDITOR_TOKEN):
        resp = await c.get("/api/iso-docs/registry-types")
        assert resp.status_code == 200
        ids = {t["id"] for t in resp.json()}
        assert visibility_setup["visible"]["id"] in ids
        assert visibility_setup["hidden"]["id"] in ids


@pytest.mark.asyncio
async def test_regular_user_lists_only_visible_registry_types(visibility_setup: dict):
    async for c in _client_as(REGULAR_TOKEN):
        resp = await c.get("/api/iso-docs/registry-types")
        assert resp.status_code == 200
        ids = {t["id"] for t in resp.json()}
        assert visibility_setup["visible"]["id"] in ids
        assert visibility_setup["hidden"]["id"] not in ids


@pytest.mark.asyncio
async def test_regular_user_can_read_visible_registry_type(visibility_setup: dict):
    async for c in _client_as(REGULAR_TOKEN):
        resp = await c.get(
            f"/api/iso-docs/registry-types/{visibility_setup['visible']['id']}"
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Visible Register"


@pytest.mark.asyncio
async def test_regular_user_cannot_read_hidden_registry_type(visibility_setup: dict):
    """Information-disclosure guard: a non-editor must not be able to
    GET an unattached registry type by id."""
    async for c in _client_as(REGULAR_TOKEN):
        resp = await c.get(
            f"/api/iso-docs/registry-types/{visibility_setup['hidden']['id']}"
        )
        assert resp.status_code == 403
