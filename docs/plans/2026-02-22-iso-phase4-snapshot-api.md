# Phase 4: Snapshot API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create the snapshot API endpoints: POST capture (triggers collector + auto-creates draft review), GET list (paginated), and GET detail. Wire the snapshots sub-router into the ISO module router.

**Architecture:** Three endpoints in `api/snapshots.py`. The POST capture endpoint calls `GoogleWorkspaceCollector.capture()`, finds the previous snapshot, creates an `AccessReviewDB` in `draft` status linked to both snapshots, and returns the snapshot. The GET endpoints use the existing `PaginatedResponse` pattern. The diff engine (Phase 5) and review actions will be wired in later.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic v2, pytest + unittest.mock

---

### Task 1: POST /capture endpoint with auto-review creation

**Files:**
- Create: `backend/app/modules/iso/api/snapshots.py`
- Test: `backend/tests/test_iso_snapshots.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_snapshots.py -v --no-header -q`
Expected: FAIL with error (module/file doesn't exist yet)

**Step 3: Write the implementation**

```python
"""ISO snapshot API endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.schemas import AccessSnapshotResponse
from app.modules.iso.services.collectors.google_workspace import (
    GoogleWorkspaceCollector,
)

logger = logging.getLogger(__name__)

DBSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter()


@router.post("/capture", response_model=AccessSnapshotResponse, status_code=201)
async def capture_snapshot(db: DBSession) -> AccessSnapshotDB:
    collector = GoogleWorkspaceCollector(db)
    try:
        snapshot = await collector.capture(run_mode="manual")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = await db.execute(
        select(AccessSnapshotDB)
        .where(AccessSnapshotDB.provider == "google_workspace")
        .where(AccessSnapshotDB.id != snapshot.id)
        .order_by(AccessSnapshotDB.captured_at.desc())
        .limit(1)
    )
    previous = result.scalar_one_or_none()

    review = AccessReviewDB(
        snapshot_id=snapshot.id,
        previous_snapshot_id=previous.id if previous else None,
        reviewer_id=snapshot.captured_by or UUID("00000000-0000-0000-0000-000000000000"),
        status="draft",
        scope="All users and groups",
    )
    db.add(review)
    await db.flush()

    logger.info("Snapshot captured, review %s created in draft", review.id)
    return snapshot
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_snapshots.py -v --no-header -q`
Expected: 4 passed

**Step 5: Commit**

```bash
git add app/modules/iso/api/snapshots.py tests/test_iso_snapshots.py
git commit -m "feat(iso): add POST /capture endpoint with auto-review creation"
```

---

### Task 2: GET /snapshots list endpoint (paginated)

**Files:**
- Modify: `backend/app/modules/iso/api/snapshots.py`
- Modify: `backend/tests/test_iso_snapshots.py`

**Step 1: Write the failing tests**

Add to `tests/test_iso_snapshots.py`:

```python
from datetime import datetime, timezone


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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_snapshots.py::TestListSnapshots -v --no-header -q`
Expected: FAIL with 404 or AttributeError

**Step 3: Add to `snapshots.py`**

Add these imports at top:

```python
import math

from fastapi import Query

from app.api.schemas.common import PaginatedResponse
from app.modules.iso.schemas import AccessSnapshotSummary
```

Add endpoint:

```python
@router.get("", response_model=PaginatedResponse[AccessSnapshotSummary])
async def list_snapshots(
    db: DBSession,
    provider: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    query = select(AccessSnapshotDB).order_by(
        AccessSnapshotDB.captured_at.desc()
    )
    count_query = select(func.count(AccessSnapshotDB.id))

    if provider:
        query = query.where(AccessSnapshotDB.provider == provider)
        count_query = count_query.where(AccessSnapshotDB.provider == provider)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    snapshots = result.scalars().all()

    return {
        "items": snapshots,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total > 0 else 0,
    }
```

Also add this import:

```python
from sqlalchemy.sql import func
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_snapshots.py -v --no-header -q`
Expected: 8 passed

**Step 5: Commit**

```bash
git add app/modules/iso/api/snapshots.py tests/test_iso_snapshots.py
git commit -m "feat(iso): add GET /snapshots list endpoint with pagination"
```

---

### Task 3: GET /snapshots/{id} detail endpoint

**Files:**
- Modify: `backend/app/modules/iso/api/snapshots.py`
- Modify: `backend/tests/test_iso_snapshots.py`

**Step 1: Write the failing tests**

Add to `tests/test_iso_snapshots.py`:

```python
class TestSnapshotDetail:
    @pytest.mark.asyncio
    async def test_get_snapshot_detail(
        self, client: AsyncClient, db_session
    ) -> None:
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_snapshots.py::TestSnapshotDetail -v --no-header -q`
Expected: FAIL with 404 or AttributeError

**Step 3: Add to `snapshots.py`**

```python
@router.get("/{snapshot_id}", response_model=AccessSnapshotResponse)
async def get_snapshot(snapshot_id: UUID, db: DBSession) -> AccessSnapshotDB:
    result = await db.execute(
        select(AccessSnapshotDB).where(AccessSnapshotDB.id == snapshot_id)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_snapshots.py -v --no-header -q`
Expected: 10 passed

**Step 5: Commit**

```bash
git add app/modules/iso/api/snapshots.py tests/test_iso_snapshots.py
git commit -m "feat(iso): add GET /snapshots/{id} detail endpoint"
```

---

### Task 4: Wire snapshots sub-router into ISO module router

**Files:**
- Modify: `backend/app/modules/iso/router.py`
- Modify: `backend/tests/test_iso_snapshots.py`

**Step 1: Write the failing test**

Add to `tests/test_iso_snapshots.py`:

```python
class TestSnapshotRouterWiring:
    @pytest.mark.asyncio
    async def test_snapshots_accessible_via_iso_prefix(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/api/iso/snapshots")
        assert response.status_code == 200
```

Note: This test may already pass if you've been running the router wiring during earlier tests. That's fine — it documents the wiring requirement.

**Step 2: Update router.py**

```python
from fastapi import APIRouter

from app.modules.iso.api import config as config_router
from app.modules.iso.api import snapshots as snapshots_router

router = APIRouter()
router.include_router(config_router.router, prefix="/config", tags=["iso-config"])
router.include_router(
    snapshots_router.router, prefix="/snapshots", tags=["iso-snapshots"]
)
```

**Step 3: Run tests to verify they pass**

Run: `pytest tests/test_iso_snapshots.py -v --no-header -q`
Expected: 11 passed

**Step 4: Commit**

```bash
git add app/modules/iso/router.py tests/test_iso_snapshots.py
git commit -m "feat(iso): wire snapshots sub-router to ISO module"
```

---

### Task 5: Full regression test + lint

**Step 1: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: 890+ passed (879 existing + 11 new)

**Step 2: Run lint**

Run: `ruff check app/modules/iso/ tests/test_iso_snapshots.py && black --check app/modules/iso/ tests/test_iso_snapshots.py`
Expected: All checks passed. If Black fails, run `black app/modules/iso/ tests/test_iso_snapshots.py` and commit the fix.
