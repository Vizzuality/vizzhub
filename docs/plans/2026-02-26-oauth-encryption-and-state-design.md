# OAuth Token Encryption & State Management Design

**Date:** 2026-02-26
**Status:** Approved

## Problem

1. **HIGH** — OAuth `access_token` and `refresh_token` stored as plaintext in `oauth_tokens` table. DB read access = permanent Google Workspace Admin API access via refresh token.
2. **MEDIUM** — OAuth CSRF state tokens stored in class-level dict (`OAuthStateManager._states`). Doesn't survive restarts, fails in multi-worker deployments.

## Decisions

- Fernet symmetric encryption (no AWS KMS) — simpler, key via env var.
- DB table for OAuth state (no Redis) — Redis is volatile in production.
- Tokens stay in DB — back-office integration token management planned next.

## Task 1: Token Encryption at Rest

### Encryption Helper

New module `app/core/token_encryption.py`:
- `encrypt(plaintext: str) -> str` — Fernet encrypt, return base64 string.
- `decrypt(ciphertext: str) -> str` — Fernet decrypt, return plaintext.
- Key from `OAUTH_ENCRYPTION_KEY` env var. Raises `ValueError` on missing key (no silent plaintext fallback).
- Add `cryptography` to dependencies.

### Service-Layer Integration

Encrypt/decrypt at service layer, not in ORM model. The model stays a plain data holder.

**Write points** (encrypt before store):
- `GoogleWorkspaceOAuth.exchange_code_for_token()`
- `GoogleWorkspaceOAuth.refresh_token()`
- `OAuthService.exchange_jira_code_for_token()`
- `OAuthService.refresh_jira_token()`

**Read points** (decrypt after load):
- `GoogleWorkspaceOAuth.get_valid_token()`
- `GoogleWorkspaceOAuth.refresh_token()` (reads refresh_token to send to Google)
- `OAuthService.get_valid_jira_token()`
- `OAuthService.refresh_jira_token()` (reads refresh_token)

### DB Schema

No schema change. Columns remain `Text` — encrypted values are base64 strings.

### Migration

Data-only Alembic migration: reads existing rows, encrypts plaintext tokens in-place. Requires `OAUTH_ENCRYPTION_KEY` env var set before running.

### Key Generation

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Task 2: OAuth State in DB

### New Model

`OAuthStateDB` in `app/models/oauth.py`:
- `state: str` — PK, the token value
- `expires_at: datetime` — UTC expiry (10 min from creation)
- `created_at: datetime` — audit trail

### OAuthStateManager Changes

Becomes async, takes `db: AsyncSession`:
- `generate_state(db) -> str` — INSERT row, return token
- `validate_state(state, db) -> bool` — SELECT + DELETE (one-time use)
- `cleanup_expired(db) -> int` — DELETE expired rows

Lazy cleanup on `generate_state()` — sufficient for low volume.

### Caller Updates

- `app/api/oauth.py` — `authorize_jira` needs `db` dep added; callbacks already have it.
- `app/modules/iso/api/config.py` — `authorize_google_workspace` already has `db`.
- Both pass `db` to state manager calls.

### Alembic Migration

Creates `oauth_states` table.

### What Stays

- Session-based double-check (`request.session["oauth_state"]`) — defense in depth.
- API shape similar, just async + db param.
- No frontend changes.

## Files Affected

| File | Change |
|------|--------|
| `app/core/token_encryption.py` | New — encrypt/decrypt helpers |
| `app/core/oauth_state.py` | Rewrite — async + DB backed |
| `app/models/oauth.py` | Add `OAuthStateDB` model |
| `app/config.py` | Add `oauth_encryption_key` setting |
| `app/modules/iso/services/google_workspace_oauth.py` | Encrypt/decrypt at read/write |
| `app/services/oauth_service.py` | Encrypt/decrypt at read/write |
| `app/api/oauth.py` | Pass db to state manager |
| `app/modules/iso/api/config.py` | Pass db to state manager |
| `alembic/versions/015_*.py` | Create oauth_states table |
| `alembic/versions/016_*.py` | Encrypt existing tokens |
| `tests/test_oauth_state.py` | Rewrite for async + DB |
| `tests/test_token_encryption.py` | New — roundtrip tests |
| `tests/test_oauth_api.py` | Update state manager mocks |
