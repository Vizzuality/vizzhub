# Report Reminder Scheduled Job — Design Spec

## Purpose

Automated Slack reminder sent on the last business day of each month, prompting the team to fill in their tracker reports.

## Schedule Logic

ARQ cron runs the job daily. The job itself checks whether today is the last business day of the month:

1. Find the last calendar day of the current month.
2. Walk backwards from that day, skipping Saturday and Sunday.
3. If today matches that date, proceed. Otherwise, exit early (no-op).

Cron registration: `cron(send_report_reminder, hour=10, minute=0)` — 10:00 UTC daily.

## Slack Channel

Configurable via `integration_settings` (provider `slack`, key `tracker_reminder_channel_id`). Reuses the existing key-value store — no migration needed.

The frontend Slack configuration panel gains one additional channel selector for the tracker reminder channel.

## Message

```
:memo: It's time to fill in your monthly report! Head over to <https://hub.vizzuality.com/tracker/my-report|Vizzhub> and complete it before the period closes.
```

Plain Slack mrkdwn. No template system (single static message, no per-project context).

## Implementation

### Backend

**New file: `backend/app/worker/report_reminder.py`**

```python
async def send_report_reminder(ctx: dict) -> dict:
```

Pattern follows `check_business_alerts.py`:

1. Create `ScheduledJobRunDB(job_name="send_report_reminder", status="running")`.
2. Check `is_last_business_day(date.today())`. If not, mark completed with `alerts_sent=0`, return.
3. Get `bot_token` via `get_slack_bot_token(db)`.
4. Get `tracker_reminder_channel_id` via `IntegrationTokenService.get_setting(db, "slack", "tracker_reminder_channel_id")`.
5. If either missing, `complete_with_error(...)`.
6. Send message via `SlackService.send_message(bot_token, channel_id, MESSAGE)`.
7. Update `ScheduledJobRunDB` — `status="completed"`, `alerts_sent=1` (or 0 on failure).

**Helper: `is_last_business_day(today: date) -> bool`**

Lives in `report_reminder.py` (private module function). Uses `calendar.monthrange` to find last day of month, then walks backwards past weekends.

**`backend/app/worker/settings.py`**

- Import `send_report_reminder`.
- Add to `WorkerSettings.functions`.
- Add `cron(send_report_reminder, hour=10, minute=0)` to `WorkerSettings.cron_jobs`.

**`backend/app/utils/slack.py`**

- Add `get_slack_tracker_reminder_channel(db)` helper (same pattern as `get_slack_leadership_channel`).

### Frontend

**Slack config panel** — add a channel selector for "Tracker Report Reminder Channel" alongside the existing leadership channel selector. Same component, different setting key.

## No Changes Required

- No DB migration (uses existing `integration_settings` key-value table).
- No new API endpoints (setting CRUD already exists).
- No new permissions (admin-only Slack config panel already gated).
- No alert_definitions row needed (this is not a per-project alert, it's a global team reminder).

## Testing

- Unit test `is_last_business_day` with known dates (end of month on weekday, Saturday, Sunday, February edge cases).
- Unit test `send_report_reminder` with mocked DB and Slack: verify it sends when last business day, skips otherwise, handles missing config.
- Integration with existing `ScheduledJobRunDB` assertions.
