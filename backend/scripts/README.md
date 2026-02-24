# Backend Scripts

This directory contains utility scripts for development and testing.

## Available Scripts

### generate_jwt_token.py

Generates JWT tokens for testing authenticated API endpoints.

**Usage**:

```bash
# Basic usage (default user)
python scripts/generate_jwt_token.py

# Custom user ID and roles
python scripts/generate_jwt_token.py --user-id "admin@example.com" --roles "user,admin"

# Custom expiration (default is 24 hours)
python scripts/generate_jwt_token.py --user-id "test" --expiry-hours 48
```

**Options**:
- `--user-id`: User identifier to include in token (default: "test-user")
- `--roles`: Comma-separated list of roles (default: "user")
- `--expiry-hours`: Token expiration in hours (default: 24)

**Example Output**:

```
================================================================================
JWT Token Generated Successfully
================================================================================

User ID: test-user
Roles: user, admin
Expires in: 24 hours

--------------------------------------------------------------------------------
Token:
--------------------------------------------------------------------------------
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

--------------------------------------------------------------------------------
Usage:
--------------------------------------------------------------------------------

curl -H "Authorization: Bearer eyJhbG..." \
     http://localhost:8000/api/scorecards

OR set as environment variable:
--------------------------------------------------------------------------------
export TOKEN="eyJhbG..."
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/scorecards

================================================================================
```

**Requirements**:
- `JWT_SECRET_KEY` must be set in your `.env` file
- Run from the `backend/` directory

**Troubleshooting**:

If you get an error about `JWT_SECRET_KEY`:
1. Check that `backend/.env` exists
2. Verify it contains: `JWT_SECRET_KEY=your-secret-key`
3. Generate a secret key with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

## Future Scripts

Additional utility scripts will be added here for:
- Database migrations
- User management
- Data seeding
- Performance testing
- Security audits
