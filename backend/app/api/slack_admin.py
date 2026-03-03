"""Slack alert and template admin API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.core.api.deps import AdminUser, DBSession, limiter
from app.api.schemas.slack import (
    AlertDefinitionResponse,
    AlertDefinitionUpdate,
    AlertTestResponse,
    MessageTemplateResponse,
    MessageTemplateUpdate,
)
from app.models.slack import AlertDefinitionDB, MessageTemplateDB
from app.core.services.integration_token_service import IntegrationTokenService
from app.services.slack_service import SlackService

logger = logging.getLogger(__name__)

ALERT_DEFINITION_NOT_FOUND = "Alert definition not found"
FAILED_TO_SEND_TEST_ALERT = "Failed to send test alert"

alerts_router = APIRouter(prefix="/admin/alerts", tags=["alerts-admin"])
templates_router = APIRouter(prefix="/admin/templates", tags=["templates-admin"])


@alerts_router.get("/", response_model=list[AlertDefinitionResponse])
@limiter.limit("100/minute")
async def list_alert_definitions(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
) -> list[AlertDefinitionDB]:
    """List all alert definitions. Requires authentication."""
    result = await db.execute(select(AlertDefinitionDB).order_by(AlertDefinitionDB.id))
    return list(result.scalars().all())


@alerts_router.put("/{alert_id}", response_model=AlertDefinitionResponse)
@limiter.limit("10/minute")
async def update_alert_definition(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    alert_id: int,
    update: AlertDefinitionUpdate,
) -> AlertDefinitionDB:
    """Update an alert definition. Requires authentication."""
    result = await db.execute(
        select(AlertDefinitionDB).where(AlertDefinitionDB.id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ALERT_DEFINITION_NOT_FOUND,
        )

    if update.is_enabled is not None:
        alert.is_enabled = update.is_enabled

    if update.config_json is not None:
        alert.config_json = update.config_json

    await db.commit()
    await db.refresh(alert)
    return alert


@alerts_router.post("/{alert_id}/test")
@limiter.limit("5/minute")
async def test_alert(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    alert_id: int,
) -> AlertTestResponse:
    """Send a test notification for an alert. Requires authentication."""
    result = await db.execute(
        select(AlertDefinitionDB).where(AlertDefinitionDB.id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ALERT_DEFINITION_NOT_FOUND,
        )

    bot_token = await IntegrationTokenService.get_token(db, "slack")
    if not bot_token:
        return AlertTestResponse(
            ok=False,
            message="Cannot send test alert",
            error="No Slack bot token configured",
        )

    channel_id = await IntegrationTokenService.get_setting(
        db, "slack", "leadership_channel_id"
    )
    if not channel_id:
        return AlertTestResponse(
            ok=False,
            message="Cannot send test alert",
            error="No leadership channel configured",
        )

    test_message = (
        f":test_tube: *Test Alert*\n"
        f"Alert type: {alert.name}\n"
        f"Category: {alert.category}\n"
        f"This is a test message from Project Scorecard."
    )

    try:
        slack_result = await SlackService.send_message(
            bot_token,
            channel_id,
            test_message,
        )

        if slack_result.get("ok"):
            return AlertTestResponse(
                ok=True,
                message="Test alert sent successfully to channel",
                channel_id=channel_id,
            )
        else:
            return AlertTestResponse(
                ok=False,
                message=FAILED_TO_SEND_TEST_ALERT,
                error=slack_result.get("error", "Unknown Slack error"),
            )
    except Exception as e:
        logger.exception(FAILED_TO_SEND_TEST_ALERT)
        return AlertTestResponse(
            ok=False,
            message=FAILED_TO_SEND_TEST_ALERT,
            error=str(e),
        )


@alerts_router.get(
    "/{alert_id}/templates", response_model=list[MessageTemplateResponse]
)
@limiter.limit("100/minute")
async def get_alert_templates(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    alert_id: int,
) -> list[MessageTemplateDB]:
    """Get templates for an alert definition. Requires authentication."""
    result = await db.execute(
        select(AlertDefinitionDB).where(AlertDefinitionDB.id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ALERT_DEFINITION_NOT_FOUND,
        )

    result = await db.execute(
        select(MessageTemplateDB)
        .where(MessageTemplateDB.alert_definition_id == alert_id)
        .order_by(MessageTemplateDB.template_type)
    )
    return list(result.scalars().all())


@templates_router.put("/{template_id}", response_model=MessageTemplateResponse)
@limiter.limit("10/minute")
async def update_message_template(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    template_id: int,
    update: MessageTemplateUpdate,
) -> MessageTemplateDB:
    """Update a message template. Requires authentication."""
    result = await db.execute(
        select(MessageTemplateDB).where(MessageTemplateDB.id == template_id)
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message template not found",
        )

    if update.message_template is not None:
        template.message_template = update.message_template

    if update.is_active is not None:
        template.is_active = update.is_active

    await db.commit()
    await db.refresh(template)
    return template
