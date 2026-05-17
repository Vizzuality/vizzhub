"""Resolve user permissions from their assigned roles."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.role import RoleDB, UserRoleDB
from app.core.permissions.roles import ROLE_PERMISSIONS


async def get_user_roles(db: AsyncSession, user_id: str) -> list[str]:
    """Get role names for a user from the user_roles join table."""
    result = await db.execute(
        select(RoleDB.name)
        .join(UserRoleDB, UserRoleDB.role_id == RoleDB.id)
        .where(UserRoleDB.user_id == user_id)
    )
    return [row[0] for row in result.all()]


async def resolve_permissions(db: AsyncSession, user_id: str) -> tuple[list[str], list[str]]:
    """Resolve a user's roles and effective permissions.

    Returns (roles, permissions) where permissions is the sorted union
    of all permissions from all assigned roles.
    """
    roles = await get_user_roles(db, user_id)
    permissions: set[str] = set()
    for role in roles:
        permissions |= ROLE_PERMISSIONS.get(role, set())
    return sorted(roles), sorted(permissions)
