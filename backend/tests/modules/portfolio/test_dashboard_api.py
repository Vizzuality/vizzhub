import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.database import get_db
from app.main import app


def _viewer() -> TokenData:
    return TokenData(
        user_id="00000000-0000-0000-0000-000000000042",
        email="v@test.com",
        roles=["manager"],
        permissions=["portfolio:view"],
    )


def _no_perms() -> TokenData:
    return TokenData(
        user_id="00000000-0000-0000-0000-000000000043",
        email="n@test.com",
        roles=["user"],
        permissions=[],
    )


@pytest_asyncio.fixture
async def viewer_client(db_session: AsyncSession) -> AsyncClient:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _viewer
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_projects_endpoint_shape(viewer_client: AsyncClient) -> None:
    resp = await viewer_client.get("/api/portfolio/dashboard/projects")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"available_years", "rows"}


@pytest.mark.asyncio
async def test_clients_endpoint_shape(viewer_client: AsyncClient) -> None:
    resp = await viewer_client.get("/api/portfolio/dashboard/clients")
    assert resp.status_code == 200
    assert set(resp.json().keys()) == {"available_years", "rows"}


@pytest.mark.asyncio
async def test_endpoints_forbidden_without_view(db_session: AsyncSession) -> None:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _no_perms
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/api/portfolio/dashboard/projects")).status_code == 403
        assert (await ac.get("/api/portfolio/dashboard/clients")).status_code == 403
    app.dependency_overrides.clear()
