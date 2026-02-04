# Google SSO Implementation Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Google Single Sign-On restricted to @vizzuality.com domain with user management in the Admin panel.

**Architecture:** Frontend uses @react-oauth/google for Google Sign-In button. Backend validates Google token, checks domain, creates/retrieves user from DB, and issues JWT. Users managed via new Admin tab.

**Tech Stack:** @react-oauth/google (frontend), python-jose + google-auth (backend), PostgreSQL users table

---

## Authentication Flow

```
User → Click "Sign in with Google" → Google OAuth → Backend validates:
  1. Google token valid? → No → 401 Unauthorized
  2. Email ends with @vizzuality.com? → No → 401 Unauthorized
  3. User exists in DB?
     → No → Create user (role: user, or admin if INITIAL_ADMIN_EMAIL)
     → Yes → Continue
  4. Generate JWT with user_id, email, role
  5. Return JWT to frontend
```

**Frontend:**
- Stores JWT in `localStorage`
- Includes JWT in `Authorization: Bearer <token>` header on all requests
- On 401 response, redirects to login

**Tokens:**
- JWT expires in 24 hours (configurable via `JWT_EXPIRE_HOURS`)
- No refresh token - user re-authenticates with Google when expired

---

## Data Model

**New `users` table:**

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    picture VARCHAR(500),
    role VARCHAR(50) DEFAULT 'user',
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

**Roles:**
- `user` - Default role, standard access
- `admin` - Can manage users, access admin panel

---

## Configuration

**New `.env` variables:**

```env
# Google OAuth
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx
ALLOWED_GOOGLE_DOMAIN=vizzuality.com

# Initial admin (gets admin role on first login)
INITIAL_ADMIN_EMAIL=miguel.mendoza@vizzuality.com

# JWT (update existing)
JWT_SECRET_KEY=xxx
JWT_EXPIRE_HOURS=24
```

**Development mode (`DEBUG=true`):**
- If `GOOGLE_CLIENT_ID` is empty, bypass authentication (current behavior)
- Allows development without Google OAuth configured

---

## API Endpoints

### Authentication

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/auth/google` | Validate Google token, return JWT |
| `GET` | `/api/auth/me` | Get current user from JWT |
| `POST` | `/api/auth/logout` | Optional - for logging purposes |

**POST /api/auth/google**

Request:
```json
{
  "credential": "google_id_token_from_frontend"
}
```

Response (200):
```json
{
  "access_token": "jwt_token",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "miguel.mendoza@vizzuality.com",
    "first_name": "Miguel",
    "last_name": "Mendoza",
    "picture": "https://...",
    "role": "admin"
  }
}
```

### User Management (Admin only)

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/admin/users` | List all users |
| `PATCH` | `/api/admin/users/{id}` | Update user role |
| `DELETE` | `/api/admin/users/{id}` | Delete user |

**GET /api/admin/users**

Response:
```json
[
  {
    "id": "uuid",
    "email": "miguel.mendoza@vizzuality.com",
    "first_name": "Miguel",
    "last_name": "Mendoza",
    "picture": "https://...",
    "role": "admin",
    "last_login_at": "2026-02-04T10:00:00Z",
    "created_at": "2026-02-04T09:00:00Z"
  }
]
```

**PATCH /api/admin/users/{id}**

Request:
```json
{
  "role": "admin"
}
```

**DELETE /api/admin/users/{id}**

Response: `204 No Content`

---

## Frontend Components

### New Components

1. **LoginPage** (`/login`)
   - Google Sign-In button using @react-oauth/google
   - Redirects to `/` on success

2. **AuthProvider** (context)
   - Manages auth state (user, isAuthenticated, isLoading)
   - Provides login, logout, getToken functions
   - On mount: checks localStorage for JWT, validates with `/api/auth/me`

3. **ProtectedRoute** (wrapper)
   - Checks AuthProvider state
   - Redirects to `/login` if not authenticated
   - Shows loading spinner while checking

4. **UsersTab** (Admin panel)
   - Table: Email, Name, Role, Last Login, Actions
   - Actions: Role dropdown (user/admin), Delete button
   - Cannot delete self (button disabled)

### Auth Flow

```
App loads → AuthProvider checks JWT in localStorage
  → JWT exists → GET /api/auth/me
    → 200 → User authenticated, render app
    → 401 → Clear localStorage, show login
  → No JWT → Show login
```

### Protected Routes

```tsx
<AuthProvider>
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route element={<ProtectedRoute />}>
      <Route path="/" element={<Dashboard />} />
      <Route path="/projects/:id" element={<ProjectDetail />} />
      <Route path="/admin" element={<AdminRoute />}>
        {/* Existing admin routes + new Users tab */}
      </Route>
    </Route>
  </Routes>
</AuthProvider>
```

---

## Error Handling

| Validation | HTTP | Message |
|------------|------|---------|
| Invalid/expired Google token | 401 | `Invalid Google token` |
| Email not @vizzuality.com | 401 | `Unauthorized domain` |
| Deleted user tries login | 401 | `User not found` |
| Expired JWT | 401 | `Token expired` |
| Non-admin accesses /admin/users | 403 | `Admin role required` |
| Admin tries to delete self | 400 | `Cannot delete yourself` |

---

## Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project or select existing
3. Enable "Google Identity" API
4. Go to Credentials → Create Credentials → OAuth 2.0 Client ID
5. Application type: Web application
6. Authorized JavaScript origins:
   - `http://localhost:5173` (development)
   - `https://your-production-domain.com` (production)
7. Copy Client ID to `GOOGLE_CLIENT_ID` in `.env`

---

## Implementation Tasks

### Backend

1. Add new config variables to `app/config.py`
2. Create `users` table migration
3. Create `UserDB` model in `app/models/user.py`
4. Create `app/api/auth.py` with Google auth endpoints
5. Create `app/api/admin_users.py` for user management
6. Update `app/core/auth.py` to load user from DB
7. Add `google-auth` dependency

### Frontend

1. Install `@react-oauth/google`
2. Create `AuthContext` and `AuthProvider`
3. Create `LoginPage` component
4. Create `ProtectedRoute` component
5. Add `UsersTab` to Admin panel
6. Update `App.tsx` with auth routing
7. Update API service to handle 401 redirects

### Testing

1. Backend unit tests for auth endpoints
2. Backend unit tests for user management
3. Frontend tests for auth flow
4. Integration test for full login flow
