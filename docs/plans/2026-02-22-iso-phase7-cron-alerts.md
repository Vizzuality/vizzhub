# ISO Phase 7: Cron Job + Failure Alerts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a monthly ARQ cron job that auto-captures Google Workspace snapshots, with Slack failure alerts on errors.

**Architecture:** New worker task `collect_iso_snapshot` follows existing patterns (ctx-based DB access, `SlackService.send_message` for alerts). Registered as cron in `WorkerSettings.cron_jobs`. Errors (OAuth expired, API failures) are caught, logged, and sent to Slack's leadership channel.

**Tech Stack:** ARQ worker, SlackService (httpx), SQLAlchemy async sessions, pytest

---

### Task 1: Create the worker task function

**Files:**
- Create: `backend/app/worker/collect_iso_snapshot.py`
- Test: `backend/tests/test_iso_cron.py`

**Step 1: Write failing tests**

Create `backend/tests/test_iso_cron.py`:

```python
"""Tests for ISO snapshot cron job."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.iso.models.access_snapshot import AccessSnapshotDB


class TestCollectIsoSnapshot:
    @pytest.mark.asyncio
    async def test_successful_capture(self, db_session) -> None:
        from app.models.oauth import OAuthTokenDB

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

        ctx = {"db": db_session}

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            return_value=mock_api_response,
        ):
            from app.worker.collect_iso_snapshot import collect_iso_snapshot

            result = await collect_iso_snapshot(ctx)

        assert result["status"] == "completed"
        assert "snapshot_id" in result

    @pytest.mark.asyncio
    async def test_failure_no_oauth_token(self, db_session) -> None:
        ctx = {"db": db_session}

        with patch(
            "app.worker.collect_iso_snapshot.send_iso_failure_alert",
            new_callable=AsyncMock,
        ) as mock_alert:
            from app.worker.collect_iso_snapshot import collect_iso_snapshot

            result = await collect_iso_snapshot(ctx)

        assert result["status"] == "error"
        assert "error" in result
        mock_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_api_error(self, db_session) -> None:
        from app.models.oauth import OAuthTokenDB

        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="ya29.test",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        ctx = {"db": db_session}

        with (
            patch(
                "httpx.AsyncClient.get",
                new_callable=AsyncMock,
                side_effect=Exception("API rate limit exceeded"),
            ),
            patch(
                "app.worker.collect_iso_snapshot.send_iso_failure_alert",
                new_callable=AsyncMock,
            ) as mock_alert,
        ):
            from app.worker.collect_iso_snapshot import collect_iso_snapshot

            result = await collect_iso_snapshot(ctx)

        assert result["status"] == "error"
        mock_alert.assert_called_once()
        call_args = mock_alert.call_args
        assert "API rate limit exceeded" in str(call_args)


class TestSendIsoFailureAlert:
    @pytest.mark.asyncio
    async def test_sends_slack_message(self, db_session) -> None:
        from app.models.slack import SlackConfigDB

        config = SlackConfigDB(
            bot_token_encrypted="xoxb-test-token",
            leadership_channel_id="C12345",
        )
        db_session.add(config)
        await db_session.flush()

        with patch(
            "app.services.slack_service.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            from app.worker.collect_iso_snapshot import send_iso_failure_alert

            await send_iso_failure_alert(db_session, "OAuth token expired")

        mock_send.assert_called_once()
        args = mock_send.call_args
        assert "xoxb-test-token" in args[0] or args[1].get("bot_token") == "xoxb-test-token"
        assert "C12345" in args[0] or args[1].get("channel_id") == "C12345"

    @pytest.mark.asyncio
    async def test_no_slack_config_does_not_raise(self, db_session) -> None:
        from app.worker.collect_iso_snapshot import send_iso_failure_alert

        await send_iso_failure_alert(db_session, "some error")

    @pytest.mark.asyncio
    async def test_slack_send_failure_does_not_raise(self, db_session) -> None:
        from app.models.slack import SlackConfigDB

        config = SlackConfigDB(
            bot_token_encrypted="xoxb-test-token",
            leadership_channel_id="C12345",
        )
        db_session.add(config)
        await db_session.flush()

        with patch(
            "app.services.slack_service.SlackService.send_message",
            new_callable=AsyncMock,
            side_effect=Exception("Network error"),
        ):
            from app.worker.collect_iso_snapshot import send_iso_failure_alert

            await send_iso_failure_alert(db_session, "OAuth error")
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_iso_cron.py -v`
Expected: FAIL (module not found)

**Step 3: Implement the worker task**

Create `backend/app/worker/collect_iso_snapshot.py`:

```python
"""ISO access snapshot cron job."""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso.services.collectors.google_workspace import (
    GoogleWorkspaceCollector,
)
from app.services.slack_service import SlackService
from app.utils.slack import get_slack_config

logger = logging.getLogger(__name__)


async def collect_iso_snapshot(ctx: dict) -> dict:
    """Capture a Google Workspace access snapshot.

    Called by ARQ cron (monthly) or triggered manually.
    On failure, sends Slack alert to leadership channel.
    """
    db: AsyncSession = ctx["db"]

    try:
        collector = GoogleWorkspaceCollector(db)
        snapshot = await collector.capture(run_mode="cron")
    except Exception as e:
        error_msg = str(e)
        logger.error(
            "ISO snapshot capture failed: %s",
            error_msg,
            exc_info=True,
        )
        await send_iso_failure_alert(db, error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    logger.info("ISO snapshot captured: %s", snapshot.id)
    return {
        "status": "completed",
        "snapshot_id": str(snapshot.id),
        "provider": snapshot.provider,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def send_iso_failure_alert(db: AsyncSession, error_message: str) -> None:
    """Send Slack notification when ISO snapshot capture fails."""
    try:
        slack_config = await get_slack_config(db)
        if not slack_config or not slack_config.bot_token_encrypted:
            logger.warning("Slack not configured, cannot send ISO failure alert")
            return
        if not slack_config.leadership_channel_id:
            logger.warning("No leadership channel configured for ISO failure alert")
            return

        message = (
            ":rotating_light: *ISO Access Review — Snapshot capture failed*\n"
            f"Error: {error_message}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            "Action required: Check Google Workspace OAuth connection in ISO settings."
        )

        await SlackService.send_message(
            slack_config.bot_token_encrypted,
            slack_config.leadership_channel_id,
            message,
        )
        logger.info("ISO failure alert sent to Slack")
    except Exception:
        logger.exception("Failed to send ISO failure Slack alert")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_cron.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/worker/collect_iso_snapshot.py backend/tests/test_iso_cron.py
git commit -m "feat(iso): add cron task for monthly snapshot capture with Slack alerts"
```

---

### Task 2: Register cron job in worker settings

**Files:**
- Modify: `backend/app/worker/settings.py`
- Test: `backend/tests/test_iso_cron.py` (add registration test)

**Step 1: Write failing test**

Add to `backend/tests/test_iso_cron.py`:

```python
class TestWorkerRegistration:
    def test_task_registered_in_worker_functions(self) -> None:
        from app.worker.settings import WorkerSettings

        function_names = [f.__name__ if callable(f) else str(f) for f in WorkerSettings.functions]
        assert "collect_iso_snapshot" in function_names

    def test_cron_job_registered(self) -> None:
        from app.worker.settings import WorkerSettings

        cron_function_names = []
        for cron_job in WorkerSettings.cron_jobs:
            name = getattr(cron_job, "name", None) or getattr(cron_job.coroutine, "__name__", "")
            cron_function_names.append(name)
        assert "collect_iso_snapshot" in cron_function_names
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_iso_cron.py::TestWorkerRegistration -v`
Expected: FAIL (not in list)

**Step 3: Register in worker settings**

In `backend/app/worker/settings.py`, add the import and registration:

```python
from app.worker.collect_iso_snapshot import collect_iso_snapshot
```

Add to `WorkerSettings.functions` list:
```python
collect_iso_snapshot,
```

Add to `WorkerSettings.cron_jobs` list:
```python
cron(collect_iso_snapshot, day=1, hour=6, minute=0),  # 1st of month at 6 AM
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_cron.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/worker/settings.py backend/tests/test_iso_cron.py
git commit -m "feat(iso): register snapshot cron job monthly on 1st at 6 AM UTC"
```

---

### Task 3: Add manual trigger endpoint

**Files:**
- Modify: `backend/app/api/scheduled_jobs.py` (add ISO job to allowlist)
- Test: `backend/tests/test_iso_cron.py` (add trigger test)

**Step 1: Write failing test**

Add to `backend/tests/test_iso_cron.py`:

```python
class TestManualTrigger:
    @pytest.mark.asyncio
    async def test_trigger_iso_snapshot_job(self, client) -> None:
        """Verify the scheduled job endpoint accepts collect_iso_snapshot."""
        with patch(
            "app.utils.redis.get_redis_pool",
            new_callable=AsyncMock,
        ) as mock_pool:
            mock_redis = AsyncMock()
            mock_redis.enqueue_job = AsyncMock(return_value=MagicMock(job_id="test-123"))
            mock_redis.close = AsyncMock()
            mock_pool.return_value = mock_redis

            response = await client.post(
                "/api/scheduled-jobs/collect_iso_snapshot/run"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_iso_cron.py::TestManualTrigger -v`
Expected: FAIL (404 — job name not in allowlist)

**Step 3: Add to allowlist**

In the scheduled jobs endpoint file (`backend/app/api/scheduled_jobs.py`), find the allowlist of job names and add `"collect_iso_snapshot"`.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_iso_cron.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/api/scheduled_jobs.py backend/tests/test_iso_cron.py
git commit -m "feat(iso): add collect_iso_snapshot to scheduled jobs allowlist"
```

---

### Task 4: Run full test suite + lint

**Step 1: Run all backend tests**

Run: `pytest`
Expected: all tests pass (925+ tests)

**Step 2: Run linters**

Run: `ruff check app/ && black --check app/`
Expected: no issues

**Step 3: Fix any lint issues if needed**

**Step 4: Final commit if lint fixes needed**

```bash
git add -A && git commit -m "style: fix lint issues in ISO cron job"
```
