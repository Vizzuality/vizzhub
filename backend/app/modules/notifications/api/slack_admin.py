"""Slack alert and template admin API endpoints."""

from typing import Annotated

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.api.deps import DBSession, limiter
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission

ScorecardManager = Annotated[TokenData, Depends(require_permission(Action.SCORECARD_MANAGE))]
from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.notifications.api.schemas.slack import (
    AlertDefinitionResponse,
    AlertDefinitionUpdate,
    AlertTestResponse,
    CustomNotificationRequest,
    CustomNotificationResponse,
    MessageTemplateResponse,
    MessageTemplateUpdate,
)
from app.core.models.user import UserDB
from app.modules.notifications.models.slack import AlertDefinitionDB, MessageTemplateDB
from app.modules.notifications.services.slack_service import SlackAPIError, SlackService

logger = structlog.get_logger()

ALERT_DEFINITION_NOT_FOUND = "Alert definition not found"
FAILED_TO_SEND_TEST_ALERT = "Failed to send test alert"

alerts_router = APIRouter(prefix="/admin/alerts", tags=["alerts-admin"])
templates_router = APIRouter(prefix="/admin/templates", tags=["templates-admin"])
custom_router = APIRouter(prefix="/admin/notifications", tags=["custom-notifications"])


@alerts_router.get("", response_model=list[AlertDefinitionResponse])
@limiter.limit("100/minute")
async def list_alert_definitions(
    request: Request,
    current_user: ScorecardManager,
    db: DBSession,
) -> list[AlertDefinitionDB]:
    """List all alert definitions. Requires authentication."""
    result = await db.execute(select(AlertDefinitionDB).order_by(AlertDefinitionDB.id))
    return list(result.scalars().all())


@alerts_router.put("/{alert_id}", response_model=AlertDefinitionResponse)
@limiter.limit("10/minute")
async def update_alert_definition(
    request: Request,
    current_user: ScorecardManager,
    db: DBSession,
    alert_id: int,
    update: AlertDefinitionUpdate,
) -> AlertDefinitionDB:
    """Update an alert definition. Requires authentication."""
    result = await db.execute(select(AlertDefinitionDB).where(AlertDefinitionDB.id == alert_id))
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

    await db.flush()
    await db.refresh(alert)
    return alert


@alerts_router.post("/{alert_id}/test")
@limiter.limit("5/minute")
async def test_alert(
    request: Request,
    current_user: ScorecardManager,
    db: DBSession,
    alert_id: int,
) -> AlertTestResponse:
    """Send a test notification for an alert. Requires authentication."""
    result = await db.execute(select(AlertDefinitionDB).where(AlertDefinitionDB.id == alert_id))
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

    # Resolution order:
    #   1. explicit recipient_slack_user_id  (DM that user)
    #   2. explicit recipient_slack_channel_id  (post to that channel)
    #   3. channel_type == 'project' → caller's own DM, so the admin pressing
    #      Test gets a representative preview of what the runtime-resolved
    #      recipient (PM, issuer) would actually receive.
    #   4. leadership channel as last resort.
    config = alert.config_json or {}
    channel_id = config.get("recipient_slack_user_id") or config.get(
        "recipient_slack_channel_id"
    )

    if not channel_id and alert.channel_type == "project":
        channel_id = await db.scalar(
            select(UserDB.slack_user_id).where(UserDB.id == current_user.user_id)
        )

    if not channel_id:
        channel_id = await IntegrationTokenService.get_setting(db, "slack", "leadership_channel_id")
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
        f"This is a test message from Vizzhub."
    )

    try:
        slack_result = await SlackService.send_message(
            bot_token,
            channel_id,
            test_message,
        )
    except (httpx.HTTPError, SlackAPIError, SQLAlchemyError) as e:
        # Known transport / API / DB failure modes return a structured
        # ok:false so the admin UI can render the error. Anything else
        # (programming bug, unexpected dependency failure) propagates to
        # the global 500 handler so the traceback hits Sentry.
        logger.exception("alert_test_send_failed", error_type=type(e).__name__)
        return AlertTestResponse(
            ok=False,
            message=FAILED_TO_SEND_TEST_ALERT,
            error=str(e),
        )

    if slack_result.get("ok"):
        return AlertTestResponse(
            ok=True,
            message="Test alert sent successfully to channel",
            channel_id=channel_id,
        )
    return AlertTestResponse(
        ok=False,
        message=FAILED_TO_SEND_TEST_ALERT,
        error=slack_result.get("error", "Unknown Slack error"),
    )


@alerts_router.get("/{alert_id}/templates", response_model=list[MessageTemplateResponse])
@limiter.limit("100/minute")
async def get_alert_templates(
    request: Request,
    current_user: ScorecardManager,
    db: DBSession,
    alert_id: int,
) -> list[MessageTemplateDB]:
    """Get templates for an alert definition. Requires authentication."""
    result = await db.execute(select(AlertDefinitionDB).where(AlertDefinitionDB.id == alert_id))
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
    current_user: ScorecardManager,
    db: DBSession,
    template_id: int,
    update: MessageTemplateUpdate,
) -> MessageTemplateDB:
    """Update a message template. Requires authentication."""
    result = await db.execute(select(MessageTemplateDB).where(MessageTemplateDB.id == template_id))
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

    await db.flush()
    await db.refresh(template)
    return template


# --- Custom notifications ---


@custom_router.post("/send-custom")
@limiter.limit("10/minute")
async def send_custom_notification(
    request: Request,
    current_user: ScorecardManager,
    db: DBSession,
    payload: CustomNotificationRequest,
) -> CustomNotificationResponse:
    """Send a custom Slack DM to a user. Requires admin."""
    bot_token = await IntegrationTokenService.get_token(db, "slack")
    if not bot_token:
        return CustomNotificationResponse(
            ok=False,
            message="Cannot send notification",
            error="No Slack bot token configured",
        )

    try:
        result = await SlackService.send_message(
            bot_token,
            payload.slack_user_id,
            payload.message,
            unfurl_links=payload.unfurl_links,
            unfurl_media=payload.unfurl_media,
        )
    except (httpx.HTTPError, SlackAPIError, SQLAlchemyError) as e:
        logger.exception("custom_notification_send_failed", error_type=type(e).__name__)
        return CustomNotificationResponse(
            ok=False,
            message="Failed to send message",
            error=str(e),
        )

    if result.get("ok"):
        return CustomNotificationResponse(
            ok=True,
            message="Message sent successfully",
        )
    return CustomNotificationResponse(
        ok=False,
        message="Failed to send message",
        error=result.get("error", "Unknown Slack error"),
    )
