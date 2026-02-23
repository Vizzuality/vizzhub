"""ISO module configuration endpoints -- Google Workspace OAuth."""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.api.deps import AdminUser, DBSession
from app.core.oauth_state import OAuthStateManager
from app.modules.iso.services.google_workspace_oauth import (
    GoogleWorkspaceOAuth,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/google-workspace")
async def get_google_workspace_status(
    current_user: AdminUser, db: DBSession
) -> dict:
    return await GoogleWorkspaceOAuth.get_status(db)


@router.get("/google-workspace/authorize")
async def authorize_google_workspace(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    domain: str = Query(..., description="Google Workspace domain"),
) -> RedirectResponse:
    state = OAuthStateManager.generate_state()
    request.session["oauth_state"] = state
    request.session["gw_domain"] = domain

    callback_url = str(request.url_for("google_workspace_callback"))
    url = GoogleWorkspaceOAuth.get_authorization_url(
        state=state, redirect_uri=callback_url, domain=domain
    )
    return RedirectResponse(url=url, status_code=307)


@router.get("/google-workspace/callback")
async def google_workspace_callback(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    code: str = Query(...),
    state: str = Query(""),
) -> dict:
    # NOTE: This endpoint requires an authenticated session. The OAuth flow
    # is initiated by a logged-in user (authorize_google_workspace), and the
    # callback returns to the same browser session which should still have
    # the auth cookie. If this causes issues with certain OAuth redirect
    # flows, auth may need to be removed and rely solely on the state param.
    session_state = request.session.get("oauth_state")
    if not session_state or session_state != state:
        logger.warning("OAuth state mismatch in Google Workspace callback")
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    if not OAuthStateManager.validate_state(state):
        logger.warning("OAuth state expired or already used")
        raise HTTPException(status_code=400, detail="State expired or already used")

    domain = request.session.get("gw_domain", "")
    callback_url = str(request.url_for("google_workspace_callback"))
    await GoogleWorkspaceOAuth.exchange_code_for_token(
        code=code, domain=domain, redirect_uri=callback_url, db=db
    )

    request.session.pop("oauth_state", None)
    request.session.pop("gw_domain", None)

    return {"status": "success", "message": "Google Workspace connected"}


@router.delete("/google-workspace/disconnect")
async def disconnect_google_workspace(
    current_user: AdminUser, db: DBSession
) -> dict:
    await GoogleWorkspaceOAuth.disconnect(db)
    return {"status": "success", "message": "Google Workspace disconnected"}
