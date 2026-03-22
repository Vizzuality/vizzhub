"""Authentication API endpoints for Google SSO."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from app.config import get_settings
from app.core.auth import create_access_token, delete_auth_cookie, get_cookie_settings
from app.core.models.role import RoleDB, UserRoleDB
from app.core.models.user import UserDB, UserPublic
from app.core.permissions.resolver import resolve_permissions
from app.modules.scorecard.services.slack_service import SlackService
from app.utils.slack import get_slack_bot_token

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleAuthRequest(BaseModel):
    """Request body for Google authentication."""

    credential: str


class AuthLoginResponse(BaseModel):
    """Response for successful authentication (no token in body)."""

    user: UserPublic


class MeResponse(BaseModel):
    """Response for /auth/me with roles, permissions, and impersonation status."""

    id: UUID
    email: str
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    picture: str | None = None
    roles: list[str] = []
    permissions: list[str] = []
    active: bool = True
    is_impersonating: bool = False
    functional_area_id: UUID | None = None
    rate_id: UUID | None = None
    dedication: Decimal | None = None
    slack_user_id: str | None = None
    slack_display_name: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


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
                logger.warning(f"Unauthorized domain attempt: {email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unauthorized domain",
                )

        # Get or create user
        result = await db.execute(select(UserDB).where(UserDB.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            user = UserDB(
                email=email,
                first_name=idinfo.get("given_name"),
                last_name=idinfo.get("family_name"),
                picture=idinfo.get("picture"),
                last_login_at=datetime.now(timezone.utc),
            )
            # Auto-link Slack profile before first commit
            try:
                bot_token = await get_slack_bot_token(db)
                if bot_token:
                    slack_user = await SlackService.lookup_user_by_email(bot_token, email)
                    if slack_user:
                        user.slack_user_id = slack_user["id"]
                        user.slack_display_name = SlackService.extract_display_name(slack_user)
            except Exception:
                logger.warning(f"Failed to auto-link Slack for {email}", exc_info=True)

            db.add(user)
            await db.flush()

            # Assign roles
            user_role_result = await db.execute(
                select(RoleDB).where(RoleDB.name == "user")
            )
            user_role_obj = user_role_result.scalar_one()
            db.add(UserRoleDB(user_id=user.id, role_id=user_role_obj.id))

            if settings.initial_admin_email and email == settings.initial_admin_email.lower():
                admin_role_result = await db.execute(
                    select(RoleDB).where(RoleDB.name == "admin")
                )
                admin_role_obj = admin_role_result.scalar_one()
                db.add(UserRoleDB(user_id=user.id, role_id=admin_role_obj.id))
                logger.info(f"Creating initial admin user: {email}")

            await db.commit()
            await db.refresh(user)
        else:
            if not user.active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account deactivated. Contact an administrator.",
                )
            # Update last login and profile info
            user.last_login_at = datetime.now(timezone.utc)
            user.first_name = idinfo.get("given_name") or user.first_name
            user.last_name = idinfo.get("family_name") or user.last_name
            user.picture = idinfo.get("picture") or user.picture
            await db.commit()
            await db.refresh(user)

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

        user_public = UserPublic(
            id=user.id,
            email=user.email,
            name=user.name,
            first_name=user.first_name,
            last_name=user.last_name,
            picture=user.picture,
            roles=roles,
            permissions=permissions,
            active=user.active,
        )
        return AuthLoginResponse(user=user_public)

    except ValueError:
        logger.warning("Google token validation failed")
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

    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        first_name=user.first_name,
        last_name=user.last_name,
        picture=user.picture,
        roles=current_user.roles,
        permissions=current_user.permissions,
        active=user.active,
        is_impersonating=request.cookies.get("admin_token") is not None,
        functional_area_id=user.functional_area_id,
        rate_id=user.rate_id,
        dedication=user.dedication,
        slack_user_id=user.slack_user_id,
        slack_display_name=user.slack_display_name,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/logout")
async def logout(current_user: CurrentUser, response: Response) -> dict:
    """Logout: clear the httpOnly cookie."""
    delete_auth_cookie(response)
    delete_auth_cookie(response, key="admin_token")
    logger.info(f"User logged out: {current_user.user_id}")
    return {"message": "Logged out successfully"}
