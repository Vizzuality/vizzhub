"""Integration tests for GET /api/taxonomies."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.taxonomy import Cardinality, TaxonomyDB, TaxonomyTermDB
from app.database import get_db
from app.main import app


def _portfolio_viewer_token() -> TokenData:
    """Synthetic token granting PORTFOLIO_VIEW (not yet in any role)."""
    return TokenData(
        user_id="00000000-0000-0000-0000-000000000042",
        email="viewer@test.com",
        roles=["user"],
        permissions=["portfolio:view"],
    )


@pytest_asyncio.fixture
async def portfolio_client(db_session: AsyncSession) -> AsyncClient:
    async def override_get_db():
        yield db_session

    async def override_get_current_user() -> TokenData:
        return _portfolio_viewer_token()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_taxonomies_returns_terms(
    portfolio_client: AsyncClient, db_session: AsyncSession
) -> None:
    tax = TaxonomyDB(slug="service", name="Service", cardinality=Cardinality.MULTI)
    db_session.add(tax)
    await db_session.flush()
    db_session.add(TaxonomyTermDB(taxonomy_id=tax.id, slug="tools", name="Tools", sort_order=1))
    await db_session.commit()

    resp = await portfolio_client.get("/api/taxonomies")
    assert resp.status_code == 200
    body = resp.json()
    service = next(t for t in body if t["slug"] == "service")
    assert service["terms"][0]["name"] == "Tools"


@pytest.mark.asyncio
async def test_list_taxonomies_forbidden_without_permission(client: AsyncClient) -> None:
    """A user without portfolio:view must be denied with 403."""

    async def _no_permission_user() -> TokenData:
        return TokenData(
            user_id="00000000-0000-0000-0000-000000000010",
            email="user@test.com",
            roles=["user"],
            permissions=[],
        )

    app.dependency_overrides[get_current_user] = _no_permission_user
    try:
        resp = await client.get("/api/taxonomies")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_list_taxonomies_excludes_inactive(
    portfolio_client: AsyncClient, db_session: AsyncSession
) -> None:
    active = TaxonomyDB(slug="active-tax", name="Active", cardinality=Cardinality.SINGLE)
    inactive = TaxonomyDB(
        slug="inactive-tax", name="Inactive", cardinality=Cardinality.SINGLE, is_active=False
    )
    db_session.add(active)
    db_session.add(inactive)
    await db_session.commit()

    resp = await portfolio_client.get("/api/taxonomies")
    assert resp.status_code == 200
    slugs = [t["slug"] for t in resp.json()]
    assert "active-tax" in slugs
    assert "inactive-tax" not in slugs
