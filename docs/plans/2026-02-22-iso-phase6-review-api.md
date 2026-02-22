# ISO Phase 6: Review API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the CRUD + sign-off API for access reviews and their actions.

**Architecture:** Five endpoints in a new `api/reviews.py` sub-router. Two guard validations: signed reviews are immutable, signing requires all actions resolved. Reuses existing models/schemas plus one new detail schema that embeds actions.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, pytest + httpx AsyncClient

---

### Task 1: Add review detail schema with embedded actions

**Files:**
- Modify: `backend/app/modules/iso/schemas.py`
- Test: `backend/tests/test_iso_module.py` (existing schema tests)

**Step 1: Add `AccessReviewDetailResponse` schema**

Add after `AccessReviewResponse` in `backend/app/modules/iso/schemas.py`:

```python
class AccessReviewDetailResponse(AccessReviewResponse):
    actions: list[AccessReviewActionResponse] = []
```

That's all for this task — a one-liner extending the existing response schema.

**Step 2: Commit**

```bash
git add backend/app/modules/iso/schemas.py
git commit -m "feat(iso): add AccessReviewDetailResponse schema with embedded actions"
```

---

### Task 2: Create reviews API with list and detail endpoints

**Files:**
- Create: `backend/app/modules/iso/api/reviews.py`
- Modify: `backend/app/modules/iso/router.py` (wire sub-router)
- Test: `backend/tests/test_iso_reviews.py`

**Step 1: Write failing tests**

Create `backend/tests/test_iso_reviews.py`:

```python
"""Tests for ISO review API endpoints."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select

from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB


def _make_snapshot(db_session, **kwargs):
    """Helper: create and flush an AccessSnapshotDB."""
    defaults = {
        "provider": "google_workspace",
        "captured_at": datetime(2026, 2, 1, tzinfo=timezone.utc),
        "data_version": "1",
        "source_metadata": {},
        "data": {"users": [], "groups": [], "group_members": {}, "role_assignments": []},
        "summary": {"total_users": 0},
    }
    defaults.update(kwargs)
    snap = AccessSnapshotDB(**defaults)
    db_session.add(snap)
    return snap


async def _make_review(db_session, snapshot_id, **kwargs):
    """Helper: create and flush an AccessReviewDB."""
    defaults = {
        "snapshot_id": snapshot_id,
        "status": "draft",
        "scope": "All users and groups",
    }
    defaults.update(kwargs)
    review = AccessReviewDB(**defaults)
    db_session.add(review)
    await db_session.flush()
    return review


async def _make_action(db_session, review_id, **kwargs):
    """Helper: create and flush an AccessReviewActionDB."""
    defaults = {
        "review_id": review_id,
        "subject_type": "user",
        "subject_id": "test@example.com",
        "change_type": "new_user",
    }
    defaults.update(kwargs)
    action = AccessReviewActionDB(**defaults)
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

    @pytest.mark.asyncio
    async def test_list_reviews_returns_items(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        await _make_review(db_session, snap.id)

        response = await client.get("/api/iso/reviews")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "draft"

    @pytest.mark.asyncio
    async def test_list_reviews_filter_by_status(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        await _make_review(db_session, snap.id, status="draft")
        await _make_review(db_session, snap.id, status="signed")

        response = await client.get("/api/iso/reviews?status=draft")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "draft"

    @pytest.mark.asyncio
    async def test_list_reviews_pagination(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        for _ in range(3):
            await _make_review(db_session, snap.id)

        response = await client.get("/api/iso/reviews?page=1&page_size=2")
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["pages"] == 2


class TestReviewDetail:
    @pytest.mark.asyncio
    async def test_get_review_detail(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        review = await _make_review(db_session, snap.id, notes="test notes")
        action = await _make_action(db_session, review.id)

        response = await client.get(f"/api/iso/reviews/{review.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(review.id)
        assert data["notes"] == "test notes"
        assert len(data["actions"]) == 1
        assert data["actions"][0]["change_type"] == "new_user"

    @pytest.mark.asyncio
    async def test_get_review_not_found(self, client: AsyncClient) -> None:
        response = await client.get(f"/api/iso/reviews/{uuid4()}")
        assert response.status_code == 404


class TestReviewRouterWiring:
    @pytest.mark.asyncio
    async def test_reviews_accessible_via_iso_prefix(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/api/iso/reviews")
        assert response.status_code == 200
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_reviews.py -v`
Expected: FAIL (module not found / 404)

**Step 3: Create `reviews.py` router**

Create `backend/app/modules/iso/api/reviews.py`:

```python
"""ISO review API endpoints."""

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.api.schemas.common import PaginatedResponse
from app.database import get_db
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.schemas import (
    AccessReviewActionResponse,
    AccessReviewDetailResponse,
    AccessReviewResponse,
)

DBSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter()


@router.get("", response_model=PaginatedResponse[AccessReviewResponse])
async def list_reviews(
    db: DBSession,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    query = select(AccessReviewDB).order_by(AccessReviewDB.created_at.desc())
    count_query = select(func.count(AccessReviewDB.id))

    if status:
        query = query.where(AccessReviewDB.status == status)
        count_query = count_query.where(AccessReviewDB.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    reviews = result.scalars().all()

    return {
        "items": reviews,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total > 0 else 0,
    }


@router.get("/{review_id}", response_model=AccessReviewDetailResponse)
async def get_review(review_id: UUID, db: DBSession) -> dict:
    result = await db.execute(
        select(AccessReviewDB).where(AccessReviewDB.id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    actions_result = await db.execute(
        select(AccessReviewActionDB)
        .where(AccessReviewActionDB.review_id == review_id)
        .order_by(AccessReviewActionDB.created_at)
    )
    actions = actions_result.scalars().all()

    return {
        **{c.key: getattr(review, c.key) for c in review.__table__.columns},
        "actions": actions,
    }
```

**Step 4: Wire the sub-router in `router.py`**

Add to `backend/app/modules/iso/router.py`:

```python
from app.modules.iso.api import reviews as reviews_router

router.include_router(
    reviews_router.router, prefix="/reviews", tags=["iso-reviews"]
)
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_iso_reviews.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/app/modules/iso/api/reviews.py backend/app/modules/iso/router.py backend/tests/test_iso_reviews.py
git commit -m "feat(iso): add review list and detail API endpoints"
```

---

### Task 3: Add PATCH review update and PATCH action update endpoints

**Files:**
- Modify: `backend/app/modules/iso/api/reviews.py`
- Modify: `backend/tests/test_iso_reviews.py`

**Step 1: Write failing tests**

Add to `backend/tests/test_iso_reviews.py`:

```python
class TestUpdateReview:
    @pytest.mark.asyncio
    async def test_update_review_notes(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        review = await _make_review(db_session, snap.id)

        response = await client.patch(
            f"/api/iso/reviews/{review.id}",
            json={"notes": "Updated notes"},
        )
        assert response.status_code == 200
        assert response.json()["notes"] == "Updated notes"

    @pytest.mark.asyncio
    async def test_update_signed_review_rejected(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        review = await _make_review(db_session, snap.id, status="signed")

        response = await client.patch(
            f"/api/iso/reviews/{review.id}",
            json={"notes": "Try to update"},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_update_review_not_found(self, client: AsyncClient) -> None:
        response = await client.patch(
            f"/api/iso/reviews/{uuid4()}",
            json={"notes": "x"},
        )
        assert response.status_code == 404


class TestUpdateAction:
    @pytest.mark.asyncio
    async def test_update_action_taken(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        review = await _make_review(db_session, snap.id)
        action = await _make_action(db_session, review.id)

        response = await client.patch(
            f"/api/iso/reviews/{review.id}/actions/{action.id}",
            json={"action_taken": "accepted", "justification": "Expected change"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action_taken"] == "accepted"
        assert data["justification"] == "Expected change"

    @pytest.mark.asyncio
    async def test_update_action_on_signed_review_rejected(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        review = await _make_review(db_session, snap.id, status="signed")
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
        snap = _make_snapshot(db_session)
        await db_session.flush()
        review = await _make_review(db_session, snap.id)

        response = await client.patch(
            f"/api/iso/reviews/{review.id}/actions/{uuid4()}",
            json={"action_taken": "accepted"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_action_wrong_review(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        review1 = await _make_review(db_session, snap.id)
        review2 = await _make_review(db_session, snap.id)
        action = await _make_action(db_session, review1.id)

        response = await client.patch(
            f"/api/iso/reviews/{review2.id}/actions/{action.id}",
            json={"action_taken": "accepted"},
        )
        assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_reviews.py::TestUpdateReview tests/test_iso_reviews.py::TestUpdateAction -v`
Expected: FAIL (405 Method Not Allowed)

**Step 3: Add PATCH endpoints to `reviews.py`**

Append to `backend/app/modules/iso/api/reviews.py`:

```python
from app.modules.iso.schemas import (
    AccessReviewActionUpdate,
    AccessReviewUpdate,
    # ... existing imports
)


@router.patch("/{review_id}", response_model=AccessReviewResponse)
async def update_review(
    review_id: UUID, body: AccessReviewUpdate, db: DBSession
) -> AccessReviewDB:
    result = await db.execute(
        select(AccessReviewDB).where(AccessReviewDB.id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.status == "signed":
        raise HTTPException(status_code=409, detail="Signed review cannot be modified")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(review, field, value)
    await db.flush()
    await db.refresh(review)
    return review


@router.patch(
    "/{review_id}/actions/{action_id}",
    response_model=AccessReviewActionResponse,
)
async def update_action(
    review_id: UUID,
    action_id: UUID,
    body: AccessReviewActionUpdate,
    db: DBSession,
) -> AccessReviewActionDB:
    result = await db.execute(
        select(AccessReviewDB).where(AccessReviewDB.id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.status == "signed":
        raise HTTPException(status_code=409, detail="Signed review cannot be modified")

    result = await db.execute(
        select(AccessReviewActionDB).where(
            AccessReviewActionDB.id == action_id,
            AccessReviewActionDB.review_id == review_id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if isinstance(value, Enum):
            value = value.value
        setattr(action, field, value)
    await db.flush()
    await db.refresh(action)
    return action
```

Note: add `from enum import Enum` at the top of the file.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_reviews.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/modules/iso/api/reviews.py backend/tests/test_iso_reviews.py
git commit -m "feat(iso): add PATCH endpoints for review and action updates"
```

---

### Task 4: Add POST sign endpoint with validation

**Files:**
- Modify: `backend/app/modules/iso/api/reviews.py`
- Modify: `backend/tests/test_iso_reviews.py`

**Step 1: Write failing tests**

Add to `backend/tests/test_iso_reviews.py`:

```python
class TestSignReview:
    @pytest.mark.asyncio
    async def test_sign_review_success(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        review = await _make_review(db_session, snap.id, status="draft")
        action = await _make_action(db_session, review.id, action_taken="accepted")

        response = await client.post(f"/api/iso/reviews/{review.id}/sign")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "signed"
        assert data["signed_at"] is not None

    @pytest.mark.asyncio
    async def test_sign_review_fails_with_unresolved_actions(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        review = await _make_review(db_session, snap.id)
        await _make_action(db_session, review.id)  # no action_taken

        response = await client.post(f"/api/iso/reviews/{review.id}/sign")
        assert response.status_code == 409
        assert "unresolved" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_sign_already_signed_review(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        review = await _make_review(db_session, snap.id, status="signed")

        response = await client.post(f"/api/iso/reviews/{review.id}/sign")
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_sign_review_not_found(self, client: AsyncClient) -> None:
        response = await client.post(f"/api/iso/reviews/{uuid4()}/sign")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_sign_review_with_no_actions_succeeds(
        self, client: AsyncClient, db_session
    ) -> None:
        snap = _make_snapshot(db_session)
        await db_session.flush()
        review = await _make_review(db_session, snap.id)

        response = await client.post(f"/api/iso/reviews/{review.id}/sign")
        assert response.status_code == 200
        assert response.json()["status"] == "signed"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_reviews.py::TestSignReview -v`
Expected: FAIL (405 Method Not Allowed)

**Step 3: Add sign endpoint**

Append to `backend/app/modules/iso/api/reviews.py`:

```python
from datetime import datetime, timezone


@router.post("/{review_id}/sign", response_model=AccessReviewResponse)
async def sign_review(review_id: UUID, db: DBSession) -> AccessReviewDB:
    result = await db.execute(
        select(AccessReviewDB).where(AccessReviewDB.id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.status == "signed":
        raise HTTPException(status_code=409, detail="Review is already signed")

    actions_result = await db.execute(
        select(AccessReviewActionDB).where(
            AccessReviewActionDB.review_id == review_id
        )
    )
    actions = actions_result.scalars().all()
    unresolved = [a for a in actions if a.action_taken is None]
    if unresolved:
        raise HTTPException(
            status_code=409,
            detail=f"{len(unresolved)} unresolved action(s) must be completed before signing",
        )

    review.status = "signed"
    review.signed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(review)
    return review
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_reviews.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/modules/iso/api/reviews.py backend/tests/test_iso_reviews.py
git commit -m "feat(iso): add sign endpoint with unresolved-actions validation"
```

---

### Task 5: Run full test suite + lint

**Step 1: Run all backend tests**

Run: `pytest`
Expected: all tests pass (906+ tests)

**Step 2: Run linters**

Run: `ruff check app/ && black --check app/`
Expected: no issues

**Step 3: Fix any lint issues if needed**

**Step 4: Final commit if lint fixes needed**

```bash
git add -A && git commit -m "style: fix lint issues in review API"
```
