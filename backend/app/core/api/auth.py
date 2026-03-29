"""Authentication API endpoints for Google SSO."""

import structlog
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from app.config import get_settings
from app.core.auth import create_access_token, delete_auth_cookie, get_cookie_settings
from app.core.models.role import RoleDB, UserRoleDB
from app.core.models.user import User, UserDB, UserPublic
from app.core.permissions.resolver import resolve_permissions
from app.modules.notifications.services.slack_service import SlackService
from app.utils.slack import get_slack_bot_token

logger = structlog.get_logger()
settings = get_settings()


async def _create_new_user(db, email: str, idinfo: dict, app_settings) -> UserDB:
    """Create a new user from Google SSO data, auto-link Slack, assign roles."""
    user = UserDB(
        email=email,
        first_name=idinfo.get("given_name"),
        last_name=idinfo.get("family_name"),
        picture=idinfo.get("picture"),
        last_login_at=datetime.now(timezone.utc),
    )
    try:
        bot_token = await get_slack_bot_token(db)
        if bot_token:
            slack_user = await SlackService.lookup_user_by_email(bot_token, email)
            if slack_user:
                user.slack_user_id = slack_user["id"]
                user.slack_display_name = SlackService.extract_display_name(slack_user)
    except Exception:
        logger.warning("slack_auto_link_failed", email=email, exc_info=True)

    db.add(user)
    await db.flush()

    user_role_obj = (await db.execute(
        select(RoleDB).where(RoleDB.name == "user")
    )).scalar_one()
    db.add(UserRoleDB(user_id=user.id, role_id=user_role_obj.id))

    if app_settings.initial_admin_email and email == app_settings.initial_admin_email.lower():
        admin_role_obj = (await db.execute(
            select(RoleDB).where(RoleDB.name == "admin")
        )).scalar_one()
        db.add(UserRoleDB(user_id=user.id, role_id=admin_role_obj.id))
        logger.info("initial_admin_created", email=email)

    await db.commit()
    await db.refresh(user)
    return user


async def _update_existing_user(db, user: UserDB, idinfo: dict) -> None:
    """Update login timestamp and profile info for existing user."""
    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated. Contact an administrator.",
        )
    user.last_login_at = datetime.now(timezone.utc)
    user.first_name = idinfo.get("given_name") or user.first_name
    user.last_name = idinfo.get("family_name") or user.last_name
    user.picture = idinfo.get("picture") or user.picture
    await db.commit()
    await db.refresh(user)


router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleAuthRequest(BaseModel):
    """Request body for Google authentication."""

    credential: str


class AuthLoginResponse(BaseModel):
    """Response for successful authentication (no token in body)."""

    user: UserPublic


class MeResponse(User):
    """Response for /auth/me with impersonation status."""

    permissions: list[str] = []
    is_impersonating: bool = False


@router.post("/google")
async def google_auth(
    request: GoogleAuthRequest,
    db: DBSession,
    response: Response,
) -> AuthLoginResponse:
    """
    Authenticate with Google OAuth.

    Validates the Google ID token, checks domain restriction,
    creates user if first login, and returns a JWT.
    """
    try:
        # Verify Google token
        idinfo = id_token.verify_oauth2_token(
            request.credential,
            google_requests.Request(),
            settings.google_client_id,
        )

        email = idinfo.get("email", "").lower()
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email not provided by Google",
            )

        # Check domain restriction
        if settings.allowed_google_domain:
            domain = email.split("@")[-1]
            if domain != settings.allowed_google_domain:
                logger.warning("auth_domain_rejected", email=email)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unauthorized domain",
                )

        # Get or create user
        result = await db.execute(select(UserDB).where(UserDB.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            user = await _create_new_user(db, email, idinfo, settings)
        else:
            await _update_existing_user(db, user, idinfo)

        # Resolve roles and permissions, then create JWT
        roles, permissions = await resolve_permissions(db, str(user.id))
        token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "roles": roles,
                "permissions": permissions,
            }
        )

        response.set_cookie(value=token, **get_cookie_settings())

        user_public = UserPublic.model_validate(user)
        user_public.roles = roles
        user_public.permissions = permissions
        return AuthLoginResponse(user=user_public)

    except ValueError:
        logger.warning("google_token_validation_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )


@router.get("/me")
async def get_current_user_info(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
) -> MeResponse:
    """Get the current authenticated user's information."""
    result = await db.execute(
        select(UserDB).where(UserDB.id == current_user.user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    user_data = User.model_validate(user)
    user_data.roles = current_user.roles
    return MeResponse(
        **user_data.model_dump(),
        permissions=current_user.permissions,
        is_impersonating=request.cookies.get("admin_token") is not None,
    )


@router.post("/logout")
async def logout(current_user: CurrentUser, response: Response) -> dict:
    """Logout: clear the httpOnly cookie."""
    delete_auth_cookie(response)
    delete_auth_cookie(response, key="admin_token")
    logger.info("user_logged_out", user_id=current_user.user_id)
    return {"message": "Logged out successfully"}
