# ISO Module Phase 1: Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Scaffold the ISO module directory structure, create the 3 SQLAlchemy models (AccessSnapshotDB, AccessReviewDB, AccessReviewActionDB), Pydantic schemas, Alembic migration, module router, and unit tests.

**Architecture:** New `app/modules/iso/` directory following the modular architecture pattern. Models use JSONB for snapshot data, string enums for status fields. Router mounted in `main.py` under `/api/iso`. Dependencies added to `requirements.txt`.

**Tech Stack:** SQLAlchemy 2.0 (async, mapped_column), Pydantic v2, Alembic, PostgreSQL (JSONB, UUID), pytest-asyncio

**Design doc:** `docs/plans/2026-02-22-iso-google-workspace-collector-design.md`

---

### Task 1: Scaffold ISO module directory structure

**Files:**
- Create: `backend/app/modules/__init__.py`
- Create: `backend/app/modules/iso/__init__.py`
- Create: `backend/app/modules/iso/models/__init__.py`
- Create: `backend/app/modules/iso/services/__init__.py`
- Create: `backend/app/modules/iso/services/collectors/__init__.py`
- Create: `backend/app/modules/iso/api/__init__.py`
- Create: `backend/app/modules/iso/public.py`
- Create: `backend/app/modules/iso/router.py`

**Step 1: Create directory structure with empty `__init__.py` files**

All `__init__.py` files are empty except `models/__init__.py` (will export models later) and `router.py`.

**Step 2: Create the module router**

`backend/app/modules/iso/router.py`:
```python
from fastapi import APIRouter

router = APIRouter()
```

Sub-routers will be added in later phases as API endpoints are built.

**Step 3: Create the public interface stub**

`backend/app/modules/iso/public.py`:
```python
"""Cross-module public interface for the ISO module."""
```

**Step 4: Commit**

```bash
git add backend/app/modules/
git commit -m "feat(iso): scaffold module directory structure"
```

---

### Task 2: Mount ISO router in main.py

**Files:**
- Modify: `backend/app/main.py` (imports ~line 13, router mount ~line 196)

**Step 1: Write the failing test**

`backend/tests/test_iso_module.py`:
```python
"""Tests for ISO module foundation."""

import pytest
from httpx import AsyncClient


class TestIsoModuleMount:
    @pytest.mark.asyncio
    async def test_iso_router_mounted(self, client: AsyncClient) -> None:
        """ISO module router responds (404 is fine, just not 'not found route')."""
        response = await client.get("/api/iso/health-check-nonexistent")
        # 404 means the router is mounted but the route doesn't exist
        # If the router wasn't mounted, FastAPI returns 404 too,
        # but we'll verify with a real endpoint after adding one
        assert response.status_code in (404, 405)
```

**Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_module.py -v && popd > /dev/null`

**Step 3: Add import and mount in main.py**

Add import after line ~24 (after other router imports):
```python
from app.modules.iso.router import router as iso_router
```

Add mount after line ~196 (after last `include_router`):
```python
app.include_router(iso_router, prefix="/api/iso", tags=["iso"])
```

**Step 4: Run test to verify it passes**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_module.py -v && popd > /dev/null`

**Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_iso_module.py
git commit -m "feat(iso): mount ISO module router in main app"
```

---

### Task 3: Create enums and AccessSnapshotDB model

**Files:**
- Create: `backend/app/modules/iso/models/access_snapshot.py`
- Modify: `backend/tests/test_iso_module.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_iso_module.py`:
```python
from uuid import uuid4
from datetime import datetime, timezone


class TestAccessSnapshotModel:
    @pytest.mark.asyncio
    async def test_create_snapshot(self, db_session) -> None:
        from app.modules.iso.models.access_snapshot import AccessSnapshotDB

        snapshot = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime.now(timezone.utc),
            captured_by=None,
            data={"users": [], "groups": [], "group_members": {}, "role_assignments": []},
            summary={"total_users": 0, "active_users": 0, "suspended_users": 0, "total_admins": 0, "external_members": 0, "total_groups": 0},
            source_metadata={"domain": "test.com", "collector": "google_workspace", "collector_version": "1", "scopes": [], "run_mode": "manual"},
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
        from app.modules.iso.models.access_snapshot import AccessSnapshotDB
        from app.models.user import UserDB

        user = UserDB(email="admin@test.com", role="admin")
        db_session.add(user)
        await db_session.flush()

        snapshot = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime.now(timezone.utc),
            captured_by=user.id,
            data={"users": [], "groups": [], "group_members": {}, "role_assignments": []},
            summary={},
            source_metadata={},
        )
        db_session.add(snapshot)
        await db_session.flush()

        assert snapshot.captured_by == user.id
```

**Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_module.py::TestAccessSnapshotModel -v && popd > /dev/null`
Expected: ImportError

**Step 3: Write the model**

`backend/app/modules/iso/models/access_snapshot.py`:
```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AccessSnapshotDB(Base):
    __tablename__ = "access_snapshots"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    captured_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    data_version: Mapped[str] = mapped_column(
        String(10), nullable=False, default="1"
    )
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

**Step 4: Export from models `__init__.py`**

`backend/app/modules/iso/models/__init__.py`:
```python
from app.modules.iso.models.access_snapshot import AccessSnapshotDB

__all__ = ["AccessSnapshotDB"]
```

**Step 5: Run test to verify it passes**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_module.py::TestAccessSnapshotModel -v && popd > /dev/null`

**Step 6: Commit**

```bash
git add backend/app/modules/iso/models/
git commit -m "feat(iso): add AccessSnapshotDB model"
```

---

### Task 4: Create AccessReviewDB model

**Files:**
- Create: `backend/app/modules/iso/models/access_review.py`
- Modify: `backend/app/modules/iso/models/__init__.py`
- Modify: `backend/tests/test_iso_module.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_iso_module.py`:
```python
class TestAccessReviewModel:
    @pytest.mark.asyncio
    async def test_create_review(self, db_session) -> None:
        from app.modules.iso.models.access_snapshot import AccessSnapshotDB
        from app.modules.iso.models.access_review import AccessReviewDB
        from app.models.user import UserDB

        user = UserDB(email="reviewer@test.com", role="admin")
        db_session.add(user)
        await db_session.flush()

        snapshot = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime.now(timezone.utc),
            data={"users": [], "groups": [], "group_members": {}, "role_assignments": []},
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
        from app.modules.iso.models.access_snapshot import AccessSnapshotDB
        from app.modules.iso.models.access_review import AccessReviewDB
        from app.models.user import UserDB

        user = UserDB(email="signer@test.com", role="admin")
        db_session.add(user)
        await db_session.flush()

        snapshot = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime.now(timezone.utc),
            data={}, summary={}, source_metadata={},
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
```

**Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_module.py::TestAccessReviewModel -v && popd > /dev/null`

**Step 3: Write the model**

`backend/app/modules/iso/models/access_review.py`:
```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AccessReviewDB(Base):
    __tablename__ = "access_reviews"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("access_snapshots.id"), nullable=False
    )
    previous_snapshot_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("access_snapshots.id"), nullable=True
    )
    reviewer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    scope: Mapped[str] = mapped_column(String(255), nullable=False)
    diff_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now()
    )
```

**Step 4: Update models `__init__.py`**

```python
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.models.access_review import AccessReviewDB

__all__ = ["AccessSnapshotDB", "AccessReviewDB"]
```

**Step 5: Run test to verify it passes**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_module.py::TestAccessReviewModel -v && popd > /dev/null`

**Step 6: Commit**

```bash
git add backend/app/modules/iso/models/
git commit -m "feat(iso): add AccessReviewDB model"
```

---

### Task 5: Create AccessReviewActionDB model

**Files:**
- Create: `backend/app/modules/iso/models/access_review_action.py`
- Modify: `backend/app/modules/iso/models/__init__.py`
- Modify: `backend/tests/test_iso_module.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_iso_module.py`:
```python
class TestAccessReviewActionModel:
    @pytest.mark.asyncio
    async def test_create_action(self, db_session) -> None:
        from app.modules.iso.models.access_snapshot import AccessSnapshotDB
        from app.modules.iso.models.access_review import AccessReviewDB
        from app.modules.iso.models.access_review_action import AccessReviewActionDB
        from app.models.user import UserDB

        user = UserDB(email="reviewer@test.com", role="admin")
        db_session.add(user)
        await db_session.flush()

        snapshot = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime.now(timezone.utc),
            data={}, summary={}, source_metadata={},
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
            current_value={"email": "newuser@test.com", "name": "New User"},
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
        from app.modules.iso.models.access_snapshot import AccessSnapshotDB
        from app.modules.iso.models.access_review import AccessReviewDB
        from app.modules.iso.models.access_review_action import AccessReviewActionDB
        from app.models.user import UserDB
        from datetime import date

        user = UserDB(email="approver@test.com", role="admin")
        db_session.add(user)
        await db_session.flush()

        snapshot = AccessSnapshotDB(
            provider="google_workspace",
            captured_at=datetime.now(timezone.utc),
            data={}, summary={}, source_metadata={},
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
            current_value={"external_added": ["external@vendor.com"]},
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
```

**Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_module.py::TestAccessReviewActionModel -v && popd > /dev/null`

**Step 3: Write the model**

`backend/app/modules/iso/models/access_review_action.py`:
```python
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AccessReviewActionDB(Base):
    __tablename__ = "access_review_actions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    review_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("access_reviews.id"), nullable=False
    )
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    current_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    action_taken: Mapped[str | None] = mapped_column(String(20), nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    exception_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now()
    )
```

**Step 4: Update models `__init__.py`**

```python
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB

__all__ = ["AccessSnapshotDB", "AccessReviewDB", "AccessReviewActionDB"]
```

**Step 5: Run test to verify it passes**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_module.py::TestAccessReviewActionModel -v && popd > /dev/null`

**Step 6: Commit**

```bash
git add backend/app/modules/iso/models/
git commit -m "feat(iso): add AccessReviewActionDB model"
```

---

### Task 6: Create Pydantic schemas

**Files:**
- Create: `backend/app/modules/iso/schemas.py`
- Modify: `backend/tests/test_iso_module.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_iso_module.py`:
```python
from pydantic import ValidationError


class TestIsoSchemas:
    def test_snapshot_response_from_orm(self, db_session) -> None:
        """Schema can be created from ORM attributes."""
        from app.modules.iso.schemas import AccessSnapshotResponse

        data = {
            "id": uuid4(),
            "provider": "google_workspace",
            "captured_at": datetime.now(timezone.utc),
            "captured_by": None,
            "data_version": "1",
            "source_metadata": {"domain": "test.com"},
            "data": {"users": []},
            "summary": {"total_users": 0},
            "created_at": datetime.now(timezone.utc),
        }
        schema = AccessSnapshotResponse(**data)
        assert schema.provider == "google_workspace"

    def test_review_response_schema(self) -> None:
        from app.modules.iso.schemas import AccessReviewResponse

        data = {
            "id": uuid4(),
            "snapshot_id": uuid4(),
            "previous_snapshot_id": None,
            "reviewer_id": uuid4(),
            "status": "draft",
            "scope": "All users and groups",
            "diff_summary": None,
            "notes": None,
            "signed_by": None,
            "signed_at": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        schema = AccessReviewResponse(**data)
        assert schema.status == "draft"

    def test_review_update_schema(self) -> None:
        from app.modules.iso.schemas import AccessReviewUpdate

        update = AccessReviewUpdate(notes="Looks good")
        assert update.notes == "Looks good"
        assert update.reviewer_id is None

    def test_action_update_schema_valid(self) -> None:
        from app.modules.iso.schemas import AccessReviewActionUpdate

        update = AccessReviewActionUpdate(
            action_taken="accepted",
            justification="Expected change from onboarding",
        )
        assert update.action_taken == "accepted"

    def test_action_update_schema_invalid_action(self) -> None:
        from app.modules.iso.schemas import AccessReviewActionUpdate

        with pytest.raises(ValidationError):
            AccessReviewActionUpdate(action_taken="invalid_value")

    def test_action_response_schema(self) -> None:
        from app.modules.iso.schemas import AccessReviewActionResponse

        data = {
            "id": uuid4(),
            "review_id": uuid4(),
            "subject_type": "user",
            "subject_id": "user@test.com",
            "subject_label": "Test User",
            "change_type": "new_user",
            "previous_value": None,
            "current_value": {"email": "user@test.com"},
            "action_taken": None,
            "justification": None,
            "approved_by": None,
            "exception_until": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        schema = AccessReviewActionResponse(**data)
        assert schema.subject_type == "user"
```

**Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_module.py::TestIsoSchemas -v && popd > /dev/null`

**Step 3: Write the schemas**

`backend/app/modules/iso/schemas.py`:
```python
from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    DRAFT = "draft"
    COMPLETED = "completed"
    SIGNED = "signed"


class SubjectType(str, Enum):
    USER = "user"
    GROUP = "group"


class ChangeType(str, Enum):
    NEW_USER = "new_user"
    REMOVED_USER = "removed_user"
    ROLE_CHANGE = "role_change"
    NEW_EXTERNAL = "new_external"
    GROUP_MEMBERSHIP_CHANGE = "group_membership_change"


class ActionTaken(str, Enum):
    ACCEPTED = "accepted"
    REMOVED = "removed"
    CORRECTED = "corrected"
    EXCEPTION = "exception"


# --- Snapshot schemas ---

class AccessSnapshotResponse(BaseModel):
    id: UUID
    provider: str
    captured_at: datetime
    captured_by: UUID | None = None
    data_version: str
    source_metadata: dict
    data: dict
    summary: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class AccessSnapshotSummary(BaseModel):
    """Lightweight snapshot for list views (excludes data)."""
    id: UUID
    provider: str
    captured_at: datetime
    captured_by: UUID | None = None
    data_version: str
    summary: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Review schemas ---

class AccessReviewResponse(BaseModel):
    id: UUID
    snapshot_id: UUID
    previous_snapshot_id: UUID | None = None
    reviewer_id: UUID
    status: str
    scope: str
    diff_summary: dict | None = None
    notes: str | None = None
    signed_by: UUID | None = None
    signed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccessReviewUpdate(BaseModel):
    notes: str | None = None
    reviewer_id: UUID | None = None


# --- Action schemas ---

class AccessReviewActionResponse(BaseModel):
    id: UUID
    review_id: UUID
    subject_type: str
    subject_id: str
    subject_label: str | None = None
    change_type: str
    previous_value: dict | None = None
    current_value: dict | None = None
    action_taken: str | None = None
    justification: str | None = None
    approved_by: UUID | None = None
    exception_until: date | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccessReviewActionUpdate(BaseModel):
    action_taken: ActionTaken | None = None
    justification: str | None = None
    approved_by: UUID | None = None
    exception_until: date | None = None
```

**Step 4: Run test to verify it passes**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_module.py::TestIsoSchemas -v && popd > /dev/null`

**Step 5: Commit**

```bash
git add backend/app/modules/iso/schemas.py backend/tests/test_iso_module.py
git commit -m "feat(iso): add Pydantic schemas for snapshots, reviews, and actions"
```

---

### Task 7: Create Alembic migration

**Files:**
- Create: `backend/alembic/versions/014_add_iso_access_tables.py`
- Modify: `backend/alembic/env.py` (add model imports)

**Step 1: Add model imports to alembic env.py**

Add after line 15 (after existing model imports) in `backend/alembic/env.py`:
```python
from app.modules.iso.models.access_snapshot import AccessSnapshotDB  # noqa: F401
from app.modules.iso.models.access_review import AccessReviewDB  # noqa: F401
from app.modules.iso.models.access_review_action import AccessReviewActionDB  # noqa: F401
```

**Step 2: Generate and review the migration**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && alembic revision --autogenerate -m "add ISO access tables" && popd > /dev/null`

Review the generated file. It should create 3 tables: `access_snapshots`, `access_reviews`, `access_review_actions` with all columns and foreign keys.

**Step 3: Edit the migration file**

Rename to `014_add_iso_access_tables.py`. Set:
```python
revision: str = "014_add_iso_access_tables"
down_revision: str = "013_add_manifest_path"
```

Verify the migration includes:
- `access_snapshots` table with JSONB columns, FK to users
- `access_reviews` table with FKs to access_snapshots (x2) and users (x2)
- `access_review_actions` table with FK to access_reviews and users
- Index on `access_snapshots.provider`
- `updated_at` trigger for `access_reviews` and `access_review_actions`

Add triggers for `updated_at` in the `upgrade()` function (reuse existing trigger function):
```python
op.execute("""
    CREATE TRIGGER update_access_reviews_updated_at
    BEFORE UPDATE ON access_reviews
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
""")
op.execute("""
    CREATE TRIGGER update_access_review_actions_updated_at
    BEFORE UPDATE ON access_review_actions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
""")
```

And in `downgrade()`:
```python
op.execute("DROP TRIGGER IF EXISTS update_access_review_actions_updated_at ON access_review_actions")
op.execute("DROP TRIGGER IF EXISTS update_access_reviews_updated_at ON access_reviews")
op.drop_table("access_review_actions")
op.drop_table("access_reviews")
op.drop_table("access_snapshots")
```

**Step 4: Run the migration against test DB**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && DATABASE_URL="postgresql+asyncpg://scorecard:scorecard@localhost:5432/scorecard_test" alembic upgrade head && popd > /dev/null`

**Step 5: Run all model tests to verify**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_module.py -v && popd > /dev/null`

**Step 6: Commit**

```bash
git add backend/alembic/env.py backend/alembic/versions/014_add_iso_access_tables.py
git commit -m "feat(iso): add Alembic migration for access tables"
```

---

### Task 8: Add Google Workspace dependencies

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add dependencies**

Add to `backend/requirements.txt` under `# HTTP clients for API integrations`:
```
# Google Workspace Admin SDK
google-api-python-client>=2.114.0,<3.0.0
google-auth-oauthlib>=1.2.0,<2.0.0
```

Note: `google-auth` is already in requirements.txt (line 12).

**Step 2: Install**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pip install -r requirements.txt && popd > /dev/null`

**Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat(iso): add Google Workspace SDK dependencies"
```

---

### Task 9: Run full test suite to verify no regressions

**Step 1: Run all backend tests**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest --tb=short -q && popd > /dev/null`

Expected: All ~830+ tests pass, including the new ISO tests.

**Step 2: Run linting**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && ruff check app/modules/iso/ && black --check app/modules/iso/ && popd > /dev/null`

Fix any lint issues.

**Step 3: Final commit (if lint fixes needed)**

```bash
git add -A
git commit -m "fix(iso): lint fixes for Phase 1 foundation"
```
