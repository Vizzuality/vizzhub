"""Report confirmation reminder scheduled job.

Sends individual Slack DMs to users who haven't confirmed their monthly
report during business days from the 2nd to the 12th of each month.
"""

import logging
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.scorecard.models.slack import ScheduledJobRunDB
from app.modules.scorecard.services.slack_service import SlackService
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.services.period_service import get_active_period
from app.utils.slack import get_slack_bot_token
from app.worker.utils import complete_with_error

logger = logging.getLogger(__name__)

CONFIRMATION_REMINDER_MESSAGE = (
    ":memo: Reminder: Your monthly report for {month} hasn't been confirmed yet. "
    "Please head over to <https://hub.vizzuality.com/tracker/my-report|Vizzhub> "
    "to complete it."
)


def _is_reminder_window(today: date) -> bool:
    """Return True if today is a business day between the 2nd and 12th."""
    return 2 <= today.day <= 12 and today.weekday() < 5


async def _get_users_pending_confirmation(
    db: AsyncSession, period_id: UUID
) -> list[UserDB]:
    """Get active users with project reporting who haven't confirmed their report."""
    confirmed_exists = exists().where(
        ReportDB.user_id == UserDB.id,
        ReportDB.reporting_period_id == period_id,
        ReportDB.estimated.is_(False),
    )

    result = await db.execute(
        select(UserDB).where(
            UserDB.active.is_(True),
            UserDB.requires_project_reporting.is_(True),
            UserDB.slack_user_id.isnot(None),
            ~confirmed_exists,
        )
    )
    return list(result.scalars().all())


async def send_report_confirmation_reminder(ctx: dict) -> dict[str, Any]:
    """Send DM reminders to users who haven't confirmed their report.

    Runs daily via ARQ cron. Only acts on business days from 2nd to 12th.
    """
    if not _is_reminder_window(date.today()):
        return {"status": "skipped", "alerts_sent": 0}

    db: AsyncSession = ctx["db"]

    job_run = ScheduledJobRunDB(
        job_name="send_report_confirmation_reminder",
        status="running",
        projects_checked=0,
        alerts_sent=0,
    )
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)

    try:
        bot_token = await get_slack_bot_token(db)
        if not bot_token:
            return await complete_with_error(
                db, job_run, "Slack not configured - missing bot token"
            )

        period = await get_active_period(db)
        if not period:
            return await complete_with_error(
                db, job_run, "No active reporting period"
            )

        users = await _get_users_pending_confirmation(db, period.id)
        if not users:
            job_run.status = "completed"
            job_run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {
                "status": "completed",
                "job_run_id": job_run.id,
                "alerts_sent": 0,
            }

        month_label = period.date.strftime("%B %Y")
        message = CONFIRMATION_REMINDER_MESSAGE.format(month=month_label)

        alerts_sent = 0
        for user in users:
            try:
                response = await SlackService.send_message(
                    bot_token, user.slack_user_id, message
                )
                if response.get("ok"):
                    alerts_sent += 1
                else:
                    logger.warning(
                        "Failed to DM user %s: %s",
                        user.slack_user_id,
                        response.get("error"),
                    )
            except Exception as e:
                logger.error("Error sending DM to %s: %s", user.slack_user_id, e)

        job_run.status = "completed"
        job_run.alerts_sent = alerts_sent
        job_run.completed_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(
            "Report confirmation reminders: %d/%d DMs sent",
            alerts_sent,
            len(users),
        )

        return {
            "status": "completed",
            "job_run_id": job_run.id,
            "alerts_sent": alerts_sent,
        }

    except Exception as e:
        logger.exception("Report confirmation reminder job failed")
        return await complete_with_error(db, job_run, str(e))
