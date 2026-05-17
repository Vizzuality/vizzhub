"""Tests for playbook pages API."""

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_dev_user(db_session: AsyncSession) -> None:
    """Create the dev user so FK constraints on created_by_id pass."""
    result = await db_session.execute(select(UserDB).where(UserDB.id == DEBUG_USER_ID))
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=DEBUG_USER_ID, email="dev@test.com"))
        await db_session.flush()


async def _create_page(client: AsyncClient, title: str = "Test Page") -> str:
    resp = await client.post(
        "/api/playbook/nodes",
        json={"title": title, "type": "page"},
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_get_page_empty(client: AsyncClient):
    page_id = await _create_page(client)
    response = await client.get(f"/api/playbook/pages/{page_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == ""
    assert data["version"] == 0


@pytest.mark.asyncio
async def test_save_page_creates_version(client: AsyncClient):
    page_id = await _create_page(client)
    response = await client.put(
        f"/api/playbook/pages/{page_id}",
        json={"content": "# Hello", "expected_version": 0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == 1
    assert data["conflict"] is False


@pytest.mark.asyncio
async def test_save_page_increments_version(client: AsyncClient):
    page_id = await _create_page(client)
    await client.put(
        f"/api/playbook/pages/{page_id}",
        json={"content": "v1", "expected_version": 0},
    )
    response = await client.put(
        f"/api/playbook/pages/{page_id}",
        json={"content": "v2", "expected_version": 1},
    )
    assert response.json()["version"] == 2


@pytest.mark.asyncio
async def test_save_page_conflict_detection(client: AsyncClient):
    page_id = await _create_page(client)
    await client.put(
        f"/api/playbook/pages/{page_id}",
        json={"content": "v1", "expected_version": 0},
    )
    response = await client.put(
        f"/api/playbook/pages/{page_id}",
        json={"content": "v2 from stale editor", "expected_version": 0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == 2
    assert data["conflict"] is True


@pytest.mark.asyncio
async def test_get_page_after_save(client: AsyncClient):
    page_id = await _create_page(client)
    await client.put(
        f"/api/playbook/pages/{page_id}",
        json={"content": "# Updated", "expected_version": 0},
    )
    response = await client.get(f"/api/playbook/pages/{page_id}")
    assert response.json()["content"] == "# Updated"
    assert response.json()["version"] == 1


@pytest.mark.asyncio
async def test_get_page_group_returns_400(client: AsyncClient):
    resp = await client.post(
        "/api/playbook/nodes",
        json={"title": "A Group", "type": "group"},
    )
    group_id = resp.json()["id"]
    response = await client.get(f"/api/playbook/pages/{group_id}")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_versions(client: AsyncClient):
    page_id = await _create_page(client)
    await client.put(
        f"/api/playbook/pages/{page_id}",
        json={"content": "v1", "expected_version": 0},
    )
    await client.put(
        f"/api/playbook/pages/{page_id}",
        json={"content": "v2", "expected_version": 1},
    )
    response = await client.get(f"/api/playbook/pages/{page_id}/versions")
    assert response.status_code == 200
    versions = response.json()
    assert len(versions) == 2
    assert versions[0]["version"] == 2
    assert versions[1]["version"] == 1


@pytest.mark.asyncio
async def test_get_specific_version(client: AsyncClient):
    page_id = await _create_page(client)
    await client.put(
        f"/api/playbook/pages/{page_id}",
        json={"content": "first version", "expected_version": 0},
    )
    await client.put(
        f"/api/playbook/pages/{page_id}",
        json={"content": "second version", "expected_version": 1},
    )
    response = await client.get(f"/api/playbook/pages/{page_id}/versions/1")
    assert response.status_code == 200
    assert response.json()["content"] == "first version"


@pytest.mark.asyncio
async def test_get_missing_version_returns_404(client: AsyncClient):
    page_id = await _create_page(client)
    response = await client.get(f"/api/playbook/pages/{page_id}/versions/99")
    assert response.status_code == 404
