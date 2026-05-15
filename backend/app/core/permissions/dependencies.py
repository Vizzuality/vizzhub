"""FastAPI dependencies for permission-based access control."""

from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, status

from app.core.auth import TokenData, get_current_user
from app.core.permissions.actions import Action

logger = structlog.get_logger()


def is_admin(permissions: list[str] | set[str]) -> bool:
    """True when the principal holds the wildcard ``Action.ALL`` permission."""
    return Action.ALL in permissions


def require_permission(*permissions: str):
    """Require the current user to have ALL listed permissions.

    Returns TokenData so it can replace CurrentUser in endpoint signatures.
    Admin users (with ``Action.ALL``) pass every check.
    Uses Depends(get_current_user) so FastAPI resolves the JWT automatically.
    """

    def checker(
        current_user: Annotated[TokenData, Depends(get_current_user)]
    ) -> TokenData:
        user_perms = set(current_user.permissions)
        if not is_admin(user_perms):
            for p in permissions:
                if p not in user_perms:
                    logger.info(
                        "auth_permission_denied",
                        user_id=current_user.user_id,
                        email=current_user.email,
                        requested=p,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission '{p}' required",
                    )
        return current_user

    return checker
