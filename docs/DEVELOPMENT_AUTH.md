# Development Authentication

## Overview

The Project Scorecard uses **Google SSO** for authentication, restricted to `@vizzuality.com` domain. For local development, authentication can be bypassed using frontend environment variables.

## Authentication System

### Google SSO (Production)

Users authenticate via Google Sign-In:

1. User clicks "Sign in with Google" on login page
2. Google returns an ID token to the frontend
3. Frontend sends token to `POST /api/auth/google`
4. Backend validates token, checks domain, creates/gets user
5. Backend sets JWT in httpOnly cookie (24h expiry)
6. Frontend uses `credentials: 'include'` for all API requests (cookies sent automatically)

### User Roles

- **user** - Default role for all new users
- **admin** - Can manage users via Admin > Users tab

The first admin is set via `INITIAL_ADMIN_EMAIL` environment variable.

## Development Configuration

### Backend (DEBUG=true)

When `DEBUG=true` in backend `.env`:

- CORS allows localhost origins (`http://localhost:5173`, `http://localhost:3000`)
- Authentication still **required** (Google SSO works locally)
- Cookie `Secure=false` (allows non-HTTPS for local dev)
- Security headers are relaxed for local development

### Frontend (VITE_BYPASS_AUTH=true)

When `VITE_BYPASS_AUTH=true` in frontend `.env`:

- Authentication is **completely bypassed**
- No login required to access the application
- Useful for rapid frontend development without Google OAuth setup

### Recommended Configurations

| Scenario | `DEBUG` | `VITE_BYPASS_AUTH` |
|----------|---------|-------------------|
| Quick frontend dev | `true` | `true` |
| Test Google OAuth locally | `true` | `false` |
| Production | `false` | `false` |

## Configuration

### Backend Environment Variables (`.env`)

```bash
# Development mode (allows localhost CORS)
DEBUG=true

# JWT Configuration
JWT_SECRET_KEY=your-secret-key-here
JWT_EXPIRE_HOURS=24

# Session for OAuth state
SESSION_SECRET_KEY=your-session-secret-here

# Google SSO
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx
ALLOWED_GOOGLE_DOMAIN=vizzuality.com
INITIAL_ADMIN_EMAIL=miguel.mendoza@vizzuality.com
```

### Frontend Environment Variables (`.env`)

```bash
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
VITE_BYPASS_AUTH=false
```

See `.env.example` files for complete configuration.

## API Endpoints

### Public Endpoints (No Auth Required)

- `GET /health` - Health check
- `POST /api/auth/google` - Google SSO login
- `GET /api/oauth/jira/*` - Jira OAuth flow

### Protected Endpoints (JWT Required)

All other endpoints require a valid JWT. The JWT is sent automatically via httpOnly cookie (`access_token`). For testing with curl, use the `--cookie` flag or Bearer header fallback:

```http
Authorization: Bearer <jwt_token>
```

### Admin-Only Endpoints

Require `admin` role:

**User Management:**
- `GET /api/admin/users` - List all users
- `PATCH /api/admin/users/{id}` - Update user role
- `DELETE /api/admin/users/{id}` - Delete user

**Slack & Notifications:**
- `/admin/slack/*` - Slack configuration
- `/admin/alerts/*` - Alert definitions and templates
- `/admin/templates/*` - Message templates
- `/admin/jobs/*` - Scheduled jobs management
- `/notifications/*` - Notification log
- `/silences/*` - Alert silences

**Global Metrics:**
- `POST /api/global/calculate` - Calculate global metrics
- `POST /api/global/recalculate` - Recalculate global metrics

**Background Jobs:**
- `POST /api/jobs/capture-history` - Create batch capture job
- `POST /api/jobs/{id}/cancel` - Cancel job
- `POST /api/jobs/{id}/retry` - Retry job
- `DELETE /api/jobs/{id}` - Delete job

## Testing Authentication

### Generate Test JWT Token

```bash
cd backend
python scripts/generate_jwt_token.py --user-id "test-user" --roles "user,admin"
```

### Manual API Testing

```bash
# Option 1: Use Bearer header (for testing)
curl -H "Authorization: Bearer <jwt_token>" http://localhost:8000/api/scorecards

# Option 2: Use cookie (how browser does it)
curl --cookie "access_token=<jwt_token>" http://localhost:8000/api/scorecards

# Health endpoint (no auth needed)
curl http://localhost:8000/health
```

### Automated Tests

```bash
cd backend
pytest tests/test_auth.py -v
```

## Code References

### Backend Implementation

- `app/api/auth.py` - Google SSO endpoints (`/auth/google`, `/auth/me`, `/auth/logout`)
- `app/api/admin_users.py` - User management endpoints (admin only)
- `app/models/user.py` - User model and Pydantic schemas
- `app/core/auth.py` - JWT token creation and validation

### Frontend Implementation

- `src/contexts/AuthContext.tsx` - Authentication state management (uses `credentials: 'include'`)
- `src/pages/LoginPage.tsx` - Google Sign-In button
- `src/components/ProtectedRoute.tsx` - Route protection (`ProtectedRoute` for auth, `AdminRoute` for admin)
- `src/components/Admin/UsersContent.tsx` - User management UI
- `src/services/api/client.ts` - Axios client with `withCredentials: true`
