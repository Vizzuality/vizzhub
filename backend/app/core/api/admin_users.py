"""Admin user management API endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Request, Response, status
from jose import JWTError
from jose import jwt as jose_jwt
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from app.config import get_settings
from app.core.api.deps import AdminUser, CurrentUser, DBSession, get_or_404
from app.core.auth import ALGORITHM, create_access_token, delete_auth_cookie, get_cookie_settings
from app.core.models.role import RoleDB, UserRoleDB
from app.core.models.user import User, UserDB, UserPublic, UserUpdate
from app.core.permissions.dependencies import is_admin
from app.core.permissions.resolver import get_user_roles, resolve_permissions
from app.modules.notifications.services.slack_service import SlackService
from app.utils.slack import get_slack_bot_token

logger = structlog.get_logger()

_USER_NOT_FOUND = "User not found"

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
    return [RoleResponse(id=r.id, name=r.name, description=r.description) for r in result.scalars()]


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

    user_ids = [u.id for u in users]
    roles_result = await db.execute(
        select(UserRoleDB.user_id, RoleDB.name)
        .join(RoleDB, RoleDB.id == UserRoleDB.role_id)
        .where(UserRoleDB.user_id.in_(user_ids))
    )
    roles_by_user: dict[str, list[str]] = {}
    for uid, role_name in roles_result.all():
        roles_by_user.setdefault(str(uid), []).append(role_name)

    user_responses = [User.model_validate(u) for u in users]
    for user_resp in user_responses:
        user_resp.roles = sorted(roles_by_user.get(str(user_resp.id), []))
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
                profile.get("display_name") or profile.get("real_name") or slack_user.get("name")
            )
            updated.append(user)

    await db.flush()
    logger.info(
        "slack_sync_all_completed", synced=len(updated), total=len(users), admin=current_user.email
    )
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
        payload = jose_jwt.decode(admin_token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        token_permissions = payload.get("permissions", [])
        if not is_admin(token_permissions):
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

    logger.info("impersonation_stopped", admin=admin.email, was=current_user.email)

    result = UserPublic.model_validate(admin)
    result.roles = payload.get("roles", [])
    result.permissions = payload.get("permissions", [])
    return result


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
    user = await get_or_404(db, UserDB, user_id, _USER_NOT_FOUND)
    user_resp = User.model_validate(user)
    user_resp.roles = await get_user_roles(db, str(user_resp.id))
    return user_resp


@router.put(
    "/{user_id}/roles",
    responses={
        400: {"description": "Missing required role or unknown roles"},
        404: {"description": "User not found"},
    },
)
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

    await get_or_404(db, UserDB, user_id, _USER_NOT_FOUND)

    await db.execute(sa_delete(UserRoleDB).where(UserRoleDB.user_id == user_id))
    for role_name in body.roles:
        db.add(UserRoleDB(user_id=user_id, role_id=found_roles[role_name].id))

    await db.flush()
    logger.info(
        "user_roles_assigned",
        user_id=str(user_id),
        roles=sorted(body.roles),
        admin=current_user.email,
    )

    return UserRolesResponse(user_id=user_id, roles=sorted(body.roles))


@router.post("/{user_id}/sync-slack")
async def sync_slack(
    user_id: UUID,
    current_user: AdminUser,
    db: DBSession,
) -> User:
    """Look up the user's Slack profile by email and store the Slack ID + display name."""
    user = await get_or_404(db, UserDB, user_id, _USER_NOT_FOUND)

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
    await db.flush()
    await db.refresh(user)

    logger.info("slack_sync_completed", email=user.email, display_name=user.slack_display_name)
    return User.model_validate(user)


@router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    update: UserUpdate,
    current_user: AdminUser,
    db: DBSession,
) -> User:
    """Update a user (admin only). Role assignment uses PUT /{user_id}/roles."""
    user = await get_or_404(db, UserDB, user_id, _USER_NOT_FOUND)

    if update.active is False and str(user_id) == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself",
        )

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    if "active" in update_data:
        logger.info(
            "user_active_changed", email=user.email, active=update.active, admin=current_user.email
        )

    await db.flush()
    await db.refresh(user)
    logger.info(
        "user_updated",
        user_id=str(user_id),
        fields=sorted(update_data.keys()),
        admin=current_user.email,
    )

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

    user = await get_or_404(db, UserDB, user_id, _USER_NOT_FOUND)

    logger.info("user_deleted", email=user.email, admin=current_user.email)
    await db.delete(user)


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

    target = await get_or_404(db, UserDB, user_id, _USER_NOT_FOUND)

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

    logger.info("impersonation_started", admin=current_user.email, target=target.email)
    result = UserPublic.model_validate(target)
    result.roles = target_roles
    result.permissions = target_permissions
    return result
