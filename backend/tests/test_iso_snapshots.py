"""Tests for ISO snapshot API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from httpx import AsyncClient

from app.models.oauth import OAuthTokenDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.models.access_review import AccessReviewDB


class TestCaptureEndpoint:
    @pytest.mark.asyncio
    async def test_capture_creates_snapshot(
        self, client: AsyncClient, db_session
    ) -> None:
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="ya29.test",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        mock_api_response = MagicMock()
        mock_api_response.json.return_value = {
            "users": [
                {
                    "id": "u1",
                    "primaryEmail": "a@empresa.com",
                    "name": {"fullName": "A"},
                    "suspended": False,
                    "orgUnitPath": "/",
                }
            ],
            "groups": [],
            "members": [],
            "items": [],
        }
        mock_api_response.raise_for_status = MagicMock()

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            return_value=mock_api_response,
        ):
            response = await client.post("/api/iso/snapshots/capture")

        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "google_workspace"
        assert "users" in data["data"]
        assert data["summary"]["total_users"] >= 1

    @pytest.mark.asyncio
    async def test_capture_creates_draft_review(
        self, client: AsyncClient, db_session
    ) -> None:
        from sqlalchemy import select

        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="ya29.test",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        mock_api_response = MagicMock()
        mock_api_response.json.return_value = {
            "users": [
                {
                    "id": "u1",
                    "primaryEmail": "a@empresa.com",
                    "name": {"fullName": "A"},
                    "suspended": False,
                    "orgUnitPath": "/",
                }
            ],
            "groups": [],
            "members": [],
            "items": [],
        }
        mock_api_response.raise_for_status = MagicMock()

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            return_value=mock_api_response,
        ):
            response = await client.post("/api/iso/snapshots/capture")

        assert response.status_code == 201
        snapshot_id = response.json()["id"]

        result = await db_session.execute(
            select(AccessReviewDB).where(
                AccessReviewDB.snapshot_id == snapshot_id
            )
        )
        review = result.scalar_one_or_none()
        assert review is not None
        assert review.status == "draft"
        assert review.scope == "All users and groups"
        assert review.previous_snapshot_id is None
        assert review.reviewer_id is None

    @pytest.mark.asyncio
    async def test_capture_links_previous_snapshot(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone
        from sqlalchemy import select

        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="ya29.test",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        previous = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={"users": [], "groups": [], "group_members": {}, "role_assignments": []},
            summary={},
        )
        db_session.add(previous)
        await db_session.flush()
        previous_id = previous.id

        mock_api_response = MagicMock()
        mock_api_response.json.return_value = {
            "users": [],
            "groups": [],
            "members": [],
            "items": [],
        }
        mock_api_response.raise_for_status = MagicMock()

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            return_value=mock_api_response,
        ):
            response = await client.post("/api/iso/snapshots/capture")

        assert response.status_code == 201
        snapshot_id = response.json()["id"]

        result = await db_session.execute(
            select(AccessReviewDB).where(
                AccessReviewDB.snapshot_id == snapshot_id
            )
        )
        review = result.scalar_one()
        assert review.previous_snapshot_id == previous_id

    @pytest.mark.asyncio
    async def test_capture_returns_400_when_not_connected(
        self, client: AsyncClient
    ) -> None:
        response = await client.post("/api/iso/snapshots/capture")
        assert response.status_code == 400


class TestListSnapshots:
    @pytest.mark.asyncio
    async def test_list_snapshots_empty(self, client: AsyncClient) -> None:
        response = await client.get("/api/iso/snapshots")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_list_snapshots_returns_summaries(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone

        snap = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={"domain": "test.com"},
            data={"users": []},
            summary={"total_users": 5},
        )
        db_session.add(snap)
        await db_session.flush()

        response = await client.get("/api/iso/snapshots")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["summary"]["total_users"] == 5
        assert "data" not in data["items"][0]

    @pytest.mark.asyncio
    async def test_list_snapshots_pagination(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone

        for i in range(3):
            snap = AccessSnapshotDB(
                provider="google_workspace",
                captured_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                data_version="1",
                source_metadata={},
                data={"users": []},
                summary={},
            )
            db_session.add(snap)
        await db_session.flush()

        response = await client.get("/api/iso/snapshots?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["pages"] == 2

    @pytest.mark.asyncio
    async def test_list_snapshots_filter_by_provider(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone

        snap1 = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={},
            summary={},
        )
        snap2 = AccessSnapshotDB(
            provider="azure_ad",
            captured_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={},
            summary={},
        )
        db_session.add_all([snap1, snap2])
        await db_session.flush()

        response = await client.get(
            "/api/iso/snapshots?provider=google_workspace"
        )
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["provider"] == "google_workspace"


class TestSnapshotDetail:
    @pytest.mark.asyncio
    async def test_get_snapshot_detail(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone

        snap = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={"domain": "empresa.com"},
            data={"users": [{"id": "u1", "email": "a@empresa.com"}]},
            summary={"total_users": 1},
        )
        db_session.add(snap)
        await db_session.flush()

        response = await client.get(f"/api/iso/snapshots/{snap.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(snap.id)
        assert data["data"]["users"][0]["email"] == "a@empresa.com"
        assert data["source_metadata"]["domain"] == "empresa.com"

    @pytest.mark.asyncio
    async def test_get_snapshot_not_found(self, client: AsyncClient) -> None:
        fake_id = uuid4()
        response = await client.get(f"/api/iso/snapshots/{fake_id}")
        assert response.status_code == 404


class TestSnapshotRouterWiring:
    @pytest.mark.asyncio
    async def test_snapshots_accessible_via_iso_prefix(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/api/iso/snapshots")
        assert response.status_code == 200
