"""HTTP tests for /api/accrual/periods."""

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.user import UserDB
from app.database import get_db
from app.main import app

# The dev-mode auth bypass synthesises this UUID — seed it so FK constraints pass.
_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_dev_user(db_session: AsyncSession) -> None:
    """Seed the synthetic dev user so created_by FK never fires."""
    result = await db_session.execute(select(UserDB).where(UserDB.id == _DEV_USER_ID))
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=_DEV_USER_ID, email="dev@test.com"))
        await db_session.flush()


def _viewer_token() -> TokenData:
    """Token with no accrual permissions."""
    return TokenData(
        user_id=str(uuid4()),
        email="viewer@example.com",
        roles=["viewer_only"],
        permissions=["accrual:view"],  # explicitly NOT period_manage
    )


@pytest_asyncio.fixture
async def viewer_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    async def override_get_current_user() -> TokenData:
        return _viewer_token()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_periods_requires_period_manage(viewer_client: AsyncClient) -> None:
    resp = await viewer_client.get("/api/accrual/periods")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_periods_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/accrual/periods")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_period_returns_201(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["start_date"] == "2026-01-01"
    assert body["status"] == "open"
    assert body["fx_rates"] == {}


@pytest.mark.asyncio
async def test_create_period_with_fx_rates(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01", "fx_rates": {"USD": "1.08", "GBP": "0.87"}},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["fx_rates"] == {"USD": "1.08", "GBP": "0.87"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fx_rates",
    [{"usd": "1.08"}, {"US": "1.08"}, {"USD": "0"}, {"USD": "-1"}, {"USD": "abc"}],
)
async def test_create_period_rejects_invalid_fx_rates(client: AsyncClient, fx_rates: dict) -> None:
    resp = await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01", "fx_rates": fx_rates},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_patch_period_fx_rates(client: AsyncClient) -> None:
    created = (await client.post("/api/accrual/periods", json={"start_date": "2026-01-01"})).json()
    resp = await client.patch(
        f"/api/accrual/periods/{created['id']}",
        json={"fx_rates": {"USD": "1.10", "CAD": "1.46"}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["fx_rates"] == {"USD": "1.10", "CAD": "1.46"}


@pytest.mark.asyncio
async def test_patch_period_not_found(client: AsyncClient) -> None:
    resp = await client.patch(
        f"/api/accrual/periods/{uuid4()}",
        json={"fx_rates": {"USD": "1.08"}},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_patch_period_requires_period_manage(viewer_client: AsyncClient) -> None:
    resp = await viewer_client.patch(
        f"/api/accrual/periods/{uuid4()}",
        json={"fx_rates": {"USD": "1.08"}},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_current_period(client: AsyncClient) -> None:
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01"},
    )
    resp = await client.get("/api/accrual/periods/current")
    assert resp.status_code == 200
    assert resp.json()["status"] == "open"
