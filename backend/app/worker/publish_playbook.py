"""ARQ task for publishing playbook static site to S3."""

import structlog

from app.modules.playbook.services.publish_service import PublishService

logger = structlog.get_logger()


async def publish_playbook_task(ctx: dict, publish_log_id: str) -> dict:
    db = ctx["db"]
    svc = PublishService()
    await svc.publish(db, publish_log_id)
    return {"publish_log_id": publish_log_id}
