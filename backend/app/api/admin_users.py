"""Admin user management API endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.core.auth import require_role
from app.models.user import User, UserDB, UserRole, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("/", response_model=list[User])
async def list_users(
    current_user: CurrentUser,
    db: DBSession,
) -> list[User]:
    """List all users (admin only)."""
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    result = await db.execute(select(UserDB).order_by(UserDB.created_at.desc()))
    users = result.scalars().all()
    return [User.model_validate(u) for u in users]


@router.patch("/{user_id}", response_model=User)
async def update_user(
    user_id: UUID,
    update: UserUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> User:
    """Update a user's role (admin only)."""
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if update.role is not None:
        user.role = update.role.value
        logger.info(f"User {user.email} role updated to {update.role.value} by {current_user.email}")

    await db.commit()
    await db.refresh(user)
    return User.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    """Delete a user (admin only). Cannot delete yourself."""
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Cannot delete yourself
    if str(user_id) == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )

    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    logger.info(f"User {user.email} deleted by {current_user.email}")
    await db.delete(user)
    await db.commit()
