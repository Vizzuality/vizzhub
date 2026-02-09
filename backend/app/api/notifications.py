"""Notifications log API endpoints."""

import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

from app.api.deps import AdminUser, DBSession, limiter
from app.api.schemas.slack import (
    AlertNotificationResponse,
    NotificationStatsResponse,
    PaginatedNotificationsResponse,
)
from app.models.project import ProjectDB
from app.models.slack import AlertDefinitionDB, AlertNotificationDB, DependabotAlertTrackedDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
@limiter.limit("100/minute")
async def list_notifications(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    project_id: UUID | None = None,
    alert_definition_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedNotificationsResponse:
    """List sent notifications with filtering and pagination."""
    query = select(AlertNotificationDB).order_by(AlertNotificationDB.sent_at.desc())
    count_query = select(func.count(AlertNotificationDB.id))

    if project_id:
        query = query.where(AlertNotificationDB.project_id == project_id)
        count_query = count_query.where(AlertNotificationDB.project_id == project_id)

    if alert_definition_id:
        query = query.where(AlertNotificationDB.alert_definition_id == alert_definition_id)
        count_query = count_query.where(
            AlertNotificationDB.alert_definition_id == alert_definition_id
        )

    if start_date:
        query = query.where(AlertNotificationDB.sent_at >= start_date)
        count_query = count_query.where(AlertNotificationDB.sent_at >= start_date)

    if end_date:
        query = query.where(AlertNotificationDB.sent_at <= end_date)
        count_query = count_query.where(AlertNotificationDB.sent_at <= end_date)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    notifications = result.scalars().all()

    project_ids = {n.project_id for n in notifications}
    alert_ids = {n.alert_definition_id for n in notifications}

    projects: dict[UUID, str] = {}
    if project_ids:
        projects_result = await db.execute(
            select(ProjectDB).where(ProjectDB.id.in_(project_ids))
        )
        projects = {p.id: p.name for p in projects_result.scalars().all()}

    alerts: dict[int, str] = {}
    if alert_ids:
        alerts_result = await db.execute(
            select(AlertDefinitionDB).where(AlertDefinitionDB.id.in_(alert_ids))
        )
        alerts = {a.id: a.name for a in alerts_result.scalars().all()}

    items = [
        AlertNotificationResponse(
            id=n.id,
            project_id=str(n.project_id),
            alert_definition_id=n.alert_definition_id,
            channel_id=n.channel_id,
            message=n.message,
            status=n.status,
            error_message=n.error_message,
            metadata_json=n.metadata_json,
            sent_at=n.sent_at,
            project_name=projects.get(n.project_id),
            alert_name=alerts.get(n.alert_definition_id),
        )
        for n in notifications
    ]

    pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedNotificationsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/stats")
@limiter.limit("60/minute")
async def get_notification_stats(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
) -> NotificationStatsResponse:
    """Get notification statistics."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_result = await db.execute(
        select(func.count(AlertNotificationDB.id)).where(
            AlertNotificationDB.sent_at >= month_start,
            AlertNotificationDB.status == "sent",
        )
    )
    total_this_month = total_result.scalar() or 0

    type_result = await db.execute(
        select(AlertDefinitionDB.name, func.count(AlertNotificationDB.id))
        .join(
            AlertDefinitionDB,
            AlertNotificationDB.alert_definition_id == AlertDefinitionDB.id,
        )
        .where(
            AlertNotificationDB.sent_at >= month_start,
            AlertNotificationDB.status == "sent",
        )
        .group_by(AlertDefinitionDB.name)
    )
    by_type = {row[0]: row[1] for row in type_result.all()}

    project_result = await db.execute(
        select(ProjectDB.name, func.count(AlertNotificationDB.id))
        .join(ProjectDB, AlertNotificationDB.project_id == ProjectDB.id)
        .where(
            AlertNotificationDB.sent_at >= month_start,
            AlertNotificationDB.status == "sent",
        )
        .group_by(ProjectDB.name)
        .order_by(func.count(AlertNotificationDB.id).desc())
        .limit(10)
    )
    by_project = [{"project_name": row[0], "count": row[1]} for row in project_result.all()]

    resolved_result = await db.execute(
        select(
            func.avg(
                func.extract("epoch", DependabotAlertTrackedDB.resolved_at)
                - func.extract("epoch", DependabotAlertTrackedDB.first_seen_at)
            )
            / 86400
        ).where(DependabotAlertTrackedDB.resolved_at.isnot(None))
    )
    avg_resolution = resolved_result.scalar()

    return NotificationStatsResponse(
        total_this_month=total_this_month,
        by_type=by_type,
        by_project=by_project,
        avg_vulnerability_resolution_days=round(avg_resolution, 1) if avg_resolution else None,
    )
