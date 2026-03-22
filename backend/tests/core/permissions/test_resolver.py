"""Tests for permission resolution from user roles."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.role import RoleDB, UserRoleDB
from app.core.models.user import UserDB
from app.core.permissions.actions import Action
from app.core.permissions.resolver import get_user_roles, resolve_permissions


@pytest_asyncio.fixture
async def seeded_roles(db_session: AsyncSession) -> dict[str, RoleDB]:
    """Seed the roles table and return name->RoleDB mapping."""
    roles = {}
    for name in ("user", "manager", "admin"):
        role = RoleDB(name=name)
        db_session.add(role)
        roles[name] = role
    await db_session.flush()
    return roles


@pytest_asyncio.fixture
async def basic_user(db_session: AsyncSession, seeded_roles) -> UserDB:
    """Create a user with only the 'user' role."""
    user = UserDB(email="basic@test.com", first_name="Basic", last_name="User")
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRoleDB(user_id=user.id, role_id=seeded_roles["user"].id))
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def manager_user(db_session: AsyncSession, seeded_roles) -> UserDB:
    """Create a user with 'user' + 'manager' roles."""
    user = UserDB(email="manager@test.com", first_name="Manager", last_name="User")
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRoleDB(user_id=user.id, role_id=seeded_roles["user"].id))
    db_session.add(UserRoleDB(user_id=user.id, role_id=seeded_roles["manager"].id))
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, seeded_roles) -> UserDB:
    """Create a user with 'user' + 'admin' roles."""
    user = UserDB(email="admin@test.com", first_name="Admin", last_name="User")
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRoleDB(user_id=user.id, role_id=seeded_roles["user"].id))
    db_session.add(UserRoleDB(user_id=user.id, role_id=seeded_roles["admin"].id))
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_get_user_roles_basic(db_session, basic_user):
    roles = await get_user_roles(db_session, str(basic_user.id))
    assert roles == ["user"]


@pytest.mark.asyncio
async def test_get_user_roles_manager(db_session, manager_user):
    roles = await get_user_roles(db_session, str(manager_user.id))
    assert set(roles) == {"user", "manager"}


@pytest.mark.asyncio
async def test_resolve_permissions_basic_user(db_session, basic_user):
    roles, permissions = await resolve_permissions(db_session, str(basic_user.id))
    assert "user" in roles
    assert Action.SCORECARD_VIEW in permissions
    assert Action.TRACKER_VIEW in permissions
    assert Action.TRACKER_MANAGE not in permissions


@pytest.mark.asyncio
async def test_resolve_permissions_manager_union(db_session, manager_user):
    roles, permissions = await resolve_permissions(db_session, str(manager_user.id))
    assert set(roles) == {"user", "manager"}
    assert Action.SCORECARD_VIEW in permissions
    assert Action.TRACKER_MANAGE in permissions
    assert Action.TRACKER_MANAGE_ALL_REPORTS in permissions


@pytest.mark.asyncio
async def test_resolve_permissions_admin_wildcard(db_session, admin_user):
    roles, permissions = await resolve_permissions(db_session, str(admin_user.id))
    assert "admin" in roles
    assert Action.ALL in permissions
