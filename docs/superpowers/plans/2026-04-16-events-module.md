# Events Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a conference/events tracking module with CRUD, attendees, stats dashboard, and Excel import.

**Architecture:** Two new DB tables (`events`, `event_attendees`) following the existing modular monolith pattern. Backend module at `app/modules/events/` with FastAPI routers, Pydantic schemas, and service layer. Frontend module at `src/modules/events/` with card-grid dashboard, filters, and stats charts. Permissions via existing RBAC system (`events:view`, `events:manage`).

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, React, TanStack Query, shadcn/ui, Recharts, openpyxl (Excel import).

**Spec:** `docs/superpowers/specs/2026-04-16-events-module-design.md`

---

### Task 1: Backend — Constants and Enums

**Files:**
- Create: `backend/app/modules/events/__init__.py`
- Create: `backend/app/modules/events/constants.py`

- [ ] **Step 1: Create module directory and empty init**

```bash
mkdir -p backend/app/modules/events/models backend/app/modules/events/schemas backend/app/modules/events/api backend/app/modules/events/services
touch backend/app/modules/events/__init__.py backend/app/modules/events/models/__init__.py backend/app/modules/events/schemas/__init__.py backend/app/modules/events/api/__init__.py backend/app/modules/events/services/__init__.py
```

- [ ] **Step 2: Write constants.py with all StrEnums**

Create `backend/app/modules/events/constants.py`:

```python
"""Enum constants for the events module."""

from enum import StrEnum


class EventType(StrEnum):
    CONFERENCE = "Conference"
    SUMMIT = "Summit"
    FORUM = "Forum"
    WORKSHOP = "Workshop"
    SYMPOSIUM = "Symposium"
    MULTI_EVENT = "Multi-event"
    NETWORKING_EVENT = "Networking event"
    ROUNDTABLE = "Roundtable"
    TRAINING = "Training"
    WEBINAR = "Webinar"
    EXHIBITION_EXPO = "Exhibition / Expo"
    INTERNAL_EVENT = "Internal event"
    OTHER = "Other"


class Theme(StrEnum):
    CLIMATE = "Climate"
    NATURE_BIODIVERSITY = "Nature & Biodiversity"
    OCEANS_WATER = "Oceans & Water"
    FOOD_LAND_SYSTEMS = "Food & Land Systems"
    ENERGY_NET_ZERO = "Energy & Net Zero"
    DATA_TECHNOLOGY = "Data & Technology"
    POLICY_FINANCE = "Policy & Finance"
    SOCIAL_JUSTICE = "Social Justice"
    URBAN_CITIES = "Urban & Cities"
    OTHER = "Other"


class RegionFocus(StrEnum):
    GLOBAL = "Global"
    EUROPE = "Europe"
    NORTH_AMERICA = "North America"
    LATIN_AMERICA_CARIBBEAN = "Latin America & Caribbean"
    AFRICA = "Africa"
    ASIA_PACIFIC = "Asia-Pacific"
    MIDDLE_EAST = "Middle East"


class AttendeeRole(StrEnum):
    ATTENDEE = "Attendee"
    SPEAKER = "Speaker"
    PANELIST = "Panelist"
    MODERATOR = "Moderator"
    EXHIBITOR = "Exhibitor"
    ORGANIZER = "Organizer"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/events/
git commit -m "feat(events): scaffold module structure and define enums"
```

---

### Task 2: Backend — Database Models

**Files:**
- Create: `backend/app/modules/events/models/event.py`
- Create: `backend/app/modules/events/models/event_attendee.py`

- [ ] **Step 1: Write EventDB model**

Create `backend/app/modules/events/models/event.py`:

```python
"""Event model — conferences, summits, workshops, etc."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class EventDB(Base):
    """Conference or event tracked by the organisation."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="ck_events_rating_range",
        ),
        CheckConstraint("cost >= 0", name="ck_events_cost_positive"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    theme_primary: Mapped[str] = mapped_column(String(100), nullable=False)
    theme_secondary: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region_focus: Mapped[str] = mapped_column(String(50), nullable=False)
    location_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cost: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    rating: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Write EventAttendeeDB model**

Create `backend/app/modules/events/models/event_attendee.py`:

```python
"""Event attendee join table — links events to users with a role."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class EventAttendeeDB(Base):
    """An attendee (user) participating in an event with a specific role."""

    __tablename__ = "event_attendees"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_attendees_event_user"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/events/models/
git commit -m "feat(events): add EventDB and EventAttendeeDB models"
```

---

### Task 3: Backend — Alembic Migration

**Files:**
- Create: `backend/alembic/versions/055_create_events.py`

- [ ] **Step 1: Write migration using raw SQL (asyncpg-safe)**

Create `backend/alembic/versions/055_create_events.py`:

```python
"""Create events and event_attendees tables.

Revision ID: 055_create_events
Revises: 054_planner_comment
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision = "055_create_events"
down_revision = "054_planner_comment"


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("theme_primary", sa.String(100), nullable=False),
        sa.Column("theme_secondary", sa.String(100), nullable=True),
        sa.Column("region_focus", sa.String(50), nullable=False),
        sa.Column("location_city", sa.String(100), nullable=True),
        sa.Column("location_country", sa.String(100), nullable=True),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column(
            "cost",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("rating", sa.SmallInteger, nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("observations", sa.Text, nullable=True),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="ck_events_rating_range",
        ),
        sa.CheckConstraint("cost >= 0", name="ck_events_cost_positive"),
    )
    op.create_index("ix_events_start_date", "events", ["start_date"])

    op.create_table(
        "event_attendees",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "event_id",
            UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "event_id", "user_id", name="uq_event_attendees_event_user"
        ),
    )
    op.create_index(
        "ix_event_attendees_event", "event_attendees", ["event_id"]
    )
    op.create_index(
        "ix_event_attendees_user", "event_attendees", ["user_id"]
    )

    # Seed the events_manager role
    op.execute(
        "INSERT INTO roles (id, name) VALUES (gen_random_uuid(), 'events_manager')"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM user_roles WHERE role_id IN "
        "(SELECT id FROM roles WHERE name = 'events_manager')"
    )
    op.execute("DELETE FROM roles WHERE name = 'events_manager'")
    op.drop_index("ix_event_attendees_user")
    op.drop_index("ix_event_attendees_event")
    op.drop_table("event_attendees")
    op.drop_index("ix_events_start_date")
    op.drop_table("events")
```

- [ ] **Step 2: Run migration locally**

```bash
cd backend && alembic upgrade head
```

Expected: migration applies successfully, tables visible in DB.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/055_create_events.py
git commit -m "feat(events): add Alembic migration for events tables and role"
```

---

### Task 4: Backend — Permissions

**Files:**
- Modify: `backend/app/core/permissions/actions.py`
- Modify: `backend/app/core/permissions/roles.py`

- [ ] **Step 1: Add event actions to Action class**

In `backend/app/core/permissions/actions.py`, add after the `ISO_DOCS_EDIT` line (line 25):

```python
    EVENTS_VIEW = "events:view"
    EVENTS_MANAGE = "events:manage"
```

- [ ] **Step 2: Add events permissions to roles**

In `backend/app/core/permissions/roles.py`, add `Action.EVENTS_VIEW` to both `"user"` and `"manager"` sets:

```python
"user": {
    Action.SCORECARD_VIEW,
    Action.SCORECARD_EDIT_METRICS,
    Action.TRACKER_VIEW,
    Action.TRACKER_MANAGE_OWN_REPORTS,
    Action.PROJECTS_VIEW,
    Action.EVENTS_VIEW,
},
"manager": {
    Action.PROJECTS_VIEW,
    Action.PROJECTS_MANAGE,
    Action.TRACKER_VIEW,
    Action.TRACKER_MANAGE,
    Action.TRACKER_MANAGE_ALL_REPORTS,
    Action.TRACKER_MANAGE_OWN_REPORTS,
    Action.EVENTS_VIEW,
},
```

Add new role for events managers:

```python
"events_manager": {
    Action.EVENTS_VIEW,
    Action.EVENTS_MANAGE,
},
```

- [ ] **Step 3: Add frontend permission constants**

In `frontend/src/core/permissions/constants.ts`, add after the `ISO_DOCS_EDIT` line (line 20):

```typescript
  EVENTS_VIEW: 'events:view',
  EVENTS_MANAGE: 'events:manage',
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/permissions/actions.py backend/app/core/permissions/roles.py frontend/src/core/permissions/constants.ts
git commit -m "feat(events): add events:view and events:manage permissions"
```

---

### Task 5: Backend — Pydantic Schemas

**Files:**
- Create: `backend/app/modules/events/schemas/event.py`
- Create: `backend/app/modules/events/schemas/event_attendee.py`

- [ ] **Step 1: Write event schemas**

Create `backend/app/modules/events/schemas/event.py`:

```python
"""Pydantic schemas for events."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.events.constants import EventType, RegionFocus, Theme


class EventCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    event_type: EventType
    theme_primary: Theme
    theme_secondary: Theme | None = None
    region_focus: RegionFocus
    location_city: str | None = Field(None, max_length=100)
    location_country: str | None = Field(None, max_length=100)
    start_date: date
    end_date: date | None = None
    cost: Decimal = Field(default=Decimal("0"), ge=0)
    rating: int | None = Field(None, ge=1, le=5)
    url: str | None = Field(None, max_length=500)
    observations: str | None = None


class EventUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=300)
    event_type: EventType | None = None
    theme_primary: Theme | None = None
    theme_secondary: Theme | None = None
    region_focus: RegionFocus | None = None
    location_city: str | None = Field(None, max_length=100)
    location_country: str | None = Field(None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    cost: Decimal | None = Field(None, ge=0)
    rating: int | None = Field(None, ge=1, le=5)
    url: str | None = Field(None, max_length=500)
    observations: str | None = None


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    event_type: str
    theme_primary: str
    theme_secondary: str | None = None
    region_focus: str
    location_city: str | None = None
    location_country: str | None = None
    start_date: date
    end_date: date | None = None
    cost: Decimal
    rating: int | None = None
    url: str | None = None
    observations: str | None = None
    created_by: UUID | None = None
    attendee_count: int = 0
    created_at: datetime
    updated_at: datetime


class EventWithAttendeesResponse(EventResponse):
    attendees: list["AttendeeResponse"] = []


from app.modules.events.schemas.event_attendee import AttendeeResponse  # noqa: E402

EventWithAttendeesResponse.model_rebuild()
```

- [ ] **Step 2: Write attendee schemas**

Create `backend/app/modules/events/schemas/event_attendee.py`:

```python
"""Pydantic schemas for event attendees."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.events.constants import AttendeeRole


class AttendeeCreate(BaseModel):
    user_id: UUID
    role: AttendeeRole


class AttendeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    user_id: UUID
    role: str
    user_name: str | None = None
    user_email: str | None = None
    functional_area: str | None = None
    created_at: datetime
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/events/schemas/
git commit -m "feat(events): add Pydantic schemas for events and attendees"
```

---

### Task 6: Backend — Event Service (list, filter, sort)

**Files:**
- Create: `backend/app/modules/events/services/event_service.py`

- [ ] **Step 1: Write the event service with list/filter/sort logic**

Create `backend/app/modules/events/services/event_service.py`:

```python
"""Event query service — list, filter, sort, detail."""

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.user import UserDB
from app.core.sql_helpers import user_display_name_expr
from app.modules.events.models.event import EventDB
from app.modules.events.models.event_attendee import EventAttendeeDB


def _base_list_query() -> Select:
    """Base query for listing events with attendee count."""
    attendee_count = (
        select(func.count())
        .where(EventAttendeeDB.event_id == EventDB.id)
        .correlate(EventDB)
        .scalar_subquery()
        .label("attendee_count")
    )
    return select(EventDB, attendee_count)


def apply_filters(
    stmt: Select,
    *,
    search: str | None = None,
    year: int | None = None,
    quarter: int | None = None,
    event_type: str | None = None,
    theme_primary: str | None = None,
    region_focus: str | None = None,
    location_country: str | None = None,
) -> Select:
    """Apply optional filters to an event list query."""
    if search:
        stmt = stmt.where(EventDB.name.ilike(f"%{search}%"))
    if year:
        stmt = stmt.where(func.extract("year", EventDB.start_date) == year)
    if quarter:
        stmt = stmt.where(func.ceil(func.extract("month", EventDB.start_date) / 3) == quarter)
    if event_type:
        stmt = stmt.where(EventDB.event_type == event_type)
    if theme_primary:
        stmt = stmt.where(EventDB.theme_primary == theme_primary)
    if region_focus:
        stmt = stmt.where(EventDB.region_focus == region_focus)
    if location_country:
        stmt = stmt.where(EventDB.location_country == location_country)
    return stmt


SORT_COLUMNS = {
    "start_date": EventDB.start_date,
    "cost": EventDB.cost,
    "rating": EventDB.rating,
    "name": EventDB.name,
}


def apply_sort(stmt: Select, sort_by: str = "start_date", sort_dir: str = "desc") -> Select:
    """Apply sorting. Defaults to newest first."""
    col = SORT_COLUMNS.get(sort_by, EventDB.start_date)
    return stmt.order_by(col.desc() if sort_dir == "desc" else col.asc())


async def list_events(
    db: AsyncSession,
    *,
    search: str | None = None,
    year: int | None = None,
    quarter: int | None = None,
    event_type: str | None = None,
    theme_primary: str | None = None,
    region_focus: str | None = None,
    location_country: str | None = None,
    sort_by: str = "start_date",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    """Return paginated event list with attendee count and total count."""
    base = _base_list_query()
    base = apply_filters(
        base,
        search=search,
        year=year,
        quarter=quarter,
        event_type=event_type,
        theme_primary=theme_primary,
        region_focus=region_focus,
        location_country=location_country,
    )

    # Total count
    count_stmt = select(func.count()).select_from(
        apply_filters(
            select(EventDB.id),
            search=search,
            year=year,
            quarter=quarter,
            event_type=event_type,
            theme_primary=theme_primary,
            region_focus=region_focus,
            location_country=location_country,
        ).subquery()
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginated results
    stmt = apply_sort(base, sort_by, sort_dir)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()

    results = []
    for event, attendee_count in rows:
        d = {c.key: getattr(event, c.key) for c in EventDB.__table__.columns}
        d["attendee_count"] = attendee_count
        results.append(d)

    return results, total


async def get_event_with_attendees(event_id: UUID, db: AsyncSession) -> dict | None:
    """Get a single event with full attendee details."""
    result = await db.execute(select(EventDB).where(EventDB.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        return None

    user_alias = aliased(UserDB)
    fa_alias = aliased(FunctionalAreaDB)

    att_stmt = (
        select(
            EventAttendeeDB,
            user_display_name_expr(user_alias).label("user_name"),
            user_alias.email.label("user_email"),
            fa_alias.name.label("functional_area"),
        )
        .join(user_alias, EventAttendeeDB.user_id == user_alias.id)
        .outerjoin(fa_alias, user_alias.functional_area_id == fa_alias.id)
        .where(EventAttendeeDB.event_id == event_id)
        .order_by(user_display_name_expr(user_alias))
    )
    att_rows = (await db.execute(att_stmt)).all()

    attendees = []
    for att, user_name, user_email, functional_area in att_rows:
        attendees.append({
            "id": att.id,
            "event_id": att.event_id,
            "user_id": att.user_id,
            "role": att.role,
            "user_name": user_name,
            "user_email": user_email,
            "functional_area": functional_area,
            "created_at": att.created_at,
        })

    d = {c.key: getattr(event, c.key) for c in EventDB.__table__.columns}
    d["attendee_count"] = len(attendees)
    d["attendees"] = attendees
    return d
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/modules/events/services/event_service.py
git commit -m "feat(events): add event service with list/filter/sort/detail"
```

---

### Task 7: Backend — Stats Service

**Files:**
- Create: `backend/app/modules/events/services/stats_service.py`

- [ ] **Step 1: Write stats aggregation service**

Create `backend/app/modules/events/services/stats_service.py`:

```python
"""Event statistics — aggregated views for the dashboard."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.user import UserDB
from app.modules.events.models.event import EventDB
from app.modules.events.models.event_attendee import EventAttendeeDB


async def get_stats(db: AsyncSession, year: int | None = None) -> dict:
    """Return aggregated event statistics."""
    year_filter = (
        (func.extract("year", EventDB.start_date) == year) if year else True
    )

    by_quarter = await _group_count(
        db,
        func.concat(
            func.extract("year", EventDB.start_date).cast(str),
            "-Q",
            func.ceil(func.extract("month", EventDB.start_date) / 3).cast(str),
        ).label("quarter"),
        year_filter,
    )

    by_theme = await _group_count(
        db, EventDB.theme_primary.label("theme"), year_filter
    )

    by_type = await _group_count(
        db, EventDB.event_type.label("event_type"), year_filter
    )

    by_region = await _group_count(
        db, EventDB.region_focus.label("region"), year_filter
    )

    by_country = await _group_count(
        db, EventDB.location_country.label("country"), year_filter
    )

    by_role = await _attendee_group_count(
        db, EventAttendeeDB.role.label("role"), year_filter
    )

    by_fa = await _attendee_fa_count(db, year_filter)

    total_cost_stmt = select(func.coalesce(func.sum(EventDB.cost), 0)).where(year_filter)
    total_cost = float((await db.execute(total_cost_stmt)).scalar_one())

    total_events_stmt = select(func.count(EventDB.id.distinct())).where(year_filter)
    total_events = (await db.execute(total_events_stmt)).scalar() or 0

    attendee_stmt = (
        select(func.count(EventAttendeeDB.user_id.distinct()))
        .join(EventDB, EventAttendeeDB.event_id == EventDB.id)
        .where(year_filter)
    )
    total_attendees = (await db.execute(attendee_stmt)).scalar() or 0

    return {
        "total_events": total_events,
        "total_attendees": total_attendees,
        "total_cost": total_cost,
        "by_quarter": by_quarter,
        "by_theme": by_theme,
        "by_type": by_type,
        "by_region": by_region,
        "by_country": by_country,
        "by_role": by_role,
        "by_fa": by_fa,
    }


async def _group_count(
    db: AsyncSession, label_col, year_filter
) -> list[dict]:
    """Count distinct events grouped by a column."""
    stmt = (
        select(label_col, func.count(EventDB.id.distinct()).label("count"))
        .where(year_filter)
        .group_by(label_col)
        .order_by(func.count(EventDB.id.distinct()).desc())
    )
    rows = (await db.execute(stmt)).all()
    return [{"label": row[0], "count": row[1]} for row in rows if row[0] is not None]


async def _attendee_group_count(
    db: AsyncSession, label_col, year_filter
) -> list[dict]:
    """Count event-attendee pairs grouped by an attendee column."""
    stmt = (
        select(label_col, func.count().label("count"))
        .join(EventDB, EventAttendeeDB.event_id == EventDB.id)
        .where(year_filter)
        .group_by(label_col)
        .order_by(func.count().desc())
    )
    rows = (await db.execute(stmt)).all()
    return [{"label": row[0], "count": row[1]} for row in rows]


async def _attendee_fa_count(db: AsyncSession, year_filter) -> list[dict]:
    """Count event participations grouped by functional area."""
    user_alias = aliased(UserDB)
    fa_alias = aliased(FunctionalAreaDB)
    stmt = (
        select(fa_alias.name.label("fa"), func.count().label("count"))
        .select_from(EventAttendeeDB)
        .join(EventDB, EventAttendeeDB.event_id == EventDB.id)
        .join(user_alias, EventAttendeeDB.user_id == user_alias.id)
        .join(fa_alias, user_alias.functional_area_id == fa_alias.id)
        .where(year_filter)
        .group_by(fa_alias.name)
        .order_by(func.count().desc())
    )
    rows = (await db.execute(stmt)).all()
    return [{"label": row[0], "count": row[1]} for row in rows]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/modules/events/services/stats_service.py
git commit -m "feat(events): add stats aggregation service"
```

---

### Task 8: Backend — API Endpoints (events CRUD)

**Files:**
- Create: `backend/app/modules/events/api/events.py`

- [ ] **Step 1: Write events CRUD router**

Create `backend/app/modules/events/api/events.py`:

```python
"""Event CRUD endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import DBSession, CurrentUser
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.modules.events.models.event import EventDB
from app.modules.events.schemas.event import (
    EventCreate,
    EventResponse,
    EventUpdate,
    EventWithAttendeesResponse,
)
from app.modules.events.services import event_service

EventsViewer = Annotated[TokenData, Depends(require_permission(Action.EVENTS_VIEW))]
EventsManager = Annotated[TokenData, Depends(require_permission(Action.EVENTS_MANAGE))]

router = APIRouter()


@router.get("")
async def list_events(
    db: DBSession,
    user: EventsViewer,
    search: str | None = None,
    year: int | None = None,
    quarter: int | None = Query(None, ge=1, le=4),
    event_type: str | None = None,
    theme_primary: str | None = None,
    region_focus: str | None = None,
    location_country: str | None = None,
    sort_by: str = Query("start_date", pattern="^(start_date|cost|rating|name)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict:
    """List events with filters, sorting, and pagination."""
    results, total = await event_service.list_events(
        db,
        search=search,
        year=year,
        quarter=quarter,
        event_type=event_type,
        theme_primary=theme_primary,
        region_focus=region_focus,
        location_country=location_country,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [EventResponse(**r) for r in results],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{event_id}", responses={404: {"description": "Event not found"}})
async def get_event(
    event_id: UUID,
    db: DBSession,
    user: EventsViewer,
) -> EventWithAttendeesResponse:
    """Get event detail with attendees."""
    result = await event_service.get_event_with_attendees(event_id, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return EventWithAttendeesResponse(**result)


@router.post("", status_code=201, responses={400: {"description": "Validation error"}})
async def create_event(
    data: EventCreate,
    db: DBSession,
    user: EventsManager,
) -> EventResponse:
    """Create a new event."""
    event = EventDB(
        **data.model_dump(),
        created_by=user.user_id,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    resp = {c.key: getattr(event, c.key) for c in EventDB.__table__.columns}
    resp["attendee_count"] = 0
    return EventResponse(**resp)


@router.put("/{event_id}", responses={404: {"description": "Event not found"}})
async def update_event(
    event_id: UUID,
    data: EventUpdate,
    db: DBSession,
    user: EventsManager,
) -> EventResponse:
    """Update an existing event."""
    result = await db.execute(select(EventDB).where(EventDB.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    await db.flush()
    await db.refresh(event)
    resp = {c.key: getattr(event, c.key) for c in EventDB.__table__.columns}
    resp["attendee_count"] = 0
    return EventResponse(**resp)


@router.delete(
    "/{event_id}",
    status_code=204,
    responses={404: {"description": "Event not found"}},
)
async def delete_event(
    event_id: UUID,
    db: DBSession,
    user: EventsManager,
) -> None:
    """Delete an event (cascades attendees)."""
    result = await db.execute(select(EventDB).where(EventDB.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    await db.delete(event)
    await db.flush()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/modules/events/api/events.py
git commit -m "feat(events): add CRUD API endpoints"
```

---

### Task 9: Backend — API Endpoints (attendees, stats, options)

**Files:**
- Create: `backend/app/modules/events/api/attendees.py`
- Create: `backend/app/modules/events/api/stats.py`
- Create: `backend/app/modules/events/api/options.py`

- [ ] **Step 1: Write attendees router**

Create `backend/app/modules/events/api/attendees.py`:

```python
"""Event attendee management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.modules.events.models.event import EventDB
from app.modules.events.models.event_attendee import EventAttendeeDB
from app.modules.events.schemas.event_attendee import AttendeeCreate, AttendeeResponse
from app.modules.events.services.event_service import get_event_with_attendees

EventsManager = Annotated[TokenData, Depends(require_permission(Action.EVENTS_MANAGE))]

router = APIRouter()


@router.post(
    "/{event_id}/attendees",
    status_code=201,
    responses={
        404: {"description": "Event not found"},
        409: {"description": "Attendee already exists"},
    },
)
async def add_attendees(
    event_id: UUID,
    attendees: list[AttendeeCreate],
    db: DBSession,
    user: EventsManager,
) -> list[AttendeeResponse]:
    """Add one or more attendees to an event."""
    event = await db.execute(select(EventDB).where(EventDB.id == event_id))
    if not event.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    created = []
    for att in attendees:
        row = EventAttendeeDB(
            event_id=event_id,
            user_id=att.user_id,
            role=att.role,
        )
        db.add(row)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User {att.user_id} is already an attendee of this event",
            )
        await db.refresh(row)
        created.append(row)

    # Re-fetch with user details
    detail = await get_event_with_attendees(event_id, db)
    attendee_ids = {c.id for c in created}
    return [
        AttendeeResponse(**a)
        for a in detail["attendees"]
        if a["id"] in attendee_ids
    ]


@router.delete(
    "/{event_id}/attendees/{user_id}",
    status_code=204,
    responses={404: {"description": "Attendee not found"}},
)
async def remove_attendee(
    event_id: UUID,
    user_id: UUID,
    db: DBSession,
    user: EventsManager,
) -> None:
    """Remove an attendee from an event."""
    result = await db.execute(
        select(EventAttendeeDB).where(
            EventAttendeeDB.event_id == event_id,
            EventAttendeeDB.user_id == user_id,
        )
    )
    attendee = result.scalar_one_or_none()
    if not attendee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendee not found"
        )
    await db.delete(attendee)
    await db.flush()
```

- [ ] **Step 2: Write stats router**

Create `backend/app/modules/events/api/stats.py`:

```python
"""Event statistics endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.modules.events.services import stats_service

EventsViewer = Annotated[TokenData, Depends(require_permission(Action.EVENTS_VIEW))]

router = APIRouter()


@router.get("/stats")
async def get_event_stats(
    db: DBSession,
    user: EventsViewer,
    year: int | None = None,
) -> dict:
    """Get aggregated event statistics."""
    return await stats_service.get_stats(db, year=year)
```

- [ ] **Step 3: Write options router**

Create `backend/app/modules/events/api/options.py`:

```python
"""Event enum options endpoint — populates frontend selects."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.modules.events.constants import AttendeeRole, EventType, RegionFocus, Theme

EventsViewer = Annotated[TokenData, Depends(require_permission(Action.EVENTS_VIEW))]

router = APIRouter()


@router.get("/options")
async def get_event_options(user: EventsViewer) -> dict:
    """Return all enum lists for populating select controls."""
    return {
        "event_types": [e.value for e in EventType],
        "themes": [t.value for t in Theme],
        "regions": [r.value for r in RegionFocus],
        "attendee_roles": [r.value for r in AttendeeRole],
    }
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/events/api/attendees.py backend/app/modules/events/api/stats.py backend/app/modules/events/api/options.py
git commit -m "feat(events): add attendees, stats, and options endpoints"
```

---

### Task 10: Backend — Router Aggregation and Mounting

**Files:**
- Create: `backend/app/modules/events/router.py`
- Create: `backend/app/modules/events/public.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write router.py**

Create `backend/app/modules/events/router.py`:

```python
"""Events module router — aggregates all events sub-routers."""

from fastapi import APIRouter

from app.modules.events.api import attendees as attendees_router
from app.modules.events.api import events as events_router
from app.modules.events.api import options as options_router
from app.modules.events.api import stats as stats_router

router = APIRouter()

router.include_router(
    events_router.router,
    tags=["events"],
)
router.include_router(
    attendees_router.router,
    tags=["events:attendees"],
)
router.include_router(
    stats_router.router,
    tags=["events:stats"],
)
router.include_router(
    options_router.router,
    tags=["events:options"],
)
```

- [ ] **Step 2: Write minimal public.py**

Create `backend/app/modules/events/public.py`:

```python
"""Public interface for the events module.

Other modules should import from here, never from events internals.
"""
```

- [ ] **Step 3: Mount in main.py**

In `backend/app/main.py`, add import after the tracker import (line 33):

```python
from app.modules.events.router import router as events_router
```

Add router mounting after the iso-docs line (line 248):

```python
app.include_router(events_router, prefix="/api/events", tags=["events"])
```

- [ ] **Step 4: Verify the API starts**

```bash
cd backend && python -c "from app.main import app; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/events/router.py backend/app/modules/events/public.py backend/app/main.py
git commit -m "feat(events): mount events router in main app"
```

---

### Task 11: Backend — Excel Import Endpoint

**Files:**
- Create: `backend/app/modules/events/api/import_events.py`

- [ ] **Step 1: Write import endpoint**

Create `backend/app/modules/events/api/import_events.py`:

```python
"""One-shot Excel import for historical event data."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.models.user import UserDB
from app.core.permissions import Action, require_permission
from app.core.sql_helpers import user_display_name_expr
from app.modules.events.models.event import EventDB
from app.modules.events.models.event_attendee import EventAttendeeDB

EventsManager = Annotated[TokenData, Depends(require_permission(Action.EVENTS_MANAGE))]

logger = structlog.get_logger()

router = APIRouter()


@router.post("/import", responses={400: {"description": "Import error"}})
async def import_events_from_excel(
    file: UploadFile = File(...),
    db: DBSession = None,
    user: EventsManager = None,
) -> dict:
    """Import events from the Excel file. Matches attendees to VizzHub users by name."""
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be .xlsx",
        )

    content = await file.read()

    import io
    wb = load_workbook(io.BytesIO(content), data_only=True)
    ws = wb["Events"]

    # Build user lookup by display name (lowercase)
    user_alias = UserDB.__table__.alias("u")
    user_rows = (await db.execute(select(UserDB))).scalars().all()
    user_lookup: dict[str, UserDB] = {}
    for u in user_rows:
        names = []
        full = " ".join(filter(None, [u.first_name, u.last_name])).strip()
        if full:
            names.append(full.lower())
        if u.name:
            names.append(u.name.lower())
        for n in names:
            user_lookup[n] = u

    # Parse rows — group by event (same name + start_date)
    events_map: dict[tuple, dict] = {}
    attendees_raw: list[tuple[tuple, str, str]] = []

    headers = [cell.value for cell in ws[1]]
    col_idx = {h: i for i, h in enumerate(headers) if h}

    skipped = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        name = row[col_idx.get("Event_name", 0)]
        if not name:
            continue

        start_date = row[col_idx.get("Start_date", 7)]
        if not start_date:
            skipped += 1
            continue

        if hasattr(start_date, "date"):
            start_date = start_date.date()

        key = (str(name).strip(), str(start_date))

        if key not in events_map:
            end_date = row[col_idx.get("End_date", 8)]
            if hasattr(end_date, "date"):
                end_date = end_date.date()

            cost_val = row[col_idx.get("Cost", 14)]
            try:
                cost = float(cost_val) if cost_val else 0
            except (ValueError, TypeError):
                cost = 0

            events_map[key] = {
                "name": str(name).strip(),
                "event_type": str(row[col_idx.get("Event_type", 1)] or "Other").strip(),
                "theme_primary": str(row[col_idx.get("Theme_Sector_primary", 2)] or "Other").strip(),
                "theme_secondary": (
                    str(row[col_idx.get("Theme_Sector_secondary", 3)]).strip()
                    if row[col_idx.get("Theme_Sector_secondary", 3)]
                    else None
                ),
                "region_focus": str(row[col_idx.get("Region_focus", 4)] or "Global").strip(),
                "location_city": (
                    str(row[col_idx.get("Location_City", 5)]).strip()
                    if row[col_idx.get("Location_City", 5)]
                    else None
                ),
                "location_country": (
                    str(row[col_idx.get("Location_Country", 6)]).strip()
                    if row[col_idx.get("Location_Country", 6)]
                    else None
                ),
                "start_date": start_date,
                "end_date": end_date,
                "cost": cost,
            }

        attendee_name = row[col_idx.get("Attendee_name", 11)]
        role = row[col_idx.get("Role_event", 13)]
        if attendee_name:
            attendees_raw.append((key, str(attendee_name).strip(), str(role or "Attendee").strip()))

    # Insert events
    event_db_map: dict[tuple, EventDB] = {}
    for key, data in events_map.items():
        event = EventDB(**data, created_by=user.user_id)
        db.add(event)
        await db.flush()
        await db.refresh(event)
        event_db_map[key] = event

    # Insert attendees
    matched = 0
    unmatched_names = set()
    for key, attendee_name, role in attendees_raw:
        event = event_db_map.get(key)
        if not event:
            continue

        matched_user = user_lookup.get(attendee_name.lower())
        if not matched_user:
            unmatched_names.add(attendee_name)
            continue

        att = EventAttendeeDB(
            event_id=event.id,
            user_id=matched_user.id,
            role=role,
        )
        db.add(att)
        matched += 1

    await db.flush()

    logger.info(
        "events_imported",
        events_created=len(event_db_map),
        attendees_matched=matched,
        attendees_unmatched=len(unmatched_names),
        skipped_rows=skipped,
    )

    return {
        "events_created": len(event_db_map),
        "attendees_matched": matched,
        "unmatched_attendee_names": sorted(unmatched_names),
        "skipped_rows": skipped,
    }
```

- [ ] **Step 2: Add import router to router.py**

In `backend/app/modules/events/router.py`, add:

```python
from app.modules.events.api import import_events as import_events_router

router.include_router(
    import_events_router.router,
    tags=["events:import"],
)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/events/api/import_events.py backend/app/modules/events/router.py
git commit -m "feat(events): add Excel import endpoint"
```

---

### Task 12: Backend — Tests

**Files:**
- Create: `backend/tests/modules/events/test_events_api.py`

- [ ] **Step 1: Write comprehensive API tests**

Create `backend/tests/modules/events/test_events_api.py` (and `__init__.py`):

```bash
mkdir -p backend/tests/modules/events
touch backend/tests/modules/events/__init__.py
```

```python
"""Tests for events module API endpoints."""

import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.asyncio
async def test_list_events_empty(client: AsyncClient, auth_headers: dict):
    """GET /api/events returns empty list when no events exist."""
    resp = await client.get("/api/events", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_event(client: AsyncClient, manager_headers: dict):
    """POST /api/events creates an event and returns it."""
    payload = {
        "name": "Test Conference 2026",
        "event_type": "Conference",
        "theme_primary": "Climate",
        "region_focus": "Europe",
        "start_date": "2026-06-15",
        "end_date": "2026-06-17",
        "cost": 1500.00,
        "rating": 4,
        "location_city": "Madrid",
        "location_country": "Spain",
    }
    resp = await client.post("/api/events", json=payload, headers=manager_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Conference 2026"
    assert data["event_type"] == "Conference"
    assert data["rating"] == 4
    assert float(data["cost"]) == 1500.00
    assert data["attendee_count"] == 0
    return data["id"]


@pytest.mark.asyncio
async def test_create_event_forbidden_without_manage(client: AsyncClient, auth_headers: dict):
    """POST /api/events returns 403 for users without events:manage."""
    payload = {
        "name": "Forbidden Event",
        "event_type": "Workshop",
        "theme_primary": "Other",
        "region_focus": "Global",
        "start_date": "2026-01-01",
    }
    resp = await client.post("/api/events", json=payload, headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_event_detail(client: AsyncClient, manager_headers: dict):
    """GET /api/events/{id} returns event with attendees list."""
    create_resp = await client.post(
        "/api/events",
        json={
            "name": "Detail Test",
            "event_type": "Summit",
            "theme_primary": "Data & Technology",
            "region_focus": "Global",
            "start_date": "2026-03-01",
        },
        headers=manager_headers,
    )
    event_id = create_resp.json()["id"]

    resp = await client.get(f"/api/events/{event_id}", headers=manager_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Detail Test"
    assert data["attendees"] == []


@pytest.mark.asyncio
async def test_update_event(client: AsyncClient, manager_headers: dict):
    """PUT /api/events/{id} updates fields."""
    create_resp = await client.post(
        "/api/events",
        json={
            "name": "Update Test",
            "event_type": "Forum",
            "theme_primary": "Climate",
            "region_focus": "Europe",
            "start_date": "2026-04-01",
        },
        headers=manager_headers,
    )
    event_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/events/{event_id}",
        json={"name": "Updated Name", "rating": 5},
        headers=manager_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
    assert resp.json()["rating"] == 5


@pytest.mark.asyncio
async def test_delete_event(client: AsyncClient, manager_headers: dict):
    """DELETE /api/events/{id} removes the event."""
    create_resp = await client.post(
        "/api/events",
        json={
            "name": "Delete Test",
            "event_type": "Workshop",
            "theme_primary": "Other",
            "region_focus": "Global",
            "start_date": "2026-05-01",
        },
        headers=manager_headers,
    )
    event_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/events/{event_id}", headers=manager_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/events/{event_id}", headers=manager_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_event_not_found(client: AsyncClient, auth_headers: dict):
    """GET /api/events/{id} returns 404 for missing event."""
    resp = await client.get(f"/api/events/{uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_options(client: AsyncClient, auth_headers: dict):
    """GET /api/events/options returns enum lists."""
    resp = await client.get("/api/events/options", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "event_types" in data
    assert "Conference" in data["event_types"]
    assert "themes" in data
    assert "regions" in data
    assert "attendee_roles" in data


@pytest.mark.asyncio
async def test_get_stats_empty(client: AsyncClient, auth_headers: dict):
    """GET /api/events/stats returns zeros when no events."""
    resp = await client.get("/api/events/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_events"] == 0
    assert data["total_cost"] == 0


@pytest.mark.asyncio
async def test_add_and_remove_attendee(
    client: AsyncClient, manager_headers: dict, test_user_id: str
):
    """POST/DELETE attendees on an event."""
    create_resp = await client.post(
        "/api/events",
        json={
            "name": "Attendee Test",
            "event_type": "Conference",
            "theme_primary": "Climate",
            "region_focus": "Europe",
            "start_date": "2026-07-01",
        },
        headers=manager_headers,
    )
    event_id = create_resp.json()["id"]

    # Add attendee
    resp = await client.post(
        f"/api/events/{event_id}/attendees",
        json=[{"user_id": test_user_id, "role": "Speaker"}],
        headers=manager_headers,
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 1
    assert resp.json()[0]["role"] == "Speaker"

    # Verify in detail
    detail = await client.get(f"/api/events/{event_id}", headers=manager_headers)
    assert len(detail.json()["attendees"]) == 1

    # Remove attendee
    resp = await client.delete(
        f"/api/events/{event_id}/attendees/{test_user_id}",
        headers=manager_headers,
    )
    assert resp.status_code == 204

    # Verify removed
    detail = await client.get(f"/api/events/{event_id}", headers=manager_headers)
    assert len(detail.json()["attendees"]) == 0


@pytest.mark.asyncio
async def test_duplicate_attendee_returns_409(
    client: AsyncClient, manager_headers: dict, test_user_id: str
):
    """Adding the same user twice to an event returns 409."""
    create_resp = await client.post(
        "/api/events",
        json={
            "name": "Dup Test",
            "event_type": "Workshop",
            "theme_primary": "Other",
            "region_focus": "Global",
            "start_date": "2026-08-01",
        },
        headers=manager_headers,
    )
    event_id = create_resp.json()["id"]

    await client.post(
        f"/api/events/{event_id}/attendees",
        json=[{"user_id": test_user_id, "role": "Attendee"}],
        headers=manager_headers,
    )

    resp = await client.post(
        f"/api/events/{event_id}/attendees",
        json=[{"user_id": test_user_id, "role": "Speaker"}],
        headers=manager_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_events_with_filters(client: AsyncClient, manager_headers: dict):
    """GET /api/events with filters returns matching events."""
    await client.post(
        "/api/events",
        json={
            "name": "Climate Summit",
            "event_type": "Summit",
            "theme_primary": "Climate",
            "region_focus": "Europe",
            "start_date": "2026-03-15",
            "cost": 2000,
        },
        headers=manager_headers,
    )
    await client.post(
        "/api/events",
        json={
            "name": "Tech Workshop",
            "event_type": "Workshop",
            "theme_primary": "Data & Technology",
            "region_focus": "Global",
            "start_date": "2026-06-01",
            "cost": 500,
        },
        headers=manager_headers,
    )

    # Filter by theme
    resp = await client.get(
        "/api/events?theme_primary=Climate", headers=manager_headers
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(e["theme_primary"] == "Climate" for e in items)

    # Search by name
    resp = await client.get("/api/events?search=Tech", headers=manager_headers)
    assert resp.status_code == 200
    assert any("Tech" in e["name"] for e in resp.json()["items"])

    # Sort by cost ascending
    resp = await client.get(
        "/api/events?sort_by=cost&sort_dir=asc", headers=manager_headers
    )
    assert resp.status_code == 200
    costs = [float(e["cost"]) for e in resp.json()["items"]]
    assert costs == sorted(costs)
```

Note: This test file assumes the test harness provides `client`, `auth_headers` (user with `events:view`), `manager_headers` (user with `events:manage`), and `test_user_id` fixtures. Adapt fixture names to match the existing test setup in `backend/tests/conftest.py`.

- [ ] **Step 2: Run tests**

```bash
cd backend && pytest tests/modules/events/ -v
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/modules/events/
git commit -m "test(events): add API tests for events CRUD, attendees, stats, options"
```

---

### Task 13: Frontend — Types and Constants

**Files:**
- Create: `frontend/src/modules/events/types/events.ts`
- Create: `frontend/src/modules/events/utils/constants.ts`

- [ ] **Step 1: Create module directory structure**

```bash
mkdir -p frontend/src/modules/events/{components,hooks,pages,services,types,utils}
```

- [ ] **Step 2: Write TypeScript types**

Create `frontend/src/modules/events/types/events.ts`:

```typescript
export const EVENT_TYPES = [
  'Conference', 'Summit', 'Forum', 'Workshop', 'Symposium',
  'Multi-event', 'Networking event', 'Roundtable', 'Training',
  'Webinar', 'Exhibition / Expo', 'Internal event', 'Other',
] as const;
export type EventType = typeof EVENT_TYPES[number];

export const THEMES = [
  'Climate', 'Nature & Biodiversity', 'Oceans & Water',
  'Food & Land Systems', 'Energy & Net Zero', 'Data & Technology',
  'Policy & Finance', 'Social Justice', 'Urban & Cities', 'Other',
] as const;
export type Theme = typeof THEMES[number];

export const REGIONS = [
  'Global', 'Europe', 'North America', 'Latin America & Caribbean',
  'Africa', 'Asia-Pacific', 'Middle East',
] as const;
export type RegionFocus = typeof REGIONS[number];

export const ATTENDEE_ROLES = [
  'Attendee', 'Speaker', 'Panelist', 'Moderator', 'Exhibitor', 'Organizer',
] as const;
export type AttendeeRole = typeof ATTENDEE_ROLES[number];

export interface EventSummary {
  id: string;
  name: string;
  event_type: string;
  theme_primary: string;
  theme_secondary: string | null;
  region_focus: string;
  location_city: string | null;
  location_country: string | null;
  start_date: string;
  end_date: string | null;
  cost: number;
  rating: number | null;
  url: string | null;
  observations: string | null;
  created_by: string | null;
  attendee_count: number;
  created_at: string;
  updated_at: string;
}

export interface Attendee {
  id: string;
  event_id: string;
  user_id: string;
  role: string;
  user_name: string | null;
  user_email: string | null;
  functional_area: string | null;
  created_at: string;
}

export interface EventDetail extends EventSummary {
  attendees: Attendee[];
}

export interface EventCreate {
  name: string;
  event_type: EventType;
  theme_primary: Theme;
  theme_secondary?: Theme | null;
  region_focus: RegionFocus;
  location_city?: string | null;
  location_country?: string | null;
  start_date: string;
  end_date?: string | null;
  cost?: number;
  rating?: number | null;
  url?: string | null;
  observations?: string | null;
}

export interface EventUpdate extends Partial<EventCreate> {}

export interface EventListResponse {
  items: EventSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface EventListParams {
  search?: string;
  year?: number;
  quarter?: number;
  event_type?: string;
  theme_primary?: string;
  region_focus?: string;
  location_country?: string;
  sort_by?: string;
  sort_dir?: string;
  page?: number;
  page_size?: number;
}

export interface StatGroup {
  label: string;
  count: number;
}

export interface EventStats {
  total_events: number;
  total_attendees: number;
  total_cost: number;
  by_quarter: StatGroup[];
  by_theme: StatGroup[];
  by_type: StatGroup[];
  by_region: StatGroup[];
  by_country: StatGroup[];
  by_role: StatGroup[];
  by_fa: StatGroup[];
}

export interface EventOptions {
  event_types: string[];
  themes: string[];
  regions: string[];
  attendee_roles: string[];
}
```

- [ ] **Step 3: Write constants**

Create `frontend/src/modules/events/utils/constants.ts`:

```typescript
export const THEME_COLORS: Record<string, string> = {
  'Climate': '#2563eb',
  'Nature & Biodiversity': '#16a34a',
  'Oceans & Water': '#0891b2',
  'Food & Land Systems': '#ca8a04',
  'Energy & Net Zero': '#ea580c',
  'Data & Technology': '#7c3aed',
  'Policy & Finance': '#dc2626',
  'Social Justice': '#db2777',
  'Urban & Cities': '#64748b',
  'Other': '#9ca3af',
};

export const ROLE_COLORS: Record<string, string> = {
  'Speaker': '#2563eb',
  'Panelist': '#7c3aed',
  'Moderator': '#0891b2',
  'Organizer': '#16a34a',
  'Exhibitor': '#ca8a04',
  'Attendee': '#64748b',
};
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/events/
git commit -m "feat(events): add frontend types and constants"
```

---

### Task 14: Frontend — API Service and Query Keys

**Files:**
- Create: `frontend/src/modules/events/services/events.ts`
- Modify: `frontend/src/core/hooks/queryKeys.ts`

- [ ] **Step 1: Write API service**

Create `frontend/src/modules/events/services/events.ts`:

```typescript
import api from '@/core/services/client';
import type {
  EventCreate,
  EventDetail,
  EventListParams,
  EventListResponse,
  EventOptions,
  EventStats,
  EventSummary,
  EventUpdate,
} from '../types/events';

export const eventsApi = {
  list: async (params: EventListParams = {}): Promise<EventListResponse> => {
    const response = await api.get<EventListResponse>('/events', { params });
    return response.data;
  },

  get: async (id: string): Promise<EventDetail> => {
    const response = await api.get<EventDetail>(`/events/${id}`);
    return response.data;
  },

  create: async (data: EventCreate): Promise<EventSummary> => {
    const response = await api.post<EventSummary>('/events', data);
    return response.data;
  },

  update: async (id: string, data: EventUpdate): Promise<EventSummary> => {
    const response = await api.put<EventSummary>(`/events/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/events/${id}`);
  },

  addAttendees: async (
    eventId: string,
    attendees: { user_id: string; role: string }[],
  ): Promise<void> => {
    await api.post(`/events/${eventId}/attendees`, attendees);
  },

  removeAttendee: async (eventId: string, userId: string): Promise<void> => {
    await api.delete(`/events/${eventId}/attendees/${userId}`);
  },

  stats: async (year?: number): Promise<EventStats> => {
    const response = await api.get<EventStats>('/events/stats', {
      params: year ? { year } : {},
    });
    return response.data;
  },

  options: async (): Promise<EventOptions> => {
    const response = await api.get<EventOptions>('/events/options');
    return response.data;
  },
};
```

- [ ] **Step 2: Add query keys**

In `frontend/src/core/hooks/queryKeys.ts`, add before the closing `} as const;` (line 247):

```typescript
  events: {
    all: ['events'] as const,
    list: (params: Record<string, unknown>) => ['events', 'list', params] as const,
    detail: (id: string) => ['events', id] as const,
    stats: (year?: number) => ['events', 'stats', year] as const,
    options: ['events', 'options'] as const,
  },
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/events/services/events.ts frontend/src/core/hooks/queryKeys.ts
git commit -m "feat(events): add API service and query keys"
```

---

### Task 15: Frontend — React Query Hooks

**Files:**
- Create: `frontend/src/modules/events/hooks/useEvents.ts`
- Create: `frontend/src/modules/events/hooks/useEvent.ts`
- Create: `frontend/src/modules/events/hooks/useEventStats.ts`
- Create: `frontend/src/modules/events/hooks/useEventOptions.ts`

- [ ] **Step 1: Write useEvents hook (list + mutations)**

Create `frontend/src/modules/events/hooks/useEvents.ts`:

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { eventsApi } from '../services/events';
import type { EventCreate, EventListParams, EventUpdate } from '../types/events';

export function useEvents(params: EventListParams = {}) {
  return useQuery({
    queryKey: queryKeys.events.list(params),
    queryFn: () => eventsApi.list(params),
  });
}

export function useCreateEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: EventCreate) => eventsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
    },
  });
}

export function useUpdateEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: EventUpdate }) =>
      eventsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
    },
  });
}

export function useDeleteEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => eventsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
    },
  });
}
```

- [ ] **Step 2: Write useEvent hook (detail + attendee mutations)**

Create `frontend/src/modules/events/hooks/useEvent.ts`:

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { eventsApi } from '../services/events';

export function useEvent(id: string) {
  return useQuery({
    queryKey: queryKeys.events.detail(id),
    queryFn: () => eventsApi.get(id),
    enabled: !!id,
  });
}

export function useAddAttendees() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      eventId,
      attendees,
    }: {
      eventId: string;
      attendees: { user_id: string; role: string }[];
    }) => eventsApi.addAttendees(eventId, attendees),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.events.detail(variables.eventId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
    },
  });
}

export function useRemoveAttendee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ eventId, userId }: { eventId: string; userId: string }) =>
      eventsApi.removeAttendee(eventId, userId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.events.detail(variables.eventId),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
    },
  });
}
```

- [ ] **Step 3: Write useEventStats and useEventOptions hooks**

Create `frontend/src/modules/events/hooks/useEventStats.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { eventsApi } from '../services/events';

export function useEventStats(year?: number) {
  return useQuery({
    queryKey: queryKeys.events.stats(year),
    queryFn: () => eventsApi.stats(year),
  });
}
```

Create `frontend/src/modules/events/hooks/useEventOptions.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { eventsApi } from '../services/events';

export function useEventOptions() {
  return useQuery({
    queryKey: queryKeys.events.options,
    queryFn: eventsApi.options,
    staleTime: Infinity,
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/events/hooks/
git commit -m "feat(events): add React Query hooks"
```

---

### Task 16: Frontend — EventCard Component

**Files:**
- Create: `frontend/src/modules/events/components/EventCard.tsx`
- Create: `frontend/src/modules/events/components/StarRating.tsx`

- [ ] **Step 1: Write StarRating component**

Create `frontend/src/modules/events/components/StarRating.tsx`:

```tsx
import { Star } from 'lucide-react';

interface StarRatingProps {
  readonly value: number | null;
  readonly onChange?: (value: number) => void;
  readonly size?: number;
}

export function StarRating({ value, onChange, size = 16 }: StarRatingProps): JSX.Element {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          disabled={!onChange}
          onClick={() => onChange?.(star)}
          className={onChange ? 'cursor-pointer hover:scale-110 transition-transform' : 'cursor-default'}
        >
          <Star
            size={size}
            className={
              value !== null && star <= value
                ? 'fill-amber-400 text-amber-400'
                : 'text-muted-foreground/30'
            }
          />
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Write EventCard component**

Create `frontend/src/modules/events/components/EventCard.tsx`:

```tsx
import { Calendar, ExternalLink, MapPin, Users } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { StarRating } from './StarRating';
import { THEME_COLORS } from '../utils/constants';
import type { EventSummary } from '../types/events';

interface EventCardProps {
  readonly event: EventSummary;
  readonly onClick: (id: string) => void;
}

function formatDateRange(start: string, end: string | null): string {
  const s = new Date(start).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
  if (!end || end === start) return s;
  const e = new Date(end).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
  return `${s} — ${e}`;
}

function formatCost(cost: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cost);
}

export function EventCard({ event, onClick }: EventCardProps): JSX.Element {
  const themeColor = THEME_COLORS[event.theme_primary] ?? THEME_COLORS['Other'];

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow flex flex-col"
      onClick={() => onClick(event.id)}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-sm leading-tight line-clamp-2">
            {event.name}
          </h3>
          <StarRating value={event.rating} size={14} />
        </div>
        <div className="flex flex-wrap gap-1 mt-1">
          <Badge variant="outline" className="text-xs">
            {event.event_type}
          </Badge>
          <Badge
            variant="outline"
            className="text-xs"
            style={{ borderColor: themeColor, color: themeColor }}
          >
            {event.theme_primary}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="pt-0 flex-1 flex flex-col justify-between gap-3">
        <div className="space-y-1.5 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <Calendar size={12} />
            <span>{formatDateRange(event.start_date, event.end_date)}</span>
          </div>
          {(event.location_city || event.location_country) && (
            <div className="flex items-center gap-1.5">
              <MapPin size={12} />
              <span>
                {[event.location_city, event.location_country]
                  .filter(Boolean)
                  .join(', ')}
              </span>
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <Users size={12} />
            <span>
              {event.attendee_count} attendee{event.attendee_count !== 1 ? 's' : ''}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t">
          <span className="text-sm font-medium">
            {formatCost(Number(event.cost))}
          </span>
          {event.url && (
            <a
              href={event.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-muted-foreground hover:text-foreground"
            >
              <ExternalLink size={14} />
            </a>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/events/components/StarRating.tsx frontend/src/modules/events/components/EventCard.tsx
git commit -m "feat(events): add EventCard and StarRating components"
```

---

### Task 17: Frontend — Events Dashboard Page

**Files:**
- Create: `frontend/src/modules/events/pages/Events.tsx`

- [ ] **Step 1: Write the Events dashboard page**

Create `frontend/src/modules/events/pages/Events.tsx`:

```tsx
import { useState } from 'react';
import { Plus, Search } from 'lucide-react';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Button } from '@/shared/components/ui/button';
import { usePermission } from '@/core/permissions/usePermission';
import { Action } from '@/core/permissions/constants';
import { useUrlState } from '@/shared/hooks/useUrlState';
import { EventCard } from '../components/EventCard';
import { useEvents } from '../hooks/useEvents';
import { useEventOptions } from '../hooks/useEventOptions';
import type { EventListParams } from '../types/events';

const ALL_VALUE = '__all__';
const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: CURRENT_YEAR - 2023 }, (_, i) => CURRENT_YEAR - i);

export default function Events(): JSX.Element {
  const canManage = usePermission(Action.EVENTS_MANAGE);
  const { data: options } = useEventOptions();

  const [params, setParams] = useUrlState<EventListParams>({
    sort_by: 'start_date',
    sort_dir: 'desc',
    page: 1,
    page_size: 50,
  });

  const { data, isLoading } = useEvents(params);

  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  function updateFilter(key: keyof EventListParams, value: string | undefined): void {
    setParams((prev) => ({
      ...prev,
      [key]: value,
      page: 1,
    }));
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Events</h1>
        {canManage && (
          <Button onClick={() => setSelectedEventId('new')}>
            <Plus size={16} className="mr-1" />
            New Event
          </Button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative w-64">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search events..."
            className="pl-9"
            value={params.search ?? ''}
            onChange={(e) => updateFilter('search', e.target.value || undefined)}
          />
        </div>

        <Select
          value={params.year?.toString() ?? ALL_VALUE}
          onValueChange={(v) =>
            updateFilter('year', v === ALL_VALUE ? undefined : v)
          }
        >
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Year" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_VALUE}>All years</SelectItem>
            {YEARS.map((y) => (
              <SelectItem key={y} value={y.toString()}>
                {y}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={params.theme_primary ?? ALL_VALUE}
          onValueChange={(v) =>
            updateFilter('theme_primary', v === ALL_VALUE ? undefined : v)
          }
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Theme" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_VALUE}>All themes</SelectItem>
            {options?.themes.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={params.event_type ?? ALL_VALUE}
          onValueChange={(v) =>
            updateFilter('event_type', v === ALL_VALUE ? undefined : v)
          }
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_VALUE}>All types</SelectItem>
            {options?.event_types.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={params.region_focus ?? ALL_VALUE}
          onValueChange={(v) =>
            updateFilter('region_focus', v === ALL_VALUE ? undefined : v)
          }
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Region" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_VALUE}>All regions</SelectItem>
            {options?.regions.map((r) => (
              <SelectItem key={r} value={r}>
                {r}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={params.sort_by ?? 'start_date'}
          onValueChange={(v) => updateFilter('sort_by', v)}
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="start_date">Date</SelectItem>
            <SelectItem value="cost">Cost</SelectItem>
            <SelectItem value="rating">Rating</SelectItem>
            <SelectItem value="name">Name</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Card grid */}
      {isLoading ? (
        <div className="text-center text-muted-foreground py-12">Loading events...</div>
      ) : data?.items.length === 0 ? (
        <div className="text-center text-muted-foreground py-12">
          No events found. {canManage && 'Create one to get started.'}
        </div>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Showing {data?.items.length} of {data?.total} events
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {data?.items.map((event) => (
              <EventCard
                key={event.id}
                event={event}
                onClick={setSelectedEventId}
              />
            ))}
          </div>
        </>
      )}

      {/* TODO: EventForm dialog will be wired in a follow-up task */}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/events/pages/Events.tsx
git commit -m "feat(events): add Events dashboard page with filters and card grid"
```

---

### Task 18: Frontend — Routing and Sidebar

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/core/components/layout/AppSidebar.tsx`

- [ ] **Step 1: Add route to App.tsx**

In `frontend/src/App.tsx`:

Add import at top:
```typescript
import Events from './modules/events/pages/Events';
```

In the BYPASS_AUTH section (after the `/playbook` route, ~line 112):
```tsx
<Route path="/events" element={<Events />} />
```

In the authenticated section (after the `/playbook` route, ~line 143):
```tsx
<Route path="/events" element={<Events />} />
```

- [ ] **Step 2: Add sidebar navigation item**

In `frontend/src/core/components/layout/AppSidebar.tsx`:

Add import at top:
```typescript
import { CalendarDays } from 'lucide-react';
```

In the navigation `<SidebarMenu>` section, add after the Playbook `<SidebarMenuItem>` block (~line 285):

```tsx
<SidebarMenuItem>
  <SidebarMenuButton
    asChild
    isActive={isActive('/events')}
    tooltip="Events"
  >
    <GuardedLink to="/events">
      <CalendarDays />
      <span>Events</span>
    </GuardedLink>
  </SidebarMenuButton>
</SidebarMenuItem>
```

- [ ] **Step 3: Verify frontend compiles**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/core/components/layout/AppSidebar.tsx
git commit -m "feat(events): add route and sidebar navigation"
```

---

### Task 19: Frontend — EventForm Component (Create/Edit)

**Files:**
- Create: `frontend/src/modules/events/components/EventForm.tsx`
- Create: `frontend/src/modules/events/components/AttendeesPicker.tsx`

- [ ] **Step 1: Write EventForm as a dialog**

Create `frontend/src/modules/events/components/EventForm.tsx`:

```tsx
import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { StarRating } from './StarRating';
import { AttendeesPicker } from './AttendeesPicker';
import { useEventOptions } from '../hooks/useEventOptions';
import { useCreateEvent, useUpdateEvent } from '../hooks/useEvents';
import { useEvent, useAddAttendees, useRemoveAttendee } from '../hooks/useEvent';
import type { EventCreate, EventDetail } from '../types/events';

interface EventFormProps {
  readonly eventId: string | null;
  readonly onClose: () => void;
}

const NONE_VALUE = '__none__';

export function EventForm({ eventId, onClose }: EventFormProps): JSX.Element {
  const isNew = eventId === 'new';
  const { data: existingEvent } = useEvent(isNew ? '' : eventId ?? '');
  const { data: options } = useEventOptions();
  const createMutation = useCreateEvent();
  const updateMutation = useUpdateEvent();
  const addAttendeesMutation = useAddAttendees();
  const removeAttendeeMutation = useRemoveAttendee();

  const [form, setForm] = useState<Partial<EventCreate>>({
    event_type: 'Conference',
    theme_primary: 'Climate',
    region_focus: 'Global',
    cost: 0,
  });
  const [rating, setRating] = useState<number | null>(null);

  useEffect(() => {
    if (existingEvent && !isNew) {
      setForm({
        name: existingEvent.name,
        event_type: existingEvent.event_type as EventCreate['event_type'],
        theme_primary: existingEvent.theme_primary as EventCreate['theme_primary'],
        theme_secondary: existingEvent.theme_secondary as EventCreate['theme_secondary'],
        region_focus: existingEvent.region_focus as EventCreate['region_focus'],
        location_city: existingEvent.location_city,
        location_country: existingEvent.location_country,
        start_date: existingEvent.start_date,
        end_date: existingEvent.end_date,
        cost: Number(existingEvent.cost),
        url: existingEvent.url,
        observations: existingEvent.observations,
      });
      setRating(existingEvent.rating);
    }
  }, [existingEvent, isNew]);

  function updateField(field: string, value: unknown): void {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    const payload = { ...form, rating } as EventCreate;
    if (isNew) {
      await createMutation.mutateAsync(payload);
    } else if (eventId) {
      await updateMutation.mutateAsync({ id: eventId, data: payload });
    }
    onClose();
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <Dialog open={!!eventId} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isNew ? 'New Event' : 'Edit Event'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              required
              value={form.name ?? ''}
              onChange={(e) => updateField('name', e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Type *</Label>
              <Select
                value={form.event_type}
                onValueChange={(v) => updateField('event_type', v)}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {options?.event_types.map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Region *</Label>
              <Select
                value={form.region_focus}
                onValueChange={(v) => updateField('region_focus', v)}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {options?.regions.map((r) => (
                    <SelectItem key={r} value={r}>{r}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Primary Theme *</Label>
              <Select
                value={form.theme_primary}
                onValueChange={(v) => updateField('theme_primary', v)}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {options?.themes.map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Secondary Theme</Label>
              <Select
                value={form.theme_secondary ?? NONE_VALUE}
                onValueChange={(v) =>
                  updateField('theme_secondary', v === NONE_VALUE ? null : v)
                }
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE_VALUE}>None</SelectItem>
                  {options?.themes.map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="start_date">Start Date *</Label>
              <Input
                id="start_date"
                type="date"
                required
                value={form.start_date ?? ''}
                onChange={(e) => updateField('start_date', e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="end_date">End Date</Label>
              <Input
                id="end_date"
                type="date"
                value={form.end_date ?? ''}
                onChange={(e) => updateField('end_date', e.target.value || null)}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="location_city">City</Label>
              <Input
                id="location_city"
                value={form.location_city ?? ''}
                onChange={(e) => updateField('location_city', e.target.value || null)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="location_country">Country</Label>
              <Input
                id="location_country"
                value={form.location_country ?? ''}
                onChange={(e) => updateField('location_country', e.target.value || null)}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="cost">Cost (EUR)</Label>
              <Input
                id="cost"
                type="number"
                min={0}
                step={0.01}
                value={form.cost ?? 0}
                onChange={(e) => updateField('cost', parseFloat(e.target.value) || 0)}
              />
            </div>
            <div className="space-y-2">
              <Label>Rating</Label>
              <StarRating value={rating} onChange={setRating} />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="url">URL</Label>
            <Input
              id="url"
              type="url"
              placeholder="https://..."
              value={form.url ?? ''}
              onChange={(e) => updateField('url', e.target.value || null)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="observations">Observations</Label>
            <Textarea
              id="observations"
              rows={3}
              value={form.observations ?? ''}
              onChange={(e) => updateField('observations', e.target.value || null)}
            />
          </div>

          {/* Attendees — only shown when editing an existing event */}
          {!isNew && eventId && existingEvent && (
            <AttendeesPicker
              eventId={eventId}
              attendees={existingEvent.attendees}
              onAdd={(attendees) =>
                addAttendeesMutation.mutate({ eventId, attendees })
              }
              onRemove={(userId) =>
                removeAttendeeMutation.mutate({ eventId, userId })
              }
            />
          )}

          <div className="flex justify-end gap-2 pt-4">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? 'Saving...' : isNew ? 'Create' : 'Save'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Write AttendeesPicker component**

Create `frontend/src/modules/events/components/AttendeesPicker.tsx`:

```tsx
import { useState } from 'react';
import { Trash2, UserPlus } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import { useUsers } from '@/core/hooks/useUsers';
import { useEventOptions } from '../hooks/useEventOptions';
import { getFullName } from '@/utils/formatters';
import { ROLE_COLORS } from '../utils/constants';
import type { Attendee } from '../types/events';

interface AttendeesPickerProps {
  readonly eventId: string;
  readonly attendees: Attendee[];
  readonly onAdd: (attendees: { user_id: string; role: string }[]) => void;
  readonly onRemove: (userId: string) => void;
}

export function AttendeesPicker({
  eventId,
  attendees,
  onAdd,
  onRemove,
}: AttendeesPickerProps): JSX.Element {
  const { data: users } = useUsers();
  const { data: options } = useEventOptions();
  const [open, setOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState('Attendee');

  const existingUserIds = new Set(attendees.map((a) => a.user_id));
  const availableUsers = (users ?? []).filter((u) => !existingUserIds.has(u.id));

  function handleSelect(userId: string): void {
    onAdd([{ user_id: userId, role: selectedRole }]);
    setOpen(false);
  }

  return (
    <div className="space-y-3">
      <Label>Attendees ({attendees.length})</Label>

      {/* Existing attendees */}
      <div className="space-y-1">
        {attendees.map((a) => (
          <div
            key={a.user_id}
            className="flex items-center justify-between py-1.5 px-2 rounded-md hover:bg-muted/50"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm">
                {a.user_name ?? a.user_email ?? 'Unknown'}
              </span>
              <span
                className="text-xs px-1.5 py-0.5 rounded"
                style={{
                  color: ROLE_COLORS[a.role] ?? '#64748b',
                  backgroundColor: `${ROLE_COLORS[a.role] ?? '#64748b'}15`,
                }}
              >
                {a.role}
              </span>
              {a.functional_area && (
                <span className="text-xs text-muted-foreground">
                  {a.functional_area}
                </span>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onRemove(a.user_id)}
            >
              <Trash2 size={14} />
            </Button>
          </div>
        ))}
      </div>

      {/* Add attendee */}
      <div className="flex items-center gap-2">
        <Select value={selectedRole} onValueChange={setSelectedRole}>
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {options?.attendee_roles.map((r) => (
              <SelectItem key={r} value={r}>
                {r}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button variant="outline" size="sm">
              <UserPlus size={14} className="mr-1" />
              Add attendee
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-64 p-0">
            <Command>
              <CommandInput placeholder="Search users..." />
              <CommandList>
                <CommandEmpty>No users found.</CommandEmpty>
                <CommandGroup>
                  {availableUsers.map((u) => (
                    <CommandItem
                      key={u.id}
                      onSelect={() => handleSelect(u.id)}
                    >
                      {getFullName(u.first_name, u.last_name, u.email)}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );
}
```

Note: This component uses `useUsers` from `@/core/hooks/useUsers`. If that hook doesn't exist with the right shape, adapt to use the existing user summaries hook (`useUserSummaries` or similar from `@/core/hooks/`). Check the actual hook name before implementing.

- [ ] **Step 3: Wire EventForm into Events page**

In `frontend/src/modules/events/pages/Events.tsx`, add import:

```typescript
import { EventForm } from '../components/EventForm';
```

Replace the TODO comment at the bottom with:

```tsx
{selectedEventId && (
  <EventForm
    eventId={selectedEventId}
    onClose={() => setSelectedEventId(null)}
  />
)}
```

Also add a delete handler if needed — or defer to the detail dialog.

- [ ] **Step 4: Verify frontend compiles**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/events/components/EventForm.tsx frontend/src/modules/events/components/AttendeesPicker.tsx frontend/src/modules/events/pages/Events.tsx
git commit -m "feat(events): add EventForm dialog with AttendeesPicker"
```

---

### Task 20: Frontend — Stats Section

**Files:**
- Create: `frontend/src/modules/events/components/StatsCharts.tsx`

- [ ] **Step 1: Write StatsCharts component**

Create `frontend/src/modules/events/components/StatsCharts.tsx`:

```tsx
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { THEME_COLORS } from '../utils/constants';
import type { StatGroup } from '../types/events';

interface ChartCardProps {
  readonly title: string;
  readonly data: StatGroup[];
  readonly colorMap?: Record<string, string>;
}

function ChartCard({ title, data, colorMap }: ChartCardProps): JSX.Element {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-4">No data</p>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data} layout="vertical" margin={{ left: 0, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="label"
                width={120}
                tick={{ fontSize: 11 }}
              />
              <Tooltip />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {data.map((entry) => (
                  <Cell
                    key={entry.label}
                    fill={colorMap?.[entry.label] ?? 'hsl(var(--primary))'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

interface StatsChartsProps {
  readonly stats: {
    by_quarter: StatGroup[];
    by_theme: StatGroup[];
    by_role: StatGroup[];
    by_fa: StatGroup[];
    by_country: StatGroup[];
    total_events: number;
    total_attendees: number;
    total_cost: number;
  };
}

function formatCost(cost: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
  }).format(cost);
}

export function StatsCharts({ stats }: StatsChartsProps): JSX.Element {
  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-3xl font-bold">{stats.total_events}</p>
            <p className="text-sm text-muted-foreground">Events</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-3xl font-bold">{stats.total_attendees}</p>
            <p className="text-sm text-muted-foreground">Unique Attendees</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-3xl font-bold">{formatCost(stats.total_cost)}</p>
            <p className="text-sm text-muted-foreground">Total Cost</p>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ChartCard title="Events per Quarter" data={stats.by_quarter} />
        <ChartCard title="By Theme" data={stats.by_theme} colorMap={THEME_COLORS} />
        <ChartCard title="By Role" data={stats.by_role} />
        <ChartCard title="By Functional Area" data={stats.by_fa} />
        <ChartCard title="By Country" data={stats.by_country} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire stats into Events page**

In `frontend/src/modules/events/pages/Events.tsx`, add imports:

```typescript
import { useEventStats } from '../hooks/useEventStats';
import { StatsCharts } from '../components/StatsCharts';
```

Add stats query after the `useEvents` call:

```typescript
const statsYear = params.year ? Number(params.year) : undefined;
const { data: stats } = useEventStats(statsYear);
```

Add stats section after the card grid (before the `EventForm` dialog):

```tsx
{stats && (
  <div className="pt-6 border-t">
    <h2 className="text-lg font-semibold mb-4">Statistics</h2>
    <StatsCharts stats={stats} />
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/events/components/StatsCharts.tsx frontend/src/modules/events/pages/Events.tsx
git commit -m "feat(events): add stats charts to dashboard"
```

---

### Task 21: CLAUDE.md and Documentation Updates

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add events module to CLAUDE.md**

In the **Project Structure** backend section, add the events module:

```
│   ├── events/            # Conference & event tracking
│   │   ├── api/           # events, attendees, stats, options, import
│   │   ├── models/        # EventDB, EventAttendeeDB
│   │   ├── services/      # event_service, stats_service
│   │   ├── router.py
│   │   └── public.py
```

In the **Project Structure** frontend section, add:

```
│   ├── events/            # Conference & event tracking dashboard
│   │   ├── components/    # EventCard, EventForm, AttendeesPicker, StarRating, StatsCharts
│   │   ├── hooks/         # useEvents, useEvent, useEventStats, useEventOptions
│   │   ├── pages/         # Events
│   │   ├── services/      # events (API client)
│   │   ├── types/         # events
│   │   └── utils/         # constants
```

In the **Constraints** section, add:

```
- **Events enums in code**: Event type, theme, region, attendee role are StrEnum (backend) / `as const` (frontend) — not PostgreSQL enum types.
- **Events cost is per-event**: Not per-attendee. `event_attendees` only stores `event_id`, `user_id`, `role`.
- **Events year/quarter derived**: Not stored — computed from `start_date` in queries.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add events module to CLAUDE.md"
```

---

### Task 22: Excel Import — Run Initial Data Load

**Files:** None (operational task)

- [ ] **Step 1: Start the backend**

```bash
cd backend && python run_server.py
```

- [ ] **Step 2: Import the Excel file**

```bash
curl -X POST http://localhost:8000/api/events/import \
  -H "Cookie: <your-auth-cookie>" \
  -F "file=@/Users/miguelmendoza/Downloads/Conferences and Events Stats.xlsx"
```

- [ ] **Step 3: Verify import results**

Check the response for `events_created`, `attendees_matched`, and `unmatched_attendee_names`. Manually resolve any unmatched names by checking VizzHub user names.

- [ ] **Step 4: Verify in the UI**

Open `http://localhost:3000/events` and confirm events appear with correct data, attendees, and filters working.
