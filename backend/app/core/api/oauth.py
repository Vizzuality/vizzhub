"""OAuth endpoints for external service authentication."""

from typing import Annotated

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.core.api.deps import DBSession, limiter
from app.core.auth import TokenData
from app.core.oauth_state import OAuthStateManager
from app.core.permissions import Action, require_permission
from app.core.security_logger import (
    log_oauth_state_validation_failed,
    log_oauth_token_issued,
    log_oauth_token_refresh,
    log_suspicious_activity,
)
from app.core.services.integration_token_service import IntegrationTokenService
from app.core.services.oauth_service import OAuthService

IntegrationAdmin = Annotated[TokenData, Depends(require_permission(Action.ADMIN_INTEGRATIONS))]

router = APIRouter()
logger = structlog.get_logger()

TOKEN_REFRESH_FAILED = "Token refresh failed"


@router.get("/jira/authorize")
@limiter.limit("10/minute")
async def authorize_jira(
    request: Request, current_user: IntegrationAdmin, db: DBSession
) -> RedirectResponse:
    """
    Initiate Jira OAuth flow with CSRF protection.

    Redirects user to Atlassian authorization page with state parameter.
    """
    # Generate state token for CSRF protection
    state = await OAuthStateManager.generate_state(db)

    # Get authorization URL with state
    authorization_url = OAuthService.get_jira_authorization_url(state=state)

    # Store state in session for validation in callback
    request.session["oauth_state"] = state

    return RedirectResponse(url=authorization_url)


@router.get("/jira/callback")
@limiter.limit("10/minute")
async def jira_callback(
    request: Request,
    code: Annotated[str, Query(description="Authorization code from Jira")],
    state: Annotated[str, Query(description="State parameter for CSRF protection")],
    db: DBSession,
) -> dict[str, str]:
    """
    Handle Jira OAuth callback with state validation and CSRF protection.

    Validates state parameter, exchanges authorization code for access token.
    """
    client_ip = request.client.host if request.client else "unknown"

    try:
        # Validate state parameter from session
        stored_state = request.session.get("oauth_state")
        if not stored_state or stored_state != state:
            log_oauth_state_validation_failed(client_ip, "State mismatch - possible CSRF attack")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid state parameter",
            )

        # Clear used state from session
        request.session.pop("oauth_state", None)

        # Validate state token hasn't been used before
        if not await OAuthStateManager.validate_state(state, db):
            log_oauth_state_validation_failed(client_ip, "State token expired or already used")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired state token",
            )

        await OAuthService.exchange_jira_code_for_token(code, db)
        await db.flush()

        log_oauth_token_issued("jira", "system", client_ip)

        # Return minimal response (no sensitive data)
        return {
            "status": "success",
            "message": "Jira authorization successful",
        }

    except SQLAlchemyError:
        logger.exception("oauth_callback_db_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authorization failed",
        )
    except (httpx.HTTPError, ValueError) as e:
        logger.exception("oauth_callback_failed")
        log_suspicious_activity(f"OAuth callback error: {type(e).__name__}", client_ip)

        settings = get_settings()
        detail = f"Authorization failed: {str(e)}" if settings.debug else "Authorization failed"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


@router.get("/jira/status")
@limiter.limit("30/minute")
async def jira_oauth_status(
    request: Request, current_user: IntegrationAdmin, db: DBSession
) -> dict[str, bool]:
    """
    Check Jira OAuth token status.

    Returns only authentication status - no sensitive data exposed.
    Requires authentication.
    """
    token = await OAuthService.get_valid_jira_token(db)

    # Return minimal information only
    return {
        "authenticated": token is not None,
    }


@router.post("/jira/refresh")
@limiter.limit("10/minute")
async def refresh_jira_token(
    request: Request, current_user: IntegrationAdmin, db: DBSession
) -> dict[str, str]:
    """
    Manually refresh Jira access token.

    Requires authentication.
    Returns success message if refresh was successful.
    """
    client_ip = request.client.host if request.client else "unknown"

    try:
        token = await OAuthService.refresh_jira_token(db)
        await db.flush()

        if not token:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No Jira token found",
            )

        # Log token refresh
        log_oauth_token_refresh("jira", current_user.user_id, client_ip)

        return {
            "status": "success",
            "message": "Token refreshed successfully",
        }

    except SQLAlchemyError:
        logger.exception("token_refresh_db_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=TOKEN_REFRESH_FAILED,
        )
    except (httpx.HTTPError, ValueError):
        logger.exception("token_refresh_failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=TOKEN_REFRESH_FAILED,
        )


@router.delete("/jira/disconnect")
@limiter.limit("10/minute")
async def disconnect_jira(
    request: Request, current_user: IntegrationAdmin, db: DBSession
) -> dict[str, str]:
    """Disconnect Jira OAuth. Deletes the stored token. Requires admin."""
    deleted = await IntegrationTokenService.delete_token(db, "jira")
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Jira token found")
    return {"status": "disconnected"}
