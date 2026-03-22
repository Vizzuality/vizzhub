"""Authentication API endpoints for Google SSO."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from app.config import get_settings
from app.core.auth import create_access_token, delete_auth_cookie, get_cookie_settings
from app.core.models.user import User, UserDB, UserPublic
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


class MeResponse(User):
    """Response for /auth/me with impersonation status."""

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
                logger.warning(f"Unauthorized domain attempt: {email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unauthorized domain",
                )

        # Get or create user
        result = await db.execute(select(UserDB).where(UserDB.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            if settings.initial_admin_email and email == settings.initial_admin_email.lower():
                logger.info(f"Creating initial admin user: {email}")

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
            await db.commit()
            await db.refresh(user)
            logger.info(f"Created new user: {email} with role {role.value}")
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

        # Create JWT and set as httpOnly cookie
        token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role,
            }
        )

        response.set_cookie(value=token, **get_cookie_settings())

        return AuthLoginResponse(
            user=UserPublic.model_validate(user),
        )

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

    user_data = User.model_validate(user)
    return MeResponse(
        **user_data.model_dump(),
        is_impersonating=request.cookies.get("admin_token") is not None,
    )


@router.post("/logout")
async def logout(current_user: CurrentUser, response: Response) -> dict:
    """Logout: clear the httpOnly cookie."""
    delete_auth_cookie(response)
    delete_auth_cookie(response, key="admin_token")
    logger.info(f"User logged out: {current_user.user_id}")
    return {"message": "Logged out successfully"}
