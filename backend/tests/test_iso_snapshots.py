"""Tests for ISO snapshot API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from httpx import AsyncClient

from app.core.token_encryption import encrypt_token
from app.models.oauth import OAuthTokenDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.models.access_review import AccessReviewDB
from tests.iso_fixtures import ensure_dev_user


class TestCaptureEndpoint:
    @pytest.mark.asyncio
    async def test_capture_creates_snapshot(
        self, client: AsyncClient, db_session
    ) -> None:
        await ensure_dev_user(db_session)
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("ya29.test"),
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

        await ensure_dev_user(db_session)
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("ya29.test"),
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
            select(AccessReviewDB).where(AccessReviewDB.snapshot_id == snapshot_id)
        )
        review = result.scalar_one_or_none()
        assert review is not None
        assert review.status == "draft"
        assert review.scope == "All users and groups"
        assert review.previous_snapshot_id is None
        assert review.reviewer_id is not None

    @pytest.mark.asyncio
    async def test_capture_links_previous_snapshot(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone
        from sqlalchemy import select

        await ensure_dev_user(db_session)
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("ya29.test"),
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        previous = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={
                "users": [],
                "groups": [],
                "group_members": {},
                "role_assignments": [],
            },
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
            select(AccessReviewDB).where(AccessReviewDB.snapshot_id == snapshot_id)
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

        response = await client.get("/api/iso/snapshots?provider=google_workspace")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["provider"] == "google_workspace"


class TestSnapshotDetail:
    @pytest.mark.asyncio
    async def test_get_snapshot_detail(self, client: AsyncClient, db_session) -> None:
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


class TestCaptureWithDiff:
    @pytest.mark.asyncio
    async def test_capture_populates_diff_and_actions(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone
        from sqlalchemy import select

        await ensure_dev_user(db_session)
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("ya29.test"),
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        previous = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={"domain": "empresa.com"},
            data={
                "users": [
                    {
                        "id": "u1",
                        "email": "a@empresa.com",
                        "name": "A",
                        "suspended": False,
                        "org_unit_path": "/",
                    },
                ],
                "groups": [],
                "group_members": {},
                "role_assignments": [],
            },
            summary={"total_users": 1},
        )
        db_session.add(previous)
        await db_session.flush()

        users_resp = MagicMock()
        users_resp.json.return_value = {
            "users": [
                {
                    "id": "u1",
                    "primaryEmail": "a@empresa.com",
                    "name": {"fullName": "A"},
                    "suspended": False,
                    "orgUnitPath": "/",
                },
                {
                    "id": "u2",
                    "primaryEmail": "new@empresa.com",
                    "name": {"fullName": "New"},
                    "suspended": False,
                    "orgUnitPath": "/",
                },
            ],
        }
        users_resp.raise_for_status = MagicMock()

        empty_resp = MagicMock()
        empty_resp.json.return_value = {}
        empty_resp.raise_for_status = MagicMock()

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=[users_resp, empty_resp, empty_resp, empty_resp],
        ):
            response = await client.post("/api/iso/snapshots/capture")

        assert response.status_code == 201

        result = await db_session.execute(
            select(AccessReviewDB).where(
                AccessReviewDB.snapshot_id == response.json()["id"]
            )
        )
        review = result.scalar_one()
        assert review.diff_summary is not None
        assert review.diff_summary["total_changes"] >= 1
        assert review.diff_summary["new_user"] >= 1

        from app.modules.iso.models.access_review_action import AccessReviewActionDB

        result = await db_session.execute(
            select(AccessReviewActionDB).where(
                AccessReviewActionDB.review_id == review.id
            )
        )
        actions = result.scalars().all()
        assert len(actions) >= 1
        new_user_actions = [a for a in actions if a.change_type == "new_user"]
        assert len(new_user_actions) >= 1

    @pytest.mark.asyncio
    async def test_first_snapshot_no_diff(
        self, client: AsyncClient, db_session
    ) -> None:
        from sqlalchemy import select

        await ensure_dev_user(db_session)
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("ya29.test"),
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "users": [
                {
                    "id": "u1",
                    "primaryEmail": "a@empresa.com",
                    "name": {"fullName": "A"},
                    "suspended": False,
                    "orgUnitPath": "/",
                },
            ],
            "groups": [],
            "members": [],
            "items": [],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            response = await client.post("/api/iso/snapshots/capture")

        assert response.status_code == 201

        result = await db_session.execute(
            select(AccessReviewDB).where(
                AccessReviewDB.snapshot_id == response.json()["id"]
            )
        )
        review = result.scalar_one()
        assert review.diff_summary is None
        assert review.previous_snapshot_id is None


class TestSnapshotReview:
    @pytest.mark.asyncio
    async def test_get_snapshot_review(self, client: AsyncClient, db_session) -> None:
        from datetime import datetime, timezone

        snap = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={"users": []},
            summary={},
        )
        db_session.add(snap)
        await db_session.flush()

        review = AccessReviewDB(
            snapshot_id=snap.id,
            reviewer_id=None,
            status="draft",
            scope="All users and groups",
        )
        db_session.add(review)
        await db_session.flush()

        response = await client.get(f"/api/iso/snapshots/{snap.id}/review")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(review.id)
        assert data["snapshot_id"] == str(snap.id)
        assert data["status"] == "draft"
        assert data["scope"] == "All users and groups"
        assert isinstance(data["actions"], list)

    @pytest.mark.asyncio
    async def test_get_snapshot_review_with_actions(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone
        from app.modules.iso.models.access_review_action import AccessReviewActionDB

        snap = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={"users": []},
            summary={},
        )
        db_session.add(snap)
        await db_session.flush()

        review = AccessReviewDB(
            snapshot_id=snap.id,
            status="draft",
            scope="All users and groups",
        )
        db_session.add(review)
        await db_session.flush()

        action = AccessReviewActionDB(
            review_id=review.id,
            subject_type="user",
            subject_id="u1",
            subject_label="John Doe",
            change_type="new_user",
        )
        db_session.add(action)
        await db_session.flush()

        response = await client.get(f"/api/iso/snapshots/{snap.id}/review")
        assert response.status_code == 200
        data = response.json()
        assert len(data["actions"]) == 1
        assert data["actions"][0]["subject_label"] == "John Doe"
        assert data["actions"][0]["change_type"] == "new_user"

    @pytest.mark.asyncio
    async def test_get_snapshot_review_not_found(self, client: AsyncClient) -> None:
        fake_id = uuid4()
        response = await client.get(f"/api/iso/snapshots/{fake_id}/review")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_snapshot_review_no_review_for_snapshot(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone

        snap = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={"users": []},
            summary={},
        )
        db_session.add(snap)
        await db_session.flush()

        response = await client.get(f"/api/iso/snapshots/{snap.id}/review")
        assert response.status_code == 404


class TestListSnapshotsReviewStatus:
    @pytest.mark.asyncio
    async def test_list_returns_review_status(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone

        snap = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={"users": []},
            summary={"total_users": 5},
        )
        db_session.add(snap)
        await db_session.flush()

        review = AccessReviewDB(
            snapshot_id=snap.id,
            status="signed",
            scope="All users and groups",
        )
        db_session.add(review)
        await db_session.flush()

        response = await client.get("/api/iso/snapshots")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["review_status"] == "signed"

    @pytest.mark.asyncio
    async def test_list_returns_null_review_status_when_no_review(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone

        snap = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={"users": []},
            summary={"total_users": 5},
        )
        db_session.add(snap)
        await db_session.flush()

        response = await client.get("/api/iso/snapshots")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["review_status"] is None


class TestDeleteSnapshot:
    @pytest.mark.asyncio
    async def test_delete_snapshot_no_review(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone

        snap = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={"users": []},
            summary={},
        )
        db_session.add(snap)
        await db_session.flush()
        snap_id = snap.id

        response = await client.delete(f"/api/iso/snapshots/{snap_id}")
        assert response.status_code == 204

        from sqlalchemy import select

        result = await db_session.execute(
            select(AccessSnapshotDB).where(AccessSnapshotDB.id == snap_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_snapshot_cascades_review_and_actions(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone
        from sqlalchemy import select
        from app.modules.iso.models.access_review_action import AccessReviewActionDB

        snap = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={"users": []},
            summary={},
        )
        db_session.add(snap)
        await db_session.flush()

        review = AccessReviewDB(
            snapshot_id=snap.id,
            status="draft",
            scope="All users and groups",
        )
        db_session.add(review)
        await db_session.flush()

        action = AccessReviewActionDB(
            review_id=review.id,
            subject_type="user",
            subject_id="u1",
            subject_label="Test User",
            change_type="new_user",
        )
        db_session.add(action)
        await db_session.flush()
        snap_id = snap.id
        review_id = review.id
        action_id = action.id

        response = await client.delete(f"/api/iso/snapshots/{snap_id}")
        assert response.status_code == 204

        result = await db_session.execute(
            select(AccessSnapshotDB).where(AccessSnapshotDB.id == snap_id)
        )
        assert result.scalar_one_or_none() is None

        result = await db_session.execute(
            select(AccessReviewDB).where(AccessReviewDB.id == review_id)
        )
        assert result.scalar_one_or_none() is None

        result = await db_session.execute(
            select(AccessReviewActionDB).where(AccessReviewActionDB.id == action_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_snapshot_not_found(self, client: AsyncClient) -> None:
        fake_id = uuid4()
        response = await client.delete(f"/api/iso/snapshots/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_snapshot_nullifies_previous_snapshot_ref(
        self, client: AsyncClient, db_session
    ) -> None:
        from datetime import datetime, timezone
        from sqlalchemy import select

        snap1 = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={"users": []},
            summary={},
        )
        snap2 = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            data_version="1",
            source_metadata={},
            data={"users": []},
            summary={},
        )
        db_session.add_all([snap1, snap2])
        await db_session.flush()

        review = AccessReviewDB(
            snapshot_id=snap2.id,
            previous_snapshot_id=snap1.id,
            status="draft",
            scope="All users and groups",
        )
        db_session.add(review)
        await db_session.flush()
        review_id = review.id

        response = await client.delete(f"/api/iso/snapshots/{snap1.id}")
        assert response.status_code == 204

        result = await db_session.execute(
            select(AccessReviewDB).where(AccessReviewDB.id == review_id)
        )
        updated_review = result.scalar_one()
        assert updated_review.previous_snapshot_id is None


class TestSnapshotRouterWiring:
    @pytest.mark.asyncio
    async def test_snapshots_accessible_via_iso_prefix(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/api/iso/snapshots")
        assert response.status_code == 200
