# Security Implementation Guide

This document describes the security measures implemented to address vulnerabilities identified in the security audit (audits/security.md).

## Overview

All critical and high-priority security vulnerabilities have been addressed:

- ✅ **SEC-002**: JWT-based authentication implemented
- ✅ **SEC-003**: OAuth CSRF protection with state validation
- ✅ **SEC-004**: Sensitive data removed from API responses
- ✅ **SEC-005**: Rate limiting on all endpoints
- ✅ **SEC-006**: Docker credentials moved to environment variables
- ✅ **SEC-007**: Security headers middleware added
- ✅ **SEC-008**: CORS configuration validates production mode
- ✅ **SEC-009**: Error messages sanitized
- ✅ **SEC-010**: JQL input validation implemented
- ✅ **SEC-011**: Database transaction error handling improved
- ✅ **SEC-012**: Structured security logging added

## Authentication & Authorization

### JWT Implementation

All API endpoints now require JWT authentication (except `/health` and OAuth callback).

**Location**: `backend/app/core/auth.py`

**Key Features**:
- JWT tokens with 30-minute expiration
- Role-based access control support
- Secure token validation
- HTTPBearer authentication scheme

**Usage Example**:
```python
from app.api.deps import CurrentUser

@router.get("/scorecards")
async def list_projects(current_user: CurrentUser, db: DBSession):
    # current_user contains: user_id, roles
    pass
```

### Configuration Required

Add to your `.env` file:

```bash
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET_KEY=your-secret-key-here
SESSION_SECRET_KEY=your-session-key-here
```

**IMPORTANT**: Use strong, random keys in production!

## OAuth CSRF Protection

### State Parameter Validation

OAuth flows now use cryptographically secure state tokens to prevent CSRF attacks.

**Location**: `backend/app/core/oauth_state.py`

**How it works**:
1. Generate random state token when initiating OAuth flow
2. Store state in user's session
3. Validate state matches in callback
4. Consume token after validation (one-time use)
5. Tokens expire after 10 minutes

**Implementation**:
- State stored in session middleware
- Double validation (session + in-memory)
- Security events logged for failed validations

## Rate Limiting

All endpoints have rate limits to prevent abuse and DoS attacks.

**Location**: `backend/app/main.py`

**Default Limits**:
- Read operations: 100 requests/minute
- Write operations: 20-30 requests/minute
- Delete operations: 10 requests/minute
- OAuth operations: 10 requests/minute

**Customization**:
```python
@router.get("/endpoint")
@limiter.limit("50/minute")  # Custom limit
async def endpoint(request: Request):
    pass
```

## Security Headers

All responses include security headers to protect against common attacks.

**Location**: `backend/app/core/security_middleware.py`

**Headers Added**:
- `Strict-Transport-Security`: Force HTTPS (production only)
- `X-Content-Type-Options`: Prevent MIME sniffing
- `X-Frame-Options`: Prevent clickjacking
- `Content-Security-Policy`: Restrict resource loading
- `Referrer-Policy`: Control referrer information
- `Permissions-Policy`: Disable unnecessary browser features

## Security Logging

Structured security event logging for monitoring and incident response.

**Location**: `backend/app/core/security_logger.py`

**Events Logged**:
- Authentication success/failure
- Authorization failures
- OAuth token issuance/refresh
- State validation failures (CSRF attempts)
- Rate limit exceeded
- Suspicious activity

**Log Format**:
```json
{
  "timestamp": "2026-01-18T10:30:00.000Z",
  "event_type": "auth_failure",
  "severity": "WARNING",
  "user_id": "user@example.com",
  "ip_address": "192.168.1.1",
  "details": "Invalid credentials"
}
```

## Input Validation

### JQL Injection Prevention

Project keys are validated before use in Jira queries.

**Location**: `backend/app/services/collectors/jira.py`

**Validation**:
- Alphanumeric, hyphens, underscores only
- Maximum 20 characters
- Uppercase letters preferred
- Quoted in JQL queries

**Example**:
```python
# Valid: "PROJ-123", "MY_PROJECT", "TEST"
# Invalid: "DROP TABLE", "'; DELETE", "../../etc"
```

## Error Handling

### Production Error Sanitization

Error messages are sanitized based on environment.

**Development Mode** (`DEBUG=true`):
- Detailed error information
- Stack traces included
- Validation error details

**Production Mode** (`DEBUG=false`):
- Generic error messages
- No stack traces
- No implementation details
- Full logging server-side

**Example**:
```python
# Production error response
{
  "detail": "Invalid request data"
}

# Development error response
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## CORS Configuration

CORS origins are validated based on environment.

**Production Mode** (`DEBUG=false`):
- Localhost origins rejected
- Only specific domains allowed
- Configuration validated on startup

**Example `.env`**:
```bash
# Development
DEBUG=true
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# Production
DEBUG=false
CORS_ORIGINS=["https://app.example.com"]
```

## Database Security

### Credentials Management

Database credentials use environment variables with defaults for development.

**Docker Compose** (`docker-compose.yml`):
```yaml
environment:
  POSTGRES_USER: ${DB_USER:-scorecard}
  POSTGRES_PASSWORD: ${DB_PASSWORD:-scorecard}
  POSTGRES_DB: ${DB_NAME:-scorecard}
```

**For Production**:
1. Create `.env.docker` (not committed to git)
2. Set strong database credentials
3. Use secrets management (AWS Secrets Manager, Vault, etc.)

### Transaction Error Handling

Database operations use proper transaction management:

```python
try:
    async with db.begin():
        # Database operations
        token = await OAuthService.exchange_code(code, db)
        # Auto-commit on success, auto-rollback on error
except SQLAlchemyError as e:
    logger.exception("Database error")
    raise HTTPException(status_code=500, detail="Operation failed")
```

## Deployment Checklist

### Before Production Deployment

- [ ] Generate strong JWT_SECRET_KEY and SESSION_SECRET_KEY
- [ ] Set DEBUG=false
- [ ] Configure production CORS_ORIGINS
- [ ] Use HTTPS-only redirect URIs
- [ ] Set up secrets management (not .env files)
- [ ] Configure database with strong credentials
- [ ] Enable security logging to SIEM
- [ ] Set up monitoring and alerting
- [ ] Run security tests
- [ ] Review all environment variables

### Environment Variables Required

```bash
# Security (REQUIRED)
JWT_SECRET_KEY=<strong-random-key>
SESSION_SECRET_KEY=<strong-random-key>

# Application
DEBUG=false
CORS_ORIGINS=["https://your-domain.com"]

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# OAuth (if using)
JIRA_OAUTH_CLIENT_ID=<your-client-id>
JIRA_OAUTH_CLIENT_SECRET=<your-client-secret>
JIRA_OAUTH_REDIRECT_URI=https://your-domain.com/api/oauth/jira/callback
```

## Testing Authentication

Since all endpoints now require authentication, you'll need to:

### 1. Generate a Test Token

For development/testing, create a simple script:

```python
# backend/scripts/generate_test_token.py
from app.core.auth import create_access_token
from datetime import timedelta

# Generate token for testing
token = create_access_token(
    data={"sub": "test-user", "roles": ["user", "admin"]},
    expires_delta=timedelta(hours=24)
)
print(f"Authorization: Bearer {token}")
```

### 2. Use Token in Requests

```bash
# Store token
export TOKEN="your-jwt-token-here"

# Make authenticated requests
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/scorecards
```

### 3. API Testing Tools

**Postman/Insomnia**:
1. Add Authorization header
2. Type: Bearer Token
3. Token: <your-jwt-token>

## Monitoring & Alerts

### Recommended Monitoring

1. **Authentication Failures**
   - Alert if > 10 failures from same IP in 5 minutes
   - May indicate brute force attack

2. **Rate Limit Exceeded**
   - Alert if frequently exceeded
   - May indicate DoS attempt or misconfigured client

3. **OAuth State Validation Failures**
   - Alert immediately
   - Indicates potential CSRF attack

4. **Database Errors**
   - Alert on connection issues
   - Monitor transaction failures

### Log Aggregation

Send security logs to centralized logging:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Splunk
- AWS CloudWatch
- Datadog

## Additional Security Recommendations

### Short-term (1-2 weeks)

1. **User Management**
   - Implement user registration/login endpoints
   - Add password hashing (already included: passlib[bcrypt])
   - Create user database model

2. **API Keys**
   - Add API key authentication for service-to-service calls
   - Implement key rotation

3. **Audit Trail**
   - Log all data modifications
   - Include user, timestamp, changes

### Long-term (1-3 months)

1. **Multi-Factor Authentication (MFA)**
   - TOTP (Time-based One-Time Password)
   - SMS or email verification

2. **OAuth for Users**
   - Allow users to login with Google/GitHub/Microsoft
   - Implement proper OAuth 2.0 authorization server

3. **Fine-grained Permissions**
   - Project-level access control
   - Read-only vs. admin roles
   - Team-based permissions

4. **Security Scanning**
   - Integrate SAST/DAST in CI/CD
   - Dependency scanning (Snyk, Dependabot)
   - Container scanning (Trivy)

## Support & Maintenance

### Security Updates

- Review security audit quarterly
- Update dependencies monthly
- Rotate secrets every 90 days
- Conduct penetration testing annually

### Incident Response

If security incident occurs:

1. **Immediate Actions**
   - Review security logs
   - Identify affected users
   - Rotate compromised secrets
   - Block malicious IPs

2. **Investigation**
   - Determine attack vector
   - Assess data exposure
   - Document timeline

3. **Remediation**
   - Apply fixes
   - Deploy updates
   - Notify affected parties
   - Update incident response plan

## References

- [Security Audit Report](../audits/security.md)
- [OAuth Setup Guide](./OAUTH_SETUP.md)
- [FastAPI Security Docs](https://fastapi.tiangolo.com/tutorial/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
