"""Authentication and authorization for the API.

TODO: Implement Google OAuth (Google Sign-In) for production authentication.
      Development mode bypass is temporary - production will require authentication.
"""

import logging
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Security constants
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    """Token payload data."""

    user_id: str
    roles: list[str] = []
    exp: datetime | None = None


class Token(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str = "bearer"


class User(BaseModel):
    """User model for authentication."""

    user_id: str
    username: str
    roles: list[str] = []


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
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

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
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]
) -> TokenData:
    """
    Validate JWT token and extract user data.

    In development mode (DEBUG=true), bypasses authentication if no token provided.
    In production mode (DEBUG=false), always requires valid JWT token.

    TODO: Replace with Google OAuth (Google Sign-In) for production.
          Development bypass is temporary.

    Args:
        credentials: HTTP Authorization credentials from request (optional in dev mode)

    Returns:
        TokenData with user information

    Raises:
        HTTPException: If token is invalid or expired (production mode only)
    """
    # Development mode: bypass authentication if no credentials provided
    if settings.debug and credentials is None:
        logger.warning(
            "SECURITY: Development mode authentication bypass used. "
            "No authentication token provided - using mock development user."
        )
        return TokenData(
            user_id="dev-user-id",
            roles=["user", "admin"],
        )

    # Production mode or token provided: validate JWT
    if credentials is None:
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
        token = credentials.credentials
        secret_key = getattr(settings, "jwt_secret_key", "")
        if not secret_key:
            raise credentials_exception

        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        roles: list[str] = payload.get("roles", [])

        if user_id is None:
            raise credentials_exception

        return TokenData(user_id=user_id, roles=roles)
    except JWTError:
        raise credentials_exception


def require_role(required_role: str):
    """
    Dependency to check if user has required role.

    Args:
        required_role: Role name required for access

    Returns:
        Dependency function that validates user role
    """

    async def role_checker(
        current_user: Annotated[TokenData, Depends(get_current_user)]
    ) -> TokenData:
        if required_role not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required for this operation",
            )
        return current_user

    return role_checker


# Type alias for authenticated user dependency
CurrentUser = Annotated[TokenData, Depends(get_current_user)]
