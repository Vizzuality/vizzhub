"""Tests for the Dependabot Slack digest (summary message + alert list in its thread)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.notifications.models.slack import AlertDefinitionDB, DependabotAlertTrackedDB
from app.worker.dependabot.digest import (
    DEFAULT_SUMMARY_TEMPLATE,
    LINES_PER_REPLY,
    DigestItem,
    build_digest_items,
    build_summary,
    format_item_line,
    send_digest,
)

PARENT_TS = "1700000000.000100"
SEND_PATH = "app.worker.dependabot.shared.SlackService.send_message"


def _alert(number: int, severity: str = "high", package: str = "lodash") -> dict:
    return {
        "number": number,
        "security_vulnerability": {"severity": severity, "package": {"name": package}},
        "security_advisory": {"identifiers": [{"type": "CVE", "value": f"CVE-2026-{number}"}]},
        "dependency": {"manifest_path": "frontend/package-lock.json"},
    }


def _tracked(
    project: ProjectDB, number: int, severity: str, notified_days_ago: int
) -> DependabotAlertTrackedDB:
    notified = datetime.now(UTC) - timedelta(days=notified_days_ago)
    return DependabotAlertTrackedDB(
        project_id=project.id,
        github_alert_id=number,
        package_name="lodash",
        severity=severity,
        first_seen_at=notified,
        last_notified_at=notified,
    )


@pytest_asyncio.fixture
async def setup(db_session: AsyncSession) -> tuple[ProjectDB, AlertDefinitionDB]:
    alert_def = AlertDefinitionDB(
        name="dependabot_high_critical",
        category="project",
        channel_type="project",
        schedule="daily",
        is_enabled=True,
    )
    project = ProjectDB(
        name="Test Project",
        github_repo="owner/my_repo",
        slack_channel_id="C123ABC",
        status="live",
    )
    db_session.add_all([alert_def, project])
    await db_session.commit()
    return project, alert_def


async def _run(
    db: AsyncSession,
    project: ProjectDB,
    alert_def: AlertDefinitionDB,
    current: list[dict],
    send_result: dict | None = None,
) -> tuple[int, AsyncMock]:
    result = await db.execute(
        select(DependabotAlertTrackedDB).where(DependabotAlertTrackedDB.project_id == project.id)
    )
    tracked = list(result.scalars().all())
    with patch(
        SEND_PATH,
        new_callable=AsyncMock,
        return_value=send_result or {"ok": True, "ts": PARENT_TS},
    ) as mock_send:
        sent = await send_digest(db, project, alert_def, "xoxb", tracked, current)
    return sent, mock_send


class TestSendDigest:
    @pytest.mark.asyncio
    async def test_no_message_when_nothing_new_and_no_reminder_due(
        self, db_session: AsyncSession, setup: tuple
    ) -> None:
        project, alert_def = setup
        db_session.add(_tracked(project, 1, "high", notified_days_ago=1))
        await db_session.commit()

        sent, mock_send = await _run(db_session, project, alert_def, [_alert(1)])

        assert sent == 0
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_due_reminder_lists_every_open_alert_and_restarts_cadence(
        self, db_session: AsyncSession, setup: tuple
    ) -> None:
        project, alert_def = setup
        due = _tracked(project, 1, "critical", notified_days_ago=3)
        not_due = _tracked(project, 2, "high", notified_days_ago=1)
        db_session.add_all([due, not_due])
        await db_session.commit()

        sent, mock_send = await _run(
            db_session, project, alert_def, [_alert(1, "critical"), _alert(2)]
        )

        assert sent == 2
        summary_call, thread_call = mock_send.call_args_list
        assert (
            "2 open high/critical vulnerabilities (1 critical, 1 high, 0 new)"
            in (summary_call.args[2])
        )
        assert "Please, fix them ASAP" in summary_call.args[2]
        assert thread_call.kwargs["thread_ts"] == PARENT_TS
        assert "#1>" in thread_call.args[2] and "#2>" in thread_call.args[2]
        await db_session.refresh(due)
        await db_session.refresh(not_due)
        assert due.last_notified_at == not_due.last_notified_at
        assert datetime.now(UTC) - due.last_notified_at < timedelta(minutes=1)

    @pytest.mark.asyncio
    async def test_long_queues_are_split_across_thread_replies(
        self, db_session: AsyncSession, setup: tuple
    ) -> None:
        project, alert_def = setup
        count = LINES_PER_REPLY * 2 + 1

        sent, mock_send = await _run(
            db_session, project, alert_def, [_alert(n) for n in range(1, count + 1)]
        )

        assert sent == count
        replies = mock_send.call_args_list[1:]
        assert len(replies) == 3
        assert sum(r.args[2].count("\n") + 1 for r in replies) == count
        tracked = await db_session.scalars(select(DependabotAlertTrackedDB))
        assert len(tracked.all()) == count

    @pytest.mark.asyncio
    async def test_failed_summary_skips_thread_and_tracking(
        self, db_session: AsyncSession, setup: tuple
    ) -> None:
        project, alert_def = setup

        sent, mock_send = await _run(
            db_session, project, alert_def, [_alert(1)], {"ok": False, "error": "x"}
        )

        assert sent == 0
        mock_send.assert_called_once()
        tracked = await db_session.scalars(select(DependabotAlertTrackedDB))
        assert tracked.all() == []


class TestFormatting:
    def test_items_sort_critical_first_then_new_then_oldest(self) -> None:
        now = datetime.now(UTC)
        old = DependabotAlertTrackedDB(github_alert_id=2, first_seen_at=now - timedelta(days=9))
        recent = DependabotAlertTrackedDB(github_alert_id=3, first_seen_at=now - timedelta(days=1))
        current = [_alert(1), _alert(2), _alert(3), _alert(4, "critical")]

        items = build_digest_items(current, {2: old, 3: recent}, now)

        assert [i.github_alert_id for i in items] == [4, 1, 2, 3]
        assert items[2].days_open == 9

    def test_line_shows_severity_package_age_and_link(self) -> None:
        item = DigestItem(7, "critical", "my_pkg", "CVE-1", "a/uv.lock", 12, is_new=False)

        line = format_item_line("owner/repo", item)

        assert line == (
            ":red_circle: *critical* `my_pkg` · CVE-1 · `a/uv.lock` · open 12d · "
            "<https://github.com/owner/repo/security/dependabot/7|#7>"
        )

    def test_summary_keeps_repo_url_unescaped(self) -> None:
        project = ProjectDB(name="P", github_repo="owner/my_repo")

        summary = build_summary(DEFAULT_SUMMARY_TEMPLATE, project, [])

        assert "<https://github.com/owner/my_repo/security/dependabot|" in summary
