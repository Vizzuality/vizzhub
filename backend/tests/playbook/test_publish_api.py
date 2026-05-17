"""Tests for playbook publish API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.user import UserDB
from app.core.permissions.roles import ROLE_PERMISSIONS
from app.main import app
from app.modules.playbook.models.publish_log import PlaybookPublishLogDB


def _user_permissions() -> list[str]:
    return sorted(ROLE_PERMISSIONS["user"])


def _admin_permissions() -> list[str]:
    perms = set()
    for role in ("user", "manager", "admin"):
        perms |= ROLE_PERMISSIONS[role]
    return sorted(perms)


ADMIN_USER_ID = "00000000-0000-0000-0000-000000000001"
REGULAR_USER_ID = "00000000-0000-0000-0000-000000000010"


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> UserDB:
    """Seed an admin user so FK constraints pass."""
    user = UserDB(
        id=UUID(ADMIN_USER_ID),
        email="admin@test.com",
        name="Admin",
    )
    db_session.add(user)
    await db_session.commit()
    return user


class TestPublishEndpoint:
    """POST /api/playbook/publish"""

    @pytest_asyncio.fixture(autouse=True)
    async def _override_admin(self):
        async def mock_admin():
            return TokenData(
                user_id=ADMIN_USER_ID,
                email="admin@test.com",
                roles=["user", "manager", "admin"],
                permissions=_admin_permissions(),
            )

        app.dependency_overrides[get_current_user] = mock_admin
        yield
        app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_creates_log_and_enqueues_job(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        admin_user: UserDB,
    ):
        with patch("app.modules.playbook.api.publish.get_redis_pool") as mock_pool:
            mock_redis = AsyncMock()
            mock_redis.enqueue_job = AsyncMock(
                return_value=MagicMock(job_id="arq-123"),
            )
            mock_pool.return_value = mock_redis
            resp = await client.post("/api/playbook/publish")

        assert resp.status_code == 201
        data = resp.json()
        assert "publish_log_id" in data

        log_id = UUID(data["publish_log_id"])
        db_session.expire_all()
        log = await db_session.get(PlaybookPublishLogDB, log_id)
        assert log is not None
        assert log.status == "running"
        assert str(log.published_by_id) == ADMIN_USER_ID

        mock_redis.enqueue_job.assert_called_once_with(
            "publish_playbook_task",
            publish_log_id=str(log_id),
        )

    @pytest.mark.asyncio
    async def test_returns_409_when_already_running(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        admin_user: UserDB,
    ):
        existing = PlaybookPublishLogDB(
            status="running",
            published_by_id=UUID(ADMIN_USER_ID),
        )
        db_session.add(existing)
        await db_session.commit()

        resp = await client.post("/api/playbook/publish")
        assert resp.status_code == 409
        assert "already running" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self, client: AsyncClient):
        async def mock_user():
            return TokenData(
                user_id=REGULAR_USER_ID,
                email="user@test.com",
                roles=["user"],
                permissions=_user_permissions(),
            )

        app.dependency_overrides[get_current_user] = mock_user

        resp = await client.post("/api/playbook/publish")
        assert resp.status_code == 403


class TestPublishStatusEndpoint:
    """GET /api/playbook/publish/status"""

    @pytest_asyncio.fixture(autouse=True)
    async def _override_admin(self):
        async def mock_admin():
            return TokenData(
                user_id=ADMIN_USER_ID,
                email="admin@test.com",
                roles=["user", "manager", "admin"],
                permissions=_admin_permissions(),
            )

        app.dependency_overrides[get_current_user] = mock_admin
        yield
        app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_returns_null_when_never_published(self, client: AsyncClient):
        resp = await client.get("/api/playbook/publish/status")
        assert resp.status_code == 200
        assert resp.json() is None

    @pytest.mark.asyncio
    async def test_returns_latest_entry(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        admin_user: UserDB,
    ):
        log = PlaybookPublishLogDB(
            status="completed",
            page_count=5,
            published_by_id=UUID(ADMIN_USER_ID),
        )
        db_session.add(log)
        await db_session.commit()

        resp = await client.get("/api/playbook/publish/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["page_count"] == 5
        assert data["started_at"] is not None
        assert data["completed_at"] is None
        assert data["error_message"] is None

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self, client: AsyncClient):
        async def mock_user():
            return TokenData(
                user_id=REGULAR_USER_ID,
                email="user@test.com",
                roles=["user"],
                permissions=_user_permissions(),
            )

        app.dependency_overrides[get_current_user] = mock_user

        resp = await client.get("/api/playbook/publish/status")
        assert resp.status_code == 403
