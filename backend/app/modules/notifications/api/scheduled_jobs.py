"""Scheduled jobs API endpoints."""

import structlog
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.core.api.deps import DBSession, limiter
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.notifications.api.schemas.slack import (
    JobTriggerResponse,
    ScheduledJobChannelUpdate,
    ScheduledJobInfo,
    ScheduledJobLastRun,
)
from app.modules.notifications.models.slack import ScheduledJobRunDB
from app.utils.redis import get_redis_pool

logger = structlog.get_logger()

JobAdmin = Annotated[TokenData, Depends(require_permission(Action.ADMIN_JOBS))]

router = APIRouter(prefix="/admin/jobs", tags=["scheduled-jobs"])

SCHEDULED_JOBS = {
    "check_dependabot_alerts": {
        "name": "check_dependabot_alerts",
        "schedule": "Daily at 8:00 AM",
        "description": "Checks all projects for new Dependabot alerts and sends Slack notifications",
    },
    "check_business_alerts": {
        "name": "check_business_alerts",
        "schedule": "Daily at 9:00 AM",
        "description": "Checks projects for budget, timeline, and overdue alerts",
        "channel_setting_key": "leadership_channel_id",
        "channel_label": "Leadership Channel",
    },
    "collect_iso_snapshot": {
        "name": "collect_iso_snapshot",
        "schedule": "Monthly on 1st at 6:00 AM UTC",
        "description": "Captures Google Workspace access snapshot for ISO compliance review",
    },
    "monthly_scorecard_capture": {
        "name": "monthly_scorecard_capture",
        "schedule": "Monthly on 5th at 2:00 AM UTC",
        "description": "Captures Jira/GitHub metrics for all scorecard-enabled projects",
    },
    "fetch_exchange_rates": {
        "name": "fetch_exchange_rates",
        "schedule": "Daily at 2:30 PM UTC",
        "description": "Fetches ECB daily exchange rates for EUR-based currency conversion",
    },
    "send_report_confirmation_reminder": {
        "name": "send_report_confirmation_reminder",
        "schedule": "Daily at 12:00 PM UTC",
        "description": "Sends DM reminders to users who haven't confirmed their monthly report (2nd-12th)",
    },
    "send_monthly_report_reminder": {
        "name": "send_monthly_report_reminder",
        "schedule": "Daily at 10:00 AM UTC",
        "description": "Sends monthly report reminder on the last business day of each month",
        "channel_setting_key": "tracker_reminder_channel_id",
        "channel_label": "Tracker Reminder Channel",
    },
    "rotate_reporting_period": {
        "name": "rotate_reporting_period",
        "schedule": "Monthly on 15th at 12:00 AM UTC",
        "description": "Finishes the active reporting period and creates a new one for the current month",
    },
    "refresh_devstack_sources": {
        "name": "refresh_devstack_sources",
        "schedule": "Daily at 6:00 AM UTC",
        "description": "Refreshes GitHub file SHAs and npm latest versions for DevStack catalog entries",
    },
}


@router.get("/scheduled")
@limiter.limit("100/minute")
async def list_scheduled_jobs(
    request: Request,
    current_user: JobAdmin,
    db: DBSession,
) -> list[ScheduledJobInfo]:
    """List all scheduled jobs with their last run status.

    Returns a list of known scheduled jobs with:
    - name: Job identifier
    - schedule: Human-readable schedule description
    - description: What the job does
    - last_run: Most recent run info (if any)
    """
    result = []

    for job_name, job_info in SCHEDULED_JOBS.items():
        query = (
            select(ScheduledJobRunDB)
            .where(ScheduledJobRunDB.job_name == job_name)
            .order_by(ScheduledJobRunDB.started_at.desc())
            .limit(1)
        )
        db_result = await db.execute(query)
        last_run_record = db_result.scalar_one_or_none()

        last_run = None
        if last_run_record:
            last_run = ScheduledJobLastRun(
                id=last_run_record.id,
                started_at=last_run_record.started_at,
                completed_at=last_run_record.completed_at,
                status=last_run_record.status,
                projects_checked=last_run_record.projects_checked,
                alerts_sent=last_run_record.alerts_sent,
                error_message=last_run_record.error_message,
            )

        channel_id = None
        channel_label = None
        channel_setting_key = job_info.get("channel_setting_key")
        if channel_setting_key:
            channel_id = await IntegrationTokenService.get_setting(
                db, "slack", channel_setting_key
            )
            channel_label = job_info.get("channel_label")

        result.append(
            ScheduledJobInfo(
                name=job_info["name"],
                schedule=job_info["schedule"],
                description=job_info["description"],
                last_run=last_run,
                channel_id=channel_id,
                channel_label=channel_label,
            )
        )

    return result


@router.post("/scheduled/{job_name}/run")
@limiter.limit("10/minute")
async def trigger_scheduled_job(
    request: Request,
    current_user: JobAdmin,
    db: DBSession,
    job_name: str,
) -> JobTriggerResponse:
    """Manually trigger a scheduled job.

    Enqueues the specified job to run immediately via ARQ.
    Returns job enqueue status.
    """
    if job_name not in SCHEDULED_JOBS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown scheduled job: {job_name}",
        )

    try:
        pool = await get_redis_pool()
        arq_job = await pool.enqueue_job(job_name)
        await pool.close()

        if arq_job:
            logger.info("job_triggered", job_name=job_name, arq_job_id=arq_job.job_id)
            return JobTriggerResponse(
                success=True,
                message=f"Job '{job_name}' has been enqueued",
                job_id=arq_job.job_id,
            )
        else:
            return JobTriggerResponse(
                success=False,
                message=f"Job '{job_name}' could not be enqueued (may already be queued)",
            )

    except Exception as e:
        logger.exception("job_enqueue_failed", job_name=job_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue job: {e}. Is Redis running?",
        )


@router.put("/scheduled/{job_name}/channel")
@limiter.limit("10/minute")
async def update_scheduled_job_channel(
    request: Request,
    current_user: JobAdmin,
    db: DBSession,
    job_name: str,
    body: ScheduledJobChannelUpdate,
) -> dict[str, str]:
    """Update the Slack channel for a scheduled job."""
    job_info = SCHEDULED_JOBS.get(job_name)
    if not job_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown scheduled job: {job_name}",
        )

    channel_setting_key = job_info.get("channel_setting_key")
    if not channel_setting_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job '{job_name}' does not have a configurable channel",
        )

    await IntegrationTokenService.set_setting(
        db, "slack", channel_setting_key, body.channel_id
    )
    await db.commit()

    return {"channel_id": body.channel_id}
