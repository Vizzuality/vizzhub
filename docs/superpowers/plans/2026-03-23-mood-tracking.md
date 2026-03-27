# Mood Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional mood/wellbeing tracking to the time report confirmation flow, with anonymous feedback support and an admin moods page.

**Architecture:** Two new columns on the `reports` table (mood, feedback_text) plus a standalone `anonymous_feedback` table with no FK/timestamps. A post-confirm dialog captures mood and optional text. Admin page at `/admin/tracker/moods` shows aggregated mood distribution and feedback.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Pydantic, React, TypeScript, React Query, shadcn/ui, Recharts

**Spec:** `docs/superpowers/specs/2026-03-23-mood-tracking-design.md`

---

### Task 1: Database Migration

**Files:**
- Create: `backend/alembic/versions/032_add_mood_tracking.py`
- Create: `backend/app/modules/tracker/models/anonymous_feedback.py`
- Modify: `backend/app/modules/tracker/models/report.py`
- Modify: `backend/app/modules/tracker/models/__init__.py`

- [ ] **Step 1: Create the anonymous_feedback model**

Create `backend/app/modules/tracker/models/anonymous_feedback.py`:

```python
"""Anonymous feedback — no FK, no timestamps, untraceable."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnonymousFeedbackDB(Base):
    __tablename__ = "anonymous_feedback"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(String(2000), nullable=False)
```

- [ ] **Step 2: Add mood and feedback_text columns to ReportDB**

Modify `backend/app/modules/tracker/models/report.py` — add two columns after `estimated`:

```python
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
# ... existing imports ...

# Add after the `estimated` column:
mood: Mapped[int | None] = mapped_column(Integer, nullable=True)
feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 3: Export new model from __init__.py**

Modify `backend/app/modules/tracker/models/__init__.py` — add:

```python
from app.modules.tracker.models.anonymous_feedback import AnonymousFeedbackDB

# Add to __all__:
"AnonymousFeedbackDB",
```

- [ ] **Step 4: Create the Alembic migration**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && alembic revision --autogenerate -m "add_mood_tracking" && popd > /dev/null`

Review the generated migration. It should:
- Add `mood` (Integer, nullable) and `feedback_text` (Text, nullable) columns to `reports`
- Create `anonymous_feedback` table with `id`, `month`, `year`, `text` — NO foreign keys, NO timestamp columns

- [ ] **Step 5: Run the migration**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && alembic upgrade head && popd > /dev/null`

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/032_add_mood_tracking.py backend/app/modules/tracker/models/anonymous_feedback.py backend/app/modules/tracker/models/report.py backend/app/modules/tracker/models/__init__.py
git commit -m "feat(tracker): add mood tracking migration and models"
```

---

### Task 2: Backend Schemas

**Files:**
- Modify: `backend/app/modules/tracker/schemas/report.py`
- Create: `backend/app/modules/tracker/schemas/mood.py`

- [ ] **Step 1: Write tests for mood validation on ReportUpdate**

Add to `backend/tests/modules/tracker/test_reports.py`:

```python
class TestMoodOnReport:
    """Test mood and feedback_text fields on report update."""

    async def test_update_report_with_mood(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = setup_reporting["report_id"]
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"estimated": False, "mood": 4},
        )
        assert resp.status_code == 200
        assert resp.json()["mood"] == 4

    async def test_update_report_mood_out_of_range(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = setup_reporting["report_id"]
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"mood": 6},
        )
        assert resp.status_code == 422

    async def test_update_report_mood_zero_rejected(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = setup_reporting["report_id"]
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"mood": 0},
        )
        assert resp.status_code == 422

    async def test_update_report_with_feedback_text(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = setup_reporting["report_id"]
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"estimated": False, "feedback_text": "Great month!"},
        )
        assert resp.status_code == 200
        assert resp.json()["feedback_text"] == "Great month!"

    async def test_update_report_mood_null_clears(
        self, client: AsyncClient, setup_reporting: dict
    ):
        report_id = setup_reporting["report_id"]
        await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"mood": 3},
        )
        resp = await client.put(
            f"/api/tracker/reports/{report_id}",
            json={"mood": None},
        )
        assert resp.status_code == 200
        assert resp.json()["mood"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/tracker/test_reports.py::TestMoodOnReport -v && popd > /dev/null`

Expected: FAIL — `mood` and `feedback_text` not in schema yet.

- [ ] **Step 3: Update ReportUpdate and ReportResponse schemas**

Modify `backend/app/modules/tracker/schemas/report.py`:

Add `Field` to the pydantic import at the top:

```python
from pydantic import BaseModel, ConfigDict, Field
```

Add two fields to the existing `ReportUpdate` class (do NOT replace — add after `estimated`):

```python
class ReportUpdate(BaseModel):
    estimated: bool | None = None
    mood: int | None = Field(None, ge=1, le=5)
    feedback_text: str | None = Field(None, max_length=2000)
```

Add two fields to the existing `ReportResponse` class (add after `estimated`):

```python
    mood: int | None = None
    feedback_text: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/tracker/test_reports.py::TestMoodOnReport -v && popd > /dev/null`

Expected: PASS

- [ ] **Step 5: Create mood schemas**

Create `backend/app/modules/tracker/schemas/mood.py`:

```python
"""Pydantic schemas for mood tracking."""

from pydantic import BaseModel, Field


class AnonymousFeedbackCreate(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2020, le=2100)
    text: str = Field(min_length=1, max_length=2000)


class NamedFeedbackItem(BaseModel):
    user_name: str
    mood: int | None = None
    text: str | None = None


class MoodsResponse(BaseModel):
    mood_distribution: dict[int, int]
    total_reports: int
    total_responses: int
    average_mood: float | None = None
    anonymous_feedback: list[str]
    named_feedback: list[NamedFeedbackItem]
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/tracker/schemas/report.py backend/app/modules/tracker/schemas/mood.py backend/tests/modules/tracker/test_reports.py
git commit -m "feat(tracker): add mood schemas and report update validation"
```

---

### Task 3: Anonymous Feedback Endpoint

**Files:**
- Create: `backend/app/modules/tracker/api/anonymous_feedback.py`
- Modify: `backend/app/modules/tracker/router.py`
- Test: `backend/tests/modules/tracker/test_anonymous_feedback.py`

- [ ] **Step 1: Write tests**

Create `backend/tests/modules/tracker/test_anonymous_feedback.py`:

```python
"""Tests for anonymous feedback endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tracker.models.anonymous_feedback import AnonymousFeedbackDB


class TestAnonymousFeedback:
    async def test_create_anonymous_feedback(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        resp = await client.post(
            "/api/tracker/anonymous-feedback",
            json={"month": 3, "year": 2026, "text": "Good vibes"},
        )
        assert resp.status_code == 201

        result = await db_session.execute(select(AnonymousFeedbackDB))
        row = result.scalar_one()
        assert row.month == 3
        assert row.year == 2026
        assert row.text == "Good vibes"

    async def test_anonymous_feedback_has_no_user_id_column(
        self, db_session: AsyncSession
    ):
        result = await db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'anonymous_feedback'"
            )
        )
        columns = {r[0] for r in result.all()}
        assert "user_id" not in columns
        assert "created_at" not in columns
        assert "updated_at" not in columns

    async def test_anonymous_feedback_has_no_fk(
        self, db_session: AsyncSession
    ):
        result = await db_session.execute(
            text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'anonymous_feedback' "
                "AND constraint_type = 'FOREIGN KEY'"
            )
        )
        assert result.all() == []

    async def test_create_anonymous_feedback_validation(
        self, client: AsyncClient
    ):
        resp = await client.post(
            "/api/tracker/anonymous-feedback",
            json={"month": 13, "year": 2026, "text": "Bad month"},
        )
        assert resp.status_code == 422

        resp = await client.post(
            "/api/tracker/anonymous-feedback",
            json={"month": 3, "year": 2026, "text": ""},
        )
        assert resp.status_code == 422

    async def test_create_anonymous_feedback_duplicates_allowed(
        self, client: AsyncClient
    ):
        payload = {"month": 3, "year": 2026, "text": "Same feedback"}
        resp1 = await client.post("/api/tracker/anonymous-feedback", json=payload)
        resp2 = await client.post("/api/tracker/anonymous-feedback", json=payload)
        assert resp1.status_code == 201
        assert resp2.status_code == 201
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/tracker/test_anonymous_feedback.py -v && popd > /dev/null`

Expected: FAIL — endpoint not found (404).

- [ ] **Step 3: Create the anonymous feedback router**

Create `backend/app/modules/tracker/api/anonymous_feedback.py`:

```python
"""Anonymous feedback endpoint — no traceability by design."""

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.models.anonymous_feedback import AnonymousFeedbackDB
from app.modules.tracker.schemas.mood import AnonymousFeedbackCreate

router = APIRouter()


@router.post("", status_code=201)
async def create_anonymous_feedback(
    data: AnonymousFeedbackCreate,
    db: DBSession,
    user: CurrentUser,
) -> dict:
    feedback = AnonymousFeedbackDB(
        month=data.month,
        year=data.year,
        text=data.text,
    )
    db.add(feedback)
    await db.commit()
    return {"status": "ok"}
```

- [ ] **Step 4: Register router in tracker module**

Modify `backend/app/modules/tracker/router.py` — add:

```python
from app.modules.tracker.api import anonymous_feedback as anonymous_feedback_router

router.include_router(
    anonymous_feedback_router.router,
    prefix="/anonymous-feedback",
    tags=["tracker:anonymous-feedback"],
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/tracker/test_anonymous_feedback.py -v && popd > /dev/null`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/tracker/api/anonymous_feedback.py backend/app/modules/tracker/router.py backend/tests/modules/tracker/test_anonymous_feedback.py
git commit -m "feat(tracker): add anonymous feedback endpoint"
```

---

### Task 4: Moods Admin Endpoint

**Files:**
- Create: `backend/app/modules/tracker/api/moods.py`
- Modify: `backend/app/modules/tracker/router.py`
- Test: `backend/tests/modules/tracker/test_moods.py`

- [ ] **Step 1: Write tests**

Create `backend/tests/modules/tracker/test_moods.py`:

```python
"""Tests for admin moods endpoint."""

import datetime as dt
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.rate import RateDB
from app.core.models.user import UserDB
from app.modules.tracker.models.anonymous_feedback import AnonymousFeedbackDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

USER_ID_1 = UUID("00000000-0000-0000-0000-000000000001")
USER_ID_2 = UUID("00000000-0000-0000-0000-000000000002")


@pytest_asyncio.fixture
async def mood_data(db_session: AsyncSession) -> dict:
    """Create test data for mood aggregation."""
    rate = RateDB(code="B", value=Decimal("15365"))
    db_session.add(rate)
    await db_session.flush()

    user1 = UserDB(
        id=USER_ID_1, email="alice@example.com",
        name="Alice Smith", rate_id=rate.id,
    )
    user2 = UserDB(
        id=USER_ID_2, email="bob@example.com",
        name="Bob Jones", rate_id=rate.id,
    )
    db_session.add_all([user1, user2])
    await db_session.flush()

    period = ReportingPeriodDB(
        date=dt.date(2026, 3, 1), base_rate=Decimal("175"), status="active",
    )
    db_session.add(period)
    await db_session.flush()

    report1 = ReportDB(
        user_id=USER_ID_1, reporting_period_id=period.id,
        estimated=False, mood=4, feedback_text="Great month",
    )
    report2 = ReportDB(
        user_id=USER_ID_2, reporting_period_id=period.id,
        estimated=False, mood=2,
    )
    db_session.add_all([report1, report2])
    await db_session.flush()

    anon = AnonymousFeedbackDB(month=3, year=2026, text="Anonymous note")
    db_session.add(anon)
    await db_session.commit()

    return {"period": period}


class TestMoodsEndpoint:
    async def test_get_moods_returns_distribution(
        self, client: AsyncClient, mood_data: dict
    ):
        resp = await client.get(
            "/api/tracker/moods", params={"month": 3, "year": 2026}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mood_distribution"]["4"] == 1
        assert data["mood_distribution"]["2"] == 1
        assert data["total_responses"] == 2
        assert data["average_mood"] == 3.0

    async def test_get_moods_includes_anonymous_feedback(
        self, client: AsyncClient, mood_data: dict
    ):
        resp = await client.get(
            "/api/tracker/moods", params={"month": 3, "year": 2026}
        )
        data = resp.json()
        assert "Anonymous note" in data["anonymous_feedback"]

    async def test_get_moods_includes_named_feedback(
        self, client: AsyncClient, mood_data: dict
    ):
        resp = await client.get(
            "/api/tracker/moods", params={"month": 3, "year": 2026}
        )
        data = resp.json()
        named = data["named_feedback"]
        assert len(named) == 2
        alice = next(n for n in named if n["user_name"] == "Alice Smith")
        assert alice["mood"] == 4
        assert alice["text"] == "Great month"
        bob = next(n for n in named if n["user_name"] == "Bob Jones")
        assert bob["mood"] == 2
        assert bob["text"] is None

    async def test_get_moods_requires_admin(
        self, non_admin_client: AsyncClient, mood_data: dict
    ):
        resp = await non_admin_client.get(
            "/api/tracker/moods", params={"month": 3, "year": 2026}
        )
        assert resp.status_code == 403

    async def test_get_moods_empty_month(
        self, client: AsyncClient, mood_data: dict
    ):
        resp = await client.get(
            "/api/tracker/moods", params={"month": 1, "year": 2025}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reports"] == 0
        assert data["total_responses"] == 0
        assert data["average_mood"] is None
        assert data["anonymous_feedback"] == []
        assert data["named_feedback"] == []
```

Note: In test mode (`DEBUG=true`), the default `client` fixture uses a mock dev user with `permissions=["*"]` (admin). The `admin_client` is just the regular `client`. For the 403 test, we need a `non_admin_client` fixture that overrides `get_current_user` to return a user without admin permissions:

```python
@pytest_asyncio.fixture
async def non_admin_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Client authenticated as a regular (non-admin) user."""
    from app.core.auth import TokenData, get_current_user

    async def override_get_db():
        yield db_session

    async def override_non_admin():
        return TokenData(
            user_id="00000000-0000-0000-0000-000000000099",
            roles=["user"],
            permissions=["tracker:view", "tracker:manage_own_reports"],
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_non_admin

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
```

Add this fixture at the top of `test_moods.py`. Replace `admin_client` references with `client` (which is already admin), and use `non_admin_client` for the 403 test.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/tracker/test_moods.py -v && popd > /dev/null`

Expected: FAIL — endpoint not found.

- [ ] **Step 3: Create the moods endpoint**

Create `backend/app/modules/tracker/api/moods.py`:

```python
"""Admin moods endpoint — aggregated mood data and feedback."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.models.user import UserDB
from app.core.permissions import Action, require_permission
from app.modules.tracker.models.anonymous_feedback import AnonymousFeedbackDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.modules.tracker.schemas.mood import MoodsResponse, NamedFeedbackItem

AdminUser = Annotated[TokenData, Depends(require_permission(Action.ALL))]

router = APIRouter()


def _user_display_name(user: UserDB) -> str:
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    if user.name:
        return user.name
    return user.email.split("@")[0] if user.email else "Unknown"


@router.get("")
async def get_moods(
    month: int = Query(ge=1, le=12),
    year: int = Query(ge=2020, le=2100),
    db: DBSession,
    user: AdminUser,
) -> MoodsResponse:
    period_result = await db.execute(
        select(ReportingPeriodDB.id).where(
            func.extract("month", ReportingPeriodDB.date) == month,
            func.extract("year", ReportingPeriodDB.date) == year,
        )
    )
    period_id = period_result.scalar_one_or_none()

    if not period_id:
        return MoodsResponse(
            mood_distribution={},
            total_reports=0,
            total_responses=0,
            average_mood=None,
            anonymous_feedback=[],
            named_feedback=[],
        )

    reports_result = await db.execute(
        select(ReportDB, UserDB)
        .join(UserDB, ReportDB.user_id == UserDB.id)
        .where(ReportDB.reporting_period_id == period_id)
    )
    rows = reports_result.all()

    total_reports = len(rows)
    mood_distribution: dict[int, int] = {}
    moods: list[int] = []
    named_feedback: list[NamedFeedbackItem] = []

    for report, db_user in rows:
        if report.mood is not None:
            mood_distribution[report.mood] = mood_distribution.get(report.mood, 0) + 1
            moods.append(report.mood)

        if report.mood is not None or report.feedback_text is not None:
            named_feedback.append(
                NamedFeedbackItem(
                    user_name=_user_display_name(db_user),
                    mood=report.mood,
                    text=report.feedback_text,
                )
            )

    average_mood = sum(moods) / len(moods) if moods else None

    anon_result = await db.execute(
        select(AnonymousFeedbackDB.text).where(
            AnonymousFeedbackDB.month == month,
            AnonymousFeedbackDB.year == year,
        )
    )
    anonymous_feedback = [r[0] for r in anon_result.all()]

    return MoodsResponse(
        mood_distribution=mood_distribution,
        total_reports=total_reports,
        total_responses=len(moods),
        average_mood=round(average_mood, 1) if average_mood is not None else None,
        anonymous_feedback=anonymous_feedback,
        named_feedback=named_feedback,
    )
```

- [ ] **Step 4: Register router**

Modify `backend/app/modules/tracker/router.py` — add:

```python
from app.modules.tracker.api import moods as moods_router

router.include_router(
    moods_router.router,
    prefix="/moods",
    tags=["tracker:moods"],
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/tracker/test_moods.py -v && popd > /dev/null`

Expected: PASS

- [ ] **Step 6: Run full tracker test suite to check no regressions**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/tracker/ -v && popd > /dev/null`

Expected: All existing tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/tracker/api/moods.py backend/app/modules/tracker/router.py backend/tests/modules/tracker/test_moods.py
git commit -m "feat(tracker): add admin moods aggregation endpoint"
```

---

### Task 5: Frontend Types, Services, and Hooks

**Files:**
- Modify: `frontend/src/modules/tracker/types/tracker.ts`
- Modify: `frontend/src/modules/tracker/services/tracker.ts`
- Modify: `frontend/src/modules/tracker/hooks/useReports.ts`
- Create: `frontend/src/modules/tracker/hooks/useMoods.ts`
- Modify: `frontend/src/core/hooks/queryKeys.ts`

- [ ] **Step 1: Add types**

Modify `frontend/src/modules/tracker/types/tracker.ts` — add at end of file:

```typescript
export interface AnonymousFeedbackCreate {
  month: number;
  year: number;
  text: string;
}

export interface NamedFeedbackItem {
  user_name: string;
  mood: number | null;
  text: string | null;
}

export interface MoodsResponse {
  mood_distribution: Record<string, number>;
  total_reports: number;
  total_responses: number;
  average_mood: number | null;
  anonymous_feedback: string[];
  named_feedback: NamedFeedbackItem[];
}
```

Also update `Report` and `ReportUpdate` interfaces:

```typescript
export interface Report {
  // ... existing fields ...
  mood: number | null;
  feedback_text: string | null;
}

export interface ReportUpdate {
  estimated?: boolean;
  mood?: number | null;
  feedback_text?: string | null;
}
```

- [ ] **Step 2: Add API methods**

Modify `frontend/src/modules/tracker/services/tracker.ts` — add imports for new types and add methods:

```typescript
// Add to imports:
import type { ..., AnonymousFeedbackCreate, MoodsResponse } from '../types/tracker';

// Add to trackerApi:
createAnonymousFeedback: async (data: AnonymousFeedbackCreate): Promise<void> => {
  await api.post('/tracker/anonymous-feedback', data);
},

getMoods: async (month: number, year: number): Promise<MoodsResponse> => {
  const { data } = await api.get<MoodsResponse>('/tracker/moods', {
    params: { month, year },
  });
  return data;
},
```

- [ ] **Step 3: Add query keys**

Modify `frontend/src/core/hooks/queryKeys.ts` — add inside `tracker`:

```typescript
moods: (month: number, year: number) =>
  ['tracker', 'moods', month, year] as const,
```

- [ ] **Step 4: Create useMoods hook**

Create `frontend/src/modules/tracker/hooks/useMoods.ts`:

```typescript
import { useMutation, useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { trackerApi } from '../services/tracker';
import type { AnonymousFeedbackCreate } from '../types/tracker';

export function useMoods(month: number, year: number) {
  return useQuery({
    queryKey: queryKeys.tracker.moods(month, year),
    queryFn: () => trackerApi.getMoods(month, year),
  });
}

export function useCreateAnonymousFeedback() {
  return useMutation({
    mutationFn: (data: AnonymousFeedbackCreate) =>
      trackerApi.createAnonymousFeedback(data),
  });
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/tracker/types/tracker.ts frontend/src/modules/tracker/services/tracker.ts frontend/src/core/hooks/queryKeys.ts frontend/src/modules/tracker/hooks/useMoods.ts
git commit -m "feat(tracker): add mood types, services, and hooks"
```

---

### Task 6: MoodDialog Component

**Files:**
- Create: `frontend/src/modules/tracker/components/MoodDialog.tsx`
- Modify: `frontend/src/modules/tracker/components/ReportEditor.tsx`

- [ ] **Step 1: Create MoodDialog component**

Create `frontend/src/modules/tracker/components/MoodDialog.tsx`:

```tsx
import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Textarea } from '@/shared/components/ui/textarea';
import { useUpdateReport } from '../hooks/useReports';
import { useCreateAnonymousFeedback } from '../hooks/useMoods';

const MOODS = [
  { value: 1, emoji: '\u{1F62B}', label: 'Very bad' },
  { value: 2, emoji: '\u{1F61F}', label: 'Bad' },
  { value: 3, emoji: '\u{1F610}', label: 'Neutral' },
  { value: 4, emoji: '\u{1F642}', label: 'Good' },
  { value: 5, emoji: '\u{1F604}', label: 'Very good' },
] as const;

interface MoodDialogProps {
  open: boolean;
  onClose: () => void;
  reportId: string;
  periodId: string;
  periodMonth: number;
  periodYear: number;
}

export default function MoodDialog({
  open,
  onClose,
  reportId,
  periodId,
  periodMonth,
  periodYear,
}: MoodDialogProps): JSX.Element {
  const [selectedMood, setSelectedMood] = useState<number | null>(null);
  const [text, setText] = useState('');
  const [isAnonymous, setIsAnonymous] = useState(false);

  const updateReport = useUpdateReport(reportId, periodId);
  const createAnonymousFeedback = useCreateAnonymousFeedback();

  const handleSubmit = async (): Promise<void> => {
    try {
      const reportUpdate: Record<string, unknown> = {};
      if (selectedMood !== null) {
        reportUpdate.mood = selectedMood;
      }
      if (text.trim() && !isAnonymous) {
        reportUpdate.feedback_text = text.trim();
      }

      if (Object.keys(reportUpdate).length > 0) {
        await updateReport.mutateAsync(reportUpdate);
      }

      if (text.trim() && isAnonymous) {
        await createAnonymousFeedback.mutateAsync({
          month: periodMonth,
          year: periodYear,
          text: text.trim(),
        });
      }
    } finally {
      onClose();
    }
  };

  const hasContent = selectedMood !== null || text.trim().length > 0;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>How did you feel during this period?</DialogTitle>
          <DialogDescription>Optional — helps us understand team wellbeing</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Mood selection */}
          <div>
            <div className="flex gap-2 mb-1">
              {MOODS.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  onClick={() =>
                    setSelectedMood(selectedMood === m.value ? null : m.value)
                  }
                  title={m.label}
                  className={`text-2xl p-2 rounded-lg border-2 transition-all flex-1 ${
                    selectedMood === m.value
                      ? 'border-primary bg-primary/10'
                      : 'border-border opacity-60 hover:opacity-100'
                  }`}
                >
                  {m.emoji}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Your mood selection is linked to your report
            </p>
          </div>

          <div className="border-t" />

          {/* Text feedback */}
          <div>
            <Textarea
              placeholder="Want to share more? (optional)"
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={2000}
              className="min-h-[72px] resize-y"
            />
          </div>

          {/* Anonymous checkbox */}
          <div className="flex items-center gap-2">
            <Checkbox
              id="anonymous"
              checked={isAnonymous}
              onCheckedChange={(checked) => setIsAnonymous(checked === true)}
            />
            <label htmlFor="anonymous" className="text-sm text-muted-foreground cursor-pointer">
              Submit text anonymously
            </label>
            <span className="text-xs text-muted-foreground opacity-70">
              (only month/year stored, no link to you)
            </span>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={onClose}>
            Skip
          </Button>
          <Button onClick={handleSubmit} disabled={!hasContent}>
            Submit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Integrate MoodDialog into ReportEditor**

Modify `frontend/src/modules/tracker/components/ReportEditor.tsx`:

Add state and import at top:

```tsx
import { useState } from 'react';
import MoodDialog from './MoodDialog';
```

Inside the component, add state:

```tsx
const [showMoodDialog, setShowMoodDialog] = useState(false);
```

Modify the Confirm button's `onClick` to first confirm, then show dialog:

```tsx
onClick={() => {
  updateReport.mutate(
    { estimated: false },
    { onSuccess: () => setShowMoodDialog(true) },
  );
}}
```

Add `MoodDialog` before the closing `</Card>` or `</Collapsible>`. Need the period's month/year — extract from `report.reporting_period_id` context. The period date is available from the parent. Add a `periodDate` prop to `ReportEditorProps`:

```tsx
interface ReportEditorProps {
  report: Report;
  title: string;
  emptyMessage?: string;
  collapsible?: boolean;
  periodDate?: string;  // ISO date string like "2026-03-01"
}
```

Render the dialog:

```tsx
{showMoodDialog && periodDate && (
  <MoodDialog
    open={showMoodDialog}
    onClose={() => setShowMoodDialog(false)}
    reportId={report.id}
    periodId={report.reporting_period_id}
    periodMonth={new Date(periodDate).getMonth() + 1}
    periodYear={new Date(periodDate).getFullYear()}
  />
)}
```

- [ ] **Step 3: Pass periodDate from MyReport to ReportEditor**

Modify `frontend/src/modules/tracker/pages/MyReport.tsx` line 104:

```tsx
<ReportEditor report={myReport} title="My Time Report" periodDate={targetPeriod.date} />
```

Also check `PeriodDetail.tsx` — if it renders `ReportEditor` for admin view, pass `periodDate` there too.

- [ ] **Step 4: Test manually**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npm run dev && popd > /dev/null`

1. Navigate to My Report
2. Add a project, set percentage
3. Click Confirm
4. Verify MoodDialog appears
5. Select a mood, type text, toggle anonymous
6. Click Submit — verify network requests
7. Click Skip — verify dialog closes with no requests

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/tracker/components/MoodDialog.tsx frontend/src/modules/tracker/components/ReportEditor.tsx frontend/src/modules/tracker/pages/MyReport.tsx
git commit -m "feat(tracker): add mood dialog on report confirm"
```

---

### Task 7: Admin Moods Page

**Files:**
- Create: `frontend/src/modules/tracker/pages/Moods.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/core/components/layout/AppSidebar.tsx`
- Modify: `frontend/src/core/components/layout/PageBreadcrumb.tsx`

- [ ] **Step 1: Create the Moods page**

Create `frontend/src/modules/tracker/pages/Moods.tsx`:

```tsx
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useMoods } from '../hooks/useMoods';

const MOOD_EMOJIS: Record<number, string> = {
  1: '\u{1F62B}',
  2: '\u{1F61F}',
  3: '\u{1F610}',
  4: '\u{1F642}',
  5: '\u{1F604}',
};

const MOOD_COLORS: Record<number, string> = {
  1: 'bg-red-500',
  2: 'bg-orange-500',
  3: 'bg-yellow-500',
  4: 'bg-green-500',
  5: 'bg-emerald-500',
};

function formatMonth(month: number, year: number): string {
  return new Date(year, month - 1).toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
  });
}

export default function Moods(): JSX.Element {
  const now = new Date();
  const { state, setState } = useUrlState({
    month: { defaultValue: now.getMonth() + 1 },
    year: { defaultValue: now.getFullYear() },
  });
  const { data, isLoading } = useMoods(state.month, state.year);

  const navigate = (delta: number): void => {
    let m = state.month + delta;
    let y = state.year;
    if (m > 12) { m = 1; y += 1; }
    if (m < 1) { m = 12; y -= 1; }
    setState({ month: m, year: y });
  };

  if (isLoading) return <LoadingSpinner />;

  const maxCount = data
    ? Math.max(...Object.values(data.mood_distribution), 1)
    : 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Team Moods</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => navigate(-1)}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm font-medium min-w-[140px] text-center">
            {formatMonth(state.month, state.year)}
          </span>
          <Button variant="outline" size="icon" onClick={() => navigate(1)}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Mood Distribution */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base">Mood Distribution</CardTitle>
        </CardHeader>
        <CardContent>
          {data && data.total_responses > 0 ? (
            <>
              <div className="flex gap-4 items-end mb-4">
                {[1, 2, 3, 4, 5].map((value) => {
                  const count = data.mood_distribution[String(value)] ?? 0;
                  const height = Math.max((count / maxCount) * 120, 4);
                  return (
                    <div key={value} className="flex-1 text-center">
                      <div className="flex justify-center mb-1">
                        <div
                          className={`w-10 rounded-t ${MOOD_COLORS[value]}`}
                          style={{ height: `${height}px` }}
                        />
                      </div>
                      <span className="text-2xl">{MOOD_EMOJIS[value]}</span>
                      <p className="text-xs text-muted-foreground">{count}</p>
                    </div>
                  );
                })}
              </div>
              <div className="flex justify-between text-xs text-muted-foreground border-t pt-2">
                <span>
                  {data.total_responses} responses out of {data.total_reports} reports
                </span>
                <span>
                  Average: {data.average_mood} {data.average_mood !== null && MOOD_EMOJIS[Math.round(data.average_mood)]}
                </span>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">No mood data for this period.</p>
          )}
        </CardContent>
      </Card>

      {/* Anonymous Feedback */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base">Anonymous Feedback</CardTitle>
        </CardHeader>
        <CardContent>
          {data && data.anonymous_feedback.length > 0 ? (
            <div className="space-y-2">
              {data.anonymous_feedback.map((text, i) => (
                <div key={i} className="border rounded-md p-3 bg-muted/30">
                  <p className="text-sm">{text}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No anonymous feedback for this period.</p>
          )}
        </CardContent>
      </Card>

      {/* Named Feedback */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base">Named Feedback</CardTitle>
        </CardHeader>
        <CardContent>
          {data && data.named_feedback.length > 0 ? (
            <div className="space-y-2">
              {data.named_feedback.map((item, i) => (
                <div key={i} className="border rounded-md p-3 bg-muted/30">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{item.user_name}</span>
                    {item.mood && <span className="text-lg">{MOOD_EMOJIS[item.mood]}</span>}
                  </div>
                  {item.text && <p className="text-sm text-muted-foreground">{item.text}</p>}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No named feedback for this period.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Add route to App.tsx**

Modify `frontend/src/App.tsx`:

Add import:

```tsx
import Moods from './modules/tracker/pages/Moods';
```

Add route inside the **admin** `<Route path="tracker" element={<TrackerLayout />}>` block (nested under the `<Route path="/admin" element={<Admin />}>` around line 54-58). This makes the full URL `/admin/tracker/moods`:

```tsx
<Route path="moods" element={<Moods />} />
```

Place it after the existing `invoices` route (line 57). The route renders at `/admin/tracker/moods` because it's nested under `/admin` > `tracker` > `moods`.

- [ ] **Step 3: Add sidebar link**

Modify `frontend/src/core/components/layout/AppSidebar.tsx` line 68-71:

```typescript
const TRACKER_TABS = [
  { to: '/admin/tracker/periods', label: 'Reporting Periods' },
  { to: '/admin/tracker/invoices', label: 'Invoices' },
  { to: '/admin/tracker/moods', label: 'Moods' },
] as const;
```

- [ ] **Step 4: Add breadcrumb**

Modify `frontend/src/core/components/layout/PageBreadcrumb.tsx` — add before the generic `/admin/tracker` check:

```typescript
if (pathname.startsWith('/admin/tracker/moods')) return [{ label: 'Moods' }];
```

- [ ] **Step 5: Test manually**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npm run dev && popd > /dev/null`

1. Log in as admin
2. Navigate to Admin > Tracker > Moods
3. Verify month navigation works
4. Verify mood distribution chart renders
5. Verify anonymous and named feedback sections show

- [ ] **Step 6: Commit**

```bash
git add frontend/src/modules/tracker/pages/Moods.tsx frontend/src/App.tsx frontend/src/core/components/layout/AppSidebar.tsx frontend/src/core/components/layout/PageBreadcrumb.tsx
git commit -m "feat(tracker): add admin moods page with distribution and feedback"
```

---

### Task 8: Final Integration Test

- [ ] **Step 1: Run full backend test suite**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/modules/tracker/ -v && popd > /dev/null`

Expected: All PASS

- [ ] **Step 2: Run frontend tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npm test && popd > /dev/null`

Expected: All PASS (no existing tests should break)

- [ ] **Step 3: Full manual E2E flow**

1. Create/activate a reporting period
2. As a regular user: go to My Report, add projects, click Confirm
3. Mood dialog appears → select mood, type text (non-anonymous), Submit
4. Reopen → Confirm again → dialog appears again (write-once per cycle)
5. This time: type text, check anonymous, Submit
6. As admin: navigate to Admin > Tracker > Moods
7. Verify mood distribution shows the mood
8. Verify named feedback shows the non-anonymous text + name
9. Verify anonymous feedback shows the anonymous text
