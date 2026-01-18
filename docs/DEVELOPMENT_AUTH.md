# Development Authentication Bypass

## Overview

The Project Scorecard API includes a **temporary** authentication bypass for development mode to allow frontend development without implementing the full authentication system.

**This is ONLY for development and will be replaced with Google OAuth (Google Sign-In) for production.**

## How It Works

### Development Mode (DEBUG=true)

When `DEBUG=true` in your environment variables:

- API requests **without** an Authorization header will bypass authentication
- A mock development user is automatically created with full permissions
- Security warnings are logged on every bypassed request
- A warning banner is displayed at application startup

**Mock Development User:**
```python
{
    "user_id": "dev-user-id",
    "roles": ["user", "admin"]
}
```

### Production Mode (DEBUG=false)

When `DEBUG=false` (production):

- All API requests **require** valid JWT authentication
- Requests without Authorization header return `401 Unauthorized`
- No authentication bypass is possible

## Configuration

### Environment Variables

```bash
# Enable development mode with authentication bypass
DEBUG=true

# Required for JWT validation (when token IS provided)
JWT_SECRET_KEY=your-secret-key-here

# Required for OAuth state management
SESSION_SECRET_KEY=your-session-secret-here
```

See `.env.example` for complete configuration.

## Security Logging

All authentication bypass usage is logged for security awareness:

```
SECURITY: Development mode authentication bypass used.
No authentication token provided - using mock development user.
```

## Startup Warning

When running in DEBUG mode, the application displays a prominent warning:

```
================================================================================
SECURITY WARNING: Running in DEBUG mode
Authentication is BYPASSED for requests without tokens
This is ONLY for development - DO NOT use in production
Production will use Google OAuth (Google Sign-In)
================================================================================
```

## Usage Examples

### Frontend Development

```typescript
// No authentication header needed in development
const response = await fetch('http://localhost:8000/api/projects');
const projects = await response.json();
```

### API Testing

```bash
# Works in development mode (DEBUG=true)
curl http://localhost:8000/api/projects

# Also works (when token is valid)
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/projects
```

## Important Notes

### DO NOT Use in Production

- **NEVER** set `DEBUG=true` in production environments
- The bypass is a security risk if enabled in production
- Production will require Google OAuth authentication

### OAuth Endpoints Not Affected

The OAuth endpoints (`/api/oauth/*`) do not require authentication and are not affected by this change:

- `/api/oauth/jira/authorize` - Start OAuth flow
- `/api/oauth/jira/callback` - OAuth callback
- `/api/oauth/jira/status` - Token status
- `/api/oauth/jira/refresh` - Token refresh

### Health Endpoint

The `/health` endpoint never requires authentication:

```bash
curl http://localhost:8000/health
# Returns: {"status": "healthy"}
```

## Future: Google OAuth

### TODO

This development bypass is temporary. The production authentication system will be:

1. **Google OAuth (Google Sign-In)**
   - Company domain users only (e.g., `@yourcompany.com`)
   - OAuth 2.0 flow with Google
   - JWT tokens issued after successful authentication

2. **No Development Bypass**
   - Remove the `DEBUG` mode bypass
   - Require authentication in all environments
   - Mock authentication only in tests

### Migration Path

When implementing Google OAuth:

1. Keep existing JWT validation code (already in place)
2. Add Google OAuth endpoints
3. Issue JWT tokens after Google authentication
4. Remove development bypass code from `auth.py`
5. Update tests to use proper authentication

## Testing

### Basic Authentication Tests

```bash
# Run all authentication tests
uv run pytest backend/tests/test_auth.py -v

# Test development mode bypass
uv run pytest backend/tests/test_auth.py::test_development_mode_bypass_allows_access_without_token -v

# Test health endpoint
uv run pytest backend/tests/test_auth.py::test_health_endpoint_does_not_require_auth -v
```

### Manual Testing

1. **Test Development Mode:**
   ```bash
   DEBUG=true uv run uvicorn app.main:app --reload
   curl http://localhost:8000/api/projects
   # Should return 200 (not 401)
   ```

2. **Test Production Mode:**
   ```bash
   DEBUG=false uv run uvicorn app.main:app --reload
   curl http://localhost:8000/api/projects
   # Should return 401 Unauthorized
   ```

## Code References

### Implementation Files

- `/Volumes/Work/Dev/project-score-card/backend/app/core/auth.py` - Authentication logic with development bypass
- `/Volumes/Work/Dev/project-score-card/backend/app/main.py` - Startup warning for DEBUG mode
- `/Volumes/Work/Dev/project-score-card/backend/app/config.py` - Settings configuration
- `/Volumes/Work/Dev/project-score-card/backend/.env.example` - Environment variable documentation

### Test Files

- `/Volumes/Work/Dev/project-score-card/backend/tests/test_auth.py` - Authentication tests including bypass test
