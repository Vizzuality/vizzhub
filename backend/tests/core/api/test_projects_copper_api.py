"""GET /api/projects/copper-opportunities."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.auth import TokenData, get_current_user
from app.core.permissions.roles import ROLE_PERMISSIONS
from app.main import app
from tests.core.services.test_copper_opportunities import WRIP, FakeCopper

ENDPOINT = "/api/projects/copper-opportunities"
FROM_DB = "app.core.api.projects_copper.CopperClient.from_db"


class _ContextCopper(FakeCopper):
    async def __aenter__(self) -> "_ContextCopper":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


@pytest.mark.asyncio
async def test_lists_importable_opportunities(client: AsyncClient) -> None:
    with patch(FROM_DB, new=AsyncMock(return_value=_ContextCopper([WRIP]))):
        resp = await client.get(ENDPOINT)

    assert resp.status_code == 200
    [opp] = resp.json()
    assert opp["opportunity_id"] == 39491052
    assert opp["group"] == "pending_signature"
    assert opp["new_client"] == {
        "name": "Systemiq.earth",
        "code": "Sys",
        "copper_company_id": 77916335,
    }


@pytest.mark.asyncio
async def test_409_when_copper_is_not_connected(client: AsyncClient) -> None:
    with patch(FROM_DB, new=AsyncMock(return_value=None)):
        resp = await client.get(ENDPOINT)

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_managers_who_cannot_create_projects_are_refused(client: AsyncClient) -> None:
    async def manager() -> TokenData:
        perms = ROLE_PERMISSIONS["user"] | ROLE_PERMISSIONS["manager"]
        return TokenData(user_id="00000000-0000-0000-0000-000000000021", permissions=sorted(perms))

    app.dependency_overrides[get_current_user] = manager
    try:
        resp = await client.get(ENDPOINT)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403
