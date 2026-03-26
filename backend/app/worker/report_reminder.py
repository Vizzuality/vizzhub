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
