"""ISO module configuration endpoints -- Google Workspace OAuth."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.oauth_state import OAuthStateManager
from app.database import get_db
from app.modules.iso.services.google_workspace_oauth import (
    GoogleWorkspaceOAuth,
)

logger = logging.getLogger(__name__)

router = APIRouter()

DBSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/google-workspace")
async def get_google_workspace_status(db: DBSession) -> dict:
    return await GoogleWorkspaceOAuth.get_status(db)


@router.get("/google-workspace/authorize")
async def authorize_google_workspace(
    request: Request,
    db: DBSession,
    domain: str = Query(..., description="Google Workspace domain"),
) -> RedirectResponse:
    state = OAuthStateManager.generate_state()
    request.session["oauth_state"] = state
    request.session["gw_domain"] = domain

    url = GoogleWorkspaceOAuth.get_authorization_url(
        state=state, domain=domain
    )
    return RedirectResponse(url=url, status_code=307)


@router.get("/google-workspace/callback")
async def google_workspace_callback(
    request: Request,
    db: DBSession,
    code: str = Query(...),
    state: str = Query(""),
) -> dict:
    session_state = request.session.get("oauth_state")
    if not session_state or session_state != state:
        logger.warning(
            "OAuth state mismatch in Google Workspace callback"
        )
        raise HTTPException(
            status_code=400, detail="Invalid state parameter"
        )

    if not OAuthStateManager.validate_state(state):
        logger.warning("OAuth state expired or already used")
        raise HTTPException(
            status_code=400, detail="State expired or already used"
        )

    domain = request.session.get("gw_domain", "")
    await GoogleWorkspaceOAuth.exchange_code_for_token(
        code=code, domain=domain, db=db
    )

    request.session.pop("oauth_state", None)
    request.session.pop("gw_domain", None)

    return {"status": "success", "message": "Google Workspace connected"}


@router.delete("/google-workspace/disconnect")
async def disconnect_google_workspace(db: DBSession) -> dict:
    await GoogleWorkspaceOAuth.disconnect(db)
    return {"status": "success", "message": "Google Workspace disconnected"}
