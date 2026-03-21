# Admin Impersonation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow admin users to impersonate any other user via token swap, with full UI controls in the avatar menu.

**Architecture:** Two new backend endpoints handle token swap via cookies. Frontend AuthContext gains `isImpersonating` state driven by `/auth/me`. Avatar menu conditionally shows impersonate/stop controls with a searchable user dialog.

**Tech Stack:** FastAPI, SQLAlchemy, jose JWT, React, shadcn Dialog+Command, TanStack Query

**Spec:** `docs/superpowers/specs/2026-03-21-admin-impersonation-design.md`

---

## Chunk 1: Backend

### Task 1: Impersonate endpoint

**Files:**
- Modify: `backend/app/core/api/admin_users.py`
- Test: `backend/tests/core/api/test_admin_users_impersonate.py`

- [ ] **Step 1: Write failing tests for impersonate endpoint**

Create `backend/tests/core/api/test_admin_users_impersonate.py`:

```python
"""Tests for admin user impersonation endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB, UserRole


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> UserDB:
    """Create an admin user in the test DB."""
    user = UserDB(
        id="00000000-0000-0000-0000-000000000001",
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN.value,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> UserDB:
    """Create a regular user in the test DB."""
    user = UserDB(
        id="00000000-0000-0000-0000-000000000002",
        email="user@test.com",
        first_name="Regular",
        last_name="User",
        role=UserRole.USER.value,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestImpersonate:
    """Tests for POST /admin/users/{user_id}/impersonate."""

    @pytest.mark.asyncio
    async def test_impersonate_returns_target_user(
        self, client: AsyncClient, admin_user: UserDB, regular_user: UserDB
    ):
        response = await client.post(
            f"/api/admin/users/{regular_user.id}/impersonate"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@test.com"
        assert data["role"] == "user"
        assert data["id"] == str(regular_user.id)

    @pytest.mark.asyncio
    async def test_impersonate_sets_cookies(
        self, client: AsyncClient, admin_user: UserDB, regular_user: UserDB
    ):
        response = await client.post(
            f"/api/admin/users/{regular_user.id}/impersonate"
        )
        assert response.status_code == 200
        cookies = {c.name: c for c in response.cookies.jar}
        assert "access_token" in cookies
        assert "admin_token" in cookies

    @pytest.mark.asyncio
    async def test_impersonate_self_returns_400(
        self, client: AsyncClient, admin_user: UserDB
    ):
        response = await client.post(
            f"/api/admin/users/{admin_user.id}/impersonate"
        )
        assert response.status_code == 400
        assert "Cannot impersonate yourself" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_impersonate_nonexistent_user_returns_404(
        self, client: AsyncClient, admin_user: UserDB
    ):
        response = await client.post(
            "/api/admin/users/00000000-0000-0000-0000-000000000099/impersonate"
        )
        assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users_impersonate.py::TestImpersonate -v && popd > /dev/null`
Expected: FAIL — 405 Method Not Allowed (endpoint doesn't exist)

- [ ] **Step 3: Implement impersonate endpoint**

In `backend/app/core/api/admin_users.py`, add imports and endpoint:

```python
# Add to imports:
from fastapi import APIRouter, HTTPException, Request, Response, status
from app.core.auth import create_access_token, get_cookie_settings
from app.core.models.user import User, UserDB, UserPublic, UserUpdate

# Add endpoint after existing endpoints:
@router.post("/{user_id}/impersonate")
async def impersonate_user(
    user_id: UUID,
    request: Request,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users_impersonate.py::TestImpersonate -v && popd > /dev/null`
Expected: all 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/api/admin_users.py backend/tests/core/api/test_admin_users_impersonate.py
git commit -m "feat(core): add admin impersonate endpoint with tests"
```

### Task 2: Stop-impersonate endpoint

**Files:**
- Modify: `backend/app/core/api/admin_users.py`
- Test: `backend/tests/core/api/test_admin_users_impersonate.py`

- [ ] **Step 1: Write failing tests for stop-impersonate**

Append to `backend/tests/core/api/test_admin_users_impersonate.py`:

```python
from app.core.api.deps import CurrentUser
from app.core.auth import create_access_token, get_current_user, TokenData


class TestStopImpersonate:
    """Tests for POST /admin/users/stop-impersonate."""

    @pytest.mark.asyncio
    async def test_stop_impersonate_restores_admin(
        self, client: AsyncClient, admin_user: UserDB, regular_user: UserDB
    ):
        # First impersonate
        resp = await client.post(
            f"/api/admin/users/{regular_user.id}/impersonate"
        )
        assert resp.status_code == 200

        # Extract cookies from impersonate response and set them on client
        for cookie in resp.cookies.jar:
            client.cookies.set(cookie.name, cookie.value)

        # Stop impersonating
        response = await client.post("/api/admin/users/stop-impersonate")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@test.com"
        assert data["role"] == "admin"
        assert data["first_name"] == "Admin"
        assert data["last_name"] == "User"

    @pytest.mark.asyncio
    async def test_stop_impersonate_without_admin_token_returns_400(
        self, client: AsyncClient, admin_user: UserDB
    ):
        response = await client.post("/api/admin/users/stop-impersonate")
        assert response.status_code == 400
        assert "Not currently impersonating" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_stop_impersonate_deletes_admin_token_cookie(
        self, client: AsyncClient, admin_user: UserDB, regular_user: UserDB
    ):
        # First impersonate
        resp = await client.post(
            f"/api/admin/users/{regular_user.id}/impersonate"
        )
        for cookie in resp.cookies.jar:
            client.cookies.set(cookie.name, cookie.value)

        # Stop
        response = await client.post("/api/admin/users/stop-impersonate")
        assert response.status_code == 200
        # admin_token should be deleted (max-age=0)
        cookies = {c.name: c for c in response.cookies.jar}
        assert "access_token" in cookies
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users_impersonate.py::TestStopImpersonate -v && popd > /dev/null`
Expected: FAIL — 405 Method Not Allowed

- [ ] **Step 3: Implement stop-impersonate endpoint**

In `backend/app/core/api/admin_users.py`, add imports and endpoint:

```python
# Add to imports (if not already):
from app.core.api.deps import AdminUser, CurrentUser, DBSession
from app.core.auth import create_access_token, get_cookie_settings, ALGORITHM

from jose import JWTError, jwt as jose_jwt
from app.config import get_settings

# Add endpoint:
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

    # Validate the admin token
    settings = get_settings()
    try:
        payload = jose_jwt.decode(
            admin_token, settings.jwt_secret_key, algorithms=[ALGORITHM]
        )
        admin_role = payload.get("role")
        if admin_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Stored token is not an admin",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid admin token",
        )

    # Restore admin token as access_token
    cookie_settings = get_cookie_settings()
    response.set_cookie(value=admin_token, **cookie_settings)

    # Delete admin_token cookie
    response.delete_cookie(
        key="admin_token",
        path=cookie_settings["path"],
        samesite=cookie_settings["samesite"],
        secure=cookie_settings["secure"],
        httponly=cookie_settings["httponly"],
    )

    # Fetch full admin user from DB for complete UserPublic response
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users_impersonate.py -v && popd > /dev/null`
Expected: all 7 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/api/admin_users.py backend/tests/core/api/test_admin_users_impersonate.py
git commit -m "feat(core): add stop-impersonate endpoint with tests"
```

### Task 3: Modify `/auth/me` and logout

**Files:**
- Modify: `backend/app/core/api/auth.py`
- Test: `backend/tests/core/api/test_admin_users_impersonate.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/core/api/test_admin_users_impersonate.py`:

```python
class TestAuthMeImpersonation:
    """Tests for /auth/me is_impersonating field."""

    @pytest.mark.asyncio
    async def test_auth_me_not_impersonating(
        self, client: AsyncClient, admin_user: UserDB
    ):
        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["is_impersonating"] is False

    @pytest.mark.asyncio
    async def test_auth_me_while_impersonating(
        self, client: AsyncClient, admin_user: UserDB, regular_user: UserDB
    ):
        # Impersonate
        resp = await client.post(
            f"/api/admin/users/{regular_user.id}/impersonate"
        )
        for cookie in resp.cookies.jar:
            client.cookies.set(cookie.name, cookie.value)

        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["is_impersonating"] is True
        assert data["email"] == "user@test.com"


class TestLogoutClearsAdminToken:
    """Tests that logout deletes admin_token cookie."""

    @pytest.mark.asyncio
    async def test_logout_while_impersonating_clears_both_cookies(
        self, client: AsyncClient, admin_user: UserDB, regular_user: UserDB
    ):
        # Impersonate
        resp = await client.post(
            f"/api/admin/users/{regular_user.id}/impersonate"
        )
        for cookie in resp.cookies.jar:
            client.cookies.set(cookie.name, cookie.value)

        # Logout
        response = await client.post("/api/auth/logout")
        assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users_impersonate.py::TestAuthMeImpersonation -v && popd > /dev/null`
Expected: FAIL — `is_impersonating` not in response

- [ ] **Step 3: Modify `/auth/me` to include `is_impersonating`**

In `backend/app/core/api/auth.py`:

1. Add `Request` to imports: `from fastapi import APIRouter, HTTPException, Request, Response, status`
2. Add a response model:

```python
class MeResponse(User):
    """Response for /auth/me with impersonation status."""
    is_impersonating: bool = False
```

Note: `MeResponse` inherits from the imported `User` model. Add the `User` import if not present (it already is: `from app.core.models.user import User, UserDB, UserPublic, UserRole`).

3. Modify the `/me` endpoint:

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

    user_data = User.model_validate(user)
    return MeResponse(
        **user_data.model_dump(),
        is_impersonating=request.cookies.get("admin_token") is not None,
    )
```

- [ ] **Step 4: Modify logout to delete `admin_token`**

In the `logout` function in `backend/app/core/api/auth.py`, add after the existing `delete_cookie` call:

```python
    # Also clear admin_token if impersonating
    response.delete_cookie(
        key="admin_token",
        path=cookie_settings["path"],
        samesite=cookie_settings["samesite"],
        secure=cookie_settings["secure"],
        httponly=cookie_settings["httponly"],
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pushd backend > /dev/null && python -m pytest tests/core/api/test_admin_users_impersonate.py -v && popd > /dev/null`
Expected: all 10 PASS

- [ ] **Step 6: Run full backend test suite for regressions**

Run: `pushd backend > /dev/null && python -m pytest --tb=short -q && popd > /dev/null`
Expected: ~1180 tests pass. The `MeResponse` change extends `User` so existing serialization should be compatible (extra field defaults to `false`).

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/api/auth.py backend/tests/core/api/test_admin_users_impersonate.py
git commit -m "feat(core): /auth/me returns is_impersonating, logout clears admin_token"
```

---

## Chunk 2: Frontend

### Task 4: Update auth types and AuthContext

**Files:**
- Modify: `frontend/src/core/types/auth.ts`
- Modify: `frontend/src/core/contexts/AuthContext.tsx`

- [ ] **Step 1: Add `isImpersonating` to auth types**

In `frontend/src/core/types/auth.ts`:

1. Add `is_impersonating` to the `User` interface (this is what `/auth/me` returns):

```typescript
export interface User {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  picture: string | null;
  role: UserRole;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
  is_impersonating?: boolean;
}
```

2. Add `isImpersonating` and methods to `AuthContextType`:

```typescript
export interface AuthContextType extends AuthState {
  login: (credential: string) => Promise<void>;
  logout: () => Promise<void>;
  isImpersonating: boolean;
  impersonate: (userId: string) => Promise<void>;
  stopImpersonating: () => Promise<void>;
}
```

- [ ] **Step 2: Update AuthContext with impersonation state and methods**

In `frontend/src/core/contexts/AuthContext.tsx`:

1. Add `isImpersonating` state:

```typescript
const [isImpersonating, setIsImpersonating] = useState<boolean>(false);
```

2. Update `validateSession` to read `is_impersonating` from response:

```typescript
const validateSession = useCallback(async (): Promise<boolean> => {
  try {
    const response = await fetch(`${API_URL}/api/auth/me`, {
      credentials: 'include',
    });

    if (response.ok) {
      const data = await response.json();
      const { is_impersonating, ...user } = data;
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
      setIsImpersonating(is_impersonating ?? false);
      setAuthState({
        user,
        isAuthenticated: true,
        isLoading: false,
      });
      return true;
    }
    return false;
  } catch {
    return false;
  }
}, []);
```

3. Add `impersonate` callback:

```typescript
const impersonate = useCallback(async (userId: string): Promise<void> => {
  const response = await fetch(`${API_URL}/api/admin/users/${userId}/impersonate`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Impersonation failed');
  }

  const user: UserPublic = await response.json();
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
  setIsImpersonating(true);
  setAuthState({
    user,
    isAuthenticated: true,
    isLoading: false,
  });
}, []);
```

4. Add `stopImpersonating` callback:

```typescript
const stopImpersonating = useCallback(async (): Promise<void> => {
  const response = await fetch(`${API_URL}/api/admin/users/stop-impersonate`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to stop impersonation');
  }

  const user: UserPublic = await response.json();
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
  setIsImpersonating(false);
  setAuthState({
    user,
    isAuthenticated: true,
    isLoading: false,
  });
}, []);
```

5. Update `contextValue` to include new fields:

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

6. Reset `isImpersonating` in `logout`:

```typescript
const logout = useCallback(async (): Promise<void> => {
  try {
    await fetch(`${API_URL}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
  } catch {
    // Best-effort; clear local state regardless
  }

  localStorage.removeItem(USER_STORAGE_KEY);
  setIsImpersonating(false);
  setAuthState({
    user: null,
    isAuthenticated: false,
    isLoading: false,
  });
}, []);
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/core/types/auth.ts frontend/src/core/contexts/AuthContext.tsx
git commit -m "feat(core): add impersonation state and methods to AuthContext"
```

### Task 5: Create ImpersonateDialog component

**Files:**
- Create: `frontend/src/core/components/layout/ImpersonateDialog.tsx`

- [ ] **Step 1: Create the dialog component**

Create `frontend/src/core/components/layout/ImpersonateDialog.tsx`:

```tsx
import { useState } from 'react';
import { UserRoundCog } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/shared/components/ui/dialog';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import { Avatar, AvatarFallback, AvatarImage } from '@/shared/components/ui/avatar';
import { useUsers } from '@/core/hooks/useUsers';
import { useAuth } from '@/core/hooks/useAuth';

interface ImpersonateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ImpersonateDialog({
  open,
  onOpenChange,
}: ImpersonateDialogProps): JSX.Element {
  const { data: users, isLoading } = useUsers();
  const auth = useAuth();
  const [search, setSearch] = useState('');

  const handleSelect = async (userId: string): Promise<void> => {
    await auth.impersonate(userId);
    onOpenChange(false);
    setSearch('');
    window.location.reload();
  };

  const filteredUsers = users?.filter(
    (u) => u.id !== auth.user?.id
  ) ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0 gap-0 max-w-md">
        <DialogHeader className="px-4 pt-4 pb-2">
          <DialogTitle className="flex items-center gap-2 text-base">
            <UserRoundCog className="h-4 w-4" />
            Impersonate User
          </DialogTitle>
          <DialogDescription>
            Select a user to view the app as them.
          </DialogDescription>
        </DialogHeader>
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search by name or email..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList className="max-h-64">
            <CommandEmpty>
              {isLoading ? 'Loading users...' : 'No users found.'}
            </CommandEmpty>
            <CommandGroup>
              {filteredUsers
                .filter((u) => {
                  const q = search.toLowerCase();
                  if (!q) return true;
                  const name = [u.first_name, u.last_name]
                    .filter(Boolean)
                    .join(' ')
                    .toLowerCase();
                  return name.includes(q) || u.email.toLowerCase().includes(q);
                })
                .map((u) => {
                  const name = [u.first_name, u.last_name]
                    .filter(Boolean)
                    .join(' ') || u.email;
                  const initials = [u.first_name, u.last_name]
                    .filter(Boolean)
                    .map((n) => n![0])
                    .join('')
                    .toUpperCase() || '?';

                  return (
                    <CommandItem
                      key={u.id}
                      value={u.id}
                      onSelect={() => handleSelect(u.id)}
                      className="flex items-center gap-3 px-4 py-2 cursor-pointer"
                    >
                      <Avatar className="h-7 w-7">
                        <AvatarImage src={u.picture ?? undefined} alt={name} />
                        <AvatarFallback className="text-xs">
                          {initials}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex flex-col min-w-0">
                        <span className="text-sm font-medium truncate">{name}</span>
                        <span className="text-xs text-muted-foreground truncate">
                          {u.email}
                        </span>
                      </div>
                      <span className="ml-auto text-xs text-muted-foreground">
                        {u.role}
                      </span>
                    </CommandItem>
                  );
                })}
            </CommandGroup>
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/core/components/layout/ImpersonateDialog.tsx
git commit -m "feat(core): add ImpersonateDialog component"
```

### Task 6: Update AppLayout avatar menu

**Files:**
- Modify: `frontend/src/core/components/layout/AppLayout.tsx`

- [ ] **Step 1: Add impersonation controls to avatar menu**

In `frontend/src/core/components/layout/AppLayout.tsx`:

1. Add imports:

```typescript
import { LogOut, FileText, UserRoundCog, UserX } from 'lucide-react';
import { useState } from 'react';
import { ImpersonateDialog } from './ImpersonateDialog';
```

2. Inside the `AppLayout` function, add state and handler:

```typescript
const [impersonateOpen, setImpersonateOpen] = useState(false);

const handleStopImpersonating = async (): Promise<void> => {
  await auth.stopImpersonating();
  window.location.reload();
};
```

3. Add orange ring to Avatar when impersonating. Change the `Avatar` className:

```tsx
<Avatar className={`h-8 w-8 ${auth.isImpersonating ? 'ring-2 ring-orange-500' : ''}`}>
```

4. In the `DropdownMenuContent`, update the label section to show impersonation status:

```tsx
<DropdownMenuLabel className="font-normal">
  <div className="flex flex-col gap-1">
    {auth.isImpersonating && (
      <p className="text-xs font-medium text-orange-500">
        Viewing as:
      </p>
    )}
    <p className="text-sm font-medium leading-none">
      {[auth.user?.first_name, auth.user?.last_name].filter(Boolean).join(' ') || 'Dev User'}
    </p>
    {auth.user?.email && (
      <p className="text-xs leading-none text-muted-foreground">
        {auth.user.email}
      </p>
    )}
  </div>
</DropdownMenuLabel>
```

5. Add impersonate/stop menu items (between My Report and Log out sections):

```tsx
{auth.user?.role === 'admin' && !auth.isImpersonating && (
  <>
    <DropdownMenuSeparator />
    <DropdownMenuItem onClick={() => setImpersonateOpen(true)}>
      <UserRoundCog className="mr-2 h-4 w-4" />
      Impersonate User
    </DropdownMenuItem>
  </>
)}
{auth.isImpersonating && (
  <>
    <DropdownMenuSeparator />
    <DropdownMenuItem onClick={handleStopImpersonating}>
      <UserX className="mr-2 h-4 w-4" />
      Stop Impersonating
    </DropdownMenuItem>
  </>
)}
```

6. Add dialog at the end of the component (before closing `</SidebarProvider>`):

```tsx
<ImpersonateDialog open={impersonateOpen} onOpenChange={setImpersonateOpen} />
```

- [ ] **Step 2: Run frontend tests for regressions**

Run: `pushd frontend > /dev/null && npx vitest run --reporter=verbose 2>&1 | tail -20 && popd > /dev/null`
Expected: ~378 tests pass

- [ ] **Step 3: Commit**

```bash
git add frontend/src/core/components/layout/AppLayout.tsx
git commit -m "feat(core): impersonation controls in avatar menu with orange ring indicator"
```

### Task 7: Manual smoke test

- [ ] **Step 1: Start backend and frontend**

Run: `pushd backend > /dev/null && python run_server.py &` and `pushd frontend > /dev/null && npm run dev &`

- [ ] **Step 2: Verify happy path**

1. Log in as admin
2. Click avatar → "Impersonate User" should appear
3. Click it → dialog with searchable user list
4. Select a user → page reloads, avatar has orange ring, menu shows "Viewing as:"
5. Navigate around → app behaves as that user
6. Click avatar → "Stop Impersonating" should appear
7. Click it → page reloads, back to admin

- [ ] **Step 3: Verify edge cases**

1. While impersonating, "Impersonate User" should NOT appear (user isn't admin)
2. While impersonating, admin pages should be inaccessible
3. While impersonating, logout works and clears everything
4. Page reload while impersonating preserves state (orange ring, "Viewing as:")
