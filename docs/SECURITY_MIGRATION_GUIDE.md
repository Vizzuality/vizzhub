# Security Migration Guide

**For Existing Deployments**: This guide helps you migrate to the secured version of the API.

## Breaking Changes

⚠️ **IMPORTANT**: All API endpoints now require authentication (except `/health` and OAuth callback).

If you have existing clients, they will need to be updated to include JWT tokens.

## Migration Steps

### Step 1: Update Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
# or with uv
uv pip install -r requirements.txt
```

**New dependencies installed**:
- python-jose[cryptography] - JWT handling
- passlib[bcrypt] - Password hashing
- slowapi - Rate limiting
- itsdangerous - Session security

### Step 2: Update Environment Variables

Add required security keys to your `.env`:

```bash
# Generate secure keys
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('SESSION_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

Add to `.env`:
```bash
JWT_SECRET_KEY=<your-generated-key>
SESSION_SECRET_KEY=<your-generated-key>
```

### Step 3: Update Docker Configuration (if using Docker)

If using Docker Compose, update environment variables:

**Option A: Create `.env.docker` file** (recommended):
```bash
cp .env.docker.example .env.docker
# Edit .env.docker with your values
```

**Option B: Update docker-compose.yml directly**:
```yaml
environment:
  - JWT_SECRET_KEY=${JWT_SECRET_KEY}
  - SESSION_SECRET_KEY=${SESSION_SECRET_KEY}
```

### Step 4: Restart Services

```bash
# Docker
docker-compose down
docker-compose up -d --build

# Manual
# Stop your running server
# Start again with: uvicorn app.main:app --reload
```

### Step 5: Update API Clients

All API clients must now include JWT tokens.

#### Python Client Example

**Before**:
```python
import requests

response = requests.get("http://localhost:8000/api/projects")
projects = response.json()
```

**After**:
```python
import requests

headers = {
    "Authorization": f"Bearer {jwt_token}"
}

response = requests.get(
    "http://localhost:8000/api/projects",
    headers=headers
)
projects = response.json()
```

#### JavaScript/TypeScript Client Example

**Before**:
```typescript
const response = await fetch('http://localhost:8000/api/projects');
const projects = await response.json();
```

**After**:
```typescript
const response = await fetch('http://localhost:8000/api/projects', {
  headers: {
    'Authorization': `Bearer ${jwtToken}`
  }
});
const projects = await response.json();
```

#### curl Example

**Before**:
```bash
curl http://localhost:8000/api/projects
```

**After**:
```bash
curl -H "Authorization: Bearer $JWT_TOKEN" \
     http://localhost:8000/api/projects
```

### Step 6: Generate Test Tokens

For development/testing:

```bash
cd backend
python scripts/generate_jwt_token.py --user-id "your-user" --expiry-hours 720
```

Save the token and use it in your API calls.

## Frontend Updates Required

If you have a React/Vue/Angular frontend, you'll need to:

### 1. Add Token Storage

```typescript
// Store token after login
localStorage.setItem('jwt_token', token);

// Retrieve token
const token = localStorage.getItem('jwt_token');
```

### 2. Add Authorization Header to API Calls

**Axios Example**:
```typescript
import axios from 'axios';

// Create axios instance with interceptor
const api = axios.create({
  baseURL: 'http://localhost:8000'
});

// Add token to all requests
api.interceptors.request.use(config => {
  const token = localStorage.getItem('jwt_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Use it
const projects = await api.get('/api/projects');
```

**Fetch Example**:
```typescript
const token = localStorage.getItem('jwt_token');

const response = await fetch('http://localhost:8000/api/projects', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});
```

### 3. Handle Authentication Errors

```typescript
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('jwt_token');
      // Redirect to login
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

## Backward Compatibility

**There is NO backward compatibility** for authentication - all endpoints now require tokens.

### Temporary Workaround (Development Only)

If you need time to update clients, you can temporarily disable authentication:

**⚠️ DO NOT USE IN PRODUCTION**

Create a temporary bypass (remove before production):

```python
# backend/app/api/deps.py
from app.core.auth import TokenData

def get_dev_user() -> TokenData:
    """Temporary dev user - REMOVE BEFORE PRODUCTION"""
    return TokenData(user_id="dev-user", roles=["admin"])

# Use this instead of CurrentUser in endpoints temporarily
DevUser = Annotated[TokenData, Depends(get_dev_user)]
```

## Testing Your Migration

### 1. Test Health Endpoint (No Auth Required)

```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy"}
```

### 2. Test Protected Endpoint Without Token

```bash
curl http://localhost:8000/api/projects
# Should return: 401 Unauthorized
```

### 3. Test Protected Endpoint With Token

```bash
TOKEN="your-jwt-token"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/projects
# Should return: [...projects...]
```

### 4. Test Rate Limiting

```bash
# Run 150 requests quickly
for i in {1..150}; do
  curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/projects
done
# After 100, should see: 429 Too Many Requests
```

### 5. Test OAuth Flow

```bash
# 1. Start OAuth flow
curl http://localhost:8000/api/oauth/jira/authorize
# Should redirect to Jira

# 2. After callback, check status
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/oauth/jira/status
# Should return: {"authenticated": true}
```

## Common Migration Issues

### Issue: "JWT_SECRET_KEY not configured"

**Cause**: Missing or empty JWT_SECRET_KEY in .env

**Solution**:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Add output to .env as JWT_SECRET_KEY=...
```

### Issue: All requests return 401

**Cause**: Missing or invalid JWT token

**Solution**:
1. Generate a fresh token: `python scripts/generate_jwt_token.py`
2. Verify token is in Authorization header: `Authorization: Bearer <token>`
3. Check token hasn't expired

### Issue: CORS errors in browser

**Cause**: Frontend domain not in CORS_ORIGINS

**Solution**:
```bash
# .env
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

### Issue: 429 Too Many Requests

**Cause**: Rate limit exceeded

**Solution**:
- Wait 1 minute
- For development, increase limits in code
- For production, this is expected behavior - adjust client retry logic

### Issue: OAuth state validation failed

**Cause**: Session middleware not configured or state mismatch

**Solution**:
1. Verify SESSION_SECRET_KEY is set in .env
2. Always initiate OAuth from /api/oauth/jira/authorize
3. Don't bookmark or manually construct callback URLs

## Rollback Plan

If you need to rollback due to issues:

### Quick Rollback

```bash
# Checkout previous version
git checkout <previous-commit-hash>

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

### Selective Rollback

If you want to keep some changes but need to disable authentication temporarily:

1. Comment out authentication requirements in endpoints:
```python
# async def endpoint(current_user: CurrentUser, ...):
async def endpoint(...):
```

2. Remove rate limiting decorators:
```python
# @limiter.limit("100/minute")
@router.get("/endpoint")
async def endpoint(...):
```

3. Restart services

**Remember**: This is temporary and insecure - fix and re-enable ASAP.

## Production Deployment

For production deployment, ensure:

- [ ] Strong JWT_SECRET_KEY and SESSION_SECRET_KEY (not dev keys)
- [ ] DEBUG=false
- [ ] CORS_ORIGINS set to production domains only
- [ ] HTTPS enforced (not HTTP)
- [ ] Secrets managed via secrets manager (not .env files)
- [ ] Monitoring and alerting configured
- [ ] User registration/login system implemented
- [ ] Security testing completed

See `docs/SECURITY_IMPLEMENTATION.md` for complete production guide.

## Getting Help

If you encounter issues during migration:

1. Check `docs/SECURITY_QUICK_START.md` for quick fixes
2. Review `docs/SECURITY_IMPLEMENTATION.md` for detailed docs
3. Check the security audit at `audits/security.md`
4. Review error logs for specific issues

## Timeline

Recommended migration timeline:

- **Day 1**: Update backend dependencies and environment
- **Day 2**: Update API clients with authentication
- **Day 3**: Update frontend with token handling
- **Day 4**: Testing and validation
- **Day 5**: Production deployment (after user management added)

## Next Steps

After successful migration:

1. ✅ Verify all API calls work with authentication
2. ✅ Test OAuth flows end-to-end
3. ✅ Verify rate limiting is working
4. ✅ Check security logs are being generated
5. ⏳ Implement user registration/login system
6. ⏳ Set up monitoring dashboards
7. ⏳ Configure production secrets management
8. ⏳ Conduct security testing

---

**Questions?** Review the full documentation in `docs/SECURITY_IMPLEMENTATION.md`
