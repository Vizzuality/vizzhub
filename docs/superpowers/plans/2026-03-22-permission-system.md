# Permission System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two-tier `user`/`admin` role system with a permission-based RBAC system supporting multiple roles per user, a new `manager` role, and granular permission checks on both backend and frontend.

**Architecture:** New `core/permissions/` module on both backend and frontend. Backend resolves permissions at login into the JWT. Frontend reads permissions from `/auth/me` and gates UI with `<Can>` component and `usePermission` hook. Database gets `roles` + `user_roles` tables; `users.role` column is dropped.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, PostgreSQL, React, TypeScript, React Router

**Spec:** `docs/superpowers/specs/2026-03-22-permission-system-design.md`

---

## File Structure

### New Files (Backend)

| File | Responsibility |
|------|---------------|
| `backend/app/core/permissions/__init__.py` | Public API: exports `Action`, `ROLE_PERMISSIONS`, `require_permission`, `resolve_permissions` |
| `backend/app/core/permissions/actions.py` | Permission string constants |
| `backend/app/core/permissions/roles.py` | Role-to-permission mapping dict |
| `backend/app/core/permissions/resolver.py` | `resolve_permissions(db, user_id)` and `get_user_roles(db, user_id)` |
| `backend/app/core/permissions/dependencies.py` | `require_permission(*permissions)` FastAPI dependency |
| `backend/app/core/models/role.py` | `RoleDB` and `UserRoleDB` SQLAlchemy models |
| `backend/alembic/versions/030_add_rbac_tables.py` | Migration: create tables, populate, drop `users.role` |
| `backend/tests/core/permissions/test_actions.py` | Tests for permission constants |
| `backend/tests/core/permissions/test_roles.py` | Tests for role mapping |
| `backend/tests/core/permissions/test_resolver.py` | Tests for permission resolution |
| `backend/tests/core/permissions/test_dependencies.py` | Tests for `require_permission` dependency |
| `backend/tests/core/api/test_role_management.py` | Tests for role assignment endpoints |

### New Files (Frontend)

| File | Responsibility |
|------|---------------|
| `frontend/src/core/permissions/constants.ts` | Permission string constants (mirrors backend `actions.py`) |
| `frontend/src/core/permissions/usePermission.ts` | `usePermission()` and `usePermissions()` hooks |
| `frontend/src/core/permissions/Can.tsx` | `<Can do={...}>` conditional rendering component |
| `frontend/src/core/permissions/PermissionRoute.tsx` | Route guard replacing `AdminRoute` |
| `frontend/src/core/permissions/index.ts` | Barrel export for the permissions module |

### Modified Files (Backend)

| File | Changes |
|------|---------|
| `backend/app/core/auth.py` | `TokenData`: add `permissions`, remove `role`. Remove `require_role`. Remove backward-compat bridge in `get_current_user`. |
| `backend/app/core/api/deps.py` | `AdminUser` redefined via `require_permission("*")`. Import from permissions module. |
| `backend/app/core/models/user.py` | Remove `UserRole` enum, `role` from `UserDB`/`UserBase`/`UserUpdate`/`UserPublic`. Add `roles`/`permissions` to `UserPublic`. |
| `backend/app/core/api/auth.py` | Login: resolve permissions, encode in JWT. `/auth/me`: return roles + permissions. First-user bootstrapping: insert into `user_roles`. |
| `backend/app/core/api/admin_users.py` | Impersonation: resolve permissions for target. Stop-impersonate: check permissions instead of role. Add role management endpoints. Update user PATCH to remove role field. |
| `backend/app/modules/tracker/api/invoices.py` | Replace `AdminUser` with `require_permission(Action.TRACKER_MANAGE)` |
| `backend/app/modules/tracker/api/admin_invoices.py` | Replace `AdminUser` with `require_permission(Action.TRACKER_MANAGE)` |
| `backend/app/modules/tracker/api/progress_reports.py` | Replace `AdminUser` with `require_permission(Action.TRACKER_MANAGE)` |
| `backend/app/modules/tracker/api/reporting_periods.py` | Replace `AdminUser`/`CurrentUser` with appropriate permissions |
| `backend/app/modules/tracker/api/budget_lines.py` | Replace `AdminUser` with `require_permission(Action.TRACKER_MANAGE)` |
| `backend/app/modules/tracker/api/non_staff_costs.py` | Replace `AdminUser`/`CurrentUser` with appropriate permissions |
| `backend/app/modules/tracker/api/reports.py` | Replace with appropriate tracker permissions |
| `backend/app/modules/tracker/api/report_parts.py` | Replace with appropriate tracker permissions |
| `backend/app/modules/tracker/api/postponements.py` | Replace `AdminUser` with `require_permission(Action.TRACKER_MANAGE)` |
| `backend/app/modules/tracker/api/project_costs.py` | Replace with appropriate tracker permissions |
| `backend/app/modules/scorecard/api/scores.py` | Replace with scorecard permissions |
| `backend/app/modules/scorecard/api/metrics.py` | Replace with scorecard permissions |
| `backend/app/modules/scorecard/api/capture.py` | Replace `AdminUser` with `require_permission(Action.SCORECARD_CAPTURE)` |
| `backend/app/modules/scorecard/api/config.py` | Replace `AdminUser` with `require_permission(Action.SCORECARD_MANAGE)` |
| `backend/app/modules/scorecard/api/collectors.py` | Replace with scorecard permissions |
| `backend/app/modules/scorecard/api/exports.py` | Replace with scorecard permissions |
| `backend/app/modules/scorecard/api/global_metrics.py` | Replace with scorecard permissions |
| `backend/app/modules/scorecard/api/integrations_admin.py` | Replace `AdminUser` with `require_permission(Action.ADMIN_INTEGRATIONS)` |
| `backend/app/modules/scorecard/api/notifications.py` | Replace with scorecard permissions |
| `backend/app/modules/scorecard/api/scheduled_jobs.py` | Replace with scorecard permissions |
| `backend/app/modules/scorecard/api/silences.py` | Replace with scorecard permissions |
| `backend/app/modules/scorecard/api/slack_admin.py` | Replace with admin permissions |
| `backend/app/modules/iso/api/config.py` | Replace with ISO permissions |
| `backend/app/modules/iso/api/exports.py` | Replace with ISO permissions |
| `backend/app/modules/iso/api/reviews.py` | Replace with ISO permissions |
| `backend/app/modules/iso/api/snapshots.py` | Replace with ISO permissions |
| `backend/app/core/api/projects_v2.py` | Replace with projects permissions |
| `backend/app/core/api/jobs.py` | Replace with admin permissions |
| `backend/app/core/api/oauth.py` | Replace with admin permissions |
| `backend/app/core/api/programs.py` | Replace with projects permissions |
| `backend/app/core/api/rates.py` | Replace with appropriate permissions |
| `backend/app/core/api/currencies.py` | Replace with appropriate permissions |
| `backend/app/core/api/functional_areas.py` | Replace with appropriate permissions |
| All test files with user fixtures | Update to use `user_roles` table instead of `role` column |

### Modified Files (Frontend)

| File | Changes |
|------|---------|
| `frontend/src/core/types/auth.ts` | Remove `UserRole`. Update `User`, `UserPublic`, `AuthState` with `roles`/`permissions`. |
| `frontend/src/core/contexts/AuthContext.tsx` | Add `permissions` to state. Populate from `/auth/me`. |
| `frontend/src/core/components/ProtectedRoute.tsx` | Remove `AdminRoute` (replaced by `PermissionRoute`). |
| `frontend/src/App.tsx` | Replace `AdminRoute` with `PermissionRoute`. |
| `frontend/src/core/components/layout/AppLayout.tsx:102` | Replace `role === 'admin'` with `usePermission`. |
| `frontend/src/core/components/layout/AppSidebar.tsx:178` | Replace `role === 'admin'` with `usePermission`. |
| `frontend/src/core/pages/Landing.tsx:171` | Replace `role === 'admin'` with `usePermission`. |
| `frontend/src/core/pages/Projects.tsx:54` | Replace `role === 'admin'` with `usePermission`. |
| `frontend/src/core/pages/UserDetail.tsx:188-203` | Replace role dropdown with multi-select checkboxes. |
| `frontend/src/modules/tracker/pages/ProjectTrackerDetail.tsx:319,326` | Wrap `InvoicesCard` and `ProgressCard` with `<Can>`. |
| `frontend/src/modules/scorecard/components/ProjectDetail/SnapshotManager.tsx:37` | Replace with `usePermission`. |
| `frontend/src/modules/scorecard/pages/GlobalDashboard/index.tsx:69` | Replace with `usePermission`. |
| `frontend/src/modules/iso/components/GitHubDataTabs.tsx:77` | **DO NOT MODIFY** — `m.role` is a GitHub org member role from snapshot data, not a user permission check. |

---

## Tasks

### Task 1: Backend Permission Module — Constants and Role Mapping

**Files:**
- Create: `backend/app/core/permissions/__init__.py`
- Create: `backend/app/core/permissions/actions.py`
- Create: `backend/app/core/permissions/roles.py`
- Create: `backend/tests/core/permissions/__init__.py`
- Create: `backend/tests/core/permissions/test_actions.py`
- Create: `backend/tests/core/permissions/test_roles.py`

- [ ] **Step 1: Create `actions.py` with permission constants**

```python
# backend/app/core/permissions/actions.py
"""Permission action constants for RBAC."""


class Action:
    """Permission string constants. Format: 'module:action'."""

    SCORECARD_VIEW = "scorecard:view"
    SCORECARD_EDIT_METRICS = "scorecard:edit_metrics"
    SCORECARD_CAPTURE = "scorecard:capture"
    SCORECARD_MANAGE = "scorecard:manage"

    TRACKER_VIEW = "tracker:view"
    TRACKER_MANAGE_OWN_REPORTS = "tracker:manage_own_reports"
    TRACKER_MANAGE_ALL_REPORTS = "tracker:manage_all_reports"
    TRACKER_MANAGE = "tracker:manage"

    ISO_VIEW = "iso:view"
    ISO_MANAGE = "iso:manage"

    PROJECTS_VIEW = "projects:view"
    PROJECTS_MANAGE = "projects:manage"

    ADMIN_USERS = "admin:users"
    ADMIN_JOBS = "admin:jobs"
    ADMIN_INTEGRATIONS = "admin:integrations"

    ALL = "*"
```

- [ ] **Step 2: Create `roles.py` with role-permission mapping**

```python
# backend/app/core/permissions/roles.py
"""Role-to-permission mapping. Roles are defined in code; assignment is runtime."""

from app.core.permissions.actions import Action

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "user": {
        Action.SCORECARD_VIEW,
        Action.SCORECARD_EDIT_METRICS,
        Action.TRACKER_VIEW,
        Action.TRACKER_MANAGE_OWN_REPORTS,
        Action.PROJECTS_VIEW,
    },
    "manager": {
        Action.TRACKER_VIEW,
        Action.TRACKER_MANAGE,
        Action.TRACKER_MANAGE_ALL_REPORTS,
        Action.TRACKER_MANAGE_OWN_REPORTS,
    },
    "admin": {
        Action.ALL,
    },
}
```

- [ ] **Step 3: Create `__init__.py` with public API**

```python
# backend/app/core/permissions/__init__.py
"""Permission system public API."""

from app.core.permissions.actions import Action
from app.core.permissions.roles import ROLE_PERMISSIONS

__all__ = ["Action", "ROLE_PERMISSIONS"]
```

- [ ] **Step 4: Write tests for actions and roles**

```python
# backend/tests/core/permissions/test_actions.py
"""Tests for permission action constants."""

from app.core.permissions.actions import Action


def test_action_strings_follow_module_action_format():
    for attr in dir(Action):
        if attr.startswith("_") or attr == "ALL":
            continue
        value = getattr(Action, attr)
        assert ":" in value, f"Action.{attr} = '{value}' missing ':' separator"


def test_no_duplicate_action_values():
    values = [
        getattr(Action, attr)
        for attr in dir(Action)
        if not attr.startswith("_")
    ]
    assert len(values) == len(set(values)), "Duplicate action values found"
```

```python
# backend/tests/core/permissions/test_roles.py
"""Tests for role-permission mapping."""

from app.core.permissions.actions import Action
from app.core.permissions.roles import ROLE_PERMISSIONS


def test_required_roles_exist():
    assert "user" in ROLE_PERMISSIONS
    assert "manager" in ROLE_PERMISSIONS
    assert "admin" in ROLE_PERMISSIONS


def test_admin_has_wildcard():
    assert Action.ALL in ROLE_PERMISSIONS["admin"]


def test_user_has_base_permissions():
    user_perms = ROLE_PERMISSIONS["user"]
    assert Action.SCORECARD_VIEW in user_perms
    assert Action.PROJECTS_VIEW in user_perms
    assert Action.TRACKER_VIEW in user_perms
    assert Action.TRACKER_MANAGE_OWN_REPORTS in user_perms


def test_user_cannot_manage_tracker():
    user_perms = ROLE_PERMISSIONS["user"]
    assert Action.TRACKER_MANAGE not in user_perms
    assert Action.TRACKER_MANAGE_ALL_REPORTS not in user_perms


def test_manager_has_tracker_management():
    manager_perms = ROLE_PERMISSIONS["manager"]
    assert Action.TRACKER_MANAGE in manager_perms
    assert Action.TRACKER_MANAGE_ALL_REPORTS in manager_perms
    assert Action.TRACKER_MANAGE_OWN_REPORTS in manager_perms


def test_all_permission_values_are_valid_actions():
    valid_actions = {
        getattr(Action, attr)
        for attr in dir(Action)
        if not attr.startswith("_")
    }
    for role, perms in ROLE_PERMISSIONS.items():
        for perm in perms:
            assert perm in valid_actions, f"Role '{role}' has unknown permission '{perm}'"
```

- [ ] **Step 5: Run tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/core/permissions/ -v && popd > /dev/null`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/permissions/ backend/tests/core/permissions/
git commit -m "feat(permissions): add Action constants and role-permission mapping"
```

---

### Task 2: Database Models and Schema Changes

**Files:**
- Create: `backend/app/core/models/role.py`
- Modify: `backend/app/core/models/user.py` (remove `UserRole` enum, `role` column, update schemas)

**Important:** The Alembic migration is deferred to Task 2b (after all code that references `users.role` is updated). This prevents the DB and code from being out of sync.

- [ ] **Step 1: Create SQLAlchemy models for roles**

```python
# backend/app/core/models/role.py
"""Role and user-role assignment models."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class RoleDB(Base):
    """Available roles."""

    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class UserRoleDB(Base):
    """Many-to-many assignment of roles to users."""

    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 2: Update `user.py` — remove `UserRole` enum and `role` column**

Remove from `backend/app/core/models/user.py`:
- Delete `UserRole` enum (lines 17-21)
- Delete `role` column from `UserDB` (line 37)
- Update `UserBase`: remove `role` field, add `roles: list[str] = ["user"]`
- Update `UserUpdate`: remove `role` field
- Update `UserPublic`: replace `role: UserRole` with `roles: list[str]` and `permissions: list[str] = []`

The resulting `UserPublic` should be:
```python
class UserPublic(BaseModel):
    """Public user info (for JWT responses)."""

    id: UUID
    email: str
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    picture: str | None = None
    roles: list[str] = []
    permissions: list[str] = []
    active: bool = True

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Commit models and schema changes (migration deferred to Task 2b)**

```bash
git add backend/app/core/models/role.py backend/app/core/models/user.py
git commit -m "feat(permissions): add RoleDB/UserRoleDB models, update User schemas (remove UserRole enum)"
```

**Note:** The `User` response schema (used by admin list/detail endpoints) no longer has a `role` field. Since `roles` cannot be derived from `model_validate(user)` alone (they live in a join table), endpoints that return user data must query roles separately. This is handled in Task 5 (login/me) and Task 7 (admin user list/detail).

---

### Task 3: Permission Resolver

**Files:**
- Create: `backend/app/core/permissions/resolver.py`
- Modify: `backend/app/core/permissions/__init__.py`
- Create: `backend/tests/core/permissions/test_resolver.py`

- [ ] **Step 1: Write failing test for `resolve_permissions`**

```python
# backend/tests/core/permissions/test_resolver.py
"""Tests for permission resolution from user roles."""

import pytest
import pytest_asyncio
from uuid import uuid4

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
    # Union: gets user perms + manager perms
    assert Action.SCORECARD_VIEW in permissions  # from user
    assert Action.TRACKER_MANAGE in permissions  # from manager
    assert Action.TRACKER_MANAGE_ALL_REPORTS in permissions  # from manager


@pytest.mark.asyncio
async def test_resolve_permissions_admin_wildcard(db_session, admin_user):
    roles, permissions = await resolve_permissions(db_session, str(admin_user.id))
    assert "admin" in roles
    assert Action.ALL in permissions
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/core/permissions/test_resolver.py -v && popd > /dev/null`
Expected: FAIL — `resolver` module does not exist yet.

- [ ] **Step 3: Implement `resolver.py`**

```python
# backend/app/core/permissions/resolver.py
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


async def resolve_permissions(
    db: AsyncSession, user_id: str
) -> tuple[list[str], list[str]]:
    """Resolve a user's roles and effective permissions.

    Returns (roles, permissions) where permissions is the sorted union
    of all permissions from all assigned roles.
    """
    roles = await get_user_roles(db, user_id)
    permissions: set[str] = set()
    for role in roles:
        permissions |= ROLE_PERMISSIONS.get(role, set())
    return sorted(roles), sorted(permissions)
```

- [ ] **Step 4: Update `__init__.py`**

Add `resolve_permissions` and `get_user_roles` to the public API exports.

- [ ] **Step 5: Run tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/core/permissions/test_resolver.py -v && popd > /dev/null`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/permissions/resolver.py backend/app/core/permissions/__init__.py backend/tests/core/permissions/test_resolver.py
git commit -m "feat(permissions): add permission resolver (roles -> permissions)"
```

---

### Task 4: Permission Dependency for FastAPI

**Files:**
- Create: `backend/app/core/permissions/dependencies.py`
- Modify: `backend/app/core/permissions/__init__.py`
- Create: `backend/tests/core/permissions/test_dependencies.py`

- [ ] **Step 1: Write failing test for `require_permission`**

```python
# backend/tests/core/permissions/test_dependencies.py
"""Tests for require_permission FastAPI dependency."""

import pytest
from fastapi import HTTPException

from app.core.auth import TokenData
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission


@pytest.mark.asyncio
async def test_admin_wildcard_passes_any_permission():
    user = TokenData(user_id="1", permissions=["*"])
    checker = require_permission(Action.ADMIN_USERS)
    result = await checker(user)
    assert result.user_id == "1"


@pytest.mark.asyncio
async def test_user_with_permission_passes():
    user = TokenData(user_id="1", permissions=["scorecard:view", "tracker:view"])
    checker = require_permission(Action.SCORECARD_VIEW)
    result = await checker(user)
    assert result.user_id == "1"


@pytest.mark.asyncio
async def test_user_without_permission_raises_403():
    user = TokenData(user_id="1", permissions=["scorecard:view"])
    checker = require_permission(Action.TRACKER_MANAGE)
    with pytest.raises(HTTPException) as exc_info:
        await checker(user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_multiple_permissions_all_required():
    user = TokenData(user_id="1", permissions=["scorecard:view"])
    checker = require_permission(Action.SCORECARD_VIEW, Action.TRACKER_VIEW)
    with pytest.raises(HTTPException) as exc_info:
        await checker(user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_multiple_permissions_all_present_passes():
    user = TokenData(
        user_id="1",
        permissions=["scorecard:view", "tracker:view", "projects:view"],
    )
    checker = require_permission(Action.SCORECARD_VIEW, Action.TRACKER_VIEW)
    result = await checker(user)
    assert result.user_id == "1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/core/permissions/test_dependencies.py -v && popd > /dev/null`
Expected: FAIL — `dependencies` module does not exist yet.

- [ ] **Step 3: Implement `dependencies.py`**

```python
# backend/app/core/permissions/dependencies.py
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
```

**Note:** The `checker` function uses `Depends(get_current_user)` so FastAPI resolves the JWT automatically when the dependency is used in an endpoint. Unit tests pass `TokenData` directly; integration tests go through the full dependency chain.

- [ ] **Step 4: Update `__init__.py`**

Add `require_permission` to exports.

- [ ] **Step 5: Run tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/core/permissions/test_dependencies.py -v && popd > /dev/null`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/permissions/dependencies.py backend/app/core/permissions/__init__.py backend/tests/core/permissions/test_dependencies.py
git commit -m "feat(permissions): add require_permission FastAPI dependency"
```

---

### Task 5: Update Auth Core — TokenData, Login, /auth/me

**Files:**
- Modify: `backend/app/core/auth.py:48-56,90-151,154-176`
- Modify: `backend/app/core/api/auth.py:37-41,43-148,151-173`
- Modify: `backend/app/core/api/deps.py:12-25`

- [ ] **Step 1: Update `TokenData` in `auth.py`**

In `backend/app/core/auth.py`:
- Add `permissions: list[str] = []` to `TokenData` (keep `roles`)
- Remove `role: str | None = None` field
- Remove the backward-compat bridge in `get_current_user` (lines 145-147: `if role and role not in roles`)
- Update `get_current_user` to read `permissions` from JWT payload
- Remove `require_role` function entirely (lines 154-176)

Updated `TokenData`:
```python
class TokenData(BaseModel):
    """Token payload data."""

    user_id: str
    email: str | None = None
    roles: list[str] = []
    permissions: list[str] = []
    exp: datetime | None = None
```

Updated `get_current_user` payload extraction:
```python
        roles: list[str] = payload.get("roles", [])
        permissions: list[str] = payload.get("permissions", [])

        return TokenData(
            user_id=user_id, email=email, roles=roles, permissions=permissions
        )
```

- [ ] **Step 2: Update `deps.py`**

In `backend/app/core/api/deps.py`:
- Remove import of `require_role`
- Import `require_permission` from `app.core.permissions`
- Redefine `AdminUser`:

```python
from app.core.permissions import require_permission

AdminUser = Annotated[TokenData, Depends(require_permission("*"))]
```

- [ ] **Step 3: Update login endpoint in `core/api/auth.py`**

In `backend/app/core/api/auth.py`:

Update imports — add `resolve_permissions` and role models:
```python
from app.core.permissions.resolver import resolve_permissions, get_user_roles
from app.core.models.role import RoleDB, UserRoleDB
```

Remove import of `UserRole`.

Update `MeResponse` (line 37-40):
```python
class MeResponse(BaseModel):
    """Response for /auth/me with roles, permissions, and impersonation status."""

    id: UUID
    email: str
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    picture: str | None = None
    roles: list[str] = []
    permissions: list[str] = []
    active: bool = True
    is_impersonating: bool = False
    functional_area_id: UUID | None = None
    rate_id: UUID | None = None
    dedication: Decimal | None = None
    slack_user_id: str | None = None
    slack_display_name: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

Update first-user creation (lines 84-98) — replace `role` assignment with `user_roles` insertion:
```python
        if user is None:
            # Create user (no role column anymore)
            user = UserDB(
                email=email,
                first_name=idinfo.get("given_name"),
                last_name=idinfo.get("family_name"),
                picture=idinfo.get("picture"),
                last_login_at=datetime.now(timezone.utc),
            )
            # ... Slack auto-link (unchanged) ...
            db.add(user)
            await db.flush()

            # Assign roles
            user_role = await db.execute(
                select(RoleDB).where(RoleDB.name == "user")
            )
            user_role_obj = user_role.scalar_one()
            db.add(UserRoleDB(user_id=user.id, role_id=user_role_obj.id))

            if settings.initial_admin_email and email == settings.initial_admin_email.lower():
                admin_role = await db.execute(
                    select(RoleDB).where(RoleDB.name == "admin")
                )
                admin_role_obj = admin_role.scalar_one()
                db.add(UserRoleDB(user_id=user.id, role_id=admin_role_obj.id))
                logger.info(f"Creating initial admin user: {email}")

            await db.commit()
            await db.refresh(user)
```

Update JWT creation (lines 128-135) — resolve permissions and encode:
```python
        roles, permissions = await resolve_permissions(db, str(user.id))
        token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "roles": roles,
                "permissions": permissions,
            }
        )
```

Update `/auth/me` endpoint (lines 151-173) — return roles and permissions from token:
```python
@router.get("/me")
async def get_current_user_info(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
) -> MeResponse:
    """Get the current authenticated user's information."""
    result = await db.execute(
        select(UserDB).where(UserDB.id == current_user.user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        first_name=user.first_name,
        last_name=user.last_name,
        picture=user.picture,
        roles=current_user.roles,
        permissions=current_user.permissions,
        active=user.active,
        is_impersonating=request.cookies.get("admin_token") is not None,
        functional_area_id=user.functional_area_id,
        rate_id=user.rate_id,
        dedication=user.dedication,
        slack_user_id=user.slack_user_id,
        slack_display_name=user.slack_display_name,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
```

Update `UserPublic` usage in `AuthLoginResponse` — since `UserPublic` no longer has a `role` field, and `roles`/`permissions` need to be populated, update the login response:
```python
        roles, permissions = await resolve_permissions(db, str(user.id))

        user_public = UserPublic(
            id=user.id,
            email=user.email,
            name=user.name,
            first_name=user.first_name,
            last_name=user.last_name,
            picture=user.picture,
            roles=roles,
            permissions=permissions,
            active=user.active,
        )

        return AuthLoginResponse(user=user_public)
```

- [ ] **Step 4: Run existing auth tests to check for regressions**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/test_auth.py tests/core/api/test_admin_users.py -v 2>&1 | head -80 && popd > /dev/null`
Expected: Some tests will fail due to `role` column removal — these will be fixed in Task 7. Check that the module imports work.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/auth.py backend/app/core/api/auth.py backend/app/core/api/deps.py
git commit -m "feat(permissions): update auth core — TokenData, login, /auth/me with permissions"
```

---

### Task 6: Update Impersonation Endpoints

**Files:**
- Modify: `backend/app/core/api/admin_users.py:197-249,252-303`

- [ ] **Step 1: Update `impersonate_user` endpoint**

In `backend/app/core/api/admin_users.py`, update the `impersonate_user` function (line 252+):

Replace the admin token creation (lines 282-288) to include roles and permissions:
```python
    admin_token = create_access_token(
        data={
            "sub": current_user.user_id,
            "email": current_user.email,
            "roles": current_user.roles,
            "permissions": current_user.permissions,
        }
    )
```

Replace the target token creation (lines 293-299) to resolve target's permissions:
```python
    target_roles, target_permissions = await resolve_permissions(db, str(target.id))
    target_token = create_access_token(
        data={
            "sub": str(target.id),
            "email": target.email,
            "roles": target_roles,
            "permissions": target_permissions,
        }
    )
```

Update the return to include roles/permissions:
```python
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
```

Add import:
```python
from app.core.permissions.resolver import resolve_permissions
```

- [ ] **Step 2: Update `stop_impersonate` endpoint**

In `stop_impersonate` (line 197+), update the admin token validation (lines 217-218):

Replace the role check:
```python
        # Before:
        admin_role = payload.get("role")
        if admin_role != UserRole.ADMIN.value:

        # After:
        admin_permissions = payload.get("permissions", [])
        if "*" not in admin_permissions:
```

Remove `UserRole` import if no longer used in this file.

Update the return to include roles/permissions for the admin:
```python
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
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/api/admin_users.py
git commit -m "feat(permissions): update impersonation to use roles/permissions in JWT"
```

---

### Task 7: Add Role Management Endpoints + Update Admin User Responses

**Files:**
- Modify: `backend/app/core/api/admin_users.py`
- Create: `backend/tests/core/api/test_role_management.py`

**Important:** Since `User.role` is gone, the admin user list/detail endpoints must now populate `roles` from the `user_roles` join table. For list endpoints, batch-query roles for all returned users. For detail endpoints, query roles for the single user. The `User` response schema should include `roles: list[str]` (inherited from `UserBase`). Example for list:

```python
from app.core.permissions.resolver import get_user_roles

# After fetching users, populate roles:
for user_response in users:
    user_response.roles = await get_user_roles(db, str(user_response.id))
```

For efficiency on the list endpoint, consider a single query that joins `users` -> `user_roles` -> `roles` and groups by user.

- [ ] **Step 1: Write failing tests for role management**

```python
# backend/tests/core/api/test_role_management.py
"""Tests for role listing and assignment endpoints."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.role import RoleDB, UserRoleDB
from app.core.models.user import UserDB


@pytest_asyncio.fixture
async def seeded_roles(db_session: AsyncSession) -> dict[str, RoleDB]:
    roles = {}
    for name, desc in [
        ("user", "Default"),
        ("manager", "Tracker management"),
        ("admin", "Full access"),
    ]:
        role = RoleDB(name=name, description=desc)
        db_session.add(role)
        roles[name] = role
    await db_session.flush()
    return roles


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, seeded_roles) -> UserDB:
    user = UserDB(id="00000000-0000-0000-0000-000000000001", email="admin@test.com", active=True)
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRoleDB(user_id=user.id, role_id=seeded_roles["user"].id))
    db_session.add(UserRoleDB(user_id=user.id, role_id=seeded_roles["admin"].id))
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def basic_user(db_session: AsyncSession, seeded_roles) -> UserDB:
    user = UserDB(id="00000000-0000-0000-0000-000000000010", email="basic@test.com", active=True)
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRoleDB(user_id=user.id, role_id=seeded_roles["user"].id))
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_list_roles(client, admin_user, seeded_roles):
    resp = await client.get("/api/admin/users/roles")
    assert resp.status_code == 200
    data = resp.json()
    names = {r["name"] for r in data}
    assert names == {"user", "manager", "admin"}


@pytest.mark.asyncio
async def test_assign_roles(client, admin_user, basic_user, seeded_roles):
    resp = await client.put(
        f"/api/admin/users/{basic_user.id}/roles",
        json={"roles": ["user", "manager"]},
    )
    assert resp.status_code == 200
    assert set(resp.json()["roles"]) == {"user", "manager"}


@pytest.mark.asyncio
async def test_assign_roles_requires_user_role(client, admin_user, basic_user, seeded_roles):
    resp = await client.put(
        f"/api/admin/users/{basic_user.id}/roles",
        json={"roles": ["manager"]},
    )
    assert resp.status_code == 400
    assert "user" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_assign_roles_invalid_role(client, admin_user, basic_user, seeded_roles):
    resp = await client.put(
        f"/api/admin/users/{basic_user.id}/roles",
        json={"roles": ["user", "nonexistent"]},
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Implement role management endpoints**

Add to `backend/app/core/api/admin_users.py`:

```python
from pydantic import BaseModel as PydanticBaseModel

class RoleResponse(PydanticBaseModel):
    id: UUID
    name: str
    description: str | None

class RoleAssignment(PydanticBaseModel):
    roles: list[str]

class UserRolesResponse(PydanticBaseModel):
    user_id: UUID
    roles: list[str]


@router.get("/roles")
async def list_roles(
    current_user: AdminUser,
    db: DBSession,
) -> list[RoleResponse]:
    """List all available roles."""
    result = await db.execute(select(RoleDB).order_by(RoleDB.name))
    return [RoleResponse(id=r.id, name=r.name, description=r.description) for r in result.scalars()]


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

    # Validate all role names exist
    result = await db.execute(select(RoleDB).where(RoleDB.name.in_(body.roles)))
    found_roles = {r.name: r for r in result.scalars()}
    missing = set(body.roles) - set(found_roles.keys())
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown roles: {', '.join(missing)}",
        )

    # Verify target user exists
    user_result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Delete existing roles and insert new ones
    await db.execute(
        sa_delete(UserRoleDB).where(UserRoleDB.user_id == user_id)
    )
    for role_name in body.roles:
        db.add(UserRoleDB(user_id=user_id, role_id=found_roles[role_name].id))

    await db.commit()

    return UserRolesResponse(user_id=user_id, roles=sorted(body.roles))
```

Add import: `from sqlalchemy import delete as sa_delete`
Add import: `from app.core.models.role import RoleDB, UserRoleDB`

- [ ] **Step 3: Run tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest tests/core/api/test_role_management.py -v && popd > /dev/null`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/api/admin_users.py backend/tests/core/api/test_role_management.py
git commit -m "feat(permissions): add role listing and assignment endpoints"
```

---

### Task 8: Migrate All Backend Endpoints to Permission Checks

**Files:** All 36 backend API files that import `AdminUser` or `CurrentUser`.

This is the largest task. The pattern is mechanical: replace `AdminUser` with `Depends(require_permission(Action.X))` and replace `CurrentUser` where finer-grained permissions are needed.

- [ ] **Step 1: Update imports in all API files**

Every file that imports from `app.core.api.deps` needs `require_permission` and `Action`:
```python
from app.core.permissions import Action, require_permission
```

- [ ] **Step 2: Migrate core API files**

**`core/api/projects_v2.py`:**
- GET endpoints (list, detail): keep `CurrentUser` (any authenticated user has `PROJECTS_VIEW`)
- POST, PUT, PATCH, DELETE: `Annotated[TokenData, Depends(require_permission(Action.PROJECTS_MANAGE))]`

**`core/api/jobs.py`:**
- All endpoints: `Annotated[TokenData, Depends(require_permission(Action.ADMIN_JOBS))]`

**`core/api/oauth.py`:**
- All endpoints: `Annotated[TokenData, Depends(require_permission(Action.ADMIN_INTEGRATIONS))]`

**`core/api/admin_users.py`:**
- All endpoints except stop-impersonate: `Annotated[TokenData, Depends(require_permission(Action.ADMIN_USERS))]`
- stop-impersonate: keep `CurrentUser` (impersonated user session)

**`core/api/rates.py`, `core/api/currencies.py`, `core/api/functional_areas.py`:**
- GET endpoints: keep `CurrentUser` (reference data, read by all)
- Write endpoints (if any): `require_permission(Action.ADMIN_USERS)`

**`core/api/programs.py`:**
- GET: keep `CurrentUser`
- Write: `require_permission(Action.PROJECTS_MANAGE)`

- [ ] **Step 3: Migrate scorecard API files**

**`scorecard/api/scores.py`:**
- GET: keep `CurrentUser` (maps to `SCORECARD_VIEW`)

**`scorecard/api/metrics.py`:**
- GET: keep `CurrentUser`
- PUT/PATCH (manual metric edits): `require_permission(Action.SCORECARD_EDIT_METRICS)`
- Admin config operations: `require_permission(Action.SCORECARD_MANAGE)`

**`scorecard/api/capture.py`:**
- All: `require_permission(Action.SCORECARD_CAPTURE)`

**`scorecard/api/config.py`:**
- All: `require_permission(Action.SCORECARD_MANAGE)`

**`scorecard/api/collectors.py`:**
- All: `require_permission(Action.SCORECARD_MANAGE)`

**`scorecard/api/exports.py`:**
- All: `require_permission(Action.SCORECARD_MANAGE)`

**`scorecard/api/global_metrics.py`:**
- GET: keep `CurrentUser`
- Write: `require_permission(Action.SCORECARD_MANAGE)`

**`scorecard/api/integrations_admin.py`:**
- All: `require_permission(Action.ADMIN_INTEGRATIONS)`

**`scorecard/api/notifications.py`:**
- All: `require_permission(Action.SCORECARD_MANAGE)`

**`scorecard/api/scheduled_jobs.py`:**
- All: `require_permission(Action.ADMIN_JOBS)`

**`scorecard/api/silences.py`:**
- GET: keep `CurrentUser`
- Write: `require_permission(Action.SCORECARD_MANAGE)`

**`scorecard/api/slack_admin.py`:**
- All: `require_permission(Action.SCORECARD_MANAGE)`

- [ ] **Step 4: Migrate tracker API files**

**`tracker/api/reports.py`:**
- GET own report: keep `CurrentUser` (maps to `TRACKER_MANAGE_OWN_REPORTS`)
- POST/PATCH own report: `require_permission(Action.TRACKER_MANAGE_OWN_REPORTS)`
- GET all reports: `require_permission(Action.TRACKER_MANAGE_ALL_REPORTS)`

**`tracker/api/report_parts.py`:**
- Read: keep `CurrentUser`
- Write own: `require_permission(Action.TRACKER_MANAGE_OWN_REPORTS)`
- Write any: `require_permission(Action.TRACKER_MANAGE_ALL_REPORTS)`

**`tracker/api/invoices.py`:**
- All: `require_permission(Action.TRACKER_MANAGE)`

**`tracker/api/admin_invoices.py`:**
- All: `require_permission(Action.TRACKER_MANAGE)`

**`tracker/api/progress_reports.py`:**
- All: `require_permission(Action.TRACKER_MANAGE)`

**`tracker/api/reporting_periods.py`:**
- GET: keep `CurrentUser` (maps to `TRACKER_VIEW`)
- Write: `require_permission(Action.TRACKER_MANAGE)`

**`tracker/api/budget_lines.py`:**
- All: `require_permission(Action.TRACKER_MANAGE)`

**`tracker/api/non_staff_costs.py`:**
- Read: keep `CurrentUser`
- Write: `require_permission(Action.TRACKER_MANAGE)`

**`tracker/api/postponements.py`:**
- All: `require_permission(Action.TRACKER_MANAGE)`

**`tracker/api/project_costs.py`:**
- GET: keep `CurrentUser` (maps to `TRACKER_VIEW`)

- [ ] **Step 5: Migrate ISO API files**

**`iso/api/config.py`:**
- All: `require_permission(Action.ISO_MANAGE)`

**`iso/api/exports.py`:**
- All: `require_permission(Action.ISO_MANAGE)`

**`iso/api/reviews.py`:**
- GET: `require_permission(Action.ISO_VIEW)`
- Write: `require_permission(Action.ISO_MANAGE)`

**`iso/api/snapshots.py`:**
- GET: `require_permission(Action.ISO_VIEW)`
- Write: `require_permission(Action.ISO_MANAGE)`

- [ ] **Step 6: Run full backend test suite**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest --tb=short -q 2>&1 | tail -20 && popd > /dev/null`
Expected: Many tests will fail due to fixture changes needed (Task 9). Note the failures.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/api/ backend/app/modules/
git commit -m "feat(permissions): migrate all endpoints to require_permission"
```

---

### Task 8b: Alembic Migration (Deferred from Task 2)

**Files:**
- Create: `backend/alembic/versions/030_add_rbac_tables.py`

**Why deferred:** The migration drops `users.role`, so all code that references `UserDB.role`, `UserRole`, or `require_role` must be updated first (Tasks 2-8). Now it is safe to run the migration.

- [ ] **Step 1: Create Alembic migration**

```python
# backend/alembic/versions/030_add_rbac_tables.py
"""Add RBAC tables (roles, user_roles) and drop users.role.

Revision ID: 030
Revises: 029
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create roles table
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # 2. Seed roles via raw SQL (gen_random_uuid() cannot be used in bulk_insert)
    op.execute("""
        INSERT INTO roles (id, name, description) VALUES
        (gen_random_uuid(), 'user', 'Default role for all users'),
        (gen_random_uuid(), 'manager', 'Tracker management (invoices, progress, periods, budgets)'),
        (gen_random_uuid(), 'admin', 'Full system access')
    """)

    # 3. Create user_roles table
    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    # 4. Populate user_roles from users.role
    # Every user gets the 'user' role
    op.execute("""
        INSERT INTO user_roles (user_id, role_id)
        SELECT u.id, r.id
        FROM users u
        CROSS JOIN roles r
        WHERE r.name = 'user'
    """)
    # Users with role='admin' also get the 'admin' role
    op.execute("""
        INSERT INTO user_roles (user_id, role_id)
        SELECT u.id, r.id
        FROM users u
        CROSS JOIN roles r
        WHERE u.role = 'admin' AND r.name = 'admin'
    """)

    # 5. Drop users.role column
    op.drop_column("users", "role")


def downgrade() -> None:
    # Restore users.role column
    op.add_column("users", sa.Column("role", sa.String(50), nullable=False, server_default="user"))

    # Populate from user_roles
    op.execute("""
        UPDATE users u SET role = 'admin'
        WHERE EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = u.id AND r.name = 'admin'
        )
    """)

    op.drop_table("user_roles")
    op.drop_table("roles")
```

**Note on revision IDs:** Verify the exact `down_revision` string matches the previous migration file. The existing migration uses `revision = "029"` and `down_revision = "028"`. If the format differs (e.g., full hash), adjust `revision`/`down_revision` to match.

- [ ] **Step 2: Run migration on test DB**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && alembic upgrade head && popd > /dev/null`
Expected: Migration applies without errors.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/030_add_rbac_tables.py
git commit -m "feat(permissions): add Alembic migration for roles/user_roles tables"
```

---

### Task 9: Update All Backend Test Fixtures

**Files:** All test files that create users with `role=` parameter.

- [ ] **Step 1: Create shared test helper for role assignment**

Add to `backend/tests/conftest.py`:

```python
from app.core.models.role import RoleDB, UserRoleDB


async def seed_roles(db_session: AsyncSession) -> dict[str, RoleDB]:
    """Seed roles table for tests. Returns name->RoleDB mapping."""
    roles = {}
    for name in ("user", "manager", "admin"):
        role = RoleDB(name=name)
        db_session.add(role)
        roles[name] = role
    await db_session.flush()
    return roles


async def assign_roles(
    db_session: AsyncSession,
    user_id,
    role_ids: list,
) -> None:
    """Assign roles to a user in tests."""
    for role_id in role_ids:
        db_session.add(UserRoleDB(user_id=user_id, role_id=role_id))
    await db_session.flush()
```

- [ ] **Step 2: Update test fixtures across all test files**

For every test file that creates `UserDB` with `role=...`:

Before:
```python
user = UserDB(email="admin@test.com", role=UserRole.ADMIN.value, active=True)
```

After:
```python
roles = await seed_roles(db_session)
user = UserDB(email="admin@test.com", active=True)
db_session.add(user)
await db_session.flush()
await assign_roles(db_session, user.id, [roles["user"].id, roles["admin"].id])
```

Key files to update:
- `tests/core/api/test_admin_users.py`
- `tests/core/api/test_admin_users_impersonate.py`
- `tests/test_auth.py`
- All tracker test files
- All scorecard test files
- All ISO test files

- [ ] **Step 3: Run full test suite**

Run: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest --tb=short -q 2>&1 | tail -30 && popd > /dev/null`
Expected: All ~1201 tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test(permissions): update all fixtures to use user_roles table"
```

---

### Task 10: Startup Validation

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add startup event to validate roles table**

The project uses `lifespan` context manager (not deprecated `@app.on_event`). Add the validation inside the existing `lifespan` function in `backend/app/main.py`, after `init_db()` and the seed calls:

```python
from app.core.permissions.roles import ROLE_PERMISSIONS

# Inside lifespan(), after seed calls:
    # Validate roles table matches code
    from sqlalchemy import select
    from app.core.models.role import RoleDB
    from app.database import get_db
    async for db in get_db():
        result = await db.execute(select(RoleDB.name))
        db_roles = {row[0] for row in result.all()}
        code_roles = set(ROLE_PERMISSIONS.keys())
        missing_in_db = code_roles - db_roles
        extra_in_db = db_roles - code_roles
        if missing_in_db:
            logger.warning(f"Roles defined in code but missing from DB: {missing_in_db}")
        if extra_in_db:
            logger.warning(f"Roles in DB but not defined in code: {extra_in_db}")
        break
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(permissions): add startup validation for roles table vs code"
```

---

### Task 11: Frontend Permission Module

**Files:**
- Create: `frontend/src/core/permissions/constants.ts`
- Create: `frontend/src/core/permissions/usePermission.ts`
- Create: `frontend/src/core/permissions/Can.tsx`
- Create: `frontend/src/core/permissions/PermissionRoute.tsx`
- Create: `frontend/src/core/permissions/index.ts`

- [ ] **Step 1: Create `constants.ts`**

```typescript
// frontend/src/core/permissions/constants.ts
export const Action = {
  SCORECARD_VIEW: 'scorecard:view',
  SCORECARD_EDIT_METRICS: 'scorecard:edit_metrics',
  SCORECARD_CAPTURE: 'scorecard:capture',
  SCORECARD_MANAGE: 'scorecard:manage',

  TRACKER_VIEW: 'tracker:view',
  TRACKER_MANAGE_OWN_REPORTS: 'tracker:manage_own_reports',
  TRACKER_MANAGE_ALL_REPORTS: 'tracker:manage_all_reports',
  TRACKER_MANAGE: 'tracker:manage',

  ISO_VIEW: 'iso:view',
  ISO_MANAGE: 'iso:manage',

  PROJECTS_VIEW: 'projects:view',
  PROJECTS_MANAGE: 'projects:manage',

  ADMIN_USERS: 'admin:users',
  ADMIN_JOBS: 'admin:jobs',
  ADMIN_INTEGRATIONS: 'admin:integrations',
} as const;

export type Permission = typeof Action[keyof typeof Action];
```

- [ ] **Step 2: Create `usePermission.ts`**

```typescript
// frontend/src/core/permissions/usePermission.ts
import { useAuth } from '@/core/hooks/useAuth';
import type { Permission } from './constants';

export function usePermission(permission: Permission): boolean {
  const { permissions } = useAuth();
  return permissions.includes('*') || permissions.includes(permission);
}

export function usePermissions(...perms: Permission[]): boolean {
  const { permissions } = useAuth();
  if (permissions.includes('*')) return true;
  return perms.every((p) => permissions.includes(p));
}
```

- [ ] **Step 3: Create `Can.tsx`**

```typescript
// frontend/src/core/permissions/Can.tsx
import type { ReactNode } from 'react';
import { usePermission } from './usePermission';
import type { Permission } from './constants';

interface CanProps {
  readonly do: Permission;
  readonly children: ReactNode;
}

export function Can({ do: permission, children }: CanProps): JSX.Element | null {
  const allowed = usePermission(permission);
  return allowed ? <>{children}</> : null;
}
```

- [ ] **Step 4: Create `PermissionRoute.tsx`**

```typescript
// frontend/src/core/permissions/PermissionRoute.tsx
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/core/hooks/useAuth';
import { usePermission } from './usePermission';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import type { Permission } from './constants';

interface PermissionRouteProps {
  readonly require: Permission;
  readonly fallback?: string;
}

export function PermissionRoute({
  require,
  fallback = '/',
}: PermissionRouteProps): JSX.Element {
  const allowed = usePermission(require);
  const { isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner className="min-h-screen" />;
  }

  if (!allowed) {
    return <Navigate to={fallback} replace />;
  }

  return <Outlet />;
}
```

- [ ] **Step 5: Create barrel `index.ts`**

```typescript
// frontend/src/core/permissions/index.ts
export { Action } from './constants';
export type { Permission } from './constants';
export { usePermission, usePermissions } from './usePermission';
export { Can } from './Can';
export { PermissionRoute } from './PermissionRoute';
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/core/permissions/
git commit -m "feat(permissions): add frontend permission module (Can, usePermission, PermissionRoute)"
```

---

### Task 12: Update Frontend Auth Types and Context

**Files:**
- Modify: `frontend/src/core/types/auth.ts`
- Modify: `frontend/src/core/contexts/AuthContext.tsx`

- [ ] **Step 1: Update `auth.ts` types**

In `frontend/src/core/types/auth.ts`:

Remove `UserRole` type (line 5).

Update `User` interface — replace `role: UserRole` with:
```typescript
  roles: string[];
  permissions: string[];
```

Update `UserPublic` interface — replace `role: UserRole` with:
```typescript
  roles: string[];
  permissions: string[];
```

Update `AuthState` — add `permissions`:
```typescript
export interface AuthState {
  user: UserPublic | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  permissions: string[];
}
```

- [ ] **Step 2: Update `AuthContext.tsx`**

In `frontend/src/core/contexts/AuthContext.tsx`:

Update `DEFAULT_AUTH_STATE`:
```typescript
const DEFAULT_AUTH_STATE: AuthState = {
  user: null,
  isAuthenticated: false,
  isLoading: true,
  permissions: [],
};
```

Update `validateSession` — extract permissions from response:
```typescript
    const data = await response.json();
    const { is_impersonating, permissions, ...user } = data as UserPublic & {
      is_impersonating?: boolean;
      permissions?: string[];
    };
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    setIsImpersonating(is_impersonating ?? false);
    setAuthState({
      user,
      isAuthenticated: true,
      isLoading: false,
      permissions: permissions ?? [],
    });
```

Update `login` — extract permissions from login response user:
```typescript
    const data: AuthLoginResponse = await response.json();
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(data.user));
    setAuthState({
      user: data.user,
      isAuthenticated: true,
      isLoading: false,
      permissions: data.user.permissions ?? [],
    });
```

Update `impersonate` — extract permissions:
```typescript
    const data = await response.json();
    const user: UserPublic = data;
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    setIsImpersonating(true);
    setAuthState({
      user,
      isAuthenticated: true,
      isLoading: false,
      permissions: user.permissions ?? [],
    });
```

Update `stopImpersonating` similarly.

Update `contextValue` to include `permissions`:
```typescript
  const contextValue = useMemo<AuthContextType>(() => ({
    ...authState,
    login,
    logout,
    isImpersonating,
    impersonate,
    stopImpersonating,
  }), [authState, login, logout, isImpersonating, impersonate, stopImpersonating]);
```

(Note: `permissions` is already in `authState` via spread.)

- [ ] **Step 3: Run frontend tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npm test -- --run 2>&1 | tail -20 && popd > /dev/null`
Expected: Some tests may fail due to changed types — note them.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/core/types/auth.ts frontend/src/core/contexts/AuthContext.tsx
git commit -m "feat(permissions): update auth types and context with permissions array"
```

---

### Task 13: Replace Frontend Role Checks

**Files:**
- Modify: `frontend/src/core/components/ProtectedRoute.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/core/components/layout/AppLayout.tsx:102`
- Modify: `frontend/src/core/components/layout/AppSidebar.tsx:178`
- Modify: `frontend/src/core/pages/Landing.tsx:171`
- Modify: `frontend/src/core/pages/Projects.tsx:54`
- Modify: `frontend/src/modules/scorecard/components/ProjectDetail/SnapshotManager.tsx:37`
- Modify: `frontend/src/modules/scorecard/pages/GlobalDashboard/index.tsx:69`
- **Skip:** `frontend/src/modules/iso/components/GitHubDataTabs.tsx:77` — NOT a user role check (GitHub org member role)

- [ ] **Step 1: Remove `AdminRoute` from `ProtectedRoute.tsx`**

Delete the `AdminRoute` component (lines 26-38). Keep `ProtectedRoute`.

- [ ] **Step 2: Update `App.tsx`**

Replace import of `AdminRoute` with `PermissionRoute`:
```typescript
import { PermissionRoute } from '@/core/permissions';
import { Action } from '@/core/permissions';
```

Replace `<Route element={<AdminRoute />}>` with permission-specific routes:
```typescript
<Route element={<PermissionRoute require={Action.ADMIN_USERS} />}>
  {/* Admin routes */}
</Route>
```

Adjust route grouping as needed — some routes may need different permissions (e.g., ISO routes need `ISO_MANAGE`, tracker admin routes need `TRACKER_MANAGE`).

- [ ] **Step 3: Replace role checks in components**

For each file, replace `user?.role === 'admin'` or `const isAdmin = user?.role === 'admin'` with the appropriate permission check.

**`AppLayout.tsx:102`** — impersonation UI (admin-only):
```typescript
import { usePermission } from '@/core/permissions';
import { Action } from '@/core/permissions';
// ...
const canImpersonate = usePermission(Action.ADMIN_USERS);
// Replace: auth.user?.role === 'admin' && !auth.isImpersonating
// With: canImpersonate && !auth.isImpersonating
```

**`AppSidebar.tsx:178`** — admin sidebar items:
```typescript
const canAdmin = usePermission(Action.ADMIN_USERS);
// Replace: const isAdmin = bypassAuth || auth.user?.role === 'admin';
// With: const isAdmin = bypassAuth || canAdmin;
```

**`Landing.tsx:171`** — admin cards:
```typescript
const canAdmin = usePermission(Action.ADMIN_USERS);
// Replace: const isAdmin = user?.role === 'admin';
// With: const isAdmin = canAdmin;
```

**`Projects.tsx:54`** — project management:
```typescript
const canManageProjects = usePermission(Action.PROJECTS_MANAGE);
// Replace: const isAdmin = bypassAuth || user?.role === 'admin';
// With: const isAdmin = bypassAuth || canManageProjects;
```

**`SnapshotManager.tsx:37`** — scorecard admin:
```typescript
const canManageScorecard = usePermission(Action.SCORECARD_MANAGE);
// Replace: const isAdmin = user?.role === 'admin';
```

**`GlobalDashboard/index.tsx:69`** — scorecard admin:
```typescript
const canManageScorecard = usePermission(Action.SCORECARD_MANAGE);
```

**`GitHubDataTabs.tsx:77`** — **SKIP.** This is `m.role === 'admin'` where `m` is a GitHub organization member from snapshot data, not the current user's role. Do not change.

- [ ] **Step 4: Gate tracker detail page sections**

In `frontend/src/modules/tracker/pages/ProjectTrackerDetail.tsx`:

Add import:
```typescript
import { Can } from '@/core/permissions';
import { Action } from '@/core/permissions';
```

Wrap `InvoicesCard` (line 319) and `ProgressCard` (line 326):
```tsx
<Can do={Action.TRACKER_MANAGE}>
  <InvoicesCard projectId={projectId || ''} />
</Can>

<Can do={Action.TRACKER_MANAGE}>
  <ProgressCard
    projectId={projectId || ''}
    periods={summary.periods}
  />
</Can>
```

- [ ] **Step 5: Run frontend tests**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npm test -- --run 2>&1 | tail -20 && popd > /dev/null`
Expected: Tests pass (update mocks if needed).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat(permissions): replace all role checks with permission checks"
```

---

### Task 14: Update User Detail Page — Role Assignment UI

**Files:**
- Modify: `frontend/src/core/pages/UserDetail.tsx:188-203`
- Modify: `frontend/src/core/services/` (if there's a users service for API calls)

- [ ] **Step 1: Add API function for role assignment**

Find or create the admin users service and add:
```typescript
async function getUserRoles(): Promise<{ id: string; name: string; description: string | null }[]> {
  const response = await client.get('/admin/users/roles');
  return response.data;
}

async function assignRoles(userId: string, roles: string[]): Promise<{ user_id: string; roles: string[] }> {
  const response = await client.put(`/admin/users/${userId}/roles`, { roles });
  return response.data;
}
```

- [ ] **Step 2: Replace role dropdown with multi-select checkboxes**

In `frontend/src/core/pages/UserDetail.tsx`, replace the role `<Select>` (lines 188-203) with checkboxes:

```tsx
{/* Roles */}
<div className="space-y-1.5">
  <Label>Roles</Label>
  <div className="flex flex-col gap-2">
    {availableRoles?.map((role) => (
      <label key={role.id} className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={userRoles.includes(role.name)}
          disabled={role.name === 'user' || isCurrentUser}
          onChange={(e) => {
            const newRoles = e.target.checked
              ? [...userRoles, role.name]
              : userRoles.filter((r) => r !== role.name);
            handleRoleChange(newRoles);
          }}
        />
        <span>{role.name}</span>
        {role.description && (
          <span className="text-muted-foreground">— {role.description}</span>
        )}
      </label>
    ))}
  </div>
  <p className="text-xs text-muted-foreground">
    Role changes take effect on the user's next login.
  </p>
</div>
```

The `handleRoleChange` function calls the `PUT /api/admin/users/{id}/roles` endpoint.

The `user` checkbox is always checked and disabled (cannot be removed).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/core/pages/UserDetail.tsx frontend/src/core/services/
git commit -m "feat(permissions): replace role dropdown with multi-select checkboxes on user detail"
```

---

### Task 15: Update Frontend Test Mocks

**Files:** All frontend test files that mock user objects with `role` field.

- [ ] **Step 1: Find all test files with `role:` in mock objects**

Search for `role:` in test files and replace with `roles: ['user']` or `roles: ['user', 'admin']` and `permissions: [...]`.

- [ ] **Step 2: Update mocks**

For admin mocks:
```typescript
// Before:
const mockUser = { ...baseUser, role: 'admin' };

// After:
const mockUser = { ...baseUser, roles: ['user', 'admin'], permissions: ['*'] };
```

For regular user mocks:
```typescript
// Before:
const mockUser = { ...baseUser, role: 'user' };

// After:
const mockUser = {
  ...baseUser,
  roles: ['user'],
  permissions: ['scorecard:view', 'scorecard:edit_metrics', 'tracker:view', 'tracker:manage_own_reports', 'projects:view'],
};
```

- [ ] **Step 3: Run full frontend test suite**

Run: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npm test -- --run 2>&1 | tail -30 && popd > /dev/null`
Expected: All ~378 tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/
git commit -m "test(permissions): update all frontend mocks to use roles/permissions"
```

---

### Task 16: Remove Dead Code and Final Cleanup

**Files:**
- Modify: `backend/app/core/auth.py` — verify `require_role` is gone
- Modify: `backend/app/core/models/user.py` — verify `UserRole` enum is gone
- Modify: `frontend/src/core/components/ProtectedRoute.tsx` — verify `AdminRoute` is gone
- Modify: `frontend/src/core/types/auth.ts` — verify `UserRole` type is gone

- [ ] **Step 1: Grep for dead references**

Run:
```bash
grep -rn "UserRole" backend/app/ frontend/src/ --include="*.py" --include="*.ts" --include="*.tsx"
grep -rn "require_role" backend/app/
grep -rn "AdminRoute" frontend/src/
grep -rn "role.*===\|role !==\|\.role\b" frontend/src/ --include="*.ts" --include="*.tsx"
```

Fix any remaining references. **Exception:** `GitHubDataTabs.tsx` uses `m.role === 'admin'` where `m` is a GitHub org member — this is data display, not a permission check. Leave it.

- [ ] **Step 2: Run full test suites**

Run backend: `pushd /Volumes/Work/Dev/vizzhub/backend > /dev/null && python -m pytest --tb=short -q && popd > /dev/null`
Run frontend: `pushd /Volumes/Work/Dev/vizzhub/frontend > /dev/null && npm test -- --run && popd > /dev/null`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore(permissions): remove dead code (UserRole, require_role, AdminRoute)"
```

---

## Deployment Notes

1. Deploy backend with migration `030` applied
2. **Rotate `JWT_SECRET_KEY`** in production to force all users to re-login (old tokens lack `permissions` field)
3. Deploy frontend
4. Verify: log in, check `/auth/me` returns `roles` and `permissions`
5. Verify: admin can assign roles on user detail page
6. Verify: non-admin user cannot see invoices/progress on tracker detail
