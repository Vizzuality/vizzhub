"""Shared API helpers for tracker module."""

from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base

logger = structlog.get_logger()


async def get_or_404(
    model: type[Base],
    obj_id: UUID,
    db: AsyncSession,
    label: str | None = None,
) -> Base:
    result = await db.execute(select(model).where(model.id == obj_id))
    obj = result.scalar_one_or_none()
    if not obj:
        name = label or model.__tablename__.rstrip("s").replace("_", " ")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{name} {obj_id} not found",
        )
    return obj


async def push_evm_to_scorecard(
    db: AsyncSession,
    project_id: UUID,
    score_cache=None,
) -> None:
    """Push tracker-derived EVM fields onto scorecard metrics."""
    try:
        from app.modules.scorecard.public import refresh_tracker_evm

        await refresh_tracker_evm(db, project_id, score_cache=score_cache)
    except Exception:
        logger.warning("scorecard_evm_refresh_failed", exc_info=True)


# Backwards-compat alias — the helper used to read backwards (`refresh_scorecard_evm`).
# Keep until callers migrate.
refresh_scorecard_evm = push_evm_to_scorecard
