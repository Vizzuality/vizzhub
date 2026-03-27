# Mood Tracking Design Spec

## Overview

Add optional mood/wellbeing tracking to the reporting flow. When a user confirms their time report, a dialog asks how they felt during the period. Two inputs: an emoji mood scale (1-5, linked to the user's report) and an optional free-text field that can be submitted anonymously.

## Data Model

### `reports` table — new columns

| Column          | Type         | Nullable | Default | Notes                          |
|-----------------|--------------|----------|---------|--------------------------------|
| `mood`          | `Integer`    | yes      | null    | 1-5 scale (`ge=1, le=5`). Linked to user. |
| `feedback_text` | `Text`       | yes      | null    | Non-anonymous text. Linked to user. |

### `anonymous_feedback` table — new table

| Column | Type      | Nullable | Default | Notes                           |
|--------|-----------|----------|---------|---------------------------------|
| `id`   | `UUID`    | no       | uuid4   | PK                              |
| `month`| `Integer` | no       | —       | 1-12                            |
| `year` | `Integer` | no       | —       | e.g. 2026                       |
| `text` | `Text`    | no       | —       | Max 2000 chars                  |

No foreign keys. No timestamps (`created_at`, `updated_at`). No user reference. Completely untraceable. Duplicate submissions are acceptable — there is no deduplication. The frontend only shows the dialog once per confirm, so duplicates would require deliberate effort.

## Mood Scale

| Value | Emoji | Label     |
|-------|-------|-----------|
| 1     | 😫    | Very bad  |
| 2     | 😟    | Bad       |
| 3     | 😐    | Neutral   |
| 4     | 🙂    | Good      |
| 5     | 😄    | Very good |

## User Flow

1. User fills in their time report (project percentages)
2. User clicks **Confirm**
3. Report is confirmed (`estimated = false`)
4. A dialog appears: "How did you feel during this period?"
   - 5 emoji buttons (optional — can skip entirely)
   - Textarea for free text (optional)
   - Checkbox "Submit anonymously" — **off by default**
   - Note below emojis: "Your mood selection is linked to your report"
   - Visual separator between mood (non-anonymous) and text section
5. **Skip** → dialog closes, mood stays null, no text saved
6. **Submit** → saves mood to `reports.mood` (always linked to user — anonymity applies only to the text field, never to mood), routes text based on checkbox:
   - Anonymous off → text saved to `reports.feedback_text`
   - Anonymous on → text saved to `anonymous_feedback` (month + year only)
7. Dialog only appears on Confirm, not on Reopen
8. Mood is **write-once per confirm cycle**. To change mood, the user must Reopen the report and Confirm again, which re-triggers the dialog. There is no standalone "edit mood" action.

## API Changes

### Modified endpoint: `PUT /api/tracker/reports/{report_id}`

Add optional fields to `ReportUpdate` schema:

```python
mood: int | None = Field(None, ge=1, le=5)
feedback_text: str | None = Field(None, max_length=2000)
```

When `estimated` transitions from `true` to `false` (confirm action), the frontend sends mood and feedback_text along with the confirm request.

### New endpoint: `POST /api/tracker/anonymous-feedback`

Request body:

```python
class AnonymousFeedbackCreate(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2020, le=2100)
    text: str = Field(min_length=1, max_length=2000)
```

Permission: any authenticated user (`CurrentUser`). No link to caller stored.

### New endpoint: `GET /api/tracker/moods`

Query params: `month` (int, required), `year` (int, required).

Response:

```python
class MoodsResponse(BaseModel):
    mood_distribution: dict[int, int]  # {1: count, 2: count, ...}
    total_reports: int
    total_responses: int
    average_mood: float | None
    anonymous_feedback: list[str]
    named_feedback: list[NamedFeedbackItem]

class NamedFeedbackItem(BaseModel):
    user_name: str
    mood: int | None
    text: str | None
```

`named_feedback` includes users who submitted either a mood or a feedback_text (or both). Users with both fields null are excluded.

Permission: admin only (`AdminUser`).

## Frontend Components

### `MoodDialog`

- Location: `frontend/src/modules/tracker/components/MoodDialog.tsx`
- Triggered by `ReportEditor` after successful confirm mutation
- Uses shadcn `Dialog` component
- State: selected mood (1-5 | null), text (string), isAnonymous (boolean, default false)
- On Submit: calls `updateReport` with mood + feedback_text (if not anonymous), then calls `createAnonymousFeedback` if anonymous
- On Skip: closes dialog

### `MoodsPage`

- Location: `frontend/src/modules/tracker/pages/Moods.tsx`
- Route: `/tracker/moods` (admin only)
- Month navigation with `◀ ▶` arrows
- Three sections:
  1. **Mood Distribution** — bar chart with emoji labels, response count, average
  2. **Anonymous Feedback** — list of text cards, no attribution
  3. **Named Feedback** — text cards with user name and mood emoji

### Hooks

- `useMoods(month, year)` — fetches `GET /api/tracker/moods`
- `useCreateAnonymousFeedback()` — posts to `POST /api/tracker/anonymous-feedback`

### Router

- Add `/tracker/moods` route to tracker routes, gated by admin permission

## Testing

### Backend

- Migration: verify `mood` and `feedback_text` columns added to reports
- Migration: verify `anonymous_feedback` table created with correct schema (no FK, no timestamps)
- `PUT /reports/{id}`: test mood field saves (1-5, null, out-of-range rejected)
- `PUT /reports/{id}`: test feedback_text saves when not anonymous
- `POST /anonymous-feedback`: test creates record with only month/year/text
- `POST /anonymous-feedback`: verify no user_id or timestamp stored
- `GET /moods`: test aggregation returns correct distribution
- `GET /moods`: test admin-only access (403 for non-admin)
- `GET /moods`: test named_feedback includes mood-only and text-only entries
