"""FastAPI dependencies for permission-based access control."""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.auth import TokenData, get_current_user


def require_permission(*permissions: str):
    """Require the current user to have ALL listed permissions.

    Returns TokenData so it can replace CurrentUser in endpoint signatures.
    Admin users (with '*' permission) pass all checks.
    Uses Depends(get_current_user) so FastAPI resolves the JWT automatically.
    """

    async def checker(
        current_user: Annotated[TokenData, Depends(get_current_user)]
    ) -> TokenData:
        user_perms = set(current_user.permissions)
        if "*" in user_perms:
            return current_user
        for p in permissions:
            if p not in user_perms:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{p}' required",
                )
        return current_user

    return checker
