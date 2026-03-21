"""Admin user management API endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from jose import JWTError, jwt as jose_jwt
from sqlalchemy import select

from app.config import get_settings
from app.core.api.deps import AdminUser, CurrentUser, DBSession
from app.core.auth import ALGORITHM, create_access_token, delete_auth_cookie, get_cookie_settings
from app.core.models.user import User, UserDB, UserPublic, UserRole, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("")
async def list_users(
    current_user: AdminUser,
    db: DBSession,
) -> list[User]:
    """List all users (admin only)."""
    result = await db.execute(select(UserDB).order_by(UserDB.created_at.desc()))
    users = result.scalars().all()
    return [User.model_validate(u) for u in users]


@router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    update: UserUpdate,
    current_user: AdminUser,
    db: DBSession,
) -> User:
    """Update a user's role (admin only)."""
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
    current_user: AdminUser,
    db: DBSession,
) -> None:
    """Delete a user (admin only). Cannot delete yourself."""
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


@router.post("/stop-impersonate")
async def stop_impersonate(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: DBSession,
) -> UserPublic:
    """Stop impersonating and restore admin session."""
    admin_token = request.cookies.get("admin_token")
    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not currently impersonating",
        )

    settings = get_settings()
    try:
        payload = jose_jwt.decode(
            admin_token, settings.jwt_secret_key, algorithms=[ALGORITHM]
        )
        admin_role = payload.get("role")
        if admin_role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Stored token is not an admin",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid admin token",
        )

    cookie_settings = get_cookie_settings()
    response.set_cookie(value=admin_token, **cookie_settings)

    delete_auth_cookie(response, key="admin_token")

    admin_id = payload["sub"]
    result = await db.execute(select(UserDB).where(UserDB.id == admin_id))
    admin = result.scalar_one_or_none()

    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found",
        )

    logger.info(
        f"Admin {admin.email} stopped impersonating "
        f"(was {current_user.email})"
    )

    return UserPublic.model_validate(admin)


@router.post("/{user_id}/impersonate")
async def impersonate_user(
    user_id: UUID,
    response: Response,
    current_user: AdminUser,
    db: DBSession,
) -> UserPublic:
    """Start impersonating another user (admin only)."""
    if str(user_id) == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot impersonate yourself",
        )

    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    target = result.scalar_one_or_none()

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Save admin JWT in admin_token cookie
    admin_token = create_access_token(
        data={
            "sub": current_user.user_id,
            "email": current_user.email,
            "role": current_user.role,
        }
    )
    cookie_settings = get_cookie_settings()
    response.set_cookie(value=admin_token, **{**cookie_settings, "key": "admin_token"})

    # Issue new JWT for target user in access_token cookie
    target_token = create_access_token(
        data={
            "sub": str(target.id),
            "email": target.email,
            "role": target.role,
        }
    )
    response.set_cookie(value=target_token, **cookie_settings)

    logger.info(f"Admin {current_user.email} started impersonating {target.email}")
    return UserPublic.model_validate(target)
