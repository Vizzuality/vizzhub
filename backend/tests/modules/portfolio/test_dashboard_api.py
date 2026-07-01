"""Integration + gating tests for GET /api/portfolio/dashboard/summary."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.database import get_db
from app.main import app


@pytest_asyncio.fixture
async def viewer_client(db_session: AsyncSession) -> AsyncClient:
    async def override_get_db():
        yield db_session

    async def override_user() -> TokenData:
        return TokenData(
            user_id="00000000-0000-0000-0000-000000000042",
            email="viewer@test.com",
            roles=["user"],
            permissions=["portfolio:view"],
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_summary_returns_shape(viewer_client: AsyncClient) -> None:
    resp = await viewer_client.get("/api/portfolio/dashboard/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {
        "year",
        "available_years",
        "kpis",
        "volume_by_year",
        "spend_by_client",
        "margin_split",
        "breakdowns",
    }
    assert body["year"] is None


@pytest.mark.asyncio
async def test_summary_forbidden_without_view(client: AsyncClient) -> None:
    async def _no_perms() -> TokenData:
        return TokenData(
            user_id="00000000-0000-0000-0000-000000000010",
            email="x@test.com",
            roles=["user"],
            permissions=[],
        )

    app.dependency_overrides[get_current_user] = _no_perms
    try:
        resp = await client.get("/api/portfolio/dashboard/summary")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
