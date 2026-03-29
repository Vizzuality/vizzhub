"""ISO module configuration endpoints -- Google Workspace OAuth + GitHub + Jira."""

import structlog
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.core.api.deps import DBSession, limiter
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission

IsoManager = Annotated[TokenData, Depends(require_permission(Action.ISO_MANAGE))]
from app.core.oauth_state import OAuthStateManager
from app.core.services.integration_token_service import IntegrationTokenService
from app.core.services.oauth_service import OAuthService
from app.modules.iso.services.google_workspace_oauth import (
    GoogleWorkspaceOAuth,
)

logger = structlog.get_logger()

router = APIRouter()

DOMAIN_PATTERN = r"^[a-zA-Z0-9]([a-zA-Z0-9-]*\.)+[a-zA-Z]{2,}$"


@router.get("/google-workspace")
@limiter.limit("30/minute")
async def get_google_workspace_status(
    request: Request, current_user: IsoManager, db: DBSession
) -> dict:
    return await GoogleWorkspaceOAuth.get_status(db)


@router.get("/google-workspace/authorize")
@limiter.limit("10/minute")
async def authorize_google_workspace(
    request: Request,
    current_user: IsoManager,
    db: DBSession,
    domain: Annotated[
        str, Query(description="Google Workspace domain", pattern=DOMAIN_PATTERN)
    ],
) -> RedirectResponse:
    state = await OAuthStateManager.generate_state(db)
    request.session["oauth_state"] = state
    request.session["gw_domain"] = domain

    callback_url = str(request.url_for("google_workspace_callback"))
    url = GoogleWorkspaceOAuth.get_authorization_url(
        state=state, redirect_uri=callback_url, domain=domain
    )
    return RedirectResponse(url=url, status_code=307)


@router.get(
    "/google-workspace/callback",
    responses={400: {"description": "Invalid or expired OAuth state"}},
)
@limiter.limit("10/minute")
async def google_workspace_callback(
    request: Request,
    current_user: IsoManager,
    db: DBSession,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()] = "",
) -> dict:
    # NOTE: This endpoint requires an authenticated session. The OAuth flow
    # is initiated by a logged-in user (authorize_google_workspace), and the
    # callback returns to the same browser session which should still have
    # the auth cookie. If this causes issues with certain OAuth redirect
    # flows, auth may need to be removed and rely solely on the state param.
    session_state = request.session.get("oauth_state")
    if not session_state or session_state != state:
        logger.warning("oauth_state_mismatch")
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    if not await OAuthStateManager.validate_state(state, db):
        logger.warning("oauth_state_expired")
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
@limiter.limit("10/minute")
async def disconnect_google_workspace(
    request: Request, current_user: IsoManager, db: DBSession
) -> dict:
    await GoogleWorkspaceOAuth.disconnect(db)
    return {"status": "success", "message": "Google Workspace disconnected"}


# --- GitHub Config ---

GITHUB_ORG_PATTERN = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$")
GITHUB_PROVIDER = "github"
GITHUB_ORG_KEY = "iso_org_name"


class GitHubOrgRequest(BaseModel):
    org_name: str = Field(..., min_length=1, max_length=100)


@router.get("/github")
@limiter.limit("30/minute")
async def get_github_status(
    request: Request, current_user: IsoManager, db: DBSession
) -> dict:
    token = await IntegrationTokenService.get_token(db, GITHUB_PROVIDER)
    org_name = await IntegrationTokenService.get_setting(
        db, GITHUB_PROVIDER, GITHUB_ORG_KEY
    )
    return {
        "connected": token is not None,
        "org_name": org_name,
    }


@router.put("/github", responses={422: {"description": "Invalid organization name"}})
@limiter.limit("10/minute")
async def save_github_org(
    request: Request,
    current_user: IsoManager,
    db: DBSession,
    body: GitHubOrgRequest,
) -> dict:
    if not GITHUB_ORG_PATTERN.match(body.org_name):
        raise HTTPException(
            status_code=422,
            detail="Invalid GitHub organization name. Use alphanumeric characters and hyphens.",
        )
    await IntegrationTokenService.set_setting(
        db, GITHUB_PROVIDER, GITHUB_ORG_KEY, body.org_name
    )
    return {"status": "success", "org_name": body.org_name}


@router.delete("/github")
@limiter.limit("10/minute")
async def clear_github_org(
    request: Request, current_user: IsoManager, db: DBSession
) -> dict:
    from sqlalchemy import delete
    from app.core.models.integration_setting import IntegrationSettingDB

    await db.execute(
        delete(IntegrationSettingDB).where(
            IntegrationSettingDB.provider == GITHUB_PROVIDER,
            IntegrationSettingDB.key == GITHUB_ORG_KEY,
        )
    )
    await db.flush()
    return {"status": "success", "message": "GitHub organization cleared"}


# --- Jira Config ---

@router.get("/jira")
@limiter.limit("30/minute")
async def get_jira_status(
    request: Request, current_user: IsoManager, db: DBSession
) -> dict:
    site_info = await OAuthService.get_jira_site_info(db)
    token = await OAuthService.get_valid_jira_token(db)
    return {
        "connected": token is not None,
        "site_url": site_info["site_url"] if site_info else None,
    }
