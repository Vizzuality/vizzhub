"""Integration tests for endpoint permission gating.

These tests bypass the DEBUG=true synthetic-admin fallback by passing a real
JWT cookie that encodes a specific permission set. This is the closest we
get to an authenticated end-to-end request without the production OAuth flow.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt

from app.config import get_settings
from app.core.auth import ALGORITHM, COOKIE_NAME

settings = get_settings()


def _signed_token(
    *, permissions: list[str], user_id: str = "00000000-0000-0000-0000-000000000999"
) -> str:
    payload = {
        "sub": user_id,
        "email": "scoped@example.com",
        "roles": ["user"],
        "permissions": permissions,
        "exp": datetime.now(UTC) + timedelta(minutes=10),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


@pytest.mark.asyncio
async def test_planner_cell_write_requires_capacity_manage(client: AsyncClient) -> None:
    """A user with only CAPACITY_VIEW cannot PATCH planner cells."""
    token = _signed_token(permissions=["capacity:view"])
    client.cookies.set(COOKIE_NAME, token)
    try:
        resp = await client.patch(
            "/api/capacity/planner/cells",
            json={"updates": []},
        )
        assert resp.status_code == 403
    finally:
        client.cookies.delete(COOKIE_NAME)


@pytest.mark.asyncio
async def test_planner_cell_write_allowed_with_capacity_manage(client: AsyncClient) -> None:
    """A user with CAPACITY_MANAGE can PATCH planner cells (empty body succeeds)."""
    token = _signed_token(permissions=["capacity:view", "capacity:manage"])
    client.cookies.set(COOKIE_NAME, token)
    try:
        resp = await client.patch(
            "/api/capacity/planner/cells",
            json={"updates": []},
        )
        assert resp.status_code == 200
        assert resp.json() == {"updated": 0}
    finally:
        client.cookies.delete(COOKIE_NAME)


@pytest.mark.asyncio
async def test_tracker_manage_endpoint_denies_basic_user(client: AsyncClient) -> None:
    """A 'user' role (TRACKER_VIEW + TRACKER_MANAGE_OWN_REPORTS only) cannot
    create reporting periods."""
    token = _signed_token(
        permissions=[
            "tracker:view",
            "tracker:manage_own_reports",
            "projects:view",
        ],
    )
    client.cookies.set(COOKIE_NAME, token)
    try:
        resp = await client.post(
            "/api/tracker/reporting-periods",
            json={"date": "2026-05-01"},
        )
        assert resp.status_code == 403
    finally:
        client.cookies.delete(COOKIE_NAME)


@pytest.mark.asyncio
async def test_admin_wildcard_passes_all_endpoints(client: AsyncClient) -> None:
    """A user with '*' clears every permission gate."""
    token = _signed_token(permissions=["*"])
    client.cookies.set(COOKIE_NAME, token)
    try:
        resp = await client.patch(
            "/api/capacity/planner/cells",
            json={"updates": []},
        )
        assert resp.status_code == 200
    finally:
        client.cookies.delete(COOKIE_NAME)


@pytest.mark.asyncio
async def test_iso_manage_endpoint_denies_iso_viewer(client: AsyncClient) -> None:
    """A user with only ISO_VIEW cannot trigger snapshot capture."""
    token = _signed_token(permissions=["iso:view"])
    client.cookies.set(COOKIE_NAME, token)
    try:
        resp = await client.post(
            "/api/iso/snapshots/capture",
            json={"provider": "google_workspace"},
        )
        assert resp.status_code == 403
    finally:
        client.cookies.delete(COOKIE_NAME)
