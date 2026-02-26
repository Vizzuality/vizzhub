# Unified Integration Tokens Design

**Date**: 2026-02-26
**Status**: Approved
**Scope**: Single PR (backend + frontend)

## Problem

Token storage is inconsistent across providers:
- **Jira/Google**: encrypted in `oauth_tokens` table (correct)
- **Slack**: plaintext in separate `slack_config` table (wrong name `bot_token_encrypted`, not actually encrypted)
- **GitHub**: plaintext in `GITHUB_TOKEN` environment variable (no DB persistence)

## Goal

Unify all integration tokens in `oauth_tokens` with Fernet encryption. Create `integration_settings` for non-token config. Single admin UI page for all 4 integrations.

## Design

### Data Model

**`oauth_tokens` (existing, no schema changes)**

Used by all 4 providers:

| Provider | token_type | access_token | refresh_token | expires_at | cloud_id | site_url |
|----------|-----------|--------------|---------------|------------|----------|----------|
| jira | Bearer | encrypted | encrypted | auto-managed | cloud ID | site URL |
| google_workspace | Bearer | encrypted | encrypted | auto-managed | NULL | domain |
| github | pat | encrypted | NULL | now + 1 year | NULL | NULL |
| slack | bot | encrypted | NULL | NULL | NULL | NULL |

**`integration_settings` (new table)**

```sql
id: UUID PK DEFAULT gen_random_uuid()
provider: VARCHAR(50) NOT NULL
key: VARCHAR(100) NOT NULL
value: TEXT NOT NULL
created_at: TIMESTAMP DEFAULT now()
updated_at: TIMESTAMP DEFAULT now()
UNIQUE(provider, key)
```

Initial records migrated from `slack_config`:
- `('slack', 'leadership_channel_id', '<value>')`

Future use:
- `('github', 'org', '<value>')` — could replace `GITHUB_ORG` env var later

### Alembic Migration

1. Create `integration_settings` table.
2. Copy `slack_config.leadership_channel_id` → `integration_settings('slack', 'leadership_channel_id', ...)`.
3. If `slack_config.bot_token_encrypted` has a value → encrypt with Fernet → insert into `oauth_tokens(provider='slack', token_type='bot', ...)`.
4. Drop `slack_config` table.
5. No GitHub data to migrate (env var). Admin must enter PAT via UI post-deploy.

### Backend Changes

**SlackService** — change token source:
- `get_bot_token()`: read from `oauth_tokens` WHERE provider='slack', decrypt.
- `get_leadership_channel()`: read from `integration_settings` WHERE provider='slack', key='leadership_channel_id'.
- Remove all `slack_config` model/query references.

**GitHubClient** — change token source:
- `get_token()`: read from `oauth_tokens` WHERE provider='github', decrypt.
- Fallback to `GITHUB_TOKEN` env var if no DB record (transitional, for existing deploys).
- When saving PAT: set `expires_at = now + 365 days`.

**Jira/Google**: no changes.

**Delete**: `SlackConfig` model, `slack_config` references.

### New Endpoints

```
GET    /admin/integrations/status           → { jira, google, github, slack } connection status
PUT    /admin/integrations/github           → save/update PAT (encrypted)
DELETE /admin/integrations/github           → disconnect (delete token)
PUT    /admin/integrations/slack            → save/update bot token (encrypted)
DELETE /admin/integrations/slack            → disconnect (delete token)
PUT    /admin/integrations/slack/settings   → update leadership_channel_id
GET    /admin/integrations/slack/channels   → list channels (moved from /admin/slack/channels)
POST   /admin/integrations/slack/test       → test connection (moved from /admin/slack/test)
```

Existing Jira OAuth endpoints stay: `/oauth/jira/authorize`, `/oauth/jira/callback`, `/oauth/jira/status`, `/oauth/jira/disconnect`.
Existing Google OAuth endpoints stay: `/iso/config/google-workspace/*`.

### Frontend Changes

**Page**: `/admin/integrations` (existing `IntegrationsTab`)

4 cards, one per provider:

**Jira card**:
- Show connection status (connected/disconnected, site URL)
- "Connect" button → triggers existing OAuth flow (`/oauth/jira/authorize`)
- "Disconnect" button with confirmation

**Google Workspace card**:
- Same as current `ISOConfig` component (no changes)

**GitHub card** (new):
- Show connection status + expiration date
- Input field for PAT (password type with show/hide)
- "Save" button → `PUT /admin/integrations/github`
- Warning badge when token expires within 30 days
- "Disconnect" button with confirmation

**Slack card**:
- Same functionality as current `SlackTab`, adapted to new endpoints
- Bot token input + save
- Channel selector for leadership channel
- Test connection button

### Token Expiration UI

- GitHub: show `expires_at` with relative time ("expires in 11 months"). Warning badge (yellow) at 30 days, error badge (red) at 7 days.
- Jira/Google: show "Connected" (auto-refresh handled transparently).
- Slack: show "Connected" (no expiration).

### Security

- All tokens encrypted with Fernet before DB storage (same `encrypt_token`/`decrypt_token` from `app/core/token_encryption.py`).
- Tokens never returned in API responses (only connection status: connected/disconnected, provider metadata).
- All endpoints require admin authentication.

### Migration Safety

- Alembic migration is forward-only (drops `slack_config`).
- Downgrade: recreate `slack_config` but data would be lost — requires DB backup before deploy.
- Deploy checklist: backup DB before running migration.
