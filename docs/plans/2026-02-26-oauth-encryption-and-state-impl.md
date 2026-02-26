# OAuth Token Encryption & State Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Encrypt OAuth tokens at rest with Fernet and replace in-memory OAuth state with a DB-backed table.

**Architecture:** Fernet symmetric encryption at the service layer (not ORM), key from env var. OAuth CSRF state moves to `oauth_states` DB table with 10-min TTL and lazy cleanup. Two Alembic migrations: one for the new table, one data-only to encrypt existing tokens.

**Tech Stack:** `cryptography` (Fernet), SQLAlchemy async, Alembic, pytest

**Design doc:** `docs/plans/2026-02-26-oauth-encryption-and-state-design.md`

---

### Task 1: Token Encryption Helper

**Files:**
- Create: `backend/app/core/token_encryption.py`
- Modify: `backend/app/config.py:8-17` (add `oauth_encryption_key` setting)
- Create: `backend/tests/test_token_encryption.py`

**Step 1: Add `oauth_encryption_key` to Settings**

In `backend/app/config.py`, add to `Settings` class after `session_secret_key`:

```python
    oauth_encryption_key: str = ""
```

**Step 2: Write the failing tests**

Create `backend/tests/test_token_encryption.py`:

```python
"""Tests for OAuth token encryption helpers."""

import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.core.token_encryption import decrypt_token, encrypt_token

TEST_KEY = Fernet.generate_key().decode()


class TestEncryptToken:
    """Test token encryption."""

    def test_encrypt_token_returns_different_string(self) -> None:
        """Encrypted value should differ from plaintext."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = TEST_KEY
            plaintext = "my-secret-token"
            encrypted = encrypt_token(plaintext)
            assert encrypted != plaintext
            assert isinstance(encrypted, str)

    def test_encrypt_token_produces_valid_fernet_output(self) -> None:
        """Output should be decodable by Fernet."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = TEST_KEY
            encrypted = encrypt_token("test-value")
            f = Fernet(TEST_KEY.encode())
            result = f.decrypt(encrypted.encode()).decode()
            assert result == "test-value"

    def test_encrypt_token_raises_without_key(self) -> None:
        """Should raise ValueError when encryption key is missing."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = ""
            with pytest.raises(ValueError, match="OAUTH_ENCRYPTION_KEY"):
                encrypt_token("test")


class TestDecryptToken:
    """Test token decryption."""

    def test_decrypt_token_roundtrip(self) -> None:
        """Encrypting then decrypting should return original value."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = TEST_KEY
            original = "access-token-xyz-123"
            encrypted = encrypt_token(original)
            decrypted = decrypt_token(encrypted)
            assert decrypted == original

    def test_decrypt_token_raises_without_key(self) -> None:
        """Should raise ValueError when encryption key is missing."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = ""
            with pytest.raises(ValueError, match="OAUTH_ENCRYPTION_KEY"):
                decrypt_token("some-ciphertext")

    def test_decrypt_token_raises_on_invalid_ciphertext(self) -> None:
        """Should raise on corrupted/invalid ciphertext."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = TEST_KEY
            with pytest.raises(Exception):
                decrypt_token("not-valid-fernet-data")

    def test_encrypt_decrypt_empty_string(self) -> None:
        """Should handle empty string."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = TEST_KEY
            encrypted = encrypt_token("")
            assert decrypt_token(encrypted) == ""

    def test_encrypt_decrypt_unicode(self) -> None:
        """Should handle unicode characters."""
        with patch("app.core.token_encryption.get_settings") as mock:
            mock.return_value.oauth_encryption_key = TEST_KEY
            original = "token-with-unicode-\u00e9\u00e8\u00ea"
            encrypted = encrypt_token(original)
            assert decrypt_token(encrypted) == original
```

**Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_token_encryption.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.token_encryption'`

**Step 4: Implement the encryption helper**

Create `backend/app/core/token_encryption.py`:

```python
"""Fernet symmetric encryption for OAuth tokens at rest."""

from cryptography.fernet import Fernet

from app.config import get_settings


def _get_fernet() -> Fernet:
    key = get_settings().oauth_encryption_key
    if not key:
        raise ValueError(
            "OAUTH_ENCRYPTION_KEY environment variable is required. "
            "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string. Returns base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a token string. Returns original plaintext."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_token_encryption.py -v`
Expected: All 8 tests PASS

**Step 6: Commit**

```bash
git add backend/app/core/token_encryption.py backend/app/config.py backend/tests/test_token_encryption.py
git commit -m "feat(oauth): add Fernet token encryption helper and config setting"
```

---

### Task 2: Encrypt Tokens in Google Workspace OAuth Service

**Files:**
- Modify: `backend/app/modules/iso/services/google_workspace_oauth.py:93-101,135-137,156`

**Step 1: Write the failing tests**

Create `backend/tests/modules/iso/test_google_workspace_oauth_encryption.py`:

```python
"""Tests that Google Workspace OAuth service encrypts tokens at rest."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.token_encryption import decrypt_token
from app.models.oauth import OAuthTokenDB
from app.modules.iso.services.google_workspace_oauth import (
    PROVIDER,
    GoogleWorkspaceOAuth,
)

TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def _mock_encryption_key():
    with patch("app.core.token_encryption.get_settings") as mock:
        mock.return_value.oauth_encryption_key = TEST_KEY
        yield


class TestGoogleWorkspaceTokenEncryption:
    """Verify tokens are encrypted before DB storage."""

    @pytest.mark.asyncio
    async def test_exchange_code_encrypts_tokens(self, db_session: AsyncSession) -> None:
        """Tokens from code exchange should be stored encrypted."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "plaintext-access-token",
            "refresh_token": "plaintext-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "test-scope",
        }
        mock_response.raise_for_status = MagicMock()

        with (
            patch("app.modules.iso.services.google_workspace_oauth.httpx.AsyncClient") as mock_client,
            patch("app.modules.iso.services.google_workspace_oauth.get_settings") as mock_settings,
        ):
            mock_settings.return_value.google_workspace_client_id = "client-id"
            mock_settings.return_value.google_workspace_client_secret = "client-secret"
            mock_settings.return_value.google_client_id = ""
            mock_settings.return_value.google_client_secret = ""
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                post=AsyncMock(return_value=mock_response)
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            await GoogleWorkspaceOAuth.exchange_code_for_token(
                code="auth-code", domain="test.com", redirect_uri="http://localhost/callback", db=db_session
            )

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == PROVIDER)
        )
        token = result.scalar_one()

        assert token.access_token != "plaintext-access-token"
        assert token.refresh_token != "plaintext-refresh-token"
        assert decrypt_token(token.access_token) == "plaintext-access-token"
        assert decrypt_token(token.refresh_token) == "plaintext-refresh-token"

    @pytest.mark.asyncio
    async def test_get_valid_token_decrypts(self, db_session: AsyncSession) -> None:
        """get_valid_token should return decrypted access token."""
        from app.core.token_encryption import encrypt_token

        token = OAuthTokenDB(
            provider=PROVIDER,
            access_token=encrypt_token("decrypted-access-token"),
            refresh_token=encrypt_token("decrypted-refresh-token"),
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            site_url="test.com",
        )
        db_session.add(token)
        await db_session.flush()

        result = await GoogleWorkspaceOAuth.get_valid_token(db_session)
        assert result == "decrypted-access-token"

    @pytest.mark.asyncio
    async def test_refresh_token_encrypts_new_tokens(self, db_session: AsyncSession) -> None:
        """Refreshed tokens should be stored encrypted."""
        from app.core.token_encryption import encrypt_token

        existing = OAuthTokenDB(
            provider=PROVIDER,
            access_token=encrypt_token("old-access"),
            refresh_token=encrypt_token("old-refresh"),
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            site_url="test.com",
        )
        db_session.add(existing)
        await db_session.flush()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with (
            patch("app.modules.iso.services.google_workspace_oauth.httpx.AsyncClient") as mock_client,
            patch("app.modules.iso.services.google_workspace_oauth.get_settings") as mock_settings,
        ):
            mock_settings.return_value.google_workspace_client_id = "client-id"
            mock_settings.return_value.google_workspace_client_secret = "client-secret"
            mock_settings.return_value.google_client_id = ""
            mock_settings.return_value.google_client_secret = ""
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                post=AsyncMock(return_value=mock_response)
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            await GoogleWorkspaceOAuth.refresh_token(db_session)

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == PROVIDER)
        )
        token = result.scalar_one()
        assert decrypt_token(token.access_token) == "new-access-token"
        assert decrypt_token(token.refresh_token) == "old-refresh"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/modules/iso/test_google_workspace_oauth_encryption.py -v`
Expected: FAIL — tokens stored as plaintext, assertions fail

**Step 3: Modify `google_workspace_oauth.py` to encrypt/decrypt**

Add import at top of file:

```python
from app.core.token_encryption import decrypt_token, encrypt_token
```

In `exchange_code_for_token` (around line 93-96), encrypt before storing:

```python
        oauth_token = OAuthTokenDB(
            provider=PROVIDER,
            access_token=encrypt_token(token_data["access_token"]),
            refresh_token=encrypt_token(token_data["refresh_token"]) if token_data.get("refresh_token") else None,
            ...
        )
```

In `refresh_token` method (around line 123-124), decrypt refresh token for the API call and encrypt new tokens:

```python
        # Before the httpx call, decrypt the refresh token
        decrypted_refresh = decrypt_token(token.refresh_token)
        # Use decrypted_refresh in the POST data instead of token.refresh_token
```

Then encrypt new values before storing (around lines 135-137):

```python
        token.access_token = encrypt_token(token_data["access_token"])
        if "refresh_token" in token_data:
            token.refresh_token = encrypt_token(token_data["refresh_token"])
```

In `get_valid_token` (around line 159), decrypt before returning:

```python
        return decrypt_token(token.access_token)
```

Also decrypt the access token returned from `refresh_token` call (line 156):

```python
                if refreshed:
                    return decrypt_token(refreshed.access_token)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/modules/iso/test_google_workspace_oauth_encryption.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add backend/app/modules/iso/services/google_workspace_oauth.py backend/tests/modules/iso/test_google_workspace_oauth_encryption.py
git commit -m "feat(oauth): encrypt Google Workspace tokens at service layer"
```

---

### Task 3: Encrypt Tokens in Jira OAuth Service

**Files:**
- Modify: `backend/app/services/oauth_service.py:91-94,126,140-142,173`

**Step 1: Write the failing tests**

Create `backend/tests/test_oauth_service_encryption.py`:

```python
"""Tests that Jira OAuth service encrypts tokens at rest."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.token_encryption import decrypt_token
from app.models.oauth import OAuthTokenDB
from app.services.oauth_service import OAuthService

TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def _mock_encryption_key():
    with patch("app.core.token_encryption.get_settings") as mock:
        mock.return_value.oauth_encryption_key = TEST_KEY
        yield


class TestJiraTokenEncryption:
    """Verify Jira tokens are encrypted before DB storage."""

    @pytest.mark.asyncio
    async def test_exchange_code_encrypts_tokens(self, db_session: AsyncSession) -> None:
        """Tokens from code exchange should be stored encrypted."""
        token_response = MagicMock()
        token_response.json.return_value = {
            "access_token": "jira-access-plain",
            "refresh_token": "jira-refresh-plain",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "read:jira-work",
        }
        token_response.raise_for_status = MagicMock()

        resources_response = MagicMock()
        resources_response.json.return_value = [
            {"id": "cloud-123", "url": "https://test.atlassian.net"}
        ]
        resources_response.raise_for_status = MagicMock()

        mock_http = MagicMock()
        mock_http.post = AsyncMock(return_value=token_response)
        mock_http.get = AsyncMock(return_value=resources_response)

        with patch("app.services.oauth_service.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            await OAuthService.exchange_jira_code_for_token("auth-code", db_session)

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        token = result.scalar_one()

        assert token.access_token != "jira-access-plain"
        assert token.refresh_token != "jira-refresh-plain"
        assert decrypt_token(token.access_token) == "jira-access-plain"
        assert decrypt_token(token.refresh_token) == "jira-refresh-plain"

    @pytest.mark.asyncio
    async def test_get_valid_token_decrypts(self, db_session: AsyncSession) -> None:
        """get_valid_jira_token should return decrypted access token."""
        from app.core.token_encryption import encrypt_token

        token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("decrypted-jira-token"),
            refresh_token=encrypt_token("refresh"),
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(token)
        await db_session.flush()

        result = await OAuthService.get_valid_jira_token(db_session)
        assert result == "decrypted-jira-token"

    @pytest.mark.asyncio
    async def test_refresh_encrypts_new_tokens(self, db_session: AsyncSession) -> None:
        """Refreshed tokens should be stored encrypted."""
        from app.core.token_encryption import encrypt_token

        existing = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("old-access"),
            refresh_token=encrypt_token("old-refresh"),
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(existing)
        await db_session.flush()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-jira-access",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = MagicMock()
        mock_http.post = AsyncMock(return_value=mock_response)

        with patch("app.services.oauth_service.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            await OAuthService.refresh_jira_token(db_session)

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        token = result.scalar_one()
        assert decrypt_token(token.access_token) == "new-jira-access"
        assert decrypt_token(token.refresh_token) == "old-refresh"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_oauth_service_encryption.py -v`
Expected: FAIL — tokens stored as plaintext

**Step 3: Modify `oauth_service.py` to encrypt/decrypt**

Add import at top:

```python
from app.core.token_encryption import decrypt_token, encrypt_token
```

In `exchange_jira_code_for_token` (lines 91-94), encrypt tokens. Note: the `access_token` local var on line 63 is used for the resources API call and must stay plaintext — only encrypt when storing to DB:

```python
        oauth_token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token(token_data["access_token"]),
            refresh_token=encrypt_token(token_data["refresh_token"]) if token_data.get("refresh_token") else None,
            ...
        )
```

In `refresh_jira_token` (line 126), decrypt refresh token for API call:

```python
                    "refresh_token": decrypt_token(token.refresh_token),
```

Encrypt updated tokens (lines 140-142):

```python
        token.access_token = encrypt_token(token_data["access_token"])
        if "refresh_token" in token_data:
            token.refresh_token = encrypt_token(token_data["refresh_token"])
```

In `get_valid_jira_token` (line 170, 173), decrypt returned tokens:

```python
                    return decrypt_token(refreshed_token.access_token)
        ...
        return decrypt_token(token.access_token)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_oauth_service_encryption.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add backend/app/services/oauth_service.py backend/tests/test_oauth_service_encryption.py
git commit -m "feat(oauth): encrypt Jira tokens at service layer"
```

---

### Task 4: OAuth State DB Model & Migration

**Files:**
- Modify: `backend/app/models/oauth.py` (add `OAuthStateDB`)
- Create: `backend/alembic/versions/015_add_oauth_states_table.py`

**Step 1: Add `OAuthStateDB` model**

Add to `backend/app/models/oauth.py` after `OAuthTokenDB`:

```python
class OAuthStateDB(Base):
    """DB-backed OAuth CSRF state tokens."""

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

**Step 2: Create Alembic migration**

Create `backend/alembic/versions/015_add_oauth_states_table.py`:

```python
"""Add oauth_states table for CSRF protection

Revision ID: 015_add_oauth_states
Revises: 014_add_iso_access_tables
Create Date: 2026-02-26

Replaces in-memory OAuthStateManager._states dict with DB table
for multi-worker support.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015_add_oauth_states"
down_revision: Union[str, None] = "014_add_iso_access_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("state", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("oauth_states")
```

**Step 3: Commit**

```bash
git add backend/app/models/oauth.py backend/alembic/versions/015_add_oauth_states_table.py
git commit -m "feat(oauth): add OAuthStateDB model and migration"
```

---

### Task 5: Rewrite OAuthStateManager to Use DB

**Files:**
- Modify: `backend/app/core/oauth_state.py` (full rewrite)
- Modify: `backend/tests/test_oauth_state.py` (full rewrite)

**Step 1: Write the failing tests**

Rewrite `backend/tests/test_oauth_state.py`:

```python
"""Tests for DB-backed OAuth state manager CSRF protection.

Tests that OAuth CSRF state tokens are stored in the database (not in-memory),
support multi-worker deployments, and enforce one-time use with TTL.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.oauth_state import OAuthStateManager
from app.models.oauth import OAuthStateDB


class TestOAuthStateGenerate:
    """Test OAuth state token generation."""

    @pytest.mark.asyncio
    async def test_generate_returns_unique_tokens(self, db_session: AsyncSession) -> None:
        """Each call should return a different token."""
        state1 = await OAuthStateManager.generate_state(db_session)
        state2 = await OAuthStateManager.generate_state(db_session)

        assert state1 != state2
        assert isinstance(state1, str)
        assert len(state1) > 0

    @pytest.mark.asyncio
    async def test_generate_stores_in_db(self, db_session: AsyncSession) -> None:
        """Token should be persisted in oauth_states table."""
        state = await OAuthStateManager.generate_state(db_session)

        result = await db_session.execute(
            select(OAuthStateDB).where(OAuthStateDB.state == state)
        )
        row = result.scalar_one_or_none()
        assert row is not None

    @pytest.mark.asyncio
    async def test_generate_sets_10_minute_expiry(self, db_session: AsyncSession) -> None:
        """Token should expire ~10 minutes from creation."""
        before = datetime.now(timezone.utc)
        state = await OAuthStateManager.generate_state(db_session)
        after = datetime.now(timezone.utc)

        result = await db_session.execute(
            select(OAuthStateDB).where(OAuthStateDB.state == state)
        )
        row = result.scalar_one()

        expected_min = before + timedelta(minutes=10)
        expected_max = after + timedelta(minutes=10)
        assert expected_min <= row.expires_at <= expected_max


class TestOAuthStateValidate:
    """Test OAuth state token validation."""

    @pytest.mark.asyncio
    async def test_validate_valid_token_returns_true(self, db_session: AsyncSession) -> None:
        """Valid unexpired token should be accepted."""
        state = await OAuthStateManager.generate_state(db_session)
        assert await OAuthStateManager.validate_state(state, db_session) is True

    @pytest.mark.asyncio
    async def test_validate_unknown_token_returns_false(self, db_session: AsyncSession) -> None:
        """Unknown token should be rejected."""
        result = await OAuthStateManager.validate_state("unknown-token-12345", db_session)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_expired_token_returns_false(self, db_session: AsyncSession) -> None:
        """Expired token should be rejected and deleted."""
        expired = OAuthStateDB(
            state="expired-token",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(expired)
        await db_session.flush()

        result = await OAuthStateManager.validate_state("expired-token", db_session)
        assert result is False

        row = await db_session.execute(
            select(OAuthStateDB).where(OAuthStateDB.state == "expired-token")
        )
        assert row.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_validate_consumes_token(self, db_session: AsyncSession) -> None:
        """Token should be deleted after successful validation."""
        state = await OAuthStateManager.generate_state(db_session)
        assert await OAuthStateManager.validate_state(state, db_session) is True

        row = await db_session.execute(
            select(OAuthStateDB).where(OAuthStateDB.state == state)
        )
        assert row.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_validate_same_token_twice_fails(self, db_session: AsyncSession) -> None:
        """Second use of same token should fail."""
        state = await OAuthStateManager.generate_state(db_session)
        assert await OAuthStateManager.validate_state(state, db_session) is True
        assert await OAuthStateManager.validate_state(state, db_session) is False


class TestOAuthStateCleanup:
    """Test cleanup of expired state tokens."""

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired(self, db_session: AsyncSession) -> None:
        """cleanup_expired should remove expired tokens."""
        db_session.add(OAuthStateDB(
            state="expired-1",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ))
        db_session.add(OAuthStateDB(
            state="expired-2",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=15),
        ))
        await db_session.flush()

        removed = await OAuthStateManager.cleanup_expired(db_session)
        assert removed == 2

    @pytest.mark.asyncio
    async def test_cleanup_keeps_valid(self, db_session: AsyncSession) -> None:
        """cleanup_expired should keep valid unexpired tokens."""
        db_session.add(OAuthStateDB(
            state="expired",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        ))
        db_session.add(OAuthStateDB(
            state="valid",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        ))
        await db_session.flush()

        removed = await OAuthStateManager.cleanup_expired(db_session)
        assert removed == 1

        row = await db_session.execute(
            select(OAuthStateDB).where(OAuthStateDB.state == "valid")
        )
        assert row.scalar_one_or_none() is not None
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_oauth_state.py -v`
Expected: FAIL — `OAuthStateManager.generate_state` is not async / wrong signature

**Step 3: Rewrite `oauth_state.py`**

Replace `backend/app/core/oauth_state.py` entirely:

```python
"""DB-backed OAuth state management for CSRF protection."""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth import OAuthStateDB


class OAuthStateManager:
    """
    Manages OAuth state tokens in the database.

    Supports multi-worker deployments — any worker can validate
    a state token generated by any other worker.
    """

    @staticmethod
    async def generate_state(db: AsyncSession) -> str:
        """Generate a cryptographically secure state token and persist it."""
        state = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        db.add(OAuthStateDB(state=state, expires_at=expires_at))
        await db.flush()

        await OAuthStateManager.cleanup_expired(db)

        return state

    @staticmethod
    async def validate_state(state: str, db: AsyncSession) -> bool:
        """Validate and consume a state token (one-time use)."""
        result = await db.execute(
            select(OAuthStateDB).where(OAuthStateDB.state == state)
        )
        row = result.scalar_one_or_none()

        if row is None:
            return False

        await db.delete(row)
        await db.flush()

        if datetime.now(timezone.utc) > row.expires_at:
            return False

        return True

    @staticmethod
    async def cleanup_expired(db: AsyncSession) -> int:
        """Remove expired states. Returns count of removed rows."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            delete(OAuthStateDB).where(OAuthStateDB.expires_at < now)
        )
        return result.rowcount
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_oauth_state.py -v`
Expected: All 9 tests PASS

**Step 5: Commit**

```bash
git add backend/app/core/oauth_state.py backend/tests/test_oauth_state.py
git commit -m "feat(oauth): rewrite OAuthStateManager with DB backing"
```

---

### Task 6: Update OAuth API Callers for Async State Manager

**Files:**
- Modify: `backend/app/api/oauth.py:27-44,78` (add `db` to authorize, async state calls)
- Modify: `backend/app/modules/iso/api/config.py:38,71` (async state calls)
- Modify: `backend/tests/test_oauth_api.py` (update mocks)

**Step 1: Update `backend/app/api/oauth.py`**

The `authorize_jira` endpoint (line 29) doesn't currently take `db`. Add `DBSession` dependency:

```python
@router.get("/jira/authorize")
@limiter.limit("10/minute")
async def authorize_jira(request: Request, current_user: CurrentUser, db: DBSession) -> RedirectResponse:
    state = await OAuthStateManager.generate_state(db)
    ...
    request.session["oauth_state"] = state
    return RedirectResponse(url=authorization_url)
```

In `jira_callback` (line 78), update validate call:

```python
        if not await OAuthStateManager.validate_state(state, db):
```

**Step 2: Update `backend/app/modules/iso/api/config.py`**

In `authorize_google_workspace` (line 38):

```python
    state = await OAuthStateManager.generate_state(db)
```

In `google_workspace_callback` (line 71):

```python
    if not await OAuthStateManager.validate_state(state, db):
```

**Step 3: Update `backend/tests/test_oauth_api.py`**

Remove all `OAuthStateManager._states.clear()` calls. Replace direct `OAuthStateManager.generate_state()` calls with mocked async versions or DB-based setup. The key changes:

- Replace `OAuthStateManager._states.clear()` → remove (DB is clean per test)
- Replace `OAuthStateManager.generate_state()` → `await OAuthStateManager.generate_state(db_session)`
- Replace `len(OAuthStateManager._states) > 0` → query `OAuthStateDB` table
- Tests that check state count should query the DB table

For tests that don't have `db_session` but need state, mock the state manager:

```python
with patch("app.api.oauth.OAuthStateManager") as mock_state:
    mock_state.generate_state = AsyncMock(return_value="test-state")
    mock_state.validate_state = AsyncMock(return_value=True)
```

**Step 4: Run all OAuth-related tests**

Run: `cd backend && python -m pytest tests/test_oauth_api.py tests/test_oauth_state.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/api/oauth.py backend/app/modules/iso/api/config.py backend/tests/test_oauth_api.py
git commit -m "feat(oauth): wire async OAuthStateManager into API endpoints"
```

---

### Task 7: Alembic Data Migration — Encrypt Existing Tokens

**Files:**
- Create: `backend/alembic/versions/016_encrypt_existing_oauth_tokens.py`

**Step 1: Create the data migration**

```python
"""Encrypt existing plaintext OAuth tokens

Revision ID: 016_encrypt_tokens
Revises: 015_add_oauth_states
Create Date: 2026-02-26

One-time migration: reads existing oauth_tokens rows and encrypts
access_token and refresh_token using OAUTH_ENCRYPTION_KEY.
Requires the env var to be set before running.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet

revision: str = "016_encrypt_tokens"
down_revision: Union[str, None] = "015_add_oauth_states"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OAUTH_TOKENS = sa.table(
    "oauth_tokens",
    sa.column("id", sa.Uuid),
    sa.column("access_token", sa.Text),
    sa.column("refresh_token", sa.Text),
)


def _get_fernet() -> Fernet:
    import os
    key = os.environ.get("OAUTH_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError(
            "OAUTH_ENCRYPTION_KEY must be set before running this migration. "
            "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def _is_fernet_token(value: str) -> bool:
    """Check if a value looks like it's already Fernet-encrypted (base64 with gAAAAA prefix)."""
    return value.startswith("gAAAAA")


def upgrade() -> None:
    conn = op.get_bind()
    f = _get_fernet()

    rows = conn.execute(sa.select(OAUTH_TOKENS)).fetchall()
    for row in rows:
        updates = {}
        if row.access_token and not _is_fernet_token(row.access_token):
            updates["access_token"] = f.encrypt(row.access_token.encode()).decode()
        if row.refresh_token and not _is_fernet_token(row.refresh_token):
            updates["refresh_token"] = f.encrypt(row.refresh_token.encode()).decode()

        if updates:
            conn.execute(
                OAUTH_TOKENS.update()
                .where(OAUTH_TOKENS.c.id == row.id)
                .values(**updates)
            )


def downgrade() -> None:
    conn = op.get_bind()
    f = _get_fernet()

    rows = conn.execute(sa.select(OAUTH_TOKENS)).fetchall()
    for row in rows:
        updates = {}
        if row.access_token and _is_fernet_token(row.access_token):
            updates["access_token"] = f.decrypt(row.access_token.encode()).decode()
        if row.refresh_token and _is_fernet_token(row.refresh_token):
            updates["refresh_token"] = f.decrypt(row.refresh_token.encode()).decode()

        if updates:
            conn.execute(
                OAUTH_TOKENS.update()
                .where(OAUTH_TOKENS.c.id == row.id)
                .values(**updates)
            )
```

**Step 2: Commit**

```bash
git add backend/alembic/versions/016_encrypt_existing_oauth_tokens.py
git commit -m "feat(oauth): add data migration to encrypt existing tokens"
```

---

### Task 8: Add `cryptography` Dependency & Env Docs

**Files:**
- Modify: `backend/requirements.txt` (add explicit `cryptography` dependency)
- Modify: `backend/.env.example` (add `OAUTH_ENCRYPTION_KEY` if file exists)

**Step 1: Add `cryptography` to requirements.txt**

Even though it's pulled in by `python-jose[cryptography]`, add it explicitly since we now depend on Fernet directly:

```
cryptography>=42.0.0,<44.0.0
```

Add after line 8 (under `# Security` section).

**Step 2: Add env var to `.env.example` if it exists**

Add `OAUTH_ENCRYPTION_KEY=` with a comment about generation.

**Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add explicit cryptography dependency and env docs"
```

---

### Task 9: Run Full Test Suite & Fix Breakage

**Step 1: Run all backend tests**

Run: `cd backend && python -m pytest --tb=short -q`

This will catch any tests that break due to:
- `OAuthStateManager` now being async (any test that calls it synchronously)
- Token values now being encrypted (any test that asserts plaintext token values from DB)
- Missing `OAUTH_ENCRYPTION_KEY` in test env

**Step 2: Fix test fixtures**

If tests fail due to missing encryption key, add to `conftest.py`:

```python
@pytest.fixture(autouse=True)
def _mock_encryption_key(monkeypatch):
    """Provide encryption key for all tests."""
    from cryptography.fernet import Fernet
    monkeypatch.setenv("OAUTH_ENCRYPTION_KEY", Fernet.generate_key().decode())
```

Or mock at the module level. The exact fix depends on which tests break.

**Step 3: Fix any remaining failures and commit**

```bash
git add -u
git commit -m "fix(tests): update test suite for encrypted tokens and async state"
```

---

### Task 10: Final Verification

**Step 1: Run full test suite**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: All ~970+ tests PASS

**Step 2: Run linting**

Run: `cd backend && ruff check app/ && black --check app/`
Expected: Clean

**Step 3: Verify migrations**

Run: `cd backend && alembic heads`
Expected: Shows `016_encrypt_tokens` as the latest head

**Step 4: Final commit if any cleanup needed**

```bash
git commit -m "chore: final cleanup for OAuth encryption and state management"
```
