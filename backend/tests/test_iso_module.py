"""Tests for ISO module foundation."""

import pytest
import pytest_asyncio
from datetime import datetime, date, timezone
from uuid import uuid4

from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.models.access_review import AccessReviewDB


class TestIsoRouterMount:
    def test_iso_router_imported(self) -> None:
        from app.modules.iso.router import router
        assert router is not None


class TestAccessSnapshotModel:
    @pytest.mark.asyncio
    async def test_create_snapshot(self, db_session) -> None:
        snapshot = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime.now(timezone.utc),
            captured_by=None,
            data={
                "users": [],
                "groups": [],
                "group_members": {},
                "role_assignments": [],
            },
            summary={
                "total_users": 0,
                "active_users": 0,
                "suspended_users": 0,
                "total_admins": 0,
                "external_members": 0,
                "total_groups": 0,
            },
            source_metadata={
                "domain": "test.com",
                "collector": "google_workspace",
                "collector_version": "1",
                "scopes": [],
                "run_mode": "manual",
            },
        )
        db_session.add(snapshot)
        await db_session.flush()

        assert snapshot.id is not None
        assert snapshot.provider == "google_workspace"
        assert snapshot.data_version == "1"
        assert snapshot.data["users"] == []
        assert snapshot.summary["total_users"] == 0
        assert snapshot.created_at is not None

    @pytest.mark.asyncio
    async def test_snapshot_with_captured_by(self, db_session) -> None:
        from app.models.user import UserDB

        user = UserDB(email="admin@test.com", role="admin")
        db_session.add(user)
        await db_session.flush()

        snapshot = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime.now(timezone.utc),
            captured_by=user.id,
            data={
                "users": [],
                "groups": [],
                "group_members": {},
                "role_assignments": [],
            },
            summary={},
            source_metadata={},
        )
        db_session.add(snapshot)
        await db_session.flush()

        assert snapshot.captured_by == user.id


class TestAccessReviewModel:
    @pytest.mark.asyncio
    async def test_create_review(self, db_session) -> None:
        from app.models.user import UserDB

        user = UserDB(email="reviewer@test.com", role="admin")
        db_session.add(user)
        await db_session.flush()

        snapshot = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime.now(timezone.utc),
            data={
                "users": [],
                "groups": [],
                "group_members": {},
                "role_assignments": [],
            },
            summary={},
            source_metadata={},
        )
        db_session.add(snapshot)
        await db_session.flush()

        review = AccessReviewDB(
            snapshot_id=snapshot.id,
            previous_snapshot_id=None,
            reviewer_id=user.id,
            status="draft",
            scope="All users and groups",
        )
        db_session.add(review)
        await db_session.flush()

        assert review.id is not None
        assert review.status == "draft"
        assert review.snapshot_id == snapshot.id
        assert review.previous_snapshot_id is None
        assert review.signed_by is None
        assert review.signed_at is None
        assert review.created_at is not None

    @pytest.mark.asyncio
    async def test_review_signed(self, db_session) -> None:
        from app.models.user import UserDB

        user = UserDB(email="signer@test.com", role="admin")
        db_session.add(user)
        await db_session.flush()

        snapshot = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime.now(timezone.utc),
            data={},
            summary={},
            source_metadata={},
        )
        db_session.add(snapshot)
        await db_session.flush()

        review = AccessReviewDB(
            snapshot_id=snapshot.id,
            reviewer_id=user.id,
            status="signed",
            scope="All users and groups",
            signed_by=user.id,
            signed_at=datetime.now(timezone.utc),
        )
        db_session.add(review)
        await db_session.flush()

        assert review.status == "signed"
        assert review.signed_by == user.id
        assert review.signed_at is not None
