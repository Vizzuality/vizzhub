"""Tests for /api/devstack/project-contexts endpoints."""

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.project import ProjectDB
from app.main import app


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def sample_project(db_session: AsyncSession) -> ProjectDB:
    project = ProjectDB(name="Acme Corp")
    db_session.add(project)
    await db_session.flush()
    return project


@pytest_asyncio.fixture
async def second_project(db_session: AsyncSession) -> ProjectDB:
    project = ProjectDB(name="Beta LLC")
    db_session.add(project)
    await db_session.flush()
    return project


@pytest_asyncio.fixture
async def viewer_client(client: AsyncClient):
    """Client authenticated as a user with only DEVSTACK_VIEW permission."""
    async def _viewer():
        return TokenData(
            user_id="00000000-0000-0000-0000-000000000030",
            email="viewer@test.com",
            roles=["user"],
            permissions=["devstack:view"],
        )

    app.dependency_overrides[get_current_user] = _viewer
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/devstack/project-contexts")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_and_list_includes_project_name(
    client: AsyncClient, sample_project: ProjectDB
) -> None:
    payload = {
        "slug": "acme-corp",
        "project_id": str(sample_project.id),
        "description": "Private CLAUDE.md for Acme",
    }
    create_resp = await client.post("/api/devstack/project-contexts", json=payload)
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["slug"] == "acme-corp"
    assert data["project_name"] == "Acme Corp"
    assert data["description"] == "Private CLAUDE.md for Acme"
    assert "id" in data

    list_resp = await client.get("/api/devstack/project-contexts")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["project_name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_create_slug_regex_rejects_spaces(
    client: AsyncClient, sample_project: ProjectDB
) -> None:
    payload = {
        "slug": "Acme Corp",  # uppercase + space — invalid
        "project_id": str(sample_project.id),
    }
    resp = await client.post("/api/devstack/project-contexts", json=payload)
    # main.py validation_exception_handler converts 422 → 400 for consistency
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_duplicate_project_link_409(
    client: AsyncClient, sample_project: ProjectDB, second_project: ProjectDB
) -> None:
    # First context for sample_project
    await client.post(
        "/api/devstack/project-contexts",
        json={"slug": "acme-corp", "project_id": str(sample_project.id)},
    )
    # Second context with different slug but same project_id → 409
    resp = await client.post(
        "/api/devstack/project-contexts",
        json={"slug": "acme-corp-2", "project_id": str(sample_project.id)},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_duplicate_slug_409(
    client: AsyncClient, sample_project: ProjectDB, second_project: ProjectDB
) -> None:
    # Create first context for sample_project
    await client.post(
        "/api/devstack/project-contexts",
        json={"slug": "my-slug", "project_id": str(sample_project.id)},
    )
    # Attempt same slug for second project → 409
    resp = await client.post(
        "/api/devstack/project-contexts",
        json={"slug": "my-slug", "project_id": str(second_project.id)},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_description(
    client: AsyncClient, sample_project: ProjectDB
) -> None:
    create_resp = await client.post(
        "/api/devstack/project-contexts",
        json={"slug": "acme-corp", "project_id": str(sample_project.id), "description": "old"},
    )
    assert create_resp.status_code == 201
    context_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/devstack/project-contexts/{context_id}",
        json={"description": "new description"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "new description"
    assert resp.json()["slug"] == "acme-corp"  # unchanged


@pytest.mark.asyncio
async def test_update_slug_rejected_400(
    client: AsyncClient, sample_project: ProjectDB
) -> None:
    create_resp = await client.post(
        "/api/devstack/project-contexts",
        json={"slug": "acme-corp", "project_id": str(sample_project.id)},
    )
    context_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/devstack/project-contexts/{context_id}",
        json={"slug": "renamed"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_204(
    client: AsyncClient, sample_project: ProjectDB
) -> None:
    create_resp = await client.post(
        "/api/devstack/project-contexts",
        json={"slug": "acme-corp", "project_id": str(sample_project.id)},
    )
    context_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/devstack/project-contexts/{context_id}")
    assert resp.status_code == 204

    # Verify it's gone
    get_resp = await client.get(f"/api/devstack/project-contexts/{context_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_viewer_can_list(
    viewer_client: AsyncClient, sample_project: ProjectDB
) -> None:
    resp = await viewer_client.get("/api/devstack/project-contexts")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_viewer_cannot_create_403(
    viewer_client: AsyncClient, sample_project: ProjectDB
) -> None:
    resp = await viewer_client.post(
        "/api/devstack/project-contexts",
        json={"slug": "acme-corp", "project_id": str(sample_project.id)},
    )
    assert resp.status_code == 403
