"""Project API surfaces client_id (write) and client_name (resolved read)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB
from app.database import get_db
from app.main import app


def _pm_token() -> TokenData:
    return TokenData(
        user_id="00000000-0000-0000-0000-000000000042",
        email="pm@test.com",
        roles=["manager"],
        permissions=["projects:view", "projects:manage"],
    )


@pytest_asyncio.fixture
async def pm_client(db_session: AsyncSession) -> AsyncClient:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _pm_token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_patch_sets_client_id_and_get_resolves_client_name(
    pm_client: AsyncClient, db_session: AsyncSession
) -> None:
    client = ClientDB(name="Acme Foundation", slug="acme-foundation", code="ACME")
    project = ProjectDB(name="Acme site", code="ACME.SITE")
    db_session.add_all([client, project])
    await db_session.flush()

    patch = await pm_client.patch(f"/api/projects/{project.id}", json={"client_id": str(client.id)})
    assert patch.status_code == 200

    got = await pm_client.get(f"/api/projects/{project.id}")
    assert got.status_code == 200
    body = got.json()
    assert body["client_id"] == str(client.id)
    assert body["client_name"] == "Acme Foundation"
