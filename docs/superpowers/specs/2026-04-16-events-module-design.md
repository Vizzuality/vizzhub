# Events Module Design

## Overview

Conference and events tracking module for VizzHub. Tracks events Vizzuality participates in, who attended, costs, and provides analytics for strategic decision-making.

## Data Model

### Table: `events`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK, default `gen_random_uuid()` | |
| `name` | VARCHAR(300) | NOT NULL | |
| `event_type` | VARCHAR(50) | NOT NULL | Enum in code |
| `theme_primary` | VARCHAR(100) | NOT NULL | Enum in code |
| `theme_secondary` | VARCHAR(100) | nullable | Same enum as theme_primary |
| `region_focus` | VARCHAR(50) | NOT NULL | Enum in code |
| `location_city` | VARCHAR(100) | nullable | |
| `location_country` | VARCHAR(100) | nullable | |
| `start_date` | DATE | NOT NULL | |
| `end_date` | DATE | nullable | Same as start_date if single-day |
| `cost` | NUMERIC(12,2) | NOT NULL, default 0 | Total event cost |
| `rating` | SMALLINT | nullable, CHECK 1-5 | Importance stars |
| `url` | VARCHAR(500) | nullable | Link to event website |
| `observations` | TEXT | nullable | Free-text notes |
| `created_by` | UUID FK → users | ON DELETE SET NULL | |
| `created_at` | TIMESTAMPTZ | server_default now() | |
| `updated_at` | TIMESTAMPTZ | server_default now(), onupdate | |

`year` and `quarter` are derived from `start_date` — not stored.

### Table: `event_attendees`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK, default `gen_random_uuid()` | |
| `event_id` | UUID FK → events | ON DELETE CASCADE, NOT NULL | |
| `user_id` | UUID FK → users | ON DELETE RESTRICT, NOT NULL | |
| `role` | VARCHAR(50) | NOT NULL | Enum in code |
| `created_at` | TIMESTAMPTZ | server_default now() | |

UNIQUE constraint on `(event_id, user_id)`.

### Enums (defined in code, not PostgreSQL types)

**Event types:** Conference, Summit, Forum, Workshop, Symposium, Multi-event, Networking event, Roundtable, Training, Webinar, Exhibition / Expo, Internal event, Other.

**Themes:** Climate, Nature & Biodiversity, Oceans & Water, Food & Land Systems, Energy & Net Zero, Data & Technology, Policy & Finance, Social Justice, Urban & Cities, Other.

**Region focus:** Global, Europe, North America, Latin America & Caribbean, Africa, Asia-Pacific, Middle East.

**Attendee roles:** Attendee, Speaker, Panelist, Moderator, Exhibitor, Organizer.

## Permissions

| Action | Constant | Assigned to |
|--------|----------|-------------|
| View events | `events:view` | `user`, `manager`, `admin` |
| Manage events (CRUD) | `events:manage` | Manually assigned + `admin` |

Frontend: `/events` route requires `events:view`. Create/edit/delete gated by `events:manage` via `<Can>`.

## API

Prefix: `/api/events`

### Events CRUD

| Method | Route | Permission | Description |
|--------|-------|------------|-------------|
| GET | `` | `events:view` | List events. Filters: year, quarter, theme_primary, event_type, region_focus, location_country, search (name). Sort: start_date, cost, rating. Pagination. |
| GET | `/{id}` | `events:view` | Event detail with attendees populated (user name, email, FA, role) |
| POST | `` | `events:manage` | Create event |
| PUT | `/{id}` | `events:manage` | Update event |
| DELETE | `/{id}` | `events:manage` | Delete event (cascades attendees) |

### Attendees

| Method | Route | Permission | Description |
|--------|-------|------------|-------------|
| POST | `/{id}/attendees` | `events:manage` | Add attendee(s) — accepts list of `{user_id, role}` |
| DELETE | `/{id}/attendees/{user_id}` | `events:manage` | Remove attendee |

### Stats

| Method | Route | Permission | Description |
|--------|-------|------------|-------------|
| GET | `/stats` | `events:view` | Aggregated stats: by quarter, theme, FA, location, role, cost. Accepts `year` filter. |

### Options

| Method | Route | Permission | Description |
|--------|-------|------------|-------------|
| GET | `/options` | `events:view` | Returns all enum lists (types, themes, regions, roles) for populating selects |

### Import

| Method | Route | Permission | Description |
|--------|-------|------------|-------------|
| POST | `/import` | `events:manage` | Import events from Excel file (one-shot initial data load) |

## Backend Structure

```
backend/app/modules/events/
├── __init__.py
├── router.py          # Aggregates sub-routers
├── public.py          # Cross-module interface (minimal initially)
├── constants.py       # StrEnum definitions for types, themes, regions, roles
├── models/
│   ├── __init__.py
│   ├── event.py       # EventDB
│   └── event_attendee.py  # EventAttendeeDB
├── schemas/
│   ├── __init__.py
│   ├── event.py       # EventCreate, EventUpdate, EventResponse, EventWithAttendeesResponse
│   └── event_attendee.py  # AttendeeCreate, AttendeeResponse
├── api/
│   ├── __init__.py
│   ├── events.py      # CRUD endpoints
│   ├── attendees.py   # Attendee management
│   ├── stats.py       # Aggregation queries
│   └── import_events.py  # Excel import
└── services/
    ├── __init__.py
    ├── event_service.py   # List/filter/sort logic
    └── stats_service.py   # Aggregation queries
```

Mounted in `main.py` as:
```python
app.include_router(events_router, prefix="/api/events", tags=["events"])
```

## Frontend Structure

```
frontend/src/modules/events/
├── components/
│   ├── EventCard.tsx         # Card for grid view
│   ├── EventForm.tsx         # Create/edit form (modal or page)
│   ├── AttendeesPicker.tsx   # Combobox multi-select with role per attendee
│   ├── StarRating.tsx        # 1-5 star display/input
│   └── StatsCharts.tsx       # Bar charts for analytics
├── hooks/
│   ├── useEvents.ts          # List query with filters
│   ├── useEvent.ts           # Detail query
│   ├── useEventStats.ts      # Stats query
│   └── useEventOptions.ts    # Options query for selects
├── pages/
│   ├── Events.tsx            # Dashboard: filters + card grid + stats
│   └── EventDetail.tsx       # Detail/edit view
├── services/
│   └── events.ts             # API client
├── types/
│   └── events.ts             # Interfaces + enum constants
└── utils/
    └── constants.ts          # Colors, labels for charts
```

## Dashboard Layout

### Filter bar
Search by name, dropdowns for year/theme/type/region/country. Sort by date/cost/rating.

### Card grid
Responsive `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`. Each card shows:
- Event name + star rating
- Type + primary theme (badges)
- Date range (start — end)
- Location (city, country)
- Cost
- URL (external link icon if present)
- Attendee avatars/initials (max 4-5 + "+N" overflow)

"New event" button gated by `events:manage`.

### Stats section
Charts below the card grid (or as a tab): events per quarter, by theme, by FA, by location, by role, total cost. Year filter.

## Data Import

One-shot script/endpoint to import the existing Excel data:
- Match `Attendee_name` to VizzHub users by name (fuzzy match or manual mapping).
- `FA` column maps to the attendee's functional area in VizzHub (informational — stored on user, not on event_attendees).
- `Year`/`Quarter` columns are ignored (derived from dates).
- `Cost` is per-event (deduplicated from repeated rows).

## MCP Integration

Add read tools to the existing MCP server in a future phase:
- `events_get_list` — list/filter events
- `events_get_stats` — aggregated stats

Not in scope for initial implementation.
