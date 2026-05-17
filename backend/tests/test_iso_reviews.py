"""Tests for ISO access review API endpoints."""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.iso_fixtures import (
    DEV_USER_ID,
    ensure_dev_user,
    make_action,
    make_review,
    make_snapshot,
)


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
    async def test_list_reviews_returns_items(self, client: AsyncClient, db_session) -> None:
        snapshot = await make_snapshot(db_session)
        await make_review(db_session, snapshot.id)

        response = await client.get("/api/iso/reviews")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "draft"

    @pytest.mark.asyncio
    async def test_list_reviews_filter_by_status(self, client: AsyncClient, db_session) -> None:
        snapshot = await make_snapshot(db_session)
        await make_review(db_session, snapshot.id, status="draft")
        snapshot2 = await make_snapshot(db_session)
        await make_review(db_session, snapshot2.id, status="signed")

        response = await client.get("/api/iso/reviews?status=draft")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "draft"

    @pytest.mark.asyncio
    async def test_list_reviews_pagination(self, client: AsyncClient, db_session) -> None:
        for _ in range(3):
            snapshot = await make_snapshot(db_session)
            await make_review(db_session, snapshot.id)

        response = await client.get("/api/iso/reviews?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["pages"] == 2


class TestReviewDetail:
    @pytest.mark.asyncio
    async def test_get_review_with_actions(self, client: AsyncClient, db_session) -> None:
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id)
        action = await make_action(db_session, review.id, action_taken="accepted")

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
    async def test_update_review_notes(self, client: AsyncClient, db_session) -> None:
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id)

        response = await client.patch(
            f"/api/iso/reviews/{review.id}",
            json={"notes": "Updated notes"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Updated notes"

    @pytest.mark.asyncio
    async def test_update_review_rejects_signed(self, client: AsyncClient, db_session) -> None:
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id, status="signed")

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
        await ensure_dev_user(db_session)
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id)
        action = await make_action(db_session, review.id)

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
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id, status="signed")
        action = await make_action(db_session, review.id)

        response = await client.patch(
            f"/api/iso/reviews/{review.id}/actions/{action.id}",
            json={"action_taken": "accepted"},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_update_action_not_found(self, client: AsyncClient, db_session) -> None:
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id)
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
        snapshot = await make_snapshot(db_session)
        review1 = await make_review(db_session, snapshot.id)
        snapshot2 = await make_snapshot(db_session)
        review2 = await make_review(db_session, snapshot2.id)
        action = await make_action(db_session, review1.id)

        response = await client.patch(
            f"/api/iso/reviews/{review2.id}/actions/{action.id}",
            json={"action_taken": "accepted"},
        )
        assert response.status_code == 404


class TestSignReview:
    @pytest.mark.asyncio
    async def test_sign_review_success(self, client: AsyncClient, db_session) -> None:
        await ensure_dev_user(db_session)
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id)
        await make_action(db_session, review.id, action_taken="accepted")

        response = await client.post(f"/api/iso/reviews/{review.id}/sign")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "signed"
        assert data["signed_at"] is not None
        assert data["signed_by"] == str(DEV_USER_ID)

    @pytest.mark.asyncio
    async def test_sign_review_fails_with_unresolved_actions(
        self, client: AsyncClient, db_session
    ) -> None:
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id)
        await make_action(db_session, review.id)

        response = await client.post(f"/api/iso/reviews/{review.id}/sign")
        assert response.status_code == 409
        assert "1 unresolved action(s)" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_sign_review_already_signed(self, client: AsyncClient, db_session) -> None:
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id, status="signed")

        response = await client.post(f"/api/iso/reviews/{review.id}/sign")
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_sign_review_not_found(self, client: AsyncClient) -> None:
        fake_id = uuid4()
        response = await client.post(f"/api/iso/reviews/{fake_id}/sign")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_sign_review_no_actions_succeeds(self, client: AsyncClient, db_session) -> None:
        await ensure_dev_user(db_session)
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id)

        response = await client.post(f"/api/iso/reviews/{review.id}/sign")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "signed"

    @pytest.mark.asyncio
    async def test_sign_with_bulk_actions_and_notes(self, client: AsyncClient, db_session) -> None:
        await ensure_dev_user(db_session)
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id)
        action = await make_action(db_session, review.id)

        response = await client.post(
            f"/api/iso/reviews/{review.id}/sign",
            json={
                "notes": "Bulk review notes",
                "actions": [
                    {
                        "action_id": str(action.id),
                        "action_taken": "accepted",
                        "justification": "Looks good",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "signed"
        assert data["notes"] == "Bulk review notes"

        detail = await client.get(f"/api/iso/reviews/{review.id}")
        action_data = detail.json()["actions"][0]
        assert action_data["action_taken"] == "accepted"
        assert action_data["justification"] == "Looks good"

    @pytest.mark.asyncio
    async def test_sign_with_unresolved_actions_after_partial_bulk(
        self, client: AsyncClient, db_session
    ) -> None:
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id)
        action1 = await make_action(db_session, review.id)
        await make_action(db_session, review.id)

        response = await client.post(
            f"/api/iso/reviews/{review.id}/sign",
            json={
                "actions": [
                    {
                        "action_id": str(action1.id),
                        "action_taken": "accepted",
                    }
                ],
            },
        )
        assert response.status_code == 409
        assert "1 unresolved action(s)" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_sign_with_empty_body_when_resolved(
        self, client: AsyncClient, db_session
    ) -> None:
        await ensure_dev_user(db_session)
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id)
        await make_action(db_session, review.id, action_taken="accepted")

        response = await client.post(
            f"/api/iso/reviews/{review.id}/sign",
            json={},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "signed"

    @pytest.mark.asyncio
    async def test_sign_with_invalid_action_id(self, client: AsyncClient, db_session) -> None:
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id)

        response = await client.post(
            f"/api/iso/reviews/{review.id}/sign",
            json={
                "actions": [
                    {
                        "action_id": str(uuid4()),
                        "action_taken": "accepted",
                    }
                ],
            },
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_sign_with_exception_and_date(self, client: AsyncClient, db_session) -> None:
        await ensure_dev_user(db_session)
        snapshot = await make_snapshot(db_session)
        review = await make_review(db_session, snapshot.id)
        action = await make_action(db_session, review.id)

        response = await client.post(
            f"/api/iso/reviews/{review.id}/sign",
            json={
                "actions": [
                    {
                        "action_id": str(action.id),
                        "action_taken": "exception",
                        "justification": "Temporary access",
                        "exception_until": "2026-06-01",
                    }
                ],
            },
        )
        assert response.status_code == 200

        detail = await client.get(f"/api/iso/reviews/{review.id}")
        action_data = detail.json()["actions"][0]
        assert action_data["action_taken"] == "exception"
        assert action_data["exception_until"] == "2026-06-01"


class TestReviewRouterWiring:
    @pytest.mark.asyncio
    async def test_reviews_accessible_via_iso_prefix(self, client: AsyncClient) -> None:
        response = await client.get("/api/iso/reviews")
        assert response.status_code == 200
