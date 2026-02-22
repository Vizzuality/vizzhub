"""Tests for ISO access review API endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB


async def _make_snapshot(db_session) -> AccessSnapshotDB:
    snapshot = AccessSnapshotDB(
        provider="google_workspace",
        captured_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        data_version="1",
        source_metadata={"domain": "test.com"},
        data={"users": []},
        summary={"total_users": 0},
    )
    db_session.add(snapshot)
    await db_session.flush()
    return snapshot


async def _make_review(
    db_session,
    snapshot_id,
    status: str = "draft",
    notes: str | None = None,
) -> AccessReviewDB:
    review = AccessReviewDB(
        snapshot_id=snapshot_id,
        status=status,
        scope="All users and groups",
        notes=notes,
    )
    db_session.add(review)
    await db_session.flush()
    return review


async def _make_action(
    db_session,
    review_id,
    action_taken: str | None = None,
    justification: str | None = None,
) -> AccessReviewActionDB:
    action = AccessReviewActionDB(
        review_id=review_id,
        subject_type="user",
        subject_id="u1",
        subject_label="User One",
        change_type="new_user",
        action_taken=action_taken,
        justification=justification,
    )
    db_session.add(action)
    await db_session.flush()
    return action


class TestListReviews:
    @pytest.mark.asyncio
    async def test_list_reviews_empty(self, client: AsyncClient) -> None:
        response = await client.get("/api/iso/reviews")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_list_reviews_returns_items(
        self, client: AsyncClient, db_session
    ) -> None:
        snapshot = await _make_snapshot(db_session)
        await _make_review(db_session, snapshot.id)

        response = await client.get("/api/iso/reviews")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "draft"

    @pytest.mark.asyncio
    async def test_list_reviews_filter_by_status(
        self, client: AsyncClient, db_session
    ) -> None:
        snapshot = await _make_snapshot(db_session)
        await _make_review(db_session, snapshot.id, status="draft")
        snapshot2 = await _make_snapshot(db_session)
        await _make_review(db_session, snapshot2.id, status="signed")

        response = await client.get("/api/iso/reviews?status=draft")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "draft"

    @pytest.mark.asyncio
    async def test_list_reviews_pagination(
        self, client: AsyncClient, db_session
    ) -> None:
        for _ in range(3):
            snapshot = await _make_snapshot(db_session)
            await _make_review(db_session, snapshot.id)

        response = await client.get("/api/iso/reviews?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["pages"] == 2


class TestReviewDetail:
    @pytest.mark.asyncio
    async def test_get_review_with_actions(
        self, client: AsyncClient, db_session
    ) -> None:
        snapshot = await _make_snapshot(db_session)
        review = await _make_review(db_session, snapshot.id)
        action = await _make_action(db_session, review.id, action_taken="accepted")

        response = await client.get(f"/api/iso/reviews/{review.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(review.id)
        assert data["status"] == "draft"
        assert len(data["actions"]) == 1
        assert data["actions"][0]["id"] == str(action.id)
        assert data["actions"][0]["action_taken"] == "accepted"

    @pytest.mark.asyncio
    async def test_get_review_not_found(self, client: AsyncClient) -> None:
        fake_id = uuid4()
        response = await client.get(f"/api/iso/reviews/{fake_id}")
        assert response.status_code == 404


class TestUpdateReview:
    @pytest.mark.asyncio
    async def test_update_review_notes(
        self, client: AsyncClient, db_session
    ) -> None:
        snapshot = await _make_snapshot(db_session)
        review = await _make_review(db_session, snapshot.id)

        response = await client.patch(
            f"/api/iso/reviews/{review.id}",
            json={"notes": "Updated notes"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Updated notes"

    @pytest.mark.asyncio
    async def test_update_review_rejects_signed(
        self, client: AsyncClient, db_session
    ) -> None:
        snapshot = await _make_snapshot(db_session)
        review = await _make_review(db_session, snapshot.id, status="signed")

        response = await client.patch(
            f"/api/iso/reviews/{review.id}",
            json={"notes": "Should fail"},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_update_review_not_found(self, client: AsyncClient) -> None:
        fake_id = uuid4()
        response = await client.patch(
            f"/api/iso/reviews/{fake_id}",
            json={"notes": "No review"},
        )
        assert response.status_code == 404


class TestUpdateAction:
    @pytest.mark.asyncio
    async def test_update_action_taken_and_justification(
        self, client: AsyncClient, db_session
    ) -> None:
        snapshot = await _make_snapshot(db_session)
        review = await _make_review(db_session, snapshot.id)
        action = await _make_action(db_session, review.id)

        response = await client.patch(
            f"/api/iso/reviews/{review.id}/actions/{action.id}",
            json={"action_taken": "accepted", "justification": "Looks good"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action_taken"] == "accepted"
        assert data["justification"] == "Looks good"

    @pytest.mark.asyncio
    async def test_update_action_rejects_signed_review(
        self, client: AsyncClient, db_session
    ) -> None:
        snapshot = await _make_snapshot(db_session)
        review = await _make_review(db_session, snapshot.id, status="signed")
        action = await _make_action(db_session, review.id)

        response = await client.patch(
            f"/api/iso/reviews/{review.id}/actions/{action.id}",
            json={"action_taken": "accepted"},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_update_action_not_found(
        self, client: AsyncClient, db_session
    ) -> None:
        snapshot = await _make_snapshot(db_session)
        review = await _make_review(db_session, snapshot.id)
        fake_action_id = uuid4()

        response = await client.patch(
            f"/api/iso/reviews/{review.id}/actions/{fake_action_id}",
            json={"action_taken": "accepted"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_action_wrong_review_returns_404(
        self, client: AsyncClient, db_session
    ) -> None:
        snapshot = await _make_snapshot(db_session)
        review1 = await _make_review(db_session, snapshot.id)
        snapshot2 = await _make_snapshot(db_session)
        review2 = await _make_review(db_session, snapshot2.id)
        action = await _make_action(db_session, review1.id)

        response = await client.patch(
            f"/api/iso/reviews/{review2.id}/actions/{action.id}",
            json={"action_taken": "accepted"},
        )
        assert response.status_code == 404


class TestReviewRouterWiring:
    @pytest.mark.asyncio
    async def test_reviews_accessible_via_iso_prefix(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/api/iso/reviews")
        assert response.status_code == 200
