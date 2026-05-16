"""Report confirmation reminder scheduled job.

Sends individual Slack DMs to users who haven't confirmed their monthly
report during business days from the 2nd to the 12th of each month.
"""

import structlog
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.notifications.services.slack_service import SlackService
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.services.period_service import get_active_period
from app.utils.slack import get_slack_bot_token
from app.worker.utils import complete_job_run, complete_with_error, start_job_run

logger = structlog.get_logger()

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
    job_run = await start_job_run(db, "send_report_confirmation_reminder")

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
            await complete_job_run(db, job_run)
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
                        "dm_send_failed",
                        slack_user_id=user.slack_user_id,
                        error=response.get("error"),
                    )
            except Exception as e:
                logger.error("dm_send_error", slack_user_id=user.slack_user_id, error=str(e))

        job_run.alerts_sent = alerts_sent
        await complete_job_run(db, job_run)

        logger.info(
            "reminders_sent",
            sent=alerts_sent,
            total=len(users),
        )

        return {
            "status": "completed",
            "job_run_id": job_run.id,
            "alerts_sent": alerts_sent,
        }

    except Exception as e:
        logger.exception("job_failed")
        return await complete_with_error(db, job_run, str(e))
