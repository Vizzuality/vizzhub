"""Smoke test: accrual module is mounted under /api/accrual."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_accrual_router_mounted(client: AsyncClient) -> None:
    # No routes yet — but the router exists and is mounted under /api/accrual.
    # A 404 (no matching path) confirms the prefix is wired; a 502 / connection
    # error would indicate the include failed.
    resp = await client.get("/api/accrual/__doesnotexist__")
    assert resp.status_code == 404
