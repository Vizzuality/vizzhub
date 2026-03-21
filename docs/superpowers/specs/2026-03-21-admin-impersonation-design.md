# Admin User Impersonation

## Overview

Admin users can impersonate any other user to test the app from their perspective. The app fully assumes the impersonated user's identity (role, permissions, data). The admin can stop impersonation at any time from the avatar menu.

This is a testing/debugging tool, not a production user-facing feature. No audit trail required.

## Approach: Token Swap

When an admin impersonates a user, the backend:
1. Saves the admin's JWT in a second httpOnly cookie (`admin_token`)
2. Issues a new JWT for the target user and sets it in `access_token`

To stop, the backend restores `admin_token` → `access_token` and deletes `admin_token`.

The existing auth system (`get_current_user`, `require_role`, middleware) is **not modified**. The swap is transparent — the app simply sees a different valid JWT.

## Backend

### New Endpoints in `admin_users.py`

**`POST /admin/users/{user_id}/impersonate`**
- Dependency: `AdminUser`, `DBSession`
- Guards: 400 if `user_id == current_user.user_id` ("Cannot impersonate yourself")
- Validates target user exists in DB
- Copies current `access_token` cookie → `admin_token` cookie (httpOnly, path=/api, samesite=lax)
- Creates new JWT with target user's `sub`, `email`, `role`
- Sets new JWT in `access_token` cookie
- Returns `UserPublic` of the target user

**`POST /admin/users/stop-impersonate`**
- Dependency: `CurrentUser` (ensures a valid session exists; the impersonated user passes this)
- Reads `admin_token` cookie; 400 if missing
- Validates it's a valid JWT belonging to an admin
- Restores `admin_token` → `access_token`
- Deletes `admin_token` cookie
- Returns `UserPublic` of the admin

### Cookie Settings

Both `admin_token` and `access_token` use identical settings:
- `httponly=True`
- `secure=not settings.DEBUG`
- `samesite="lax"`
- `path="/api"`
- `max_age=settings.JWT_EXPIRE_HOURS * 3600`

### Changes to Existing Auth

- `core/api/auth.py` — **Logout endpoint**: also deletes `admin_token` cookie if present (prevents orphaned admin JWT after logout-while-impersonating)
- `core/api/auth.py` — **`GET /auth/me`**: response includes `is_impersonating: bool` (true when `admin_token` cookie is present on the request). This is the authoritative source of impersonation state, eliminating localStorage desync issues.

### No Changes To

- `core/auth.py` — `get_current_user()`, `create_access_token()`, `require_role()` untouched
- `core/api/deps.py` — `CurrentUser`, `AdminUser` untouched
- No middleware changes

## Frontend

### AuthContext Changes

New state and methods added to `AuthContext`:

```typescript
interface AuthContextType {
  // ... existing fields
  isImpersonating: boolean;
  impersonate: (userId: string) => Promise<void>;
  stopImpersonating: () => Promise<void>;
}
```

- **`isImpersonating`**: Derived from `/api/auth/me` response (`is_impersonating` field). Set on login, `validateSession`, and after impersonate/stop calls. No localStorage flag needed — the backend is the source of truth.
- **`impersonate(userId)`**: `POST /api/admin/users/{userId}/impersonate`, updates `auth_user` in localStorage with returned user, sets `isImpersonating: true`.
- **`stopImpersonating()`**: `POST /api/admin/users/stop-impersonate`, updates `auth_user` with returned admin, sets `isImpersonating: false`.

On app mount, `validateSession` calls `/api/auth/me` which returns `is_impersonating`, keeping state in sync even after page reload or localStorage clear.

### AppLayout Avatar Menu

Current menu items: user name/email, My Report (conditional), Log out.

**When admin and NOT impersonating:**
- Existing items stay
- New item: "Impersonate User" (with `UserRoundCog` or similar icon)
- Clicking opens a dialog with a combobox (searchable) listing all users from `GET /api/admin/users`
- Selecting a user calls `impersonate(userId)` and closes the dialog

**When impersonating:**
- Menu header shows "Viewing as: {impersonated user name}" instead of/above the regular name
- Avatar gets an orange ring indicator (`ring-2 ring-orange-500`) so admin doesn't forget
- New item: "Stop Impersonating" (with `UserX` or `RotateCcw` icon) replaces "Impersonate User"
- "Stop Impersonating" calls `stopImpersonating()`
- Log out still works (ends impersonated session; admin would need to log in again)

### User Selector Dialog

- Reuses existing shadcn `Dialog` + `Command` (combobox) components
- Fetches users from `GET /api/admin/users` on dialog open
- Shows user name + email in each option
- Filters by name or email as user types

## Edge Cases

- **Admin token cookie lost** (cleared manually, expired): Admin uses normal logout/login flow to restore their session. No special handling needed.
- **App reload while impersonating**: `validateSession` calls `/api/auth/me` which returns the impersonated user with `is_impersonating: true`. State restores correctly without localStorage dependency.
- **Self-impersonation**: Blocked with 400 "Cannot impersonate yourself."
- **Logout while impersonating**: Logout endpoint deletes both `access_token` and `admin_token` cookies. Clean state.
- **Impersonating and navigating to admin pages**: The impersonated user may not be admin, so admin routes will deny access. This is expected — the admin is experiencing the app as that user.
- **Nested impersonation**: Not possible. While impersonating, the user is not admin, so "Impersonate User" menu item won't appear.

## Files Modified

### Backend
- `backend/app/core/api/admin_users.py` — 2 new endpoints
- `backend/app/core/api/auth.py` — logout deletes `admin_token`; `/auth/me` returns `is_impersonating`

### Frontend
- `frontend/src/core/contexts/AuthContext.tsx` — `isImpersonating`, `impersonate()`, `stopImpersonating()`
- `frontend/src/core/components/layout/AppLayout.tsx` — menu items, orange ring, impersonation dialog
- New: `frontend/src/core/components/layout/ImpersonateDialog.tsx` — user selector dialog
