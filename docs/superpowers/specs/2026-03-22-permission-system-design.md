# Permission System Design

## Overview

Replace the current two-tier role system (`user`/`admin`) with a permission-based RBAC system. Permissions are string constants mapped to roles in code. Users can have multiple roles; their effective permissions are the union of all role permissions. Permissions are resolved at login time and encoded in the JWT.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Manager scope | All projects (no ownership check) | Keeps it simple; project-scoped permissions deferred |
| Hidden vs disabled UI | Hidden entirely | Cleaner UX, no "locked" affordances |
| Frontend permission source | Backend resolves permissions, frontend consumes list | Single source of truth |
| Migration strategy | Big bang, no behavior changes for existing roles | Clean cut, no dual-system maintenance |
| Manager capabilities | Full tracker module + all users' reports | Managers need complete tracker oversight |
| Role model | Multiple roles per user (union of permissions) | Composable — avoids role explosion for future modules |
| Role storage | Join table (`user_roles`) | Standard relational pattern, easy to query |
| Permission resolution | Cached in JWT at login time | No per-request DB hit; role changes take effect on next login |
| Role-permission mapping | Defined in code, not DB | Roles change rarely; code is reviewable and testable |
| Role assignment | Runtime via admin UI | Admins assign/remove roles without deploys |

## Database Schema

### New Tables

```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(255)
);

CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);
```

### Migration from Existing Schema

1. Create `roles` table, seed with `user`, `manager`, `admin`
2. Create `user_roles` table
3. Populate `user_roles` from `users.role`:
   - `role='user'` -> gets `user` role
   - `role='admin'` -> gets `user` + `admin` roles
4. Drop `users.role` column
5. **Force re-login**: rotate `JWT_SECRET_KEY` after deployment to invalidate all existing sessions. Old JWTs contain the `role` field and lack `permissions` — they are incompatible with the new system.

### Startup Validation

On application startup, verify that every key in `ROLE_PERMISSIONS` has a matching row in the `roles` table. Log a warning if they diverge. This catches mismatches between code and DB (e.g., a new role added in code but not seeded in a migration).

## Backend: Permission Module

**Location:** `app/core/permissions/`

### `actions.py` — Permission Constants

```python
class Action:
    # Scorecard
    SCORECARD_VIEW = "scorecard:view"
    SCORECARD_EDIT_METRICS = "scorecard:edit_metrics"
    SCORECARD_CAPTURE = "scorecard:capture"
    SCORECARD_MANAGE = "scorecard:manage"

    # Tracker
    TRACKER_VIEW = "tracker:view"
    TRACKER_MANAGE_OWN_REPORTS = "tracker:manage_own_reports"
    TRACKER_MANAGE_ALL_REPORTS = "tracker:manage_all_reports"
    TRACKER_MANAGE = "tracker:manage"

    # ISO
    ISO_VIEW = "iso:view"
    ISO_MANAGE = "iso:manage"

    # Projects
    PROJECTS_VIEW = "projects:view"
    PROJECTS_MANAGE = "projects:manage"

    # Admin (granular, for future non-admin roles that need partial admin access)
    ADMIN_USERS = "admin:users"
    ADMIN_JOBS = "admin:jobs"
    ADMIN_INTEGRATIONS = "admin:integrations"
```

### `roles.py` — Role-Permission Mapping

```python
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
        "*",
    },
}
```

Permissions resolve as the **union** across all user roles. Admin uses `"*"` wildcard — automatically granted all current and future permissions.

**Role composition rule:** The `manager` role is always additive on top of `user`. Backend enforces that every user must have the `user` role. This means `manager`-only permissions (tracker management) do not need to duplicate base permissions like `PROJECTS_VIEW` — they are inherited from the `user` role.

**Permission assignment notes:**
- `SCORECARD_CAPTURE` and `SCORECARD_MANAGE` are admin-only (no regression — capture endpoints already use `AdminUser` today)
- `ISO_VIEW` and `ISO_MANAGE` are admin-only (no change — ISO pages already use `AdminRoute` today)
- `PROJECTS_MANAGE` is admin-only (no change — project CRUD already uses `AdminUser` today)
- `TRACKER_MANAGE_OWN_REPORTS` gates the "My Report" page (submit/edit own time reports)
- `TRACKER_VIEW` is read-only access to tracker dashboards (burn, time reports, budgets) but **excludes** invoices and progress reports
- `TRACKER_MANAGE` gates invoices, progress reports, reporting periods, budget lines, non-staff costs

### `resolver.py` — Permission Resolution

```python
async def resolve_permissions(db: AsyncSession, user_id: str) -> tuple[list[str], list[str]]:
    """Query user_roles, map through ROLE_PERMISSIONS, return (roles, permissions)."""
    roles = await get_user_roles(db, user_id)
    permissions = set()
    for role in roles:
        permissions |= ROLE_PERMISSIONS.get(role, set())
    return roles, sorted(permissions)
```

Called at login and during impersonation token creation. Result encoded in JWT.

### `dependencies.py` — FastAPI Dependency

```python
def require_permission(*permissions: str):
    """Require user to have ALL listed permissions. Returns TokenData."""
    async def checker(current_user: CurrentUser) -> TokenData:
        user_perms = set(current_user.permissions)
        if "*" in user_perms:
            return current_user
        for p in permissions:
            if p not in user_perms:
                raise HTTPException(403, f"Permission '{p}' required")
        return current_user
    return checker
```

No DB query — reads from JWT payload. Returns `TokenData`, so it replaces `CurrentUser` in the endpoint signature when a permission check is needed:

```python
# Endpoint that needs identity + permission check
@router.patch("/{report_id}")
async def update_report(
    report_id: UUID,
    user: Annotated[TokenData, Depends(require_permission(Action.TRACKER_MANAGE_OWN_REPORTS))],
    db: DBSession,
):
    # user.user_id available for ownership check
    ...
```

### Backward Compatibility

```python
AdminUser = Annotated[TokenData, Depends(require_permission("*"))]
```

`CurrentUser` stays as-is (any authenticated user). `AdminUser` becomes a thin alias over `require_permission("*")`.

## JWT & Auth Integration

### TokenData Changes

```python
class TokenData(BaseModel):
    user_id: str
    email: str | None = None
    roles: list[str] = []
    permissions: list[str] = []
```

The `role: str | None` field is removed. The backward-compatibility bridge (`if role and role not in roles`) is removed.

### Login Flow

1. Validate Google credential
2. Find/create user in DB
3. Query `user_roles` table -> get role names
4. Resolve permissions via `ROLE_PERMISSIONS` mapping -> flat list of strings
5. Encode in JWT: `{ sub, email, roles, permissions }`
6. Set cookie

### First-User Bootstrapping

The current `INITIAL_ADMIN_EMAIL` logic creates the first user with `role=admin`. After migration, this must insert into `user_roles` instead: create the user, then assign both `user` and `admin` roles via the `user_roles` join table.

### Impersonation Token Creation

Both `impersonate_user` and `stop_impersonate` endpoints create JWTs. These must resolve permissions from `user_roles` for the target user using `resolve_permissions()` before encoding the token. The admin backup token (`admin_token` cookie) must also include the admin's resolved permissions.

### `/auth/me` Response

```python
class AuthMeResponse(BaseModel):
    id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    picture: str | None
    roles: list[str]
    permissions: list[str]
    active: bool
    is_impersonating: bool = False
```

Frontend receives `permissions` for access checks and `roles` for display only.

## Pydantic Schema Changes

The `UserRole` enum is removed. Schemas that reference it are updated:

```python
# Before
class UserBase(BaseModel):
    role: UserRole = UserRole.USER

class UserUpdate(BaseModel):
    role: UserRole | None = None

class UserPublic(BaseModel):
    role: UserRole

# After
class UserBase(BaseModel):
    roles: list[str] = ["user"]

class UserUpdate(BaseModel):
    # role assignment moves to dedicated endpoint
    # (PUT /api/admin/users/{id}/roles)

class UserPublic(BaseModel):
    roles: list[str]
    permissions: list[str]
```

`UserPublic` gains `roles` and `permissions`. The `role` field is removed from all schemas. Role assignment is handled by the dedicated roles endpoint, not by `UserUpdate`.

## Frontend: Permission Module

**Location:** `src/core/permissions/`

### `constants.ts` — Permission Strings

```typescript
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

### `usePermission.ts` — Hook

```typescript
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

### `Can.tsx` — Conditional Rendering Component

```typescript
interface CanProps {
  do: Permission;
  children: ReactNode;
}

export function Can({ do: permission, children }: CanProps): JSX.Element | null {
  const allowed = usePermission(permission);
  return allowed ? <>{children}</> : null;
}
```

### `PermissionRoute.tsx` — Route Guard

```typescript
interface PermissionRouteProps {
  require: Permission;
  fallback?: string;
}

export function PermissionRoute({
  require,
  fallback = '/',
}: PermissionRouteProps): JSX.Element {
  const allowed = usePermission(require);
  const { isLoading } = useAuth();

  if (isLoading) return <LoadingSpinner className="min-h-screen" />;
  if (!allowed) return <Navigate to={fallback} replace />;
  return <Outlet />;
}
```

Default fallback is `/` (landing page, accessible to all authenticated users).

### Frontend Type Changes

```typescript
// auth.ts — updated types

export interface UserPublic {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  picture: string | null;
  roles: string[];           // replaces role: UserRole
  permissions: string[];     // new
  active: boolean;
}

export interface AuthState {
  user: UserPublic | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  permissions: string[];     // top-level for easy access via useAuth()
}

export interface AuthContextType extends AuthState {
  login: (credential: string) => Promise<void>;
  logout: () => Promise<void>;
  isImpersonating: boolean;
  impersonate: (userId: string) => Promise<void>;
  stopImpersonating: () => Promise<void>;
}
```

The `UserRole` type is removed. `AuthContext` populates `permissions` from the `/auth/me` response during `validateSession()`.

### Usage Examples

```tsx
// Route guard
<Route element={<PermissionRoute require={Action.ADMIN_USERS} />}>
  <Route path="admin/*" element={...} />
</Route>

// Conditional UI (hidden, not disabled)
<Can do={Action.TRACKER_MANAGE}>
  <InvoicesTab />
</Can>

// In logic
const canManage = usePermission(Action.TRACKER_MANAGE);
```

### Tracker Detail Page

Users with `TRACKER_VIEW` see the tracker page but invoices and progress report sections are hidden. Only users with `TRACKER_MANAGE` see those sections:

```tsx
<BurnDashboard />
<Can do={Action.TRACKER_MANAGE}>
  <InvoicesTab />
  <ProgressReportsTab />
</Can>
```

## Admin UI: Role Assignment

### Current Behavior
Single dropdown on user detail page: `user` | `admin`

### New Behavior
Multi-select checkboxes: `user`, `manager`, `admin`. Every user must have at least the `user` role (enforced by backend).

### Endpoints

```
GET  /api/admin/users/roles              -> [{ id, name, description }]
PUT  /api/admin/users/{user_id}/roles    -> { roles: ["user", "manager"] }
```

`PUT` replaces all roles. Backend validates `user` role is always present and all role names exist.

### Token Invalidation

Role changes take effect on next login. Admin UI displays: "Role changes take effect on the user's next login."

## Migration Checklist

### Backend
1. Alembic migration: create `roles`, `user_roles`, populate from `users.role`, drop `users.role` column
2. Add `core/permissions/` module (`actions.py`, `roles.py`, `resolver.py`, `dependencies.py`)
3. Add startup validation: verify `roles` table matches `ROLE_PERMISSIONS` keys
4. Update `auth.py`: `TokenData` gains `permissions`, loses `role`; remove backward-compat bridge
5. Update login flow: resolve permissions via `resolve_permissions()` at token creation
6. Update first-user bootstrapping (`INITIAL_ADMIN_EMAIL`): insert into `user_roles` instead of setting `role`
7. Update impersonation endpoints: resolve permissions for target user when creating tokens
8. Update `/auth/me`: return `roles` + `permissions`
9. Update Pydantic schemas: remove `UserRole` enum, update `UserBase`/`UserUpdate`/`UserPublic`
10. Replace all `AdminUser` usages (~90 endpoints) with `require_permission(Action.X)`
11. Replace `CurrentUser` usages where permission gating is needed
12. Add role management endpoints (`GET /api/admin/users/roles`, `PUT /api/admin/users/{id}/roles`)
13. Update SQLAlchemy models: remove `role` from `UserDB`, add `RoleDB` and `UserRoleDB`

### Frontend
1. Add `core/permissions/` module (`constants.ts`, `usePermission.ts`, `Can.tsx`, `PermissionRoute.tsx`)
2. Update `auth.ts` types: remove `UserRole`, add `roles` + `permissions` to `UserPublic` and `AuthState`
3. Update `AuthContext`: populate `permissions` from `/auth/me` response
4. Replace `AdminRoute` with `PermissionRoute` in `App.tsx`
5. Replace all `user?.role === 'admin'` checks (~14 locations) with `<Can>` or `usePermission()`
6. Update user detail page: role dropdown -> multi-select checkboxes
7. Gate invoices and progress sections in tracker detail with `<Can do={Action.TRACKER_MANAGE}>`

### Tests
- Update backend fixtures: use `user_roles` table instead of `role` column
- Add tests for `resolve_permissions`, `require_permission`
- Add tests for role assignment endpoints
- Add tests for permission gating on tracker endpoints (user vs manager vs admin)
- Update frontend mocks: include `permissions` array, remove `role`

### Deployment
1. Deploy backend with migration
2. Rotate `JWT_SECRET_KEY` to force all users to re-login (old tokens lack `permissions` field)
3. Deploy frontend
