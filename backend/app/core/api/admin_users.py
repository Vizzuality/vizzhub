"""Admin user management API endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from jose import JWTError, jwt as jose_jwt
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import delete as sa_delete, select

from app.config import get_settings
from app.core.api.deps import AdminUser, CurrentUser, DBSession
from app.core.auth import ALGORITHM, create_access_token, delete_auth_cookie, get_cookie_settings
from app.core.models.role import RoleDB, UserRoleDB
from app.core.models.user import User, UserDB, UserPublic, UserUpdate
from app.core.permissions.resolver import get_user_roles, resolve_permissions
from app.modules.scorecard.services.slack_service import SlackService
from app.utils.slack import get_slack_bot_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


# ---------------------------------------------------------------------------
# Pydantic models for role management
# ---------------------------------------------------------------------------

class RoleResponse(PydanticBaseModel):
    id: UUID
    name: str
    description: str | None


class RoleAssignment(PydanticBaseModel):
    roles: list[str]


class UserRolesResponse(PydanticBaseModel):
    user_id: UUID
    roles: list[str]


# ---------------------------------------------------------------------------
# Role management endpoints (must precede /{user_id} routes)
# ---------------------------------------------------------------------------

@router.get("/roles")
async def list_roles(
    current_user: AdminUser,
    db: DBSession,
) -> list[RoleResponse]:
    """List all available roles."""
    result = await db.execute(select(RoleDB).order_by(RoleDB.name))
    return [
        RoleResponse(id=r.id, name=r.name, description=r.description)
        for r in result.scalars()
    ]


# ---------------------------------------------------------------------------
# Static-path endpoints (before {user_id} catch-all)
# ---------------------------------------------------------------------------

@router.get("")
async def list_users(
    current_user: AdminUser,
    db: DBSession,
    include_inactive: bool = False,
) -> list[User]:
    """List all users (admin only). Excludes inactive by default."""
    query = select(UserDB)
    if not include_inactive:
        query = query.where(UserDB.active == True)  # noqa: E712
    result = await db.execute(query.order_by(UserDB.created_at.desc()))
    users = result.scalars().all()

    user_responses = [User.model_validate(u) for u in users]
    for user_resp in user_responses:
        user_resp.roles = await get_user_roles(db, str(user_resp.id))
    return user_responses


@router.post("/sync-slack-all")
async def sync_slack_all(
    current_user: AdminUser,
    db: DBSession,
) -> list[User]:
    """Sync Slack profiles for all active users."""
    bot_token = await get_slack_bot_token(db)
    if not bot_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack integration not configured",
        )

    result = await db.execute(
        select(UserDB).where(UserDB.active == True).order_by(UserDB.email)  # noqa: E712
    )
    users = result.scalars().all()
    updated = []

    for user in users:
        slack_user = await SlackService.lookup_user_by_email(bot_token, user.email)
        if slack_user:
            profile = slack_user.get("profile", {})
            user.slack_user_id = slack_user["id"]
            user.slack_display_name = (
                profile.get("display_name")
                or profile.get("real_name")
                or slack_user.get("name")
            )
            updated.append(user)

    await db.commit()
    logger.info(f"Synced Slack for {len(updated)}/{len(users)} users by {current_user.email}")
    return [User.model_validate(u) for u in updated]


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
        admin_permissions = payload.get("permissions", [])
        if "*" not in admin_permissions:
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

    admin_roles, admin_permissions = await resolve_permissions(db, str(admin.id))
    return UserPublic(
        id=admin.id,
        email=admin.email,
        name=admin.name,
        first_name=admin.first_name,
        last_name=admin.last_name,
        picture=admin.picture,
        roles=admin_roles,
        permissions=admin_permissions,
        active=admin.active,
    )


# ---------------------------------------------------------------------------
# Parameterized endpoints (/{user_id} pattern)
# ---------------------------------------------------------------------------

@router.get("/{user_id}")
async def get_user(
    user_id: UUID,
    current_user: AdminUser,
    db: DBSession,
) -> User:
    """Get a single user by ID (admin only)."""
    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user_resp = User.model_validate(user)
    user_resp.roles = await get_user_roles(db, str(user_resp.id))
    return user_resp


@router.put("/{user_id}/roles")
async def assign_roles(
    user_id: UUID,
    body: RoleAssignment,
    current_user: AdminUser,
    db: DBSession,
) -> UserRolesResponse:
    """Replace all roles for a user. 'user' role is always required."""
    if "user" not in body.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The 'user' role is required for all users",
        )

    result = await db.execute(select(RoleDB).where(RoleDB.name.in_(body.roles)))
    found_roles = {r.name: r for r in result.scalars()}
    missing = set(body.roles) - set(found_roles.keys())
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown roles: {', '.join(sorted(missing))}",
        )

    user_result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    await db.execute(
        sa_delete(UserRoleDB).where(UserRoleDB.user_id == user_id)
    )
    for role_name in body.roles:
        db.add(UserRoleDB(user_id=user_id, role_id=found_roles[role_name].id))

    await db.commit()

    return UserRolesResponse(user_id=user_id, roles=sorted(body.roles))


@router.post("/{user_id}/sync-slack")
async def sync_slack(
    user_id: UUID,
    current_user: AdminUser,
    db: DBSession,
) -> User:
    """Look up the user's Slack profile by email and store the Slack ID + display name."""
    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    bot_token = await get_slack_bot_token(db)
    if not bot_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack integration not configured",
        )

    slack_user = await SlackService.lookup_user_by_email(bot_token, user.email)
    if not slack_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Slack user found for {user.email}",
        )

    user.slack_user_id = slack_user["id"]
    user.slack_display_name = SlackService.extract_display_name(slack_user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"Synced Slack for {user.email}: {user.slack_display_name}")
    return User.model_validate(user)


@router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    update: UserUpdate,
    current_user: AdminUser,
    db: DBSession,
) -> User:
    """Update a user (admin only). Role assignment uses PUT /{user_id}/roles."""
    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if update.active is False and str(user_id) == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself",
        )

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    if "active" in update_data:
        logger.info(f"User {user.email} active={update.active} by {current_user.email}")

    await db.commit()
    await db.refresh(user)

    user_resp = User.model_validate(user)
    user_resp.roles = await get_user_roles(db, str(user_resp.id))
    return user_resp


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

    if not target.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot impersonate an inactive user",
        )

    admin_token = create_access_token(
        data={
            "sub": current_user.user_id,
            "email": current_user.email,
            "roles": current_user.roles,
            "permissions": current_user.permissions,
        }
    )
    cookie_settings = get_cookie_settings()
    response.set_cookie(value=admin_token, **{**cookie_settings, "key": "admin_token"})

    target_roles, target_permissions = await resolve_permissions(db, str(target.id))
    target_token = create_access_token(
        data={
            "sub": str(target.id),
            "email": target.email,
            "roles": target_roles,
            "permissions": target_permissions,
        }
    )
    response.set_cookie(value=target_token, **cookie_settings)

    logger.info(f"Admin {current_user.email} started impersonating {target.email}")
    return UserPublic(
        id=target.id,
        email=target.email,
        name=target.name,
        first_name=target.first_name,
        last_name=target.last_name,
        picture=target.picture,
        roles=target_roles,
        permissions=target_permissions,
        active=target.active,
    )
