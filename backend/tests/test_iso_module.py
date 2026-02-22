"""Tests for ISO module foundation."""

import pytest
import pytest_asyncio
from datetime import datetime, date, timezone
from uuid import uuid4

from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB


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


class TestAccessReviewActionModel:
    @pytest.mark.asyncio
    async def test_create_action(self, db_session) -> None:
        from app.models.user import UserDB

        user = UserDB(email="reviewer@test.com", role="admin")
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
            status="draft",
            scope="All users and groups",
        )
        db_session.add(review)
        await db_session.flush()

        action = AccessReviewActionDB(
            review_id=review.id,
            subject_type="user",
            subject_id="newuser@test.com",
            subject_label="New User",
            change_type="new_user",
            previous_value=None,
            current_value={
                "email": "newuser@test.com",
                "name": "New User",
            },
        )
        db_session.add(action)
        await db_session.flush()

        assert action.id is not None
        assert action.subject_type == "user"
        assert action.change_type == "new_user"
        assert action.action_taken is None
        assert action.justification is None

    @pytest.mark.asyncio
    async def test_action_with_decision(self, db_session) -> None:
        from app.models.user import UserDB

        user = UserDB(email="approver@test.com", role="admin")
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
            status="draft",
            scope="All users and groups",
        )
        db_session.add(review)
        await db_session.flush()

        action = AccessReviewActionDB(
            review_id=review.id,
            subject_type="user",
            subject_id="external@vendor.com",
            change_type="new_external",
            current_value={
                "external_added": ["external@vendor.com"],
            },
            action_taken="exception",
            justification="Approved vendor access for Q1 project",
            approved_by=user.id,
            exception_until=date(2026, 6, 30),
        )
        db_session.add(action)
        await db_session.flush()

        assert action.action_taken == "exception"
        assert action.exception_until == date(2026, 6, 30)
        assert action.approved_by == user.id
