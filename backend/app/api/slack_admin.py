"""Slack admin API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DBSession, limiter
from app.api.schemas.slack import (
    AlertDefinitionResponse,
    AlertDefinitionUpdate,
    AlertTestResponse,
    MessageTemplateResponse,
    MessageTemplateUpdate,
    SlackChannel,
    SlackConfigResponse,
    SlackConfigUpdate,
    SlackTestResult,
)
from app.models.slack import AlertDefinitionDB, MessageTemplateDB, SlackConfigDB
from app.services.slack_service import SlackService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/slack", tags=["slack-admin"])
alerts_router = APIRouter(prefix="/admin/alerts", tags=["alerts-admin"])
templates_router = APIRouter(prefix="/admin/templates", tags=["templates-admin"])


async def get_slack_config_or_create(db: DBSession) -> SlackConfigDB:
    """Get the singleton Slack config, creating it if needed."""
    result = await db.execute(select(SlackConfigDB).limit(1))
    config = result.scalar_one_or_none()
    if config is None:
        config = SlackConfigDB()
        db.add(config)
        await db.commit()
        await db.refresh(config)
    return config


@router.get("/config", response_model=SlackConfigResponse)
@limiter.limit("100/minute")
async def get_slack_config(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
) -> SlackConfigResponse:
    """Get Slack config (token masked). Requires authentication."""
    config = await get_slack_config_or_create(db)
    return SlackConfigResponse(
        id=config.id,
        bot_token_configured=config.bot_token_encrypted is not None,
        leadership_channel_id=config.leadership_channel_id,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.put("/config", response_model=SlackConfigResponse)
@limiter.limit("10/minute")
async def update_slack_config(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    update: SlackConfigUpdate,
) -> SlackConfigResponse:
    """Update Slack config. Requires authentication."""
    config = await get_slack_config_or_create(db)

    if update.bot_token is not None:
        config.bot_token_encrypted = update.bot_token

    if update.leadership_channel_id is not None:
        config.leadership_channel_id = update.leadership_channel_id

    await db.commit()
    await db.refresh(config)

    return SlackConfigResponse(
        id=config.id,
        bot_token_configured=config.bot_token_encrypted is not None,
        leadership_channel_id=config.leadership_channel_id,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("/test", response_model=SlackTestResult)
@limiter.limit("10/minute")
async def test_slack_connection(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
) -> SlackTestResult:
    """Test Slack connection using configured bot token. Requires authentication."""
    config = await get_slack_config_or_create(db)

    if not config.bot_token_encrypted:
        return SlackTestResult(ok=False, error="No bot token configured")

    try:
        result = await SlackService.test_connection(config.bot_token_encrypted)
        if result.get("ok"):
            return SlackTestResult(
                ok=True,
                team=result.get("team"),
                bot_id=result.get("bot_id"),
            )
        else:
            return SlackTestResult(ok=False, error=result.get("error", "Unknown error"))
    except Exception as e:
        logger.exception("Failed to test Slack connection")
        return SlackTestResult(ok=False, error=str(e))


@router.get("/channels", response_model=list[SlackChannel])
@limiter.limit("10/minute")
async def list_slack_channels(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
) -> list[SlackChannel]:
    """List available Slack channels. Requires authentication."""
    config = await get_slack_config_or_create(db)

    if not config.bot_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No bot token configured",
        )

    try:
        channels = await SlackService.list_channels(config.bot_token_encrypted)
        return [
            SlackChannel(
                id=ch["id"],
                name=ch["name"],
                is_private=ch.get("is_private", False),
            )
            for ch in channels
        ]
    except Exception as e:
        logger.exception("Failed to list Slack channels")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list channels: {e}",
        )


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
            detail="Alert definition not found",
        )

    if update.is_enabled is not None:
        alert.is_enabled = update.is_enabled

    if update.config_json is not None:
        alert.config_json = update.config_json

    await db.commit()
    await db.refresh(alert)
    return alert


@alerts_router.post("/{alert_id}/test", response_model=AlertTestResponse)
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
            detail="Alert definition not found",
        )

    config = await get_slack_config_or_create(db)

    if not config.bot_token_encrypted:
        return AlertTestResponse(
            ok=False,
            message="Cannot send test alert",
            error="No Slack bot token configured",
        )

    channel_id = config.leadership_channel_id
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
            config.bot_token_encrypted,
            channel_id,
            test_message,
        )

        if slack_result.get("ok"):
            return AlertTestResponse(
                ok=True,
                message=f"Test alert sent successfully to channel",
                channel_id=channel_id,
            )
        else:
            return AlertTestResponse(
                ok=False,
                message="Failed to send test alert",
                error=slack_result.get("error", "Unknown Slack error"),
            )
    except Exception as e:
        logger.exception("Failed to send test alert")
        return AlertTestResponse(
            ok=False,
            message="Failed to send test alert",
            error=str(e),
        )


@alerts_router.get("/{alert_id}/templates", response_model=list[MessageTemplateResponse])
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
            detail="Alert definition not found",
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
