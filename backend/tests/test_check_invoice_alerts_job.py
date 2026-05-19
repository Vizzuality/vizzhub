"""Tests for the check_invoice_alerts daily cron job.

The job fires three Slack alerts per invoice based on the effective
scheduled date:
- ``advance_30d`` / ``advance_15d``: DM to the project manager when
  days_until ≤ threshold and no prior alert exists for the current
  effective date + kind.
- ``issue_reminder``: post to the configured channel pinging the
  configured issuer when days_until == 1.

Dedup keys live in ``alert_notifications.metadata_json``
({invoice_id, fired_for_date, alert_kind}).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.oauth import OAuthTokenDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.core.token_encryption import encrypt_token
from app.modules.notifications.models.slack import (
    AlertDefinitionDB,
    AlertNotificationDB,
    MessageTemplateDB,
)
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.postponement import InvoicePostponementDB
from app.worker.check_invoice_alerts import (
    ALERT_ADVANCE,
    ALERT_ISSUE,
    KIND_30D,
    check_invoice_alerts,
)


@pytest_asyncio.fixture
async def slack_and_alerts(db_session: AsyncSession) -> dict[str, AlertDefinitionDB]:
    """Seed Slack token + the two invoice alert definitions with templates."""
    db_session.add(
        OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test-token"),
            token_type="bot",
        )
    )

    advance = AlertDefinitionDB(
        name=ALERT_ADVANCE,
        category="business",
        channel_type="project",
        schedule="daily",
        is_enabled=True,
        config_json={"days_before": [30, 15]},
    )
    issue = AlertDefinitionDB(
        name=ALERT_ISSUE,
        category="business",
        channel_type="leadership",
        schedule="daily",
        is_enabled=True,
        config_json={
            "recipient_slack_user_id": "U_ISSUER",
            "recipient_slack_channel_id": "C_INVOICES",
            "days_before": 1,
        },
    )
    db_session.add_all([advance, issue])
    await db_session.flush()

    db_session.add_all(
        [
            MessageTemplateDB(
                alert_definition_id=advance.id,
                template_type="initial",
                message_template=(
                    "{project_name}|{milestone}|{amount}|{currency}|"
                    "{due_date}|{days_until}|{detail_url}"
                ),
                is_active=True,
            ),
            MessageTemplateDB(
                alert_definition_id=issue.id,
                template_type="initial",
                message_template=(
                    "<@{issuer}>|{project_name}|{milestone}|{amount}|"
                    "{currency}|{due_date}|{detail_url}"
                ),
                is_active=True,
            ),
        ]
    )
    await db_session.commit()
    return {ALERT_ADVANCE: advance, ALERT_ISSUE: issue}


async def _make_invoice_with_pm(
    db: AsyncSession,
    *,
    due_in_days: int,
    pm_slack: str | None = "U_PM_123",
    raw_status: str = "scheduled",
) -> tuple[ProjectDB, InvoiceDB, UserDB | None]:
    pm: UserDB | None = None
    pm_id = None
    if pm_slack is not None:
        pm = UserDB(
            email=f"pm-{pm_slack}@example.com",
            name="PM",
            slack_user_id=pm_slack,
        )
        db.add(pm)
        await db.flush()
        pm_id = pm.id

    project = ProjectDB(
        name="Proj X",
        status="live",
        currency="euro",
        project_manager_id=pm_id,
    )
    db.add(project)
    await db.flush()

    invoice = InvoiceDB(
        project_id=project.id,
        amount=Decimal("1234"),
        due_date=date.today() + timedelta(days=due_in_days),
        milestone="M1",
        status=raw_status,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return project, invoice, pm


@pytest.mark.asyncio
class TestInvoiceAlerts:
    async def test_30d_alert_fires_for_pm(self, db_session: AsyncSession, slack_and_alerts) -> None:
        project, invoice, pm = await _make_invoice_with_pm(db_session, due_in_days=20)
        assert pm is not None

        with patch(
            "app.worker.check_invoice_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            result = await check_invoice_alerts({"db": db_session})

        assert result["status"] == "completed"
        # 20 days away → both 30d AND 15d thresholds hit (15 < 20? No, 20 > 15
        # so only 30d fires). Sanity check the count.
        assert result["alerts_sent"] == 1
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args.args[1] == pm.slack_user_id  # channel = PM DM

        # Confirm dedup metadata captured for re-runs.
        log = (
            await db_session.execute(
                select(AlertNotificationDB).where(
                    AlertNotificationDB.alert_definition_id == slack_and_alerts[ALERT_ADVANCE].id
                )
            )
        ).scalar_one()
        assert log.metadata_json["alert_kind"] == KIND_30D
        assert log.metadata_json["invoice_id"] == str(invoice.id)
        assert log.metadata_json["fired_for_date"] == invoice.due_date.isoformat()

    async def test_15d_and_30d_fire_independently(
        self, db_session: AsyncSession, slack_and_alerts
    ) -> None:
        """An invoice 10 days away should fire BOTH 30d and 15d alerts."""
        await _make_invoice_with_pm(db_session, due_in_days=10)

        with patch(
            "app.worker.check_invoice_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ):
            result = await check_invoice_alerts({"db": db_session})

        assert result["alerts_sent"] == 2

    async def test_no_double_fire_same_day(
        self, db_session: AsyncSession, slack_and_alerts
    ) -> None:
        await _make_invoice_with_pm(db_session, due_in_days=20)

        with patch(
            "app.worker.check_invoice_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            await check_invoice_alerts({"db": db_session})
            await check_invoice_alerts({"db": db_session})

        # Two runs but only one Slack call — dedup honoured.
        assert mock_send.call_count == 1

    async def test_approved_postpone_shifts_effective_date_and_refires(
        self, db_session: AsyncSession, slack_and_alerts
    ) -> None:
        """After an approved postpone the effective date changes, so the
        30d alert fires again for the NEW date."""
        project, invoice, pm = await _make_invoice_with_pm(db_session, due_in_days=20)

        with patch(
            "app.worker.check_invoice_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            await check_invoice_alerts({"db": db_session})
            assert mock_send.call_count == 1

            # Admin-approved postpone → new effective date in 25 days.
            new_date = date.today() + timedelta(days=25)
            db_session.add(
                InvoicePostponementDB(
                    invoice_id=invoice.id,
                    postponed_to=new_date,
                    reason="Client requested",
                    approval_status="approved",
                )
            )
            await db_session.commit()

            await check_invoice_alerts({"db": db_session})
            assert mock_send.call_count == 2

    async def test_postpone_pending_uses_original_date(
        self, db_session: AsyncSession, slack_and_alerts
    ) -> None:
        """A pending postpone request has no effect — original due_date wins."""
        project, invoice, pm = await _make_invoice_with_pm(db_session, due_in_days=20)
        db_session.add(
            InvoicePostponementDB(
                invoice_id=invoice.id,
                postponed_to=date.today() + timedelta(days=50),
                reason="please",
                approval_status="pending",
            )
        )
        await db_session.commit()

        with patch(
            "app.worker.check_invoice_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            await check_invoice_alerts({"db": db_session})

        assert mock_send.call_count == 1
        log = (
            await db_session.execute(
                select(AlertNotificationDB).where(
                    AlertNotificationDB.alert_definition_id == slack_and_alerts[ALERT_ADVANCE].id
                )
            )
        ).scalar_one()
        assert log.metadata_json["fired_for_date"] == invoice.due_date.isoformat()

    async def test_issue_reminder_one_day_before_to_channel(
        self, db_session: AsyncSession, slack_and_alerts
    ) -> None:
        project, invoice, pm = await _make_invoice_with_pm(db_session, due_in_days=1)

        with patch(
            "app.worker.check_invoice_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            await check_invoice_alerts({"db": db_session})

        # day_until == 1 hits all three: 30d, 15d, and issue_reminder.
        assert mock_send.call_count == 3
        # The issue_reminder call uses the channel, not a PM DM.
        targets = {call.args[1] for call in mock_send.call_args_list}
        assert "C_INVOICES" in targets

        # And mentions the issuer in the message body.
        issue_msg = next(
            call.args[2] for call in mock_send.call_args_list if call.args[1] == "C_INVOICES"
        )
        assert "<@U_ISSUER>" in issue_msg

    async def test_issue_reminder_skipped_without_channel_config(
        self, db_session: AsyncSession, slack_and_alerts
    ) -> None:
        """If channel id is missing, the issue reminder must not fire."""
        slack_and_alerts[ALERT_ISSUE].config_json = {
            "recipient_slack_user_id": "U_ISSUER",
            "recipient_slack_channel_id": "",
            "days_before": 1,
        }
        await db_session.commit()

        await _make_invoice_with_pm(db_session, due_in_days=1)

        with patch(
            "app.worker.check_invoice_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            await check_invoice_alerts({"db": db_session})

        # Only 30d + 15d fire (2 calls). No issue reminder.
        assert mock_send.call_count == 2

    async def test_pm_without_slack_id_skips_advance_alerts(
        self, db_session: AsyncSession, slack_and_alerts
    ) -> None:
        """Project with PM lacking slack_user_id → advance alerts skipped silently."""
        pm = UserDB(email="nopm@example.com", name="NoSlack PM", slack_user_id=None)
        db_session.add(pm)
        await db_session.flush()

        project = ProjectDB(name="P", status="live", currency="dollar", project_manager_id=pm.id)
        db_session.add(project)
        await db_session.flush()
        db_session.add(
            InvoiceDB(
                project_id=project.id,
                amount=Decimal("100"),
                due_date=date.today() + timedelta(days=10),
                milestone="M1",
                status="scheduled",
            )
        )
        await db_session.commit()

        with patch(
            "app.worker.check_invoice_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            result = await check_invoice_alerts({"db": db_session})

        assert result["alerts_sent"] == 0
        mock_send.assert_not_called()

    async def test_paid_invoice_skipped(self, db_session: AsyncSession, slack_and_alerts) -> None:
        await _make_invoice_with_pm(db_session, due_in_days=10, raw_status="paid")

        with patch(
            "app.worker.check_invoice_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            result = await check_invoice_alerts({"db": db_session})

        assert result["alerts_sent"] == 0
        mock_send.assert_not_called()
