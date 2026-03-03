"""OAuth endpoints for external service authentication."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import AdminUser, CurrentUser, DBSession, limiter
from app.config import get_settings
from app.core.oauth_state import OAuthStateManager
from app.core.security_logger import (
    log_oauth_state_validation_failed,
    log_oauth_token_issued,
    log_oauth_token_refresh,
    log_suspicious_activity,
)
from app.core.services.integration_token_service import IntegrationTokenService
from app.core.services.oauth_service import OAuthService

router = APIRouter()
logger = logging.getLogger(__name__)

TOKEN_REFRESH_FAILED = "Token refresh failed"


@router.get("/jira/authorize")
@limiter.limit("10/minute")
async def authorize_jira(
    request: Request, current_user: CurrentUser, db: DBSession
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
            log_oauth_state_validation_failed(
                client_ip, "State mismatch - possible CSRF attack"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid state parameter",
            )

        # Clear used state from session
        request.session.pop("oauth_state", None)

        # Validate state token hasn't been used before
        if not await OAuthStateManager.validate_state(state, db):
            log_oauth_state_validation_failed(
                client_ip, "State token expired or already used"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired state token",
            )

        # Exchange authorization code for token
        await OAuthService.exchange_jira_code_for_token(code, db)
        await db.commit()

        # Log successful OAuth token issuance
        log_oauth_token_issued("jira", "system", client_ip)

        # Return minimal response (no sensitive data)
        return {
            "status": "success",
            "message": "Jira authorization successful",
        }

    except HTTPException:
        raise
    except SQLAlchemyError:
        logger.exception("Database error during OAuth callback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authorization failed",
        )
    except Exception as e:
        logger.exception("OAuth callback failed")
        log_suspicious_activity(f"OAuth callback error: {type(e).__name__}", client_ip)

        # In development, show actual error for debugging
        settings = get_settings()
        detail = (
            f"Authorization failed: {str(e)}"
            if settings.debug
            else "Authorization failed"
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


@router.get("/jira/status")
@limiter.limit("30/minute")
async def jira_oauth_status(
    request: Request, current_user: CurrentUser, db: DBSession
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
    request: Request, current_user: CurrentUser, db: DBSession
) -> dict[str, str]:
    """
    Manually refresh Jira access token.

    Requires authentication.
    Returns success message if refresh was successful.
    """
    client_ip = request.client.host if request.client else "unknown"

    try:
        token = await OAuthService.refresh_jira_token(db)
        await db.commit()

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

    except HTTPException:
        raise
    except SQLAlchemyError:
        logger.exception("Database error during token refresh")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=TOKEN_REFRESH_FAILED,
        )
    except Exception:
        logger.exception(TOKEN_REFRESH_FAILED)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=TOKEN_REFRESH_FAILED,
        )


@router.delete("/jira/disconnect")
@limiter.limit("10/minute")
async def disconnect_jira(
    request: Request, current_user: AdminUser, db: DBSession
) -> dict[str, str]:
    """Disconnect Jira OAuth. Deletes the stored token. Requires admin."""
    deleted = await IntegrationTokenService.delete_token(db, "jira")
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No Jira token found"
        )
    return {"status": "disconnected"}
