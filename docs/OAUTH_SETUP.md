# OAuth 2.0 Setup Guide

This guide explains how to configure OAuth 2.0 authentication for Jira and GitHub.

## Why OAuth 2.0?

- **More secure**: No passwords stored, tokens can be revoked
- **Better permissions**: Granular scopes control access
- **Automatic refresh**: Tokens refresh automatically
- **Recommended by Atlassian**: OAuth 1.0a and basic auth are deprecated

## Jira OAuth 2.0 Setup

### Step 1: Create OAuth App in Atlassian

1. Go to [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/)
2. Click **Create** → **OAuth 2.0 integration**
3. Fill in the details:
   - **App name**: Project Scorecard
   - **Permissions/Scopes** (under "Jira API" - use **Classic scopes** tab):
     - `read:jira-work` (read issues, projects, boards, and execute JQL searches)
     - `read:jira-user` (read user information)
     - `offline_access` (**REQUIRED** - enables refresh tokens for automatic token renewal)

   **Important Notes**:
   - Use the **Classic** tab, not Granular scopes (classic scopes are recommended by Atlassian)
   - Do NOT add scopes from "User Identity API" (like `read:me`)
   - Classic scopes provide the necessary permissions for JQL searches and issue access
   - **`offline_access` is mandatory** - without it, tokens cannot be refreshed and you'll need to re-authorize every hour
4. Click **Add** under **Authorization** section
5. Set **Callback URL**: `http://localhost:8000/api/oauth/jira/callback`
   - For production: Use your production URL (e.g., `https://scorecard.company.com/api/oauth/jira/callback`)

### Step 2: Get Client Credentials

1. After creating the app, copy the **Client ID**
2. Generate a **Client Secret** and copy it
3. Save both securely

### Step 3: Configure Backend

Add to `backend/.env`:

```bash
JIRA_OAUTH_CLIENT_ID=your-client-id-here
JIRA_OAUTH_CLIENT_SECRET=your-client-secret-here
JIRA_OAUTH_REDIRECT_URI=http://localhost:8000/api/oauth/jira/callback
# Note: OAuth scopes are hardcoded in OAuthService.JIRA_REQUIRED_SCOPES (no env var needed)
```

### Step 4: Run Database Migration

```bash
cd backend
uv run alembic upgrade head
```

### Step 5: Authorize the App

1. Start the backend server:
   ```bash
   uvicorn app.main:app --reload
   ```

2. Visit the authorization URL:
   ```
   http://localhost:8000/api/oauth/jira/authorize
   ```

3. You'll be redirected to Atlassian login
4. Grant permissions to the app
5. After success, you'll be redirected back with a success message

### Step 6: Verify Authentication

Check OAuth status:
```bash
curl http://localhost:8000/api/oauth/jira/status
```

Response:
```json
{
  "authenticated": true,
  "cloud_id": "your-cloud-id",
  "site_url": "https://your-domain.atlassian.net"
}
```

## Using the Jira Collector

The Jira collector automatically uses OAuth if configured:

```python
from app.services.collectors.jira import JiraCollector

# Pass database session to enable OAuth
async with get_db() as db:
    collector = JiraCollector(db=db)
    metrics = await collector.collect(project_key="PROJ")
```

**Fallback**: If OAuth is not configured, it falls back to legacy API token auth.

## Token Refresh

Tokens are automatically refreshed when:
- Token expires
- Token is about to expire (5-minute buffer)
- API call returns 401 Unauthorized

Manual refresh (optional):
```bash
curl -X POST http://localhost:8000/api/oauth/jira/refresh
```

## Troubleshooting

### "No Jira authentication configured" error

**Cause**: Neither OAuth nor legacy auth is set up.

**Solution**: Configure either:
- OAuth (recommended): Set `JIRA_OAUTH_CLIENT_ID` and `JIRA_OAUTH_CLIENT_SECRET`
- Legacy auth: Set `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN`

### "Failed to exchange authorization code" error

**Cause**: Invalid callback URL or client credentials.

**Solution**:
1. Verify callback URL matches in:
   - Atlassian Developer Console
   - `.env` file (`JIRA_OAUTH_REDIRECT_URI`)
2. Check client ID and secret are correct

### Token expired and refresh failed

**Cause**: Refresh token is invalid or expired.

**Solution**: Re-authorize the app by visiting `/api/oauth/jira/authorize` again.

### "Unauthorized; scope does not match" error

**Cause**: OAuth token doesn't have the required scopes for the API endpoint.

**Solution**:
1. Verify you're using **Classic scopes** (`read:jira-work read:jira-user offline_access`)
2. Go to Atlassian Developer Console → Your App → Permissions
3. Make sure you selected scopes from the **Classic** tab, not Granular
4. Re-authorize the app after changing scopes: `/api/oauth/jira/authorize`

**Note**: The `/rest/api/3/search` endpoint requires `read:jira-work` classic scope for JQL searches.

### "OAuth not configured" or "Need to re-authorize after server restart" error

**Cause**: Missing `offline_access` scope - tokens cannot be refreshed automatically.

**Symptoms**:
- Token expires after 1 hour
- Need to re-authorize every time server restarts
- Database shows `refresh_token` is NULL

**Solution**:
1. Check `.env` file includes `offline_access` in scopes:
   ```bash
   JIRA_OAUTH_SCOPES=read:jira-work read:jira-user offline_access
   ```
2. Go to Atlassian Developer Console → Your App → Permissions
3. Add `offline_access` scope (it's in the "Classic scopes" tab)
4. Restart backend server to load new scopes
5. **Re-authorize the app**: Visit `/api/oauth/jira/authorize`
6. Verify refresh token exists:
   ```bash
   psql -U scorecard -d scorecard -h localhost -c "SELECT provider, expires_at, refresh_token IS NOT NULL as has_refresh_token FROM oauth_tokens;"
   ```
   Should show `has_refresh_token = t` (true)

**Why this happens**: Without `offline_access`, Atlassian doesn't send a refresh_token in the OAuth response. The access_token expires after 1 hour and cannot be renewed automatically.

## Production Deployment

### Update Callback URL

1. In Atlassian Developer Console, add production callback:
   ```
   https://your-domain.com/api/oauth/jira/callback
   ```

2. Update `.env`:
   ```bash
   JIRA_OAUTH_REDIRECT_URI=https://your-domain.com/api/oauth/jira/callback
   ```

### Security Best Practices

1. **Never commit** `.env` file to git
2. Use environment variables in production (not `.env` files)
3. Rotate client secret periodically
4. Use HTTPS for all callbacks in production
5. Monitor OAuth tokens table for suspicious activity

## API Endpoints

### `GET /api/oauth/jira/authorize`
Initiate OAuth flow (redirects to Atlassian)

### `GET /api/oauth/jira/callback`
OAuth callback (handles authorization code)

### `GET /api/oauth/jira/status`
Check authentication status

### `POST /api/oauth/jira/refresh`
Manually refresh access token

## Database Schema

OAuth tokens are stored in the `oauth_tokens` table:

```sql
CREATE TABLE oauth_tokens (
    id UUID PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,  -- 'jira' or 'github'
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type VARCHAR(50) DEFAULT 'Bearer',
    expires_at TIMESTAMPTZ,
    scope TEXT,
    cloud_id VARCHAR(255),  -- Jira cloud ID
    site_url VARCHAR(500),  -- Jira site URL
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## GitHub OAuth (Future)

GitHub OAuth will follow a similar pattern. Configuration:

```bash
GITHUB_OAUTH_CLIENT_ID=your-github-client-id
GITHUB_OAUTH_CLIENT_SECRET=your-github-client-secret
```

Endpoints will be:
- `/api/oauth/github/authorize`
- `/api/oauth/github/callback`
- `/api/oauth/github/status`
