# Report Reminder Scheduled Job — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send a Slack reminder on the last business day of each month prompting the team to fill in their tracker reports.

**Architecture:** ARQ cron runs `send_report_reminder` daily at 10:00 UTC. The function checks if today is the last business day of the month (walking backwards from month-end past weekends). If yes, sends a static message to a configurable Slack channel. Uses the existing `ScheduledJobRunDB` for audit and `integration_settings` for channel config.

**Tech Stack:** Python 3.12, FastAPI, ARQ, SQLAlchemy async, Pydantic, pytest

**Spec:** `docs/superpowers/specs/2026-03-26-report-reminder-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `backend/app/worker/report_reminder.py` | Job function + `_is_last_business_day` helper |
| Create | `backend/tests/test_report_reminder_job.py` | All tests for the job |
| Modify | `backend/app/worker/settings.py` | Register function + cron |
| Modify | `backend/app/utils/slack.py` | Add `get_slack_tracker_reminder_channel` |
| Modify | `backend/app/modules/scorecard/api/integrations_admin.py` | Return new setting in status + save it |
| Modify | `backend/app/modules/scorecard/api/schemas/integrations.py` | Add field to `SlackSettingsUpdate` + `AllIntegrationsStatus` |
| Modify | `frontend/src/core/services/integrations.ts` | Add field to types + API call |
| Modify | `frontend/src/modules/scorecard/components/Settings/SlackTab.tsx` | Add channel selector UI |

---

### Task 1: `_is_last_business_day` helper — tests

**Files:**
- Create: `backend/tests/test_report_reminder_job.py`

- [ ] **Step 1: Write tests for `_is_last_business_day`**

```python
"""Tests for Report Reminder scheduled job."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.integration_setting import IntegrationSettingDB
from app.core.models.oauth import OAuthTokenDB
from app.core.token_encryption import encrypt_token
from app.modules.scorecard.models.slack import ScheduledJobRunDB
from app.worker.report_reminder import _is_last_business_day, send_report_reminder


class TestIsLastBusinessDay:
    """Tests for last-business-day-of-month logic."""

    def test_last_day_is_weekday(self) -> None:
        """2026-03-31 is Tuesday — last business day."""
        assert _is_last_business_day(date(2026, 3, 31)) is True

    def test_last_day_is_saturday(self) -> None:
        """2026-01-31 is Saturday — Friday 30th is the last business day."""
        assert _is_last_business_day(date(2026, 1, 30)) is True
        assert _is_last_business_day(date(2026, 1, 31)) is False

    def test_last_day_is_sunday(self) -> None:
        """2026-05-31 is Sunday — Friday 29th is the last business day."""
        assert _is_last_business_day(date(2026, 5, 29)) is True
        assert _is_last_business_day(date(2026, 5, 31)) is False
        assert _is_last_business_day(date(2026, 5, 30)) is False

    def test_february_non_leap(self) -> None:
        """2026-02-28 is Saturday — Friday 27th is the last business day."""
        assert _is_last_business_day(date(2026, 2, 27)) is True
        assert _is_last_business_day(date(2026, 2, 28)) is False

    def test_february_leap_year(self) -> None:
        """2028-02-29 is Tuesday — it is the last business day."""
        assert _is_last_business_day(date(2028, 2, 29)) is True

    def test_mid_month_is_false(self) -> None:
        """A random mid-month date is never the last business day."""
        assert _is_last_business_day(date(2026, 3, 15)) is False

    def test_december(self) -> None:
        """2026-12-31 is Thursday — last business day."""
        assert _is_last_business_day(date(2026, 12, 31)) is True
```

- [ ] **Step 2: Run tests — expect ImportError**

Run: `cd backend && python -m pytest tests/test_report_reminder_job.py::TestIsLastBusinessDay -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.worker.report_reminder'`

---

### Task 2: `_is_last_business_day` helper — implementation

**Files:**
- Create: `backend/app/worker/report_reminder.py`

- [ ] **Step 1: Implement the helper**

```python
"""Report reminder scheduled job.

Sends a Slack reminder on the last business day of each month,
prompting the team to fill in their tracker reports.

Runs daily via ARQ cron; exits early on non-target days.
"""

import calendar
import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scorecard.models.slack import ScheduledJobRunDB
from app.modules.scorecard.services.slack_service import SlackService
from app.utils.slack import get_slack_bot_token, get_slack_tracker_reminder_channel
from app.worker.utils import complete_with_error

logger = logging.getLogger(__name__)

REPORT_REMINDER_MESSAGE = (
    ":memo: It's time to fill in your monthly report! "
    "Head over to <https://hub.vizzuality.com/tracker/my-report|Vizzhub> "
    "and complete it before the period closes."
)


def _is_last_business_day(today: date) -> bool:
    """Return True if *today* is the last business day (Mon-Fri) of its month."""
    _, last_day = calendar.monthrange(today.year, today.month)
    d = date(today.year, today.month, last_day)
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d = d.replace(day=d.day - 1)
    return today == d
```

- [ ] **Step 2: Run tests — expect PASS**

Run: `cd backend && python -m pytest tests/test_report_reminder_job.py::TestIsLastBusinessDay -v`
Expected: all 7 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/worker/report_reminder.py backend/tests/test_report_reminder_job.py
git commit -m "feat(tracker): add _is_last_business_day helper with tests"
```

---

### Task 3: Slack utils — `get_slack_tracker_reminder_channel`

**Files:**
- Modify: `backend/app/utils/slack.py`

- [ ] **Step 1: Add helper function**

Add after the existing `get_slack_leadership_channel` function:

```python
async def get_slack_tracker_reminder_channel(db: AsyncSession) -> str | None:
    """Get the tracker reminder channel ID."""
    return await IntegrationTokenService.get_setting(
        db, "slack", "tracker_reminder_channel_id"
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/utils/slack.py
git commit -m "feat(tracker): add get_slack_tracker_reminder_channel util"
```

---

### Task 4: `send_report_reminder` job — tests

**Files:**
- Modify: `backend/tests/test_report_reminder_job.py`

- [ ] **Step 1: Add job integration tests**

Append to `test_report_reminder_job.py`:

```python
class TestSendReportReminder:
    """Integration tests for send_report_reminder job."""

    @pytest_asyncio.fixture
    async def setup_slack(self, db_session: AsyncSession) -> None:
        """Set up Slack token and tracker reminder channel."""
        token = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test-token"),
            token_type="bot",
        )
        db_session.add(token)

        setting = IntegrationSettingDB(
            provider="slack",
            key="tracker_reminder_channel_id",
            value="C_TRACKER_REMIND",
        )
        db_session.add(setting)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_skips_when_not_last_business_day(
        self, db_session: AsyncSession, setup_slack: None
    ) -> None:
        """Job should complete with alerts_sent=0 on non-target days."""
        ctx = {"db": db_session}
        with patch(
            "app.worker.report_reminder._is_last_business_day", return_value=False
        ):
            result = await send_report_reminder(ctx)

        assert result["status"] == "completed"
        assert result["alerts_sent"] == 0

    @pytest.mark.asyncio
    async def test_sends_on_last_business_day(
        self, db_session: AsyncSession, setup_slack: None
    ) -> None:
        """Job should send Slack message on the last business day."""
        ctx = {"db": db_session}
        mock_response = {"ok": True, "ts": "1234567890.123456"}

        with (
            patch(
                "app.worker.report_reminder._is_last_business_day", return_value=True
            ),
            patch(
                "app.worker.report_reminder.SlackService.send_message",
                new_callable=AsyncMock,
                return_value=mock_response,
            ) as mock_send,
        ):
            result = await send_report_reminder(ctx)

        assert result["status"] == "completed"
        assert result["alerts_sent"] == 1
        mock_send.assert_called_once_with(
            "xoxb-test-token", "C_TRACKER_REMIND", REPORT_REMINDER_MESSAGE
        )

    @pytest.mark.asyncio
    async def test_error_when_no_bot_token(
        self, db_session: AsyncSession
    ) -> None:
        """Job should error when Slack bot token is not configured."""
        ctx = {"db": db_session}
        with patch(
            "app.worker.report_reminder._is_last_business_day", return_value=True
        ):
            result = await send_report_reminder(ctx)

        assert result["status"] == "error"
        assert "bot token" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_error_when_no_channel(
        self, db_session: AsyncSession
    ) -> None:
        """Job should error when tracker reminder channel is not configured."""
        token = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test-token"),
            token_type="bot",
        )
        db_session.add(token)
        await db_session.commit()

        ctx = {"db": db_session}
        with patch(
            "app.worker.report_reminder._is_last_business_day", return_value=True
        ):
            result = await send_report_reminder(ctx)

        assert result["status"] == "error"
        assert "channel" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_handles_slack_failure(
        self, db_session: AsyncSession, setup_slack: None
    ) -> None:
        """Job should complete with alerts_sent=0 when Slack send fails."""
        ctx = {"db": db_session}
        mock_response = {"ok": False, "error": "channel_not_found"}

        with (
            patch(
                "app.worker.report_reminder._is_last_business_day", return_value=True
            ),
            patch(
                "app.worker.report_reminder.SlackService.send_message",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            result = await send_report_reminder(ctx)

        assert result["status"] == "completed"
        assert result["alerts_sent"] == 0

    @pytest.mark.asyncio
    async def test_creates_scheduled_job_run(
        self, db_session: AsyncSession, setup_slack: None
    ) -> None:
        """Job should persist a ScheduledJobRunDB record."""
        ctx = {"db": db_session}
        with patch(
            "app.worker.report_reminder._is_last_business_day", return_value=False
        ):
            result = await send_report_reminder(ctx)

        from sqlalchemy import select

        rows = (
            await db_session.execute(
                select(ScheduledJobRunDB).where(
                    ScheduledJobRunDB.job_name == "send_report_reminder"
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "completed"
        assert rows[0].id == result["job_run_id"]
```

- [ ] **Step 2: Run tests — expect FAIL (job not implemented yet)**

Run: `cd backend && python -m pytest tests/test_report_reminder_job.py::TestSendReportReminder -v`
Expected: FAIL — `send_report_reminder` has no body yet

---

### Task 5: `send_report_reminder` job — implementation

**Files:**
- Modify: `backend/app/worker/report_reminder.py`

- [ ] **Step 1: Implement the job function**

Add after `_is_last_business_day` in `report_reminder.py`:

```python
async def send_report_reminder(ctx: dict) -> dict[str, Any]:
    """Send monthly report reminder to Slack on the last business day.

    Runs daily via ARQ cron. On non-target days, exits with alerts_sent=0.
    """
    db: AsyncSession = ctx["db"]

    job_run = ScheduledJobRunDB(
        job_name="send_report_reminder",
        status="running",
        projects_checked=0,
        alerts_sent=0,
    )
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)

    try:
        if not _is_last_business_day(date.today()):
            job_run.status = "completed"
            job_run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {
                "status": "completed",
                "job_run_id": job_run.id,
                "alerts_sent": 0,
            }

        bot_token = await get_slack_bot_token(db)
        if not bot_token:
            return await complete_with_error(
                db, job_run, "Slack not configured - missing bot token"
            )

        channel_id = await get_slack_tracker_reminder_channel(db)
        if not channel_id:
            return await complete_with_error(
                db, job_run, "Tracker reminder channel not configured"
            )

        response = await SlackService.send_message(
            bot_token, channel_id, REPORT_REMINDER_MESSAGE
        )

        alerts_sent = 1 if response.get("ok") else 0
        if not response.get("ok"):
            logger.error(
                f"Failed to send report reminder: {response.get('error')}"
            )

        job_run.status = "completed"
        job_run.alerts_sent = alerts_sent
        job_run.completed_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "status": "completed",
            "job_run_id": job_run.id,
            "alerts_sent": alerts_sent,
        }

    except Exception as e:
        logger.exception("Report reminder job failed")
        return await complete_with_error(db, job_run, str(e))
```

- [ ] **Step 2: Run all tests**

Run: `cd backend && python -m pytest tests/test_report_reminder_job.py -v`
Expected: all 13 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/worker/report_reminder.py backend/tests/test_report_reminder_job.py backend/app/utils/slack.py
git commit -m "feat(tracker): implement send_report_reminder job"
```

---

### Task 6: Register in ARQ worker settings

**Files:**
- Modify: `backend/app/worker/settings.py`

- [ ] **Step 1: Add import**

After line 76 (`from app.worker.fetch_exchange_rates import fetch_exchange_rates`), add:

```python
from app.worker.report_reminder import send_report_reminder  # noqa: E402
```

- [ ] **Step 2: Add to functions list**

Add `send_report_reminder` to `WorkerSettings.functions` list.

- [ ] **Step 3: Add cron entry**

Add to `WorkerSettings.cron_jobs` list:

```python
cron(send_report_reminder, hour=10, minute=0),  # Daily — sends only on last business day
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/worker/settings.py
git commit -m "feat(tracker): register report_reminder in ARQ worker"
```

---

### Task 7: Backend API — expose new setting

**Files:**
- Modify: `backend/app/modules/scorecard/api/schemas/integrations.py`
- Modify: `backend/app/modules/scorecard/api/integrations_admin.py`

- [ ] **Step 1: Update `SlackSettingsUpdate` schema**

In `schemas/integrations.py`, add field to `SlackSettingsUpdate`:

```python
class SlackSettingsUpdate(BaseModel):
    """Update Slack integration settings."""

    leadership_channel_id: str | None = Field(None, max_length=50)
    tracker_reminder_channel_id: str | None = Field(None, max_length=50)
```

- [ ] **Step 2: Update `get_all_integrations_status` endpoint**

In `integrations_admin.py`, add after the `leadership_channel_id` read (line 57-58):

```python
tracker_reminder_channel_id = await IntegrationTokenService.get_setting(
    db, "slack", "tracker_reminder_channel_id"
)
```

And update the return to include it:

```python
slack_settings={
    "leadership_channel_id": leadership_channel_id,
    "tracker_reminder_channel_id": tracker_reminder_channel_id,
},
```

- [ ] **Step 3: Update `update_slack_settings` endpoint**

In `integrations_admin.py`, add after the `leadership_channel_id` block (line 169-172):

```python
if body.tracker_reminder_channel_id is not None:
    await IntegrationTokenService.set_setting(
        db, "slack", "tracker_reminder_channel_id", body.tracker_reminder_channel_id
    )
```

And update the return:

```python
tracker_reminder_channel_id = await IntegrationTokenService.get_setting(
    db, "slack", "tracker_reminder_channel_id"
)
return {
    "leadership_channel_id": leadership_channel_id,
    "tracker_reminder_channel_id": tracker_reminder_channel_id,
}
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/scorecard/api/schemas/integrations.py backend/app/modules/scorecard/api/integrations_admin.py
git commit -m "feat(tracker): expose tracker_reminder_channel_id in Slack settings API"
```

---

### Task 8: Frontend — types & API client

**Files:**
- Modify: `frontend/src/core/services/integrations.ts`

- [ ] **Step 1: Update `AllIntegrationsStatus` type**

Change `slack_settings` type:

```typescript
slack_settings: {
  leadership_channel_id: string | null;
  tracker_reminder_channel_id: string | null;
};
```

- [ ] **Step 2: Update `updateSlackSettings`**

```typescript
updateSlackSettings: async (data: {
  leadership_channel_id?: string;
  tracker_reminder_channel_id?: string;
}): Promise<{ leadership_channel_id: string | null; tracker_reminder_channel_id: string | null }> => {
  const response = await api.put('/admin/integrations/slack/settings', data);
  return response.data;
},
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/core/services/integrations.ts
git commit -m "feat(tracker): add tracker_reminder_channel_id to frontend API types"
```

---

### Task 9: Frontend — Slack config UI

**Files:**
- Modify: `frontend/src/modules/scorecard/components/Settings/SlackTab.tsx`

- [ ] **Step 1: Update `SlackTabProps` interface**

```typescript
interface SlackTabProps {
  readonly status?: ProviderStatus;
  readonly slackSettings?: {
    leadership_channel_id: string | null;
    tracker_reminder_channel_id: string | null;
  };
}
```

- [ ] **Step 2: Add state and mutation for tracker reminder channel**

After `selectedChannel` state (line 41):

```typescript
const [selectedReminderChannel, setSelectedReminderChannel] = useState<string>('');
```

After `saveChannel` mutation (line 61-67):

```typescript
const saveReminderChannel = useMutation({
  mutationFn: (channelId: string) =>
    integrationsApi.updateSlackSettings({ tracker_reminder_channel_id: channelId }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.integrations.status });
  },
});

const handleSaveReminderChannel = (): void => {
  if (selectedReminderChannel) {
    saveReminderChannel.mutate(selectedReminderChannel);
  }
};
```

- [ ] **Step 3: Add UI block for tracker reminder channel**

After the Leadership Channel `</div>` (after line 244, before the Disconnect AlertDialog), add:

```tsx
{/* Tracker Report Reminder Channel */}
<div className="space-y-2">
  <Label>Tracker Report Reminder Channel</Label>
  <p className="text-sm text-muted-foreground">
    A monthly reminder to fill in tracker reports will be sent to this
    channel on the last business day of each month.
  </p>
  <div className="flex items-center gap-2">
    <Label className="text-sm text-muted-foreground">Current:</Label>
    {slackSettings?.tracker_reminder_channel_id ? (
      <Badge variant="secondary">
        #
        {channels?.find(
          (c) => c.id === slackSettings.tracker_reminder_channel_id,
        )?.name || slackSettings.tracker_reminder_channel_id}
      </Badge>
    ) : (
      <span className="text-sm text-muted-foreground">Not set</span>
    )}
  </div>

  <div className="flex gap-2">
    <SlackChannelCombobox
      value={selectedReminderChannel}
      onValueChange={setSelectedReminderChannel}
      channels={channels ?? []}
      disabled={channelsLoading}
      placeholder={channelsLoading ? 'Loading...' : 'Select channel'}
      className="w-[300px]"
    />
    <Button
      onClick={handleSaveReminderChannel}
      disabled={!selectedReminderChannel || saveReminderChannel.isPending}
    >
      {saveReminderChannel.isPending ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        'Save'
      )}
    </Button>
  </div>
</div>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/scorecard/components/Settings/SlackTab.tsx
git commit -m "feat(tracker): add tracker reminder channel selector to Slack settings UI"
```

---

### Task 10: Full test suite verification

- [ ] **Step 1: Run backend tests**

Run: `cd backend && python -m pytest tests/test_report_reminder_job.py -v`
Expected: all 13 tests PASS

- [ ] **Step 2: Run full backend test suite**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: all ~1340+ tests PASS, no regressions

- [ ] **Step 3: Run frontend tests**

Run: `cd frontend && npx vitest run --reporter=verbose 2>&1 | tail -20`
Expected: all ~391+ tests PASS

- [ ] **Step 4: Manual smoke test**

1. Start backend + frontend locally
2. Go to Admin > Settings > Slack tab
3. Verify "Tracker Report Reminder Channel" selector appears below Leadership Channel
4. Select a channel and save — verify badge updates
