"""Admin API endpoints for managing integration tokens."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.api.deps import CurrentUser, DBSession, limiter
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission

IntegrationAdmin = Annotated[TokenData, Depends(require_permission(Action.ADMIN_INTEGRATIONS))]
from app.modules.scorecard.api.schemas.integrations import (
    AllIntegrationsStatus,
    GitHubTokenInput,
    ProviderStatus,
    SlackSettingsUpdate,
    SlackTokenInput,
)
from app.modules.scorecard.api.schemas.slack import SlackChannel, SlackTestResult
from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.scorecard.services.slack_service import SlackService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/integrations", tags=["integrations-admin"])

GITHUB_PAT_EXPIRY_DAYS = 365


def _format_provider_status(raw: dict) -> ProviderStatus:
    """Convert raw status dict to ProviderStatus with ISO-formatted dates."""
    return ProviderStatus(
        connected=raw["connected"],
        expires_at=raw["expires_at"].isoformat() if raw["expires_at"] else None,
        token_type=raw["token_type"],
        site_url=raw["site_url"],
        created_at=raw["created_at"].isoformat() if raw["created_at"] else None,
    )


@router.get("/status")
@limiter.limit("100/minute")
async def get_all_integrations_status(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
) -> AllIntegrationsStatus:
    """Get connection status for all integration providers."""
    jira_raw = await IntegrationTokenService.get_provider_status(db, "jira")
    google_raw = await IntegrationTokenService.get_provider_status(
        db, "google_workspace"
    )
    github_raw = await IntegrationTokenService.get_provider_status(db, "github")
    slack_raw = await IntegrationTokenService.get_provider_status(db, "slack")

    leadership_channel_id = await IntegrationTokenService.get_setting(
        db, "slack", "leadership_channel_id"
    )

    return AllIntegrationsStatus(
        jira=_format_provider_status(jira_raw),
        google_workspace=_format_provider_status(google_raw),
        github=_format_provider_status(github_raw),
        slack=_format_provider_status(slack_raw),
        slack_settings={"leadership_channel_id": leadership_channel_id},
    )


@router.put("/github")
@limiter.limit("10/minute")
async def save_github_token(
    request: Request,
    current_user: IntegrationAdmin,
    db: DBSession,
    body: GitHubTokenInput,
) -> ProviderStatus:
    """Save a GitHub Personal Access Token. Requires admin role."""
    record = await IntegrationTokenService.save_token(
        db,
        provider="github",
        token=body.token,
        token_type="pat",
        expires_in_days=GITHUB_PAT_EXPIRY_DAYS,
    )
    await db.commit()

    return ProviderStatus(
        connected=True,
        expires_at=record.expires_at.isoformat() if record.expires_at else None,
        token_type=record.token_type,
        site_url=record.site_url,
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


@router.delete("/github")
@limiter.limit("10/minute")
async def delete_github_token(
    request: Request,
    current_user: IntegrationAdmin,
    db: DBSession,
) -> dict[str, str]:
    """Disconnect GitHub integration. Requires admin role."""
    deleted = await IntegrationTokenService.delete_token(db, "github")
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub token not found",
        )
    await db.commit()
    return {"status": "disconnected"}


@router.put("/slack")
@limiter.limit("10/minute")
async def save_slack_token(
    request: Request,
    current_user: IntegrationAdmin,
    db: DBSession,
    body: SlackTokenInput,
) -> ProviderStatus:
    """Save a Slack bot token. Requires admin role."""
    record = await IntegrationTokenService.save_token(
        db,
        provider="slack",
        token=body.token,
        token_type="bot",
        expires_in_days=None,
    )
    await db.commit()

    return ProviderStatus(
        connected=True,
        expires_at=record.expires_at.isoformat() if record.expires_at else None,
        token_type=record.token_type,
        site_url=record.site_url,
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


@router.delete("/slack")
@limiter.limit("10/minute")
async def delete_slack_token(
    request: Request,
    current_user: IntegrationAdmin,
    db: DBSession,
) -> dict[str, str]:
    """Disconnect Slack integration. Requires admin role."""
    deleted = await IntegrationTokenService.delete_token(db, "slack")
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slack token not found",
        )
    await db.commit()
    return {"status": "disconnected"}


@router.put("/slack/settings")
@limiter.limit("10/minute")
async def update_slack_settings(
    request: Request,
    current_user: IntegrationAdmin,
    db: DBSession,
    body: SlackSettingsUpdate,
) -> dict[str, str | None]:
    """Update Slack integration settings. Requires admin role."""
    if body.leadership_channel_id is not None:
        await IntegrationTokenService.set_setting(
            db, "slack", "leadership_channel_id", body.leadership_channel_id
        )
    await db.commit()

    leadership_channel_id = await IntegrationTokenService.get_setting(
        db, "slack", "leadership_channel_id"
    )
    return {"leadership_channel_id": leadership_channel_id}


@router.get("/slack/channels")
@limiter.limit("100/minute")
async def list_slack_channels(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
) -> list[SlackChannel]:
    """List available Slack channels. Requires authentication."""
    token = await IntegrationTokenService.get_token(db, "slack")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Slack token configured",
        )

    try:
        channels = await SlackService.list_channels(token)
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


@router.post("/slack/test")
@limiter.limit("10/minute")
async def test_slack_connection(
    request: Request,
    current_user: IntegrationAdmin,
    db: DBSession,
) -> SlackTestResult:
    """Test Slack connection using configured bot token. Requires admin role."""
    token = await IntegrationTokenService.get_token(db, "slack")
    if not token:
        return SlackTestResult(ok=False, error="No Slack token configured")

    try:
        result = await SlackService.test_connection(token)
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
