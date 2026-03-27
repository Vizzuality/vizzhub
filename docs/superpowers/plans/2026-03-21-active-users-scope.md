# Active Users Default Scope Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Filter deactivated users from all operational listings by default, keeping them visible only where historical data requires it (tracker reports, cost calculations).

**Architecture:** Add `include_inactive` query param to `GET /admin/users` (default `false`). Block login for inactive users. Expose `active` field to frontend. Admin UI shows inactive toggle + active/deactivate controls.

**Tech Stack:** FastAPI, SQLAlchemy, React, TanStack Query, shadcn/ui, Tailwind

---

## File Structure

**Backend changes:**
- Modify: `backend/app/core/api/admin_users.py` — add `include_inactive` param to `list_users`, apply `active` field in `update_user`, block impersonation of inactive users
- Modify: `backend/app/core/api/auth.py` — block login for inactive users
- Modify: `backend/app/core/models/user.py` — add `active` to `UserPublic` schema

**Backend tests:**
- Modify: `backend/tests/core/api/test_admin_users_impersonate.py` — add inactive impersonation test
- Create: `backend/tests/core/api/test_admin_users.py` — tests for list_users filtering, update_user active field, login block

**Frontend changes:**
- Modify: `frontend/src/core/types/auth.ts` — add `active` to `User` and `UserPublic`
- Modify: `frontend/src/core/hooks/useUsers.ts` — accept `includeInactive` param, add `useToggleUserActive` mutation
- Modify: `frontend/src/core/components/Admin/UsersContent.tsx` — show active status, toggle, show/hide inactive
- Modify: `frontend/src/core/components/layout/ImpersonateDialog.tsx` — filter inactive users client-side

**Not touched (historical data):**
- `backend/app/modules/tracker/services/cost_service.py`
- `backend/app/modules/tracker/api/enrichment.py`

---

## Chunk 1: Backend — Schema, API, and Auth

### Task 1: Add `active` to `UserPublic` schema

**Files:**
- Modify: `backend/app/core/models/user.py:100-111`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/core/api/test_admin_users.py`:

```python
"""Tests for admin user management endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB, UserPublic, UserRole


class TestUserPublicSchema:
    """UserPublic should include active field."""

    def test_user_public_includes_active_field(self):
        user = UserDB(
            id="00000000-0000-0000-0000-000000000001",
            email="test@test.com",
            first_name="Test",
            last_name="User",
            role=UserRole.USER.value,
            active=True,
        )
        public = UserPublic.model_validate(user)
        assert public.active is True

    def test_user_public_inactive_user(self):
        user = UserDB(
            id="00000000-0000-0000-0000-000000000002",
            email="inactive@test.com",
            first_name="Inactive",
            last_name="User",
            role=UserRole.USER.value,
            active=False,
        )
        public = UserPublic.model_validate(user)
        assert public.active is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users.py::TestUserPublicSchema -v && popd > /dev/null`
Expected: FAIL — `UserPublic` has no `active` field, so `model_validate` won't include it and `assert public.active` will fail with `AttributeError`.

- [ ] **Step 3: Add `active` to `UserPublic`**

In `backend/app/core/models/user.py`, add `active: bool = True` to `UserPublic`:

```python
class UserPublic(BaseModel):
    """Public user info (for JWT responses)."""

    id: UUID
    email: str
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    picture: str | None = None
    role: UserRole
    active: bool = True

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users.py::TestUserPublicSchema -v && popd > /dev/null`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/models/user.py backend/tests/core/api/test_admin_users.py
git commit -m "feat(core): add active field to UserPublic schema"
```

---

### Task 2: Filter inactive users in `list_users` endpoint

**Files:**
- Modify: `backend/app/core/api/admin_users.py:20-28`
- Modify: `backend/tests/core/api/test_admin_users.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/core/api/test_admin_users.py`:

```python
@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> UserDB:
    """Create an admin user in the test DB."""
    user = UserDB(
        id="00000000-0000-0000-0000-000000000001",
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN.value,
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def active_user(db_session: AsyncSession) -> UserDB:
    """Create an active regular user."""
    user = UserDB(
        id="00000000-0000-0000-0000-000000000010",
        email="active@test.com",
        first_name="Active",
        last_name="User",
        role=UserRole.USER.value,
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession) -> UserDB:
    """Create an inactive user."""
    user = UserDB(
        id="00000000-0000-0000-0000-000000000011",
        email="inactive@test.com",
        first_name="Inactive",
        last_name="User",
        role=UserRole.USER.value,
        active=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestListUsers:
    """Tests for GET /admin/users."""

    @pytest.mark.asyncio
    async def test_list_users_excludes_inactive_by_default(
        self, client: AsyncClient, admin_user: UserDB, active_user: UserDB, inactive_user: UserDB
    ):
        response = await client.get("/api/admin/users")
        assert response.status_code == 200
        emails = [u["email"] for u in response.json()]
        assert "active@test.com" in emails
        assert "admin@test.com" in emails
        assert "inactive@test.com" not in emails

    @pytest.mark.asyncio
    async def test_list_users_includes_inactive_when_requested(
        self, client: AsyncClient, admin_user: UserDB, active_user: UserDB, inactive_user: UserDB
    ):
        response = await client.get("/api/admin/users?include_inactive=true")
        assert response.status_code == 200
        emails = [u["email"] for u in response.json()]
        assert "inactive@test.com" in emails
        assert "active@test.com" in emails

    @pytest.mark.asyncio
    async def test_list_users_response_includes_active_field(
        self, client: AsyncClient, admin_user: UserDB, active_user: UserDB, inactive_user: UserDB
    ):
        response = await client.get("/api/admin/users?include_inactive=true")
        assert response.status_code == 200
        users_by_email = {u["email"]: u for u in response.json()}
        assert users_by_email["active@test.com"]["active"] is True
        assert users_by_email["inactive@test.com"]["active"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users.py::TestListUsers -v && popd > /dev/null`
Expected: FAIL — `list_users` returns all users (no filtering).

- [ ] **Step 3: Add `include_inactive` param to `list_users`**

In `backend/app/core/api/admin_users.py`, update the `list_users` endpoint:

```python
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
    return [User.model_validate(u) for u in users]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users.py::TestListUsers -v && popd > /dev/null`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/api/admin_users.py backend/tests/core/api/test_admin_users.py
git commit -m "feat(core): filter inactive users from list_users by default"
```

---

### Task 3: Apply `active` field in `update_user` endpoint

**Files:**
- Modify: `backend/app/core/api/admin_users.py:31-54`
- Modify: `backend/tests/core/api/test_admin_users.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/core/api/test_admin_users.py`:

```python
class TestUpdateUser:
    """Tests for PATCH /admin/users/{user_id}."""

    @pytest.mark.asyncio
    async def test_deactivate_user(
        self, client: AsyncClient, admin_user: UserDB, active_user: UserDB
    ):
        response = await client.patch(
            f"/api/admin/users/{active_user.id}",
            json={"active": False},
        )
        assert response.status_code == 200
        assert response.json()["active"] is False

    @pytest.mark.asyncio
    async def test_reactivate_user(
        self, client: AsyncClient, admin_user: UserDB, inactive_user: UserDB
    ):
        response = await client.patch(
            f"/api/admin/users/{inactive_user.id}",
            json={"active": True},
        )
        assert response.status_code == 200
        assert response.json()["active"] is True

    @pytest.mark.asyncio
    async def test_cannot_deactivate_self(
        self, client: AsyncClient, admin_user: UserDB
    ):
        response = await client.patch(
            f"/api/admin/users/{admin_user.id}",
            json={"active": False},
        )
        assert response.status_code == 400
        assert "Cannot deactivate yourself" in response.json()["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users.py::TestUpdateUser -v && popd > /dev/null`
Expected: FAIL — `update_user` only handles `role`, ignores `active`.

- [ ] **Step 3: Apply all `UserUpdate` fields in `update_user`**

In `backend/app/core/api/admin_users.py`, replace the `update_user` endpoint:

```python
@router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    update: UserUpdate,
    current_user: AdminUser,
    db: DBSession,
) -> User:
    """Update a user (admin only)."""
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
        if field == "role":
            setattr(user, field, value.value)
            logger.info(f"User {user.email} role updated to {value.value} by {current_user.email}")
        else:
            setattr(user, field, value)

    if "active" in update_data:
        logger.info(f"User {user.email} active={update.active} by {current_user.email}")

    await db.commit()
    await db.refresh(user)
    return User.model_validate(user)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users.py::TestUpdateUser -v && popd > /dev/null`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/api/admin_users.py backend/tests/core/api/test_admin_users.py
git commit -m "feat(core): apply active field in update_user, block self-deactivation"
```

---

### Task 4: Block login for inactive users

**Files:**
- Modify: `backend/app/core/api/auth.py:78-108`
- Modify: `backend/tests/core/api/test_admin_users.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/core/api/test_admin_users.py`:

```python
from unittest.mock import patch, MagicMock


class TestInactiveUserLogin:
    """Tests for login block on inactive users."""

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_login(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """An existing inactive user should get 403 on Google login."""
        # Create an inactive user directly in DB
        user = UserDB(
            id="00000000-0000-0000-0000-000000000020",
            email="deactivated@test.com",
            first_name="Deactivated",
            last_name="User",
            role=UserRole.USER.value,
            active=False,
        )
        db_session.add(user)
        await db_session.commit()

        # Mock Google token verification to return this user's email
        mock_idinfo = {
            "email": "deactivated@test.com",
            "given_name": "Deactivated",
            "family_name": "User",
            "picture": None,
        }
        with patch("app.core.api.auth.id_token.verify_oauth2_token", return_value=mock_idinfo):
            response = await client.post(
                "/api/auth/google",
                json={"credential": "fake-google-token"},
            )
        assert response.status_code == 403
        assert "Account deactivated" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_active_user_can_login(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """An existing active user should be able to login."""
        user = UserDB(
            id="00000000-0000-0000-0000-000000000021",
            email="active-login@test.com",
            first_name="Active",
            last_name="Login",
            role=UserRole.USER.value,
            active=True,
        )
        db_session.add(user)
        await db_session.commit()

        mock_idinfo = {
            "email": "active-login@test.com",
            "given_name": "Active",
            "family_name": "Login",
            "picture": None,
        }
        with patch("app.core.api.auth.id_token.verify_oauth2_token", return_value=mock_idinfo):
            response = await client.post(
                "/api/auth/google",
                json={"credential": "fake-google-token"},
            )
        assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users.py::TestInactiveUserLogin -v && popd > /dev/null`
Expected: FAIL — inactive user login returns 200 (no check).

- [ ] **Step 3: Add inactive check to Google auth**

In `backend/app/core/api/auth.py`, after the `else:` block (line 101) where existing user is found, add an active check. Replace the `else:` block:

```python
        else:
            if not user.active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account deactivated. Contact an administrator.",
                )
            # Update last login and profile info
            user.last_login_at = datetime.now(timezone.utc)
            user.first_name = idinfo.get("given_name") or user.first_name
            user.last_name = idinfo.get("family_name") or user.last_name
            user.picture = idinfo.get("picture") or user.picture
            await db.commit()
            await db.refresh(user)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users.py::TestInactiveUserLogin -v && popd > /dev/null`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/api/auth.py backend/tests/core/api/test_admin_users.py
git commit -m "feat(core): block login for inactive users with 403"
```

---

### Task 5: Block impersonation of inactive users

**Files:**
- Modify: `backend/app/core/api/admin_users.py:139-184`
- Modify: `backend/tests/core/api/test_admin_users_impersonate.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/core/api/test_admin_users_impersonate.py`, inside `TestImpersonate` class:

```python
    @pytest_asyncio.fixture
    async def inactive_user(self, db_session: AsyncSession) -> UserDB:
        """Create an inactive user."""
        user = UserDB(
            id="00000000-0000-0000-0000-000000000003",
            email="inactive@test.com",
            first_name="Inactive",
            last_name="User",
            role=UserRole.USER.value,
            active=False,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_impersonate_inactive_user_returns_400(
        self, client: AsyncClient, admin_user: UserDB, inactive_user: UserDB
    ):
        response = await client.post(
            f"/api/admin/users/{inactive_user.id}/impersonate"
        )
        assert response.status_code == 400
        assert "Cannot impersonate an inactive user" in response.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users_impersonate.py::TestImpersonate::test_impersonate_inactive_user_returns_400 -v && popd > /dev/null`
Expected: FAIL — returns 200 (no active check).

- [ ] **Step 3: Add inactive check to impersonation**

In `backend/app/core/api/admin_users.py`, in `impersonate_user`, after the `target is None` check (line 156-160), add:

```python
    if not target.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot impersonate an inactive user",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users_impersonate.py::TestImpersonate::test_impersonate_inactive_user_returns_400 -v && popd > /dev/null`
Expected: PASS

- [ ] **Step 5: Run all backend tests to check for regressions**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users.py tests/core/api/test_admin_users_impersonate.py -v && popd > /dev/null`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/api/admin_users.py backend/tests/core/api/test_admin_users_impersonate.py
git commit -m "feat(core): block impersonation of inactive users"
```

---

## Chunk 2: Frontend — Types, Hooks, and UI

### Task 6: Add `active` to frontend types

**Files:**
- Modify: `frontend/src/core/types/auth.ts`

- [ ] **Step 1: Add `active` to `User` and `UserPublic` interfaces**

In `frontend/src/core/types/auth.ts`:

Add `active: boolean;` to `User` interface (after `role`):

```typescript
export interface User {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  picture: string | null;
  role: UserRole;
  active: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
  is_impersonating?: boolean;
}
```

Add `active: boolean;` to `UserPublic` interface (after `role`):

```typescript
export interface UserPublic {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  picture: string | null;
  role: UserRole;
  active: boolean;
}
```

- [ ] **Step 2: Run frontend type check**

Run: `pushd frontend > /dev/null && npx tsc --noEmit && popd > /dev/null`
Expected: PASS (new field with no default may cause issues if mock data doesn't include it — check).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/core/types/auth.ts
git commit -m "feat(core): add active field to frontend User types"
```

---

### Task 7: Update `useUsers` hook with `includeInactive` param and `useToggleUserActive`

**Files:**
- Modify: `frontend/src/core/hooks/useUsers.ts`

- [ ] **Step 1: Add `includeInactive` param to `useUsers`**

Replace the full file `frontend/src/core/hooks/useUsers.ts`:

```typescript
/**
 * Hooks for user management (admin only)
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/core/services/client';
import { User, UserRole } from '../types/auth';
import { queryKeys } from './queryKeys';

/**
 * Fetch users (admin only). Excludes inactive by default.
 */
export function useUsers(
  includeInactive = false,
): ReturnType<typeof useQuery<User[], Error>> {
  return useQuery({
    queryKey: [...queryKeys.users.all, { includeInactive }],
    queryFn: async (): Promise<User[]> => {
      const params = includeInactive ? { include_inactive: true } : {};
      const response = await api.get<User[]>('/admin/users', { params });
      return response.data;
    },
  });
}

/**
 * Update user role (admin only)
 */
export function useUpdateUserRole(): ReturnType<
  typeof useMutation<User, Error, { userId: string; role: UserRole }>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, role }): Promise<User> => {
      const response = await api.patch<User>(`/admin/users/${userId}`, { role });
      return response.data;
    },
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
    },
  });
}

/**
 * Toggle user active status (admin only)
 */
export function useToggleUserActive(): ReturnType<
  typeof useMutation<User, Error, { userId: string; active: boolean }>
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, active }): Promise<User> => {
      const response = await api.patch<User>(`/admin/users/${userId}`, { active });
      return response.data;
    },
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
    },
  });
}

/**
 * Delete user (admin only)
 */
export function useDeleteUser(): ReturnType<typeof useMutation<void, Error, string>> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (userId): Promise<void> => {
      await api.delete(`/admin/users/${userId}`);
    },
    onSuccess: (): void => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
    },
  });
}
```

- [ ] **Step 2: Run type check**

Run: `pushd frontend > /dev/null && npx tsc --noEmit && popd > /dev/null`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/core/hooks/useUsers.ts
git commit -m "feat(core): add includeInactive param and useToggleUserActive hook"
```

---

### Task 8: Update `UsersContent` with active status and toggle

**Files:**
- Modify: `frontend/src/core/components/Admin/UsersContent.tsx`

- [ ] **Step 1: Update `UsersContent` with active column and controls**

Replace the full file `frontend/src/core/components/Admin/UsersContent.tsx`:

```tsx
/**
 * User management tab in Admin panel
 */

import { useState } from 'react';
import { useUsers, useUpdateUserRole, useDeleteUser, useToggleUserActive } from '../../hooks/useUsers';
import { useAuth } from '../../hooks/useAuth';
import { User, UserRole } from '../../types/auth';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { Switch } from '@/shared/components/ui/switch';
import { Label } from '@/shared/components/ui/label';
import { Trash2 } from 'lucide-react';

function formatDate(dateString: string | null): string {
  if (!dateString) return 'Never';
  return new Date(dateString).toLocaleString();
}

export function UsersContent(): JSX.Element {
  const [showInactive, setShowInactive] = useState(false);
  const { data: users, isLoading, error } = useUsers(showInactive);
  const updateRole = useUpdateUserRole();
  const deleteUser = useDeleteUser();
  const toggleActive = useToggleUserActive();
  const { user: currentUser } = useAuth();

  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const showMessage = (type: 'success' | 'error', text: string): void => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 3000);
  };

  const handleRoleChange = async (userId: string, newRole: UserRole): Promise<void> => {
    try {
      await updateRole.mutateAsync({ userId, role: newRole });
      showMessage('success', 'User role updated');
    } catch (err) {
      showMessage('error', err instanceof Error ? err.message : 'Failed to update role');
    }
  };

  const handleToggleActive = async (userId: string, active: boolean): Promise<void> => {
    try {
      await toggleActive.mutateAsync({ userId, active });
      showMessage('success', active ? 'User activated' : 'User deactivated');
    } catch (err) {
      showMessage('error', err instanceof Error ? err.message : 'Failed to update status');
    }
  };

  const handleDelete = async (): Promise<void> => {
    if (!userToDelete) return;

    try {
      await deleteUser.mutateAsync(userToDelete.id);
      showMessage('success', 'User deleted');
    } catch (err) {
      showMessage('error', err instanceof Error ? err.message : 'Failed to delete user');
    } finally {
      setUserToDelete(null);
    }
  };

  if (isLoading) {
    return <LoadingSpinner className="py-8" />;
  }

  if (error) {
    return (
      <div className="text-destructive text-center py-8">
        Error loading users: {error.message}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Users</h2>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Switch
              id="show-inactive"
              checked={showInactive}
              onCheckedChange={setShowInactive}
            />
            <Label htmlFor="show-inactive" className="text-sm text-muted-foreground">
              Show inactive
            </Label>
          </div>
          <span className="text-muted-foreground text-sm">
            {users?.length || 0} users
          </span>
        </div>
      </div>

      {message && (
        <div className={`p-3 rounded-md text-sm ${
          message.type === 'success' ? 'bg-green-500/10 text-green-500' : 'bg-destructive/10 text-destructive'
        }`}>
          {message.text}
        </div>
      )}

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left p-3 font-medium">Email</th>
              <th className="text-left p-3 font-medium">Name</th>
              <th className="text-left p-3 font-medium">Role</th>
              <th className="text-left p-3 font-medium">Status</th>
              <th className="text-left p-3 font-medium">Last Login</th>
              <th className="w-[80px] p-3"></th>
            </tr>
          </thead>
          <tbody>
            {users?.map((user) => {
              const isCurrentUser = currentUser?.id === user.id;
              const fullName = [user.first_name, user.last_name].filter(Boolean).join(' ') || '-';

              return (
                <tr key={user.id} className={`border-t ${!user.active ? 'opacity-60' : ''}`}>
                  <td className="p-3 font-medium">{user.email}</td>
                  <td className="p-3">{fullName}</td>
                  <td className="p-3">
                    <Select
                      value={user.role}
                      onValueChange={(value) => handleRoleChange(user.id, value as UserRole)}
                      disabled={isCurrentUser}
                    >
                      <SelectTrigger className="w-[100px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="user">user</SelectItem>
                        <SelectItem value="admin">admin</SelectItem>
                      </SelectContent>
                    </Select>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${
                        user.active ? 'bg-green-500' : 'bg-muted-foreground'
                      }`} />
                      <span className="text-sm text-foreground">
                        {user.active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </td>
                  <td className="p-3 text-muted-foreground text-sm">
                    {formatDate(user.last_login_at)}
                  </td>
                  <td className="p-3 flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleToggleActive(user.id, !user.active)}
                      disabled={isCurrentUser}
                      title={isCurrentUser ? 'Cannot change your own status' : user.active ? 'Deactivate user' : 'Activate user'}
                    >
                      {user.active ? 'Deactivate' : 'Activate'}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setUserToDelete(user)}
                      disabled={isCurrentUser}
                      title={isCurrentUser ? 'Cannot delete yourself' : 'Delete user'}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <AlertDialog open={!!userToDelete} onOpenChange={() => setUserToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete User</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {userToDelete?.email}? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
```

- [ ] **Step 2: Run type check**

Run: `pushd frontend > /dev/null && npx tsc --noEmit && popd > /dev/null`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/core/components/Admin/UsersContent.tsx
git commit -m "feat(core): add active status column and toggle to UsersContent"
```

---

### Task 9: Filter inactive users in ImpersonateDialog

**Files:**
- Modify: `frontend/src/core/components/layout/ImpersonateDialog.tsx:47-49`

- [ ] **Step 1: Add active filter to ImpersonateDialog**

In `frontend/src/core/components/layout/ImpersonateDialog.tsx`, update the `filteredUsers` line (line 47-49):

Replace:
```typescript
  const filteredUsers = users?.filter(
    (u) => u.id !== auth.user?.id,
  ) ?? [];
```

With:
```typescript
  const filteredUsers = users?.filter(
    (u) => u.id !== auth.user?.id && u.active,
  ) ?? [];
```

- [ ] **Step 2: Run type check**

Run: `pushd frontend > /dev/null && npx tsc --noEmit && popd > /dev/null`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/core/components/layout/ImpersonateDialog.tsx
git commit -m "feat(core): filter inactive users from ImpersonateDialog"
```

---

### Task 10: Run full test suite

- [ ] **Step 1: Run all backend tests**

Run: `pushd backend > /dev/null && python -m pytest --tb=short -q && popd > /dev/null`
Expected: All pass, no regressions.

- [ ] **Step 2: Run all frontend tests**

Run: `pushd frontend > /dev/null && npm test -- --run && popd > /dev/null`
Expected: All pass, no regressions.

- [ ] **Step 3: Run frontend type check**

Run: `pushd frontend > /dev/null && npx tsc --noEmit && popd > /dev/null`
Expected: No errors.
