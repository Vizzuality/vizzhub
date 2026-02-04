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
5. Backend returns JWT (24h expiry)
6. Frontend stores JWT, includes in all API requests

### User Roles

- **user** - Default role for all new users
- **admin** - Can manage users via Admin > Users tab

The first admin is set via `INITIAL_ADMIN_EMAIL` environment variable.

## Development Configuration

### Backend (DEBUG=true)

When `DEBUG=true` in backend `.env`:

- CORS allows localhost origins (`http://localhost:5173`, `http://localhost:3000`)
- Authentication still **required** (Google SSO works locally)
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

All other endpoints require a valid JWT in the Authorization header:

```http
Authorization: Bearer <jwt_token>
```

### Admin-Only Endpoints

Require `admin` role:

- `GET /api/admin/users` - List all users
- `PATCH /api/admin/users/{id}` - Update user role
- `DELETE /api/admin/users/{id}` - Delete user

## Testing Authentication

### Generate Test JWT Token

```bash
cd backend
python scripts/generate_jwt_token.py --user-id "test-user" --roles "user,admin"
```

### Manual API Testing

```bash
# Get a JWT after Google login (use browser)
# Then test protected endpoints:
curl -H "Authorization: Bearer <jwt_token>" http://localhost:8000/api/projects

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

- `src/contexts/AuthContext.tsx` - Authentication state management
- `src/pages/LoginPage.tsx` - Google Sign-In button
- `src/components/ProtectedRoute.tsx` - Route protection
- `src/components/Admin/UsersContent.tsx` - User management UI
