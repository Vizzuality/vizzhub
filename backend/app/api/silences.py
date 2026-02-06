"""Alert silences API endpoints."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import AdminUser, DBSession, limiter
from app.api.schemas.slack import (
    AlertSilenceCreate,
    AlertSilenceResponse,
    AlertSilenceUpdate,
)
from app.models.project import ProjectDB
from app.models.slack import AlertDefinitionDB, AlertSilenceDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/silences", tags=["silences"])


@router.get("", response_model=list[AlertSilenceResponse])
@limiter.limit("100/minute")
async def list_silences(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    project_id: UUID | None = None,
    include_expired: bool = False,
) -> list[AlertSilenceResponse]:
    """List alert silences."""
    query = select(AlertSilenceDB)

    if project_id:
        query = query.where(AlertSilenceDB.project_id == project_id)

    if not include_expired:
        now = datetime.now(timezone.utc)
        query = query.where(
            (AlertSilenceDB.silenced_until.is_(None))
            | (AlertSilenceDB.silenced_until > now)
        )

    result = await db.execute(query)
    silences = result.scalars().all()

    responses = []
    for silence in silences:
        project_result = await db.execute(
            select(ProjectDB).where(ProjectDB.id == silence.project_id)
        )
        project = project_result.scalar_one_or_none()

        alert_name = None
        if silence.alert_definition_id:
            alert_result = await db.execute(
                select(AlertDefinitionDB).where(
                    AlertDefinitionDB.id == silence.alert_definition_id
                )
            )
            alert = alert_result.scalar_one_or_none()
            alert_name = alert.name if alert else None

        responses.append(
            AlertSilenceResponse(
                id=silence.id,
                project_id=str(silence.project_id),
                alert_definition_id=silence.alert_definition_id,
                silenced_until=silence.silenced_until,
                reason=silence.reason,
                created_by=silence.created_by,
                created_at=silence.created_at,
                project_name=project.name if project else None,
                alert_name=alert_name,
            )
        )

    return responses


@router.post(
    "", response_model=AlertSilenceResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("30/minute")
async def create_silence(
    request: Request,
    silence: AlertSilenceCreate,
    current_user: AdminUser,
    db: DBSession,
) -> AlertSilenceResponse:
    """Create a new alert silence."""
    try:
        project_uuid = UUID(silence.project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project ID format",
        )

    project_result = await db.execute(
        select(ProjectDB).where(ProjectDB.id == project_uuid)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    alert_name = None
    if silence.alert_definition_id:
        alert_result = await db.execute(
            select(AlertDefinitionDB).where(
                AlertDefinitionDB.id == silence.alert_definition_id
            )
        )
        alert = alert_result.scalar_one_or_none()
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert definition not found",
            )
        alert_name = alert.name

    db_silence = AlertSilenceDB(
        project_id=project_uuid,
        alert_definition_id=silence.alert_definition_id,
        silenced_until=silence.silenced_until,
        reason=silence.reason,
        created_by=current_user.user_id if current_user else None,
    )
    db.add(db_silence)
    await db.commit()
    await db.refresh(db_silence)

    return AlertSilenceResponse(
        id=db_silence.id,
        project_id=str(db_silence.project_id),
        alert_definition_id=db_silence.alert_definition_id,
        silenced_until=db_silence.silenced_until,
        reason=db_silence.reason,
        created_by=db_silence.created_by,
        created_at=db_silence.created_at,
        project_name=project.name,
        alert_name=alert_name,
    )


@router.put("/{silence_id}", response_model=AlertSilenceResponse)
@limiter.limit("30/minute")
async def update_silence(
    request: Request,
    silence_id: int,
    update: AlertSilenceUpdate,
    current_user: AdminUser,
    db: DBSession,
) -> AlertSilenceResponse:
    """Update a silence."""
    result = await db.execute(
        select(AlertSilenceDB).where(AlertSilenceDB.id == silence_id)
    )
    silence = result.scalar_one_or_none()

    if not silence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Silence not found",
        )

    if update.silenced_until is not None:
        silence.silenced_until = update.silenced_until
    if update.reason is not None:
        silence.reason = update.reason

    await db.commit()
    await db.refresh(silence)

    project_result = await db.execute(
        select(ProjectDB).where(ProjectDB.id == silence.project_id)
    )
    project = project_result.scalar_one_or_none()

    alert_name = None
    if silence.alert_definition_id:
        alert_result = await db.execute(
            select(AlertDefinitionDB).where(
                AlertDefinitionDB.id == silence.alert_definition_id
            )
        )
        alert = alert_result.scalar_one_or_none()
        alert_name = alert.name if alert else None

    return AlertSilenceResponse(
        id=silence.id,
        project_id=str(silence.project_id),
        alert_definition_id=silence.alert_definition_id,
        silenced_until=silence.silenced_until,
        reason=silence.reason,
        created_by=silence.created_by,
        created_at=silence.created_at,
        project_name=project.name if project else None,
        alert_name=alert_name,
    )


@router.delete("/{silence_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def delete_silence(
    request: Request,
    silence_id: int,
    current_user: AdminUser,
    db: DBSession,
) -> None:
    """Delete a silence."""
    result = await db.execute(
        select(AlertSilenceDB).where(AlertSilenceDB.id == silence_id)
    )
    silence = result.scalar_one_or_none()

    if not silence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Silence not found",
        )

    await db.delete(silence)
    await db.commit()
