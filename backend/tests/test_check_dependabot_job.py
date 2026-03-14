"""Tests for Dependabot check job.

This module tests the check_dependabot_alerts cron job which runs daily
to scan all projects for new Dependabot alerts and send Slack notifications.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.token_encryption import encrypt_token
from app.core.models.oauth import OAuthTokenDB
from app.core.models.project import ProjectDB
from app.modules.scorecard.models.slack import (
    AlertDefinitionDB,
    DependabotAlertTrackedDB,
    MessageTemplateDB,
)
from app.worker.check_dependabot import check_dependabot_alerts


def _add_slack_token(db_session: AsyncSession) -> OAuthTokenDB:
    """Helper to create a Slack bot token in the new oauth_tokens table."""
    token = OAuthTokenDB(
        provider="slack",
        access_token=encrypt_token("xoxb-test-token"),
        token_type="bot",
    )
    db_session.add(token)
    return token


def _add_github_token(db_session: AsyncSession) -> OAuthTokenDB:
    """Helper to create a GitHub token in the oauth_tokens table."""
    token = OAuthTokenDB(
        provider="github",
        access_token=encrypt_token("ghp-test-token"),
        token_type="pat",
    )
    db_session.add(token)
    return token


class TestCheckDependabotJobExists:
    """Basic existence tests for the job."""

    def test_check_dependabot_job_exists(self) -> None:
        """check_dependabot_alerts function should be callable."""
        assert callable(check_dependabot_alerts)


class TestCheckDependabotJob:
    """Integration tests for the Dependabot check job."""

    @pytest.mark.asyncio
    async def test_job_creates_job_run_record(self, db_session: AsyncSession) -> None:
        """Job should create a ScheduledJobRunDB record at start."""
        _add_slack_token(db_session)
        _add_github_token(db_session)

        alert_def = AlertDefinitionDB(
            name="dependabot_high_critical",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
        )
        db_session.add(alert_def)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_dependabot.DependabotCollector.fetch_alerts",
            new_callable=AsyncMock,
            return_value=[],
        ):

            result = await check_dependabot_alerts(ctx)

        assert result["status"] == "completed"
        assert "job_run_id" in result

    @pytest.mark.asyncio
    async def test_job_skips_projects_without_github_repo(
        self, db_session: AsyncSession
    ) -> None:
        """Job should skip projects without github_repo configured."""
        _add_slack_token(db_session)
        _add_github_token(db_session)

        alert_def = AlertDefinitionDB(
            name="dependabot_high_critical",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
        )
        db_session.add(alert_def)

        project = ProjectDB(
            name="Project Without GitHub",
            github_repo=None,
            slack_channel_id="C123ABC",
            status="live",
        )
        db_session.add(project)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_dependabot.DependabotCollector.fetch_alerts",
            new_callable=AsyncMock,
        ) as mock_fetch:

            result = await check_dependabot_alerts(ctx)

        mock_fetch.assert_not_called()
        assert result["projects_checked"] == 0

    @pytest.mark.asyncio
    async def test_job_skips_projects_without_slack_channel(
        self, db_session: AsyncSession
    ) -> None:
        """Job should skip projects without slack_channel_id configured."""
        _add_slack_token(db_session)
        _add_github_token(db_session)

        alert_def = AlertDefinitionDB(
            name="dependabot_high_critical",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
        )
        db_session.add(alert_def)

        project = ProjectDB(
            name="Project Without Slack",
            github_repo="owner/repo",
            slack_channel_id=None,
        )
        db_session.add(project)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_dependabot.DependabotCollector.fetch_alerts",
            new_callable=AsyncMock,
        ) as mock_fetch:

            result = await check_dependabot_alerts(ctx)

        mock_fetch.assert_not_called()
        assert result["projects_checked"] == 0

    @pytest.mark.asyncio
    async def test_job_processes_project_with_github_and_slack(
        self, db_session: AsyncSession
    ) -> None:
        """Job should process projects with both github_repo and slack_channel_id."""
        _add_slack_token(db_session)
        _add_github_token(db_session)

        alert_def = AlertDefinitionDB(
            name="dependabot_high_critical",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
        )
        db_session.add(alert_def)

        project = ProjectDB(
            name="Full Project",
            github_repo="owner/repo",
            slack_channel_id="C123ABC",
            status="live",
        )
        db_session.add(project)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_dependabot.DependabotCollector.fetch_alerts",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_fetch:

            result = await check_dependabot_alerts(ctx)

        mock_fetch.assert_called_once_with("owner/repo", "ghp-test-token")
        assert result["projects_checked"] == 1

    @pytest.mark.asyncio
    async def test_job_sends_notification_for_new_alert(
        self, db_session: AsyncSession
    ) -> None:
        """Job should send Slack notification for new high/critical alerts."""
        _add_slack_token(db_session)
        _add_github_token(db_session)

        alert_def = AlertDefinitionDB(
            name="dependabot_high_critical",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        template = MessageTemplateDB(
            alert_definition_id=alert_def.id,
            template_type="initial",
            message_template=":warning: New Dependabot alert in {project_name}: {package_name} ({severity})",
            is_active=True,
        )
        db_session.add(template)

        project = ProjectDB(
            name="Test Project",
            github_repo="owner/repo",
            slack_channel_id="C123ABC",
            status="live",
        )
        db_session.add(project)
        await db_session.commit()

        mock_alerts = [
            {
                "number": 1,
                "security_vulnerability": {
                    "severity": "critical",
                    "package": {"name": "lodash"},
                },
                "security_advisory": {
                    "identifiers": [{"type": "CVE", "value": "CVE-2024-1234"}],
                },
                "dependency": {
                    "manifest_path": "frontend/package-lock.json",
                },
            }
        ]

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_dependabot.DependabotCollector.fetch_alerts",
            new_callable=AsyncMock,
            return_value=mock_alerts,
        ), patch(
            "app.worker.check_dependabot.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:

            result = await check_dependabot_alerts(ctx)

        mock_send.assert_called_once()
        assert result["alerts_sent"] >= 1

    @pytest.mark.asyncio
    async def test_job_tracks_notified_alerts(self, db_session: AsyncSession) -> None:
        """Job should create tracking records for notified alerts."""
        _add_slack_token(db_session)
        _add_github_token(db_session)

        alert_def = AlertDefinitionDB(
            name="dependabot_high_critical",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        template = MessageTemplateDB(
            alert_definition_id=alert_def.id,
            template_type="initial",
            message_template="Alert: {package_name}",
            is_active=True,
        )
        db_session.add(template)

        project = ProjectDB(
            name="Test Project",
            github_repo="owner/repo",
            slack_channel_id="C123ABC",
            status="live",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        mock_alerts = [
            {
                "number": 42,
                "security_vulnerability": {
                    "severity": "high",
                    "package": {"name": "axios"},
                },
                "security_advisory": {"identifiers": []},
                "dependency": {"manifest_path": "package-lock.json"},
            }
        ]

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_dependabot.DependabotCollector.fetch_alerts",
            new_callable=AsyncMock,
            return_value=mock_alerts,
        ), patch(
            "app.worker.check_dependabot.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ):
            await check_dependabot_alerts(ctx)

        from sqlalchemy import select

        result = await db_session.execute(
            select(DependabotAlertTrackedDB).where(
                DependabotAlertTrackedDB.project_id == project.id,
                DependabotAlertTrackedDB.github_alert_id == 42,
            )
        )
        tracked = result.scalar_one_or_none()

        assert tracked is not None
        assert tracked.package_name == "axios"
        assert tracked.severity == "high"
        assert tracked.manifest_path == "package-lock.json"

    @pytest.mark.asyncio
    async def test_job_skips_already_tracked_alerts(
        self, db_session: AsyncSession
    ) -> None:
        """Job should not send notification for already tracked alerts."""
        _add_slack_token(db_session)
        _add_github_token(db_session)

        alert_def = AlertDefinitionDB(
            name="dependabot_high_critical",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
        )
        db_session.add(alert_def)

        project = ProjectDB(
            name="Test Project",
            github_repo="owner/repo",
            slack_channel_id="C123ABC",
            status="live",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        existing_tracked = DependabotAlertTrackedDB(
            project_id=project.id,
            github_alert_id=42,
            package_name="axios",
            severity="high",
            last_notified_at=datetime.now(timezone.utc),
        )
        db_session.add(existing_tracked)
        await db_session.commit()

        mock_alerts = [
            {
                "number": 42,
                "security_vulnerability": {
                    "severity": "high",
                    "package": {"name": "axios"},
                },
                "security_advisory": {"identifiers": []},
                "dependency": {"manifest_path": "package-lock.json"},
            }
        ]

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_dependabot.DependabotCollector.fetch_alerts",
            new_callable=AsyncMock,
            return_value=mock_alerts,
        ), patch(
            "app.worker.check_dependabot.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:

            result = await check_dependabot_alerts(ctx)

        mock_send.assert_not_called()
        assert result["alerts_sent"] == 0

    @pytest.mark.asyncio
    async def test_job_marks_resolved_alerts(self, db_session: AsyncSession) -> None:
        """Job should mark alerts as resolved when they disappear from GitHub."""
        _add_slack_token(db_session)
        _add_github_token(db_session)

        alert_def = AlertDefinitionDB(
            name="dependabot_high_critical",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
        )
        db_session.add(alert_def)

        project = ProjectDB(
            name="Test Project",
            github_repo="owner/repo",
            slack_channel_id="C123ABC",
            status="live",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        existing_tracked = DependabotAlertTrackedDB(
            project_id=project.id,
            github_alert_id=42,
            package_name="axios",
            severity="high",
            resolved_at=None,
        )
        db_session.add(existing_tracked)
        await db_session.commit()
        await db_session.refresh(existing_tracked)

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_dependabot.DependabotCollector.fetch_alerts",
            new_callable=AsyncMock,
            return_value=[],
        ):

            await check_dependabot_alerts(ctx)

        await db_session.refresh(existing_tracked)
        assert existing_tracked.resolved_at is not None

    @pytest.mark.asyncio
    async def test_job_respects_silence(self, db_session: AsyncSession) -> None:
        """Job should not send notifications for silenced projects."""
        from datetime import timedelta

        from app.modules.scorecard.models.slack import AlertSilenceDB

        _add_slack_token(db_session)
        _add_github_token(db_session)

        alert_def = AlertDefinitionDB(
            name="dependabot_high_critical",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        project = ProjectDB(
            name="Silenced Project",
            github_repo="owner/repo",
            slack_channel_id="C123ABC",
            status="live",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        silence = AlertSilenceDB(
            project_id=project.id,
            alert_definition_id=alert_def.id,
            silenced_until=datetime.now(timezone.utc) + timedelta(hours=1),
            reason="Maintenance",
        )
        db_session.add(silence)
        await db_session.commit()

        mock_alerts = [
            {
                "number": 1,
                "security_vulnerability": {
                    "severity": "critical",
                    "package": {"name": "lodash"},
                },
                "security_advisory": {"identifiers": []},
                "dependency": {"manifest_path": "package-lock.json"},
            }
        ]

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_dependabot.DependabotCollector.fetch_alerts",
            new_callable=AsyncMock,
            return_value=mock_alerts,
        ), patch(
            "app.worker.check_dependabot.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:

            await check_dependabot_alerts(ctx)

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_job_returns_error_without_slack_config(
        self, db_session: AsyncSession
    ) -> None:
        """Job should return error status when Slack is not configured."""
        alert_def = AlertDefinitionDB(
            name="dependabot_high_critical",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
        )
        db_session.add(alert_def)
        await db_session.commit()

        ctx = {"db": db_session}

        result = await check_dependabot_alerts(ctx)

        assert result["status"] == "error"
        assert "not configured" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_job_returns_error_without_github_token(
        self, db_session: AsyncSession
    ) -> None:
        """Job should return error status when GitHub token is not configured."""
        _add_slack_token(db_session)

        alert_def = AlertDefinitionDB(
            name="dependabot_high_critical",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
        )
        db_session.add(alert_def)
        await db_session.commit()

        ctx = {"db": db_session}

        result = await check_dependabot_alerts(ctx)

        assert result["status"] == "error"
        assert "github" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_job_skips_finished_projects(self, db_session: AsyncSession) -> None:
        """Job should skip finished projects."""
        from datetime import date

        _add_slack_token(db_session)
        _add_github_token(db_session)

        alert_def = AlertDefinitionDB(
            name="dependabot_high_critical",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=True,
        )
        db_session.add(alert_def)

        project = ProjectDB(
            name="Finished Project",
            github_repo="owner/repo",
            slack_channel_id="C123ABC",
            status="finished",
            finished_at=date(2024, 1, 1),
        )
        db_session.add(project)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_dependabot.DependabotCollector.fetch_alerts",
            new_callable=AsyncMock,
        ) as mock_fetch:

            result = await check_dependabot_alerts(ctx)

        mock_fetch.assert_not_called()
        assert result["projects_checked"] == 0
