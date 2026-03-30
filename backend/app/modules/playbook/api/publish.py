"""Playbook publish API — trigger and monitor static-site generation."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, desc

from app.core.api.deps import AdminUser, DBSession
from app.modules.playbook.models.publish_log import PlaybookPublishLogDB
from app.utils.redis import get_redis_pool

router = APIRouter()


class PublishResponse(BaseModel):
    publish_log_id: str


class PublishStatusResponse(BaseModel):
    status: str
    page_count: int | None
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
    model_config = {"from_attributes": True}


@router.post("/publish", status_code=status.HTTP_201_CREATED)
async def trigger_publish(
    db: DBSession,
    user: AdminUser,
) -> PublishResponse:
    """Trigger a playbook static-site publish."""
    result = await db.execute(
        select(PlaybookPublishLogDB).where(
            PlaybookPublishLogDB.status == "running",
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A publish is already running.",
        )

    log = PlaybookPublishLogDB(
        status="running",
        published_by_id=user.user_id,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    pool = await get_redis_pool()
    await pool.enqueue_job(
        "publish_playbook_task",
        publish_log_id=str(log.id),
    )

    return PublishResponse(publish_log_id=str(log.id))


@router.get("/publish/status")
async def publish_status(
    db: DBSession,
    user: AdminUser,
) -> PublishStatusResponse | None:
    """Get the latest publish log entry."""
    result = await db.execute(
        select(PlaybookPublishLogDB).order_by(
            desc(PlaybookPublishLogDB.started_at),
        ).limit(1)
    )
    log = result.scalar_one_or_none()
    if log is None:
        return None
    return PublishStatusResponse.model_validate(log)


@router.get("/publish/history")
async def publish_history(
    db: DBSession,
    user: AdminUser,
    limit: int = 10,
) -> list[PublishStatusResponse]:
    """Get recent publish log entries."""
    result = await db.execute(
        select(PlaybookPublishLogDB).order_by(
            desc(PlaybookPublishLogDB.started_at),
        ).limit(limit)
    )
    return [PublishStatusResponse.model_validate(log) for log in result.scalars().all()]
