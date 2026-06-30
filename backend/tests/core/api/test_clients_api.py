"""Integration tests for /api/clients CRUD endpoints."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.client import ClientDB
from app.database import get_db
from app.main import app


def _manager_token() -> TokenData:
    """Synthetic token granting portfolio:view + portfolio:manage."""
    return TokenData(
        user_id="00000000-0000-0000-0000-000000000042",
        email="manager@test.com",
        roles=["manager"],
        permissions=["portfolio:view", "portfolio:manage"],
    )


@pytest_asyncio.fixture
async def portfolio_manager_client(db_session: AsyncSession) -> AsyncClient:
    async def override_get_db():
        yield db_session

    async def override_get_current_user() -> TokenData:
        return _manager_token()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_client_slugifies(
    portfolio_manager_client: AsyncClient,
) -> None:
    resp = await portfolio_manager_client.post("/api/clients", json={"name": "Acme Foundation"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "acme-foundation"
    assert body["project_count"] == 0


@pytest.mark.asyncio
async def test_create_duplicate_slug_409(
    portfolio_manager_client: AsyncClient,
) -> None:
    await portfolio_manager_client.post("/api/clients", json={"name": "Dup Co"})
    resp = await portfolio_manager_client.post("/api/clients", json={"name": "Dup Co"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_clients_search(
    portfolio_manager_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    db_session.add(ClientDB(name="Findable Org", slug="findable-org"))
    await db_session.commit()
    resp = await portfolio_manager_client.get("/api/clients", params={"search": "findable"})
    assert resp.status_code == 200
    assert any(c["slug"] == "findable-org" for c in resp.json()["items"])


@pytest.mark.asyncio
async def test_patch_duplicate_slug_409(
    portfolio_manager_client: AsyncClient,
) -> None:
    """Renaming a client to a name that slugifies to an existing client's slug must 409."""
    r1 = await portfolio_manager_client.post("/api/clients", json={"name": "Acme Ltd"})
    assert r1.status_code == 201
    r2 = await portfolio_manager_client.post("/api/clients", json={"name": "Beta Org"})
    assert r2.status_code == 201
    beta_id = r2.json()["id"]
    resp = await portfolio_manager_client.patch(
        f"/api/clients/{beta_id}", json={"name": "Acme Ltd"}
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_patch_own_name_succeeds(
    portfolio_manager_client: AsyncClient,
) -> None:
    """Renaming a client to its own current name (same slug) must succeed with 200."""
    r = await portfolio_manager_client.post("/api/clients", json={"name": "Same Name Co"})
    assert r.status_code == 201
    client_id = r.json()["id"]
    resp = await portfolio_manager_client.patch(
        f"/api/clients/{client_id}", json={"name": "Same Name Co"}
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "same-name-co"


@pytest.mark.asyncio
async def test_create_client_forbidden_without_manage_permission(
    client: AsyncClient,
) -> None:
    """A user without portfolio:manage must be denied with 403."""

    async def _viewer_only() -> TokenData:
        return TokenData(
            user_id="00000000-0000-0000-0000-000000000010",
            email="viewer@test.com",
            roles=["user"],
            permissions=["portfolio:view"],
        )

    app.dependency_overrides[get_current_user] = _viewer_only
    try:
        resp = await client.post("/api/clients", json={"name": "No Access"})
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_merge_endpoint_returns_merged_projects(
    portfolio_manager_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /{target_id}/merge reassigns projects and returns merged_projects count."""
    target = ClientDB(name="Canonical Corp", slug="canonical-corp")
    source = ClientDB(name="Old Name Corp", slug="old-name-corp")
    db_session.add_all([target, source])
    await db_session.commit()

    resp = await portfolio_manager_client.post(
        f"/api/clients/{target.id}/merge",
        json={"source_ids": [str(source.id)]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["merged_projects"] == 0
    assert body["target"]["id"] == str(target.id)
    assert body["target"]["slug"] == "canonical-corp"


@pytest.mark.asyncio
async def test_merge_endpoint_400_on_target_in_sources(
    portfolio_manager_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /{target_id}/merge with target in source_ids must return 400."""
    c = ClientDB(name="Self Ref", slug="self-ref")
    db_session.add(c)
    await db_session.commit()

    resp = await portfolio_manager_client.post(
        f"/api/clients/{c.id}/merge",
        json={"source_ids": [str(c.id)]},
    )
    assert resp.status_code == 400
