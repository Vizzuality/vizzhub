"""Tests for ISO snapshot cron job and failure alerts."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.token_encryption import encrypt_token
from app.core.models.integration_setting import IntegrationSettingDB
from app.core.models.oauth import OAuthTokenDB
from app.modules.notifications.models.slack import ScheduledJobRunDB
from app.worker.collect_iso_snapshot import (
    collect_iso_snapshot,
    send_iso_failure_alert,
)


class TestCollectIsoSnapshot:
    @pytest.mark.asyncio
    async def test_successful_gw_capture(self, db_session: AsyncSession) -> None:
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("ya29.test"),
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
            result = await collect_iso_snapshot({"db": db_session})

        assert result["status"] == "completed"
        assert "google_workspace" in result["providers"]
        assert "snapshot_id" in result["providers"]["google_workspace"]
        assert "job_run_id" in result

    @pytest.mark.asyncio
    async def test_successful_capture_creates_job_run(
        self, db_session: AsyncSession
    ) -> None:
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("ya29.test"),
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

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
            await collect_iso_snapshot({"db": db_session})

        db_result = await db_session.execute(
            select(ScheduledJobRunDB).where(
                ScheduledJobRunDB.job_name == "collect_iso_snapshot"
            )
        )
        job_run = db_result.scalar_one()
        assert job_run.status == "completed"
        assert job_run.completed_at is not None

    @pytest.mark.asyncio
    async def test_no_providers_connected_completes_with_no_captures(
        self, db_session: AsyncSession
    ) -> None:
        result = await collect_iso_snapshot({"db": db_session})

        assert result["status"] == "completed"
        assert result["providers"] == {}
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_gw_failure_creates_error_and_sends_alert(
        self, db_session: AsyncSession
    ) -> None:
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("ya29.test"),
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

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
            result = await collect_iso_snapshot({"db": db_session})

        assert result["status"] == "error"
        assert any("API rate limit exceeded" in e for e in result["error"].split(";"))
        mock_alert.assert_called_once()
        alert_msg = mock_alert.call_args[0][1]
        assert "google_workspace" in alert_msg
        assert "API rate limit exceeded" in alert_msg

    @pytest.mark.asyncio
    async def test_gw_failure_does_not_block_github(
        self, db_session: AsyncSession
    ) -> None:
        gw_token = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("ya29.test"),
            site_url="empresa.com",
        )
        gh_token = OAuthTokenDB(
            provider="github",
            access_token=encrypt_token("ghp_test"),
            token_type="pat",
        )
        gh_setting = IntegrationSettingDB(
            provider="github",
            key="iso_org_name",
            value="acme-corp",
        )
        db_session.add_all([gw_token, gh_token, gh_setting])
        await db_session.flush()

        with (
            patch(
                "app.worker.collect_iso_snapshot.GoogleWorkspaceCollector.capture",
                new_callable=AsyncMock,
                side_effect=Exception("GW OAuth expired"),
            ),
            patch(
                "app.worker.collect_iso_snapshot.GitHubCollector.capture",
                new_callable=AsyncMock,
            ) as mock_gh_capture,
            patch(
                "app.worker.collect_iso_snapshot.send_iso_failure_alert",
                new_callable=AsyncMock,
            ),
        ):
            mock_gh_capture.return_value = MagicMock(id="gh-snap-1")
            result = await collect_iso_snapshot({"db": db_session})

        assert result["status"] == "completed"
        assert "github" in result["providers"]
        assert len(result["errors"]) == 1
        assert "google_workspace" in result["errors"][0]


class TestSendIsoFailureAlert:
    @pytest.mark.asyncio
    async def test_sends_slack_message(self, db_session: AsyncSession) -> None:
        token = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test-token"),
            token_type="bot",
        )
        db_session.add(token)

        setting = IntegrationSettingDB(
            provider="slack",
            key="leadership_channel_id",
            value="C_LEADERSHIP",
        )
        db_session.add(setting)
        await db_session.flush()

        with patch(
            "app.worker.collect_iso_snapshot.SlackService.send_message",
            new_callable=AsyncMock,
        ) as mock_send:
            await send_iso_failure_alert(db_session, "OAuth token expired")

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == "xoxb-test-token"
        assert call_args[0][1] == "C_LEADERSHIP"
        assert "OAuth token expired" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_no_slack_config_does_not_raise(
        self, db_session: AsyncSession
    ) -> None:
        await send_iso_failure_alert(db_session, "Some error")

    @pytest.mark.asyncio
    async def test_slack_send_failure_does_not_raise(
        self, db_session: AsyncSession
    ) -> None:
        token = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test-token"),
            token_type="bot",
        )
        db_session.add(token)

        setting = IntegrationSettingDB(
            provider="slack",
            key="leadership_channel_id",
            value="C_LEADERSHIP",
        )
        db_session.add(setting)
        await db_session.flush()

        with patch(
            "app.worker.collect_iso_snapshot.SlackService.send_message",
            new_callable=AsyncMock,
            side_effect=Exception("Slack API error"),
        ):
            await send_iso_failure_alert(db_session, "Some error")


class TestWorkerRegistration:
    def test_task_registered_in_worker_functions(self) -> None:
        from app.worker.settings import WorkerSettings

        function_names = [
            f.__name__ if callable(f) else str(f) for f in WorkerSettings.functions
        ]
        assert "collect_iso_snapshot" in function_names

    def test_cron_job_registered(self) -> None:
        from app.worker.settings import WorkerSettings

        cron_function_names = []
        for cron_job in WorkerSettings.cron_jobs:
            name = getattr(cron_job.coroutine, "__name__", "")
            cron_function_names.append(name)
        assert "collect_iso_snapshot" in cron_function_names


class TestManualTrigger:
    @pytest.mark.asyncio
    async def test_trigger_iso_snapshot_job(self, client: AsyncClient) -> None:
        mock_job = MagicMock()
        mock_job.job_id = "test-123"

        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock(return_value=mock_job)
        mock_pool.close = AsyncMock()

        with patch(
            "app.modules.scorecard.api.scheduled_jobs.get_redis_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ):
            response = await client.post(
                "/api/admin/jobs/scheduled/collect_iso_snapshot/run"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
