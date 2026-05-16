"""ARQ task for publishing playbook static site to S3."""

import structlog

from app.modules.playbook.services.publish_service import PublishService

logger = structlog.get_logger()

JOB_NAME = "publish_playbook_task"


async def publish_playbook_task(ctx: dict, publish_log_id: str) -> dict:
    logger.info("job_started", job_name=JOB_NAME, publish_log_id=publish_log_id)
    db = ctx["db"]
    try:
        svc = PublishService()
        await svc.publish(db, publish_log_id)
    except Exception:
        logger.exception("job_failed", job_name=JOB_NAME, publish_log_id=publish_log_id)
        raise
    logger.info("job_completed", job_name=JOB_NAME, publish_log_id=publish_log_id)
    return {"publish_log_id": publish_log_id}
