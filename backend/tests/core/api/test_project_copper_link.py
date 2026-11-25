"""Projects remember the Copper opportunity they came from."""

import pytest
from httpx import AsyncClient

from tests.conftest import DEFAULT_PROGRAM_ID


@pytest.fixture(autouse=True)
def _seed_program(default_program: str) -> None:
    """Projects require a program on create."""


def _payload(**extra) -> dict:
    return {"program_id": DEFAULT_PROGRAM_ID, "name": "WRIP Design", "code": "Sys.WRIP", **extra}


@pytest.mark.asyncio
async def test_create_stores_copper_opportunity(client: AsyncClient) -> None:
    resp = await client.post("/api/projects", json=_payload(copper_opportunity_id=39491052))

    assert resp.status_code == 201
    assert resp.json()["copper_opportunity_id"] == 39491052


@pytest.mark.asyncio
async def test_full_edit_without_the_field_keeps_the_link(client: AsyncClient) -> None:
    created = (
        await client.post("/api/projects", json=_payload(copper_opportunity_id=39491052))
    ).json()

    resp = await client.put(f"/api/projects/{created['id']}", json=_payload(name="WRIP"))

    assert resp.status_code == 200
    assert resp.json()["copper_opportunity_id"] == 39491052


@pytest.mark.asyncio
async def test_patch_links_and_unlinks_an_opportunity(client: AsyncClient) -> None:
    created = (await client.post("/api/projects", json=_payload())).json()

    linked = await client.patch(
        f"/api/projects/{created['id']}", json={"copper_opportunity_id": 39133412}
    )
    unlinked = await client.patch(
        f"/api/projects/{created['id']}", json={"copper_opportunity_id": None}
    )

    assert linked.json()["copper_opportunity_id"] == 39133412
    assert unlinked.json()["copper_opportunity_id"] is None
