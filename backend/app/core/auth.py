"""Authentication and authorization for the API."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Security constants
ALGORITHM = "HS256"
COOKIE_NAME = "access_token"

security = HTTPBearer(auto_error=False)


def get_cookie_settings() -> dict:
    """Return cookie parameters based on environment."""
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "secure": not settings.debug,
        "samesite": "lax",
        "path": "/api",
        "max_age": settings.jwt_expire_hours * 3600,
    }


def delete_auth_cookie(response, key: str = COOKIE_NAME) -> None:
    """Delete an auth cookie with the standard security settings."""
    cookie_settings = get_cookie_settings()
    response.delete_cookie(
        key=key,
        path=cookie_settings["path"],
        samesite=cookie_settings["samesite"],
        secure=cookie_settings["secure"],
        httponly=cookie_settings["httponly"],
    )


class TokenData(BaseModel):
    """Token payload data."""

    user_id: str
    email: str | None = None
    roles: list[str] = []
    permissions: list[str] = []
    exp: datetime | None = None


def create_access_token(
    data: dict[str, str | list[str]], expires_delta: timedelta | None = None
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Token payload data
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(hours=settings.jwt_expire_hours)

    to_encode.update({"exp": expire})

    # Get secret key from environment
    secret_key = getattr(settings, "jwt_secret_key", "")
    if not secret_key:
        raise ValueError(
            "JWT_SECRET_KEY not configured. Please set JWT_SECRET_KEY environment variable."
        )

    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> TokenData:
    """
    Validate JWT token and extract user data.

    Reads the token from the httpOnly cookie first, then falls back to
    the Authorization: Bearer header.

    In development mode (DEBUG=true), bypasses authentication if no token found.
    """
    # Extract token: cookie first, then Bearer header
    token: str | None = request.cookies.get(COOKIE_NAME)
    if not token and credentials is not None:
        token = credentials.credentials

    # Development mode: bypass authentication if no token found.
    # In production we refuse to honor this even if `debug` accidentally
    # ends up true — the synthetic admin must never appear there.
    if settings.debug and token is None:
        if settings.app_env == "production":
            logger.critical(
                "auth_bypass_blocked_in_production",
                app_env=settings.app_env,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        logger.critical(
            "auth_bypass_dev_mode",
            synthetic_user_id="00000000-0000-0000-0000-000000000001",
            app_env=settings.app_env,
        )
        return TokenData(
            user_id="00000000-0000-0000-0000-000000000001",
            roles=["user", "admin"],
            permissions=["*"],
        )

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. No bearer token provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        secret_key = getattr(settings, "jwt_secret_key", "")
        if not secret_key:
            raise credentials_exception

        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        email: str | None = payload.get("email")
        roles: list[str] = payload.get("roles", [])
        permissions: list[str] = payload.get("permissions", [])

        if user_id is None:
            raise credentials_exception

        return TokenData(user_id=user_id, email=email, roles=roles, permissions=permissions)
    except JWTError:
        raise credentials_exception
