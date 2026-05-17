"""Permission-denial tests for capacity planner write endpoints.

These exercise the FastAPI dependency chain (`require_permission`) — the
direct-call tests in `test_planner.py` bypass it. A regression that drops
the `CapacityManager` annotation off `update_cells` / `delete_row` must
fail loudly here.
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.database import get_db
from app.main import app


def _viewer_token() -> TokenData:
    """A user-role token: has CAPACITY_VIEW, lacks CAPACITY_MANAGE."""
    return TokenData(
        user_id=str(uuid4()),
        email="viewer@example.com",
        roles=["user"],
        permissions=["capacity:view"],
    )


@pytest_asyncio.fixture
async def viewer_client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient]:
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
async def test_update_cells_denies_user_without_capacity_manage(
    viewer_client: AsyncClient,
) -> None:
    """PATCH /api/capacity/planner/cells must reject CAPACITY_VIEW-only users."""
    body = {
        "updates": [
            {
                "project_id": str(uuid4()),
                "user_id": str(uuid4()),
                "week_start": "2026-01-05",
                "percentage": 50,
            }
        ]
    }
    resp = await viewer_client.patch("/api/capacity/planner/cells", json=body)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_row_denies_user_without_capacity_manage(
    viewer_client: AsyncClient,
) -> None:
    """DELETE /api/capacity/planner/rows/... must reject CAPACITY_VIEW-only users."""
    resp = await viewer_client.delete(f"/api/capacity/planner/rows/{uuid4()}/{uuid4()}")
    assert resp.status_code == 403
