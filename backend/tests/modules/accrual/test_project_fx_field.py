"""Round-trip locked_fx_rate through Project CRUD.

The DB column was added in migration 077; the Pydantic schemas were
extended at the same time. These tests verify the end-to-end flow:
PATCH sets the value, GET returns it, PATCH null clears it.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_patch_project_sets_locked_fx_rate(client: AsyncClient) -> None:
    create = await client.post(
        "/api/projects",
        json={"name": "Locked FX Project", "code": "TEST.AC.LOCK1"},
    )
    assert create.status_code == 201, create.text
    pid = create.json()["id"]
    assert create.json()["locked_fx_rate"] is None

    patch = await client.patch(f"/api/projects/{pid}", json={"locked_fx_rate": 1.105})
    assert patch.status_code == 200, patch.text
    assert float(patch.json()["locked_fx_rate"]) == pytest.approx(1.105)

    get = await client.get(f"/api/projects/{pid}")
    assert get.status_code == 200
    assert float(get.json()["locked_fx_rate"]) == pytest.approx(1.105)


@pytest.mark.asyncio
async def test_patch_project_clears_locked_fx_rate(client: AsyncClient) -> None:
    create = await client.post(
        "/api/projects",
        json={"name": "Locked FX Clear", "code": "TEST.AC.LOCK2"},
    )
    pid = create.json()["id"]

    await client.patch(f"/api/projects/{pid}", json={"locked_fx_rate": 1.10})
    clear = await client.patch(f"/api/projects/{pid}", json={"locked_fx_rate": None})
    assert clear.status_code == 200, clear.text
    assert clear.json()["locked_fx_rate"] is None


@pytest.mark.asyncio
async def test_create_project_persists_locked_fx_rate(client: AsyncClient) -> None:
    response = await client.post(
        "/api/projects",
        json={
            "name": "Born with rate",
            "code": "TEST.AC.LOCK4",
            "locked_fx_rate": 1.234567,
        },
    )
    assert response.status_code == 201, response.text
    assert float(response.json()["locked_fx_rate"]) == pytest.approx(1.234567)


@pytest.mark.asyncio
async def test_create_project_rejects_negative_locked_fx_rate(client: AsyncClient) -> None:
    response = await client.post(
        "/api/projects",
        json={
            "name": "Bad rate",
            "code": "TEST.AC.LOCK3",
            "locked_fx_rate": -1.5,
        },
    )
    assert response.status_code == 400, response.text
