# Security Quick Start Guide

Get up and running with the secured API in 5 minutes.

## 1. Update Your Environment

Copy the example and add your secret keys:

```bash
cd backend
cp .env.example .env
```

Edit `.env` and generate secure keys:

```bash
# Generate keys
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('SESSION_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

Add the generated keys to your `.env` file:

```bash
# .env
JWT_SECRET_KEY=your-generated-key-here
SESSION_SECRET_KEY=your-generated-key-here
```

## 2. Install New Dependencies

```bash
cd backend
uv pip install -r requirements.txt
```

New security packages installed:
- `python-jose` - JWT token handling
- `passlib` - Password hashing
- `slowapi` - Rate limiting
- `itsdangerous` - Session security

## 3. Generate a Test Token

```bash
cd backend
python scripts/generate_jwt_token.py --user-id "dev-user" --roles "user,admin"
```

Copy the token from the output.

## 4. Test Authenticated Endpoints

```bash
# Set your token
export TOKEN="paste-your-jwt-token-here"

# Test authentication
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/projects

# Should work (authenticated)
# Without token will return 401 Unauthorized
```

## 5. Start the Application

```bash
# Using Docker Compose
docker-compose down && docker-compose up -d --build

# Or manually
cd backend
uv run uvicorn app.main:app --reload
```

## Common Tasks

### Create a New Token

```bash
python scripts/generate_jwt_token.py --user-id "YOUR_USER_ID"
```

### Test Without Authentication

```bash
# This should fail with 401 Unauthorized
curl http://localhost:8000/api/projects

# This should succeed
curl http://localhost:8000/health
```

### Test Rate Limiting

```bash
# Run 200 requests quickly
for i in {1..200}; do
  curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/projects
done

# After 100 requests/minute, you'll see 429 Too Many Requests
```

### Check Security Headers

```bash
curl -I http://localhost:8000/health

# Look for:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# Content-Security-Policy: ...
```

## API Testing with Tools

### Postman / Insomnia

1. Create new request
2. Set URL: `http://localhost:8000/api/projects`
3. Go to Authorization tab
4. Type: Bearer Token
5. Token: Paste your JWT token
6. Send request

### curl with Environment Variable

```bash
# Set token once
export API_TOKEN="your-jwt-token"

# Use in multiple requests
curl -H "Authorization: Bearer $API_TOKEN" http://localhost:8000/api/projects
curl -H "Authorization: Bearer $API_TOKEN" http://localhost:8000/api/config
```

## Troubleshooting

### Error: "JWT_SECRET_KEY not configured"

**Solution**: Add `JWT_SECRET_KEY` to your `.env` file

```bash
# Generate a key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Add to .env
echo "JWT_SECRET_KEY=your-generated-key" >> .env
```

### Error: "Could not validate credentials"

**Solutions**:
1. Token expired - Generate a new token
2. Wrong secret key - Verify `JWT_SECRET_KEY` matches in `.env`
3. Malformed token - Check you copied the complete token

### Error: "Invalid state parameter"

This is expected! It means OAuth CSRF protection is working.

**Solution**: Start the OAuth flow from `/api/oauth/jira/authorize` instead of calling the callback directly.

### Error: 429 Too Many Requests

You've exceeded the rate limit.

**Solution**: Wait a minute or adjust rate limits in the code for development:

```python
@router.get("/endpoint")
@limiter.limit("1000/minute")  # Higher limit for dev
async def endpoint(...):
```

## Development Tips

### Disable Authentication for Testing

Not recommended, but if you need to test without auth temporarily:

1. Comment out `current_user: CurrentUser` parameter
2. Remove `@limiter.limit()` decorator
3. Remember to re-enable before committing!

**Better approach**: Generate a long-lived dev token:

```bash
python scripts/generate_jwt_token.py --expiry-hours 720  # 30 days
```

### Check JWT Token Contents

Use [jwt.io](https://jwt.io) to decode and inspect your token (paste the token, don't share the secret!).

### Test OAuth Flow

1. Start at: `http://localhost:8000/api/oauth/jira/authorize`
2. Login to Jira
3. Get redirected to callback with state parameter
4. Check logs for successful token issuance

## Security in Production

When deploying to production:

1. **Use strong secrets** (not the dev ones!)
2. **Set DEBUG=false**
3. **Use HTTPS only**
4. **Restrict CORS origins**
5. **Implement user registration/login**
6. **Set up monitoring and alerts**

See `docs/SECURITY_IMPLEMENTATION.md` for complete production guide.

## Next Steps

- [ ] Read full security documentation: `docs/SECURITY_IMPLEMENTATION.md`
- [ ] Review implemented fixes: `SECURITY_FIXES_SUMMARY.md`
- [ ] Implement user registration/login endpoints
- [ ] Set up monitoring for security events
- [ ] Configure production secrets management

## Questions?

Check these resources:
- Full implementation guide: `docs/SECURITY_IMPLEMENTATION.md`
- Security audit report: `audits/security.md`
- FastAPI security docs: https://fastapi.tiangolo.com/tutorial/security/
