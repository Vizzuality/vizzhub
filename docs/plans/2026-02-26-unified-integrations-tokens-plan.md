# Unified Integration Tokens — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate all provider tokens (Jira, Google, GitHub, Slack) into `oauth_tokens` with Fernet encryption, replace `slack_config` with `integration_settings`, and unify the admin UI.

**Architecture:** New `IntegrationSettingDB` model for non-token config. Alembic migration moves Slack data, drops `slack_config`. New `/admin/integrations/` endpoints. `GitHubClient` reads PAT from DB instead of env var. Frontend renders 4 provider cards in the existing IntegrationsTab.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Fernet encryption, React, TypeScript, TanStack Query, Tailwind CSS

**Design doc:** `docs/plans/2026-02-26-unified-integrations-tokens-design.md`

---

### Task 1: IntegrationSettingDB Model

**Files:**
- Create: `backend/app/models/integration_setting.py`
- Modify: `backend/app/models/__init__.py` (if exists, to export new model)
- Test: `backend/tests/test_integration_settings_model.py`

**Step 1: Write the failing test**

```python
"""Tests for IntegrationSettingDB model."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.integration_setting import IntegrationSettingDB


class TestIntegrationSettingDB:
    @pytest.mark.asyncio
    async def test_create_setting(self, db_session) -> None:
        setting = IntegrationSettingDB(
            provider="slack",
            key="leadership_channel_id",
            value="C12345678",
        )
        db_session.add(setting)
        await db_session.commit()
        await db_session.refresh(setting)

        assert setting.id is not None
        assert setting.provider == "slack"
        assert setting.key == "leadership_channel_id"
        assert setting.value == "C12345678"
        assert setting.created_at is not None
        assert setting.updated_at is not None

    @pytest.mark.asyncio
    async def test_unique_constraint_provider_key(self, db_session) -> None:
        s1 = IntegrationSettingDB(provider="slack", key="channel", value="C1")
        db_session.add(s1)
        await db_session.commit()

        s2 = IntegrationSettingDB(provider="slack", key="channel", value="C2")
        db_session.add(s2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
```

**Step 2: Run test to verify it fails**

Run: `pushd backend > /dev/null && python -m pytest tests/test_integration_settings_model.py -v && popd > /dev/null`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.integration_setting'`

**Step 3: Write minimal implementation**

Create `backend/app/models/integration_setting.py`:

```python
"""Integration settings model for non-token provider configuration."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class IntegrationSettingDB(Base):
    """Key-value settings per integration provider."""

    __tablename__ = "integration_settings"
    __table_args__ = (
        UniqueConstraint("provider", "key", name="uq_integration_settings_provider_key"),
    )

    id: Mapped[uuid4] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now()
    )
```

**Step 4: Run test to verify it passes**

Run: `pushd backend > /dev/null && python -m pytest tests/test_integration_settings_model.py -v && popd > /dev/null`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/models/integration_setting.py backend/tests/test_integration_settings_model.py
git commit -m "feat: add IntegrationSettingDB model"
```

---

### Task 2: Alembic Migration — create `integration_settings`, migrate Slack data, drop `slack_config`

**Files:**
- Create: `backend/alembic/versions/017_unify_integration_tokens.py`

**Context:**
- Previous migration: `016_encrypt_existing_oauth_tokens` (revision ID is in the file)
- `slack_config` has columns: `id`, `bot_token_encrypted` (plaintext!), `leadership_channel_id`, `created_at`, `updated_at`
- The bot token must be encrypted with Fernet before inserting into `oauth_tokens`
- Use `encrypt_token` from `app.core.token_encryption`

**Step 1: Write the migration**

Read the latest migration file (`backend/alembic/versions/016_encrypt_existing_oauth_tokens.py`) to get its revision ID for the `down_revision`. Then create:

```python
"""Unify integration tokens.

Create integration_settings table, migrate Slack data from slack_config
to oauth_tokens (encrypted) and integration_settings, drop slack_config.

Revision ID: 017
Revises: <016_revision_id>
"""

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


def _encrypt_token(plaintext: str) -> str:
    """Encrypt using same Fernet approach as app.core.token_encryption."""
    from app.core.token_encryption import encrypt_token
    return encrypt_token(plaintext)


def upgrade() -> None:
    # 1. Create integration_settings table
    op.create_table(
        "integration_settings",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("provider", sa.String(50), nullable=False, index=True),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "key", name="uq_integration_settings_provider_key"),
    )

    # 2. Migrate data from slack_config
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT bot_token_encrypted, leadership_channel_id FROM slack_config LIMIT 1"))
    row = result.fetchone()

    if row:
        # Migrate leadership_channel_id to integration_settings
        if row.leadership_channel_id:
            conn.execute(
                sa.text(
                    "INSERT INTO integration_settings (id, provider, key, value) "
                    "VALUES (:id, 'slack', 'leadership_channel_id', :value)"
                ),
                {"id": str(uuid.uuid4()), "value": row.leadership_channel_id},
            )

        # Migrate bot token to oauth_tokens (encrypt it)
        if row.bot_token_encrypted:
            encrypted = _encrypt_token(row.bot_token_encrypted)
            now = datetime.now(timezone.utc)
            conn.execute(
                sa.text(
                    "INSERT INTO oauth_tokens (id, provider, access_token, token_type, created_at, updated_at) "
                    "VALUES (:id, 'slack', :token, 'bot', :now, :now)"
                ),
                {"id": str(uuid.uuid4()), "token": encrypted, "now": now},
            )

    # 3. Drop slack_config table
    op.drop_table("slack_config")


def downgrade() -> None:
    # Recreate slack_config (data is lost — requires DB backup)
    op.create_table(
        "slack_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_token_encrypted", sa.Text(), nullable=True),
        sa.Column("leadership_channel_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.drop_table("integration_settings")
```

**Step 2: Run migration against test DB to verify**

Run: `pushd backend > /dev/null && alembic upgrade head && popd > /dev/null`
Expected: Migration applies without errors.

**Step 3: Run existing tests to check nothing breaks**

Run: `pushd backend > /dev/null && python -m pytest tests/test_integration_settings_model.py -v && popd > /dev/null`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/alembic/versions/017_unify_integration_tokens.py
git commit -m "feat: add migration to unify integration tokens"
```

---

### Task 3: Integration token service — shared read/write helpers

**Files:**
- Create: `backend/app/services/integration_token_service.py`
- Test: `backend/tests/test_integration_token_service.py`

**Step 1: Write the failing tests**

```python
"""Tests for IntegrationTokenService."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.integration_setting import IntegrationSettingDB
from app.models.oauth import OAuthTokenDB
from app.services.integration_token_service import IntegrationTokenService


class TestGetToken:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_token(self, db_session) -> None:
        result = await IntegrationTokenService.get_token(db_session, "github")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_decrypted_token(self, db_session) -> None:
        from app.core.token_encryption import encrypt_token
        encrypted = encrypt_token("ghp_test123")
        token = OAuthTokenDB(provider="github", access_token=encrypted, token_type="pat")
        db_session.add(token)
        await db_session.commit()

        result = await IntegrationTokenService.get_token(db_session, "github")
        assert result == "ghp_test123"


class TestSaveToken:
    @pytest.mark.asyncio
    async def test_saves_encrypted_token(self, db_session) -> None:
        from app.core.token_encryption import decrypt_token
        await IntegrationTokenService.save_token(
            db_session, provider="github", token="ghp_abc", token_type="pat",
            expires_in_days=365,
        )

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "github")
        )
        row = result.scalar_one()
        assert decrypt_token(row.access_token) == "ghp_abc"
        assert row.token_type == "pat"
        assert row.expires_at is not None

    @pytest.mark.asyncio
    async def test_replaces_existing_token(self, db_session) -> None:
        await IntegrationTokenService.save_token(
            db_session, provider="slack", token="xoxb-old", token_type="bot",
        )
        await IntegrationTokenService.save_token(
            db_session, provider="slack", token="xoxb-new", token_type="bot",
        )

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "slack")
        )
        rows = result.scalars().all()
        assert len(rows) == 1


class TestDeleteToken:
    @pytest.mark.asyncio
    async def test_deletes_token(self, db_session) -> None:
        await IntegrationTokenService.save_token(
            db_session, provider="github", token="ghp_x", token_type="pat",
        )
        deleted = await IntegrationTokenService.delete_token(db_session, "github")
        assert deleted is True

        result = await IntegrationTokenService.get_token(db_session, "github")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, db_session) -> None:
        deleted = await IntegrationTokenService.delete_token(db_session, "github")
        assert deleted is False


class TestGetSetting:
    @pytest.mark.asyncio
    async def test_returns_none_when_missing(self, db_session) -> None:
        result = await IntegrationTokenService.get_setting(db_session, "slack", "channel")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_value(self, db_session) -> None:
        setting = IntegrationSettingDB(provider="slack", key="leadership_channel_id", value="C123")
        db_session.add(setting)
        await db_session.commit()

        result = await IntegrationTokenService.get_setting(db_session, "slack", "leadership_channel_id")
        assert result == "C123"


class TestSetSetting:
    @pytest.mark.asyncio
    async def test_creates_new_setting(self, db_session) -> None:
        await IntegrationTokenService.set_setting(db_session, "slack", "leadership_channel_id", "C999")
        result = await IntegrationTokenService.get_setting(db_session, "slack", "leadership_channel_id")
        assert result == "C999"

    @pytest.mark.asyncio
    async def test_updates_existing_setting(self, db_session) -> None:
        await IntegrationTokenService.set_setting(db_session, "slack", "leadership_channel_id", "C111")
        await IntegrationTokenService.set_setting(db_session, "slack", "leadership_channel_id", "C222")
        result = await IntegrationTokenService.get_setting(db_session, "slack", "leadership_channel_id")
        assert result == "C222"


class TestGetProviderStatus:
    @pytest.mark.asyncio
    async def test_disconnected_status(self, db_session) -> None:
        status = await IntegrationTokenService.get_provider_status(db_session, "github")
        assert status["connected"] is False
        assert status["expires_at"] is None

    @pytest.mark.asyncio
    async def test_connected_status_with_expiry(self, db_session) -> None:
        await IntegrationTokenService.save_token(
            db_session, provider="github", token="ghp_x", token_type="pat",
            expires_in_days=365,
        )
        status = await IntegrationTokenService.get_provider_status(db_session, "github")
        assert status["connected"] is True
        assert status["expires_at"] is not None
```

**Step 2: Run test to verify it fails**

Run: `pushd backend > /dev/null && python -m pytest tests/test_integration_token_service.py -v && popd > /dev/null`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

Create `backend/app/services/integration_token_service.py`:

```python
"""Shared service for reading/writing integration tokens and settings."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.token_encryption import decrypt_token, encrypt_token
from app.models.integration_setting import IntegrationSettingDB
from app.models.oauth import OAuthTokenDB


class IntegrationTokenService:

    @staticmethod
    async def get_token(db: AsyncSession, provider: str) -> str | None:
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == provider)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return decrypt_token(row.access_token)

    @staticmethod
    async def get_token_record(db: AsyncSession, provider: str) -> OAuthTokenDB | None:
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == provider)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def save_token(
        db: AsyncSession,
        *,
        provider: str,
        token: str,
        token_type: str,
        expires_in_days: int | None = None,
    ) -> OAuthTokenDB:
        await db.execute(
            delete(OAuthTokenDB).where(OAuthTokenDB.provider == provider)
        )
        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        record = OAuthTokenDB(
            provider=provider,
            access_token=encrypt_token(token),
            token_type=token_type,
            expires_at=expires_at,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def delete_token(db: AsyncSession, provider: str) -> bool:
        result = await db.execute(
            delete(OAuthTokenDB).where(OAuthTokenDB.provider == provider)
        )
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def get_setting(db: AsyncSession, provider: str, key: str) -> str | None:
        result = await db.execute(
            select(IntegrationSettingDB).where(
                IntegrationSettingDB.provider == provider,
                IntegrationSettingDB.key == key,
            )
        )
        row = result.scalar_one_or_none()
        return row.value if row else None

    @staticmethod
    async def set_setting(db: AsyncSession, provider: str, key: str, value: str) -> None:
        result = await db.execute(
            select(IntegrationSettingDB).where(
                IntegrationSettingDB.provider == provider,
                IntegrationSettingDB.key == key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
        else:
            db.add(IntegrationSettingDB(provider=provider, key=key, value=value))
        await db.commit()

    @staticmethod
    async def get_provider_status(db: AsyncSession, provider: str) -> dict:
        record = await IntegrationTokenService.get_token_record(db, provider)
        if record is None:
            return {"connected": False, "expires_at": None, "token_type": None}
        return {
            "connected": True,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            "token_type": record.token_type,
            "site_url": record.site_url,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }
```

**Step 4: Run test to verify it passes**

Run: `pushd backend > /dev/null && python -m pytest tests/test_integration_token_service.py -v && popd > /dev/null`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/integration_token_service.py backend/tests/test_integration_token_service.py
git commit -m "feat: add IntegrationTokenService for unified token management"
```

---

### Task 4: Admin integrations API endpoints

**Files:**
- Create: `backend/app/api/integrations_admin.py`
- Create: `backend/app/api/schemas/integrations.py`
- Test: `backend/tests/test_integrations_admin_api.py`

**Step 1: Write the failing tests**

```python
"""Tests for admin integrations API."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.token_encryption import encrypt_token
from app.models.integration_setting import IntegrationSettingDB
from app.models.oauth import OAuthTokenDB


class TestIntegrationsStatus:
    @pytest.mark.asyncio
    async def test_all_disconnected(self, client: AsyncClient) -> None:
        response = await client.get("/api/admin/integrations/status")
        assert response.status_code == 200
        data = response.json()
        assert data["github"]["connected"] is False
        assert data["slack"]["connected"] is False
        assert data["jira"]["connected"] is False
        assert data["google_workspace"]["connected"] is False


class TestGitHubIntegration:
    @pytest.mark.asyncio
    async def test_save_github_pat(self, client: AsyncClient) -> None:
        response = await client.put(
            "/api/admin/integrations/github",
            json={"token": "ghp_test12345"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["expires_at"] is not None

    @pytest.mark.asyncio
    async def test_delete_github_token(self, client: AsyncClient, db_session) -> None:
        token = OAuthTokenDB(
            provider="github",
            access_token=encrypt_token("ghp_test"),
            token_type="pat",
        )
        db_session.add(token)
        await db_session.commit()

        response = await client.delete("/api/admin/integrations/github")
        assert response.status_code == 200


class TestSlackIntegration:
    @pytest.mark.asyncio
    async def test_save_slack_token(self, client: AsyncClient) -> None:
        response = await client.put(
            "/api/admin/integrations/slack",
            json={"token": "xoxb-test-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True

    @pytest.mark.asyncio
    async def test_update_slack_settings(self, client: AsyncClient) -> None:
        response = await client.put(
            "/api/admin/integrations/slack/settings",
            json={"leadership_channel_id": "C12345"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_slack_token(self, client: AsyncClient, db_session) -> None:
        token = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test"),
            token_type="bot",
        )
        db_session.add(token)
        await db_session.commit()

        response = await client.delete("/api/admin/integrations/slack")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_slack_channels(self, client: AsyncClient, db_session) -> None:
        token = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test"),
            token_type="bot",
        )
        db_session.add(token)
        await db_session.commit()

        with patch(
            "app.api.integrations_admin.SlackService.list_channels",
            new_callable=AsyncMock,
            return_value=[{"id": "C1", "name": "general", "is_private": False}],
        ):
            response = await client.get("/api/admin/integrations/slack/channels")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_slack_test_connection(self, client: AsyncClient, db_session) -> None:
        token = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test"),
            token_type="bot",
        )
        db_session.add(token)
        await db_session.commit()

        with patch(
            "app.api.integrations_admin.SlackService.test_connection",
            new_callable=AsyncMock,
            return_value={"ok": True, "team": "TestTeam", "bot_id": "B1"},
        ):
            response = await client.post("/api/admin/integrations/slack/test")
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
```

**Step 2: Run test to verify it fails**

Run: `pushd backend > /dev/null && python -m pytest tests/test_integrations_admin_api.py -v && popd > /dev/null`
Expected: FAIL

**Step 3: Write Pydantic schemas**

Create `backend/app/api/schemas/integrations.py`:

```python
"""Schemas for admin integrations API."""

from pydantic import BaseModel, Field


class ProviderStatus(BaseModel):
    connected: bool
    expires_at: str | None = None
    token_type: str | None = None
    site_url: str | None = None
    created_at: str | None = None


class AllIntegrationsStatus(BaseModel):
    jira: ProviderStatus
    google_workspace: ProviderStatus
    github: ProviderStatus
    slack: ProviderStatus
    slack_settings: dict[str, str | None] = {}


class GitHubTokenInput(BaseModel):
    token: str = Field(..., min_length=1, description="GitHub Personal Access Token")


class SlackTokenInput(BaseModel):
    token: str = Field(..., min_length=1, description="Slack bot token (xoxb-...)")


class SlackSettingsUpdate(BaseModel):
    leadership_channel_id: str | None = Field(None, max_length=50)
```

**Step 4: Write the API router**

Create `backend/app/api/integrations_admin.py`:

```python
"""Admin integrations API — unified token management for all providers."""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import AdminUser, CurrentUser, DBSession, limiter
from app.api.schemas.integrations import (
    AllIntegrationsStatus,
    GitHubTokenInput,
    ProviderStatus,
    SlackSettingsUpdate,
    SlackTokenInput,
)
from app.api.schemas.slack import SlackChannel, SlackTestResult
from app.services.integration_token_service import IntegrationTokenService
from app.services.slack_service import SlackService

logger = logging.getLogger(__name__)

GITHUB_PAT_EXPIRY_DAYS = 365

router = APIRouter(prefix="/admin/integrations", tags=["integrations-admin"])


@router.get("/status")
@limiter.limit("100/minute")
async def get_all_integrations_status(
    request: Request, current_user: CurrentUser, db: DBSession
) -> AllIntegrationsStatus:
    jira = await IntegrationTokenService.get_provider_status(db, "jira")
    google = await IntegrationTokenService.get_provider_status(db, "google_workspace")
    github = await IntegrationTokenService.get_provider_status(db, "github")
    slack = await IntegrationTokenService.get_provider_status(db, "slack")

    leadership_channel = await IntegrationTokenService.get_setting(
        db, "slack", "leadership_channel_id"
    )

    return AllIntegrationsStatus(
        jira=ProviderStatus(**jira),
        google_workspace=ProviderStatus(**google),
        github=ProviderStatus(**github),
        slack=ProviderStatus(**slack),
        slack_settings={"leadership_channel_id": leadership_channel},
    )


# --- GitHub ---

@router.put("/github")
@limiter.limit("10/minute")
async def save_github_token(
    request: Request, current_user: AdminUser, db: DBSession, body: GitHubTokenInput
) -> ProviderStatus:
    await IntegrationTokenService.save_token(
        db, provider="github", token=body.token, token_type="pat",
        expires_in_days=GITHUB_PAT_EXPIRY_DAYS,
    )
    status_data = await IntegrationTokenService.get_provider_status(db, "github")
    return ProviderStatus(**status_data)


@router.delete("/github")
@limiter.limit("10/minute")
async def delete_github_token(
    request: Request, current_user: AdminUser, db: DBSession
) -> dict[str, str]:
    deleted = await IntegrationTokenService.delete_token(db, "github")
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No GitHub token found")
    return {"status": "disconnected"}


# --- Slack ---

@router.put("/slack")
@limiter.limit("10/minute")
async def save_slack_token(
    request: Request, current_user: AdminUser, db: DBSession, body: SlackTokenInput
) -> ProviderStatus:
    await IntegrationTokenService.save_token(
        db, provider="slack", token=body.token, token_type="bot",
    )
    status_data = await IntegrationTokenService.get_provider_status(db, "slack")
    return ProviderStatus(**status_data)


@router.delete("/slack")
@limiter.limit("10/minute")
async def delete_slack_token(
    request: Request, current_user: AdminUser, db: DBSession
) -> dict[str, str]:
    deleted = await IntegrationTokenService.delete_token(db, "slack")
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Slack token found")
    return {"status": "disconnected"}


@router.put("/slack/settings")
@limiter.limit("10/minute")
async def update_slack_settings(
    request: Request, current_user: AdminUser, db: DBSession, body: SlackSettingsUpdate
) -> dict[str, str | None]:
    if body.leadership_channel_id is not None:
        await IntegrationTokenService.set_setting(
            db, "slack", "leadership_channel_id", body.leadership_channel_id
        )
    channel = await IntegrationTokenService.get_setting(db, "slack", "leadership_channel_id")
    return {"leadership_channel_id": channel}


@router.get("/slack/channels")
@limiter.limit("10/minute")
async def list_slack_channels(
    request: Request, current_user: CurrentUser, db: DBSession
) -> list[SlackChannel]:
    token = await IntegrationTokenService.get_token(db, "slack")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No Slack bot token configured"
        )
    try:
        channels = await SlackService.list_channels(token)
        return [
            SlackChannel(id=ch["id"], name=ch["name"], is_private=ch.get("is_private", False))
            for ch in channels
        ]
    except Exception as e:
        logger.exception("Failed to list Slack channels")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list channels: {e}",
        )


@router.post("/slack/test")
@limiter.limit("10/minute")
async def test_slack_connection(
    request: Request, current_user: AdminUser, db: DBSession
) -> SlackTestResult:
    token = await IntegrationTokenService.get_token(db, "slack")
    if not token:
        return SlackTestResult(ok=False, error="No bot token configured")
    try:
        result = await SlackService.test_connection(token)
        if result.get("ok"):
            return SlackTestResult(ok=True, team=result.get("team"), bot_id=result.get("bot_id"))
        return SlackTestResult(ok=False, error=result.get("error", "Unknown error"))
    except Exception as e:
        logger.exception("Failed to test Slack connection")
        return SlackTestResult(ok=False, error=str(e))
```

**Step 5: Mount the new router in `main.py`**

In `backend/app/main.py`, add import and mount:

```python
from app.api.integrations_admin import router as integrations_admin_router
# ...
app.include_router(integrations_admin_router, prefix="/api")
```

**Step 6: Run tests to verify they pass**

Run: `pushd backend > /dev/null && python -m pytest tests/test_integrations_admin_api.py -v && popd > /dev/null`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/app/api/integrations_admin.py backend/app/api/schemas/integrations.py backend/tests/test_integrations_admin_api.py backend/app/main.py
git commit -m "feat: add admin integrations API endpoints"
```

---

### Task 5: Update GitHubClient to read PAT from DB

**Files:**
- Modify: `backend/app/services/collectors/github/client.py`
- Modify: `backend/tests/test_github_collector.py`

**Step 1: Write the failing test**

Add test to `backend/tests/test_github_collector.py`:

```python
class TestGitHubClientFromDB:
    @pytest.mark.asyncio
    async def test_github_client_reads_token_from_db(self, db_session) -> None:
        """Client should prefer DB token over env var."""
        from app.core.token_encryption import encrypt_token
        from app.models.oauth import OAuthTokenDB

        token = OAuthTokenDB(
            provider="github",
            access_token=encrypt_token("ghp_from_db"),
            token_type="pat",
        )
        db_session.add(token)
        await db_session.commit()

        # This test verifies the new DB-based token retrieval
        from app.services.integration_token_service import IntegrationTokenService
        result = await IntegrationTokenService.get_token(db_session, "github")
        assert result == "ghp_from_db"
```

**Step 2: Update GitHubClient**

Modify `backend/app/services/collectors/github/client.py`:

The `GitHubClient` is used in synchronous-style contexts (collectors) that don't have a DB session. The cleanest approach is:
- Keep the env var fallback for now (collectors create their own client without DB context)
- Add a class method `from_db_token(token: str)` that creates a client with a specific token
- The workers/collectors that already have a DB session can use `IntegrationTokenService.get_token()` and pass it

Update `__init__` to accept an optional `token` parameter:

```python
class GitHubClient:
    """Authenticated HTTP client for GitHub API."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            token = self._token or get_settings().github_token
            if not token:
                raise ConfigurationError(
                    "GitHub token not configured. "
                    "Set token via Admin > Integrations or GITHUB_TOKEN env var."
                )
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers=headers,
                timeout=HTTP_CLIENT_TIMEOUT,
            )
        return self._client
```

**Step 3: Update collectors that create GitHubClient to pass DB token when available**

Check `backend/app/services/collectors/github/__init__.py` and `backend/app/worker/check_dependabot.py`. In the workers that have a DB session, add token retrieval:

```python
from app.services.integration_token_service import IntegrationTokenService

token = await IntegrationTokenService.get_token(db, "github")
client = GitHubClient(token=token)
```

Keep env var fallback in `GitHubClient.__init__` for backwards compatibility.

**Step 4: Fix existing tests that mock `get_settings`**

Update existing tests in `test_github_collector.py` — they mock `get_settings().github_token`. These should still work since the env var is the fallback.

**Step 5: Run all GitHub collector tests**

Run: `pushd backend > /dev/null && python -m pytest tests/test_github_collector.py tests/test_github_pr_size.py tests/test_github_review_turnaround.py tests/test_github_deployment_frequency.py tests/test_github_change_failure_rate.py tests/test_github_vulnerabilities.py -v && popd > /dev/null`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/app/services/collectors/github/client.py backend/tests/test_github_collector.py
git commit -m "feat: GitHubClient reads PAT from DB with env var fallback"
```

---

### Task 6: Update Slack consumers to read from `oauth_tokens` + `integration_settings`

**Files:**
- Modify: `backend/app/utils/slack.py`
- Modify: `backend/app/api/slack_admin.py` (keep alerts/templates, remove old config endpoints)
- Modify: `backend/app/worker/check_business_alerts.py`
- Modify: `backend/app/worker/check_dependabot.py`
- Modify: `backend/tests/test_slack_admin_api.py`
- Modify: `backend/tests/test_check_business_alerts_job.py`
- Modify: `backend/tests/test_check_dependabot_job.py`
- Delete: `backend/app/models/slack.py` → remove only `SlackConfigDB` class (keep alert models)

**Step 1: Update `app/utils/slack.py`**

Replace `get_slack_config` with functions that read from new tables:

```python
"""Shared Slack utility functions for worker modules."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.integration_token_service import IntegrationTokenService


async def get_slack_bot_token(db: AsyncSession) -> str | None:
    """Get the decrypted Slack bot token."""
    return await IntegrationTokenService.get_token(db, "slack")


async def get_slack_leadership_channel(db: AsyncSession) -> str | None:
    """Get the leadership channel ID."""
    return await IntegrationTokenService.get_setting(db, "slack", "leadership_channel_id")
```

**Step 2: Remove `SlackConfigDB` from `app/models/slack.py`**

Delete the `SlackConfigDB` class (lines 48-61). Keep `AlertDefinitionDB`, `MessageTemplateDB`, and all other models.

**Step 3: Update `slack_admin.py`**

Remove the `/config` GET and PUT endpoints (replaced by `/admin/integrations/*`). Remove `get_slack_config_or_create()` helper. Keep alerts/templates endpoints. Update the test alert endpoint to read token from new source:

For the `test_alert` endpoint (line 198), replace `config.bot_token_encrypted` with `await IntegrationTokenService.get_token(db, "slack")` and `config.leadership_channel_id` with `await IntegrationTokenService.get_setting(db, "slack", "leadership_channel_id")`.

**Step 4: Update workers**

In `check_business_alerts.py` and `check_dependabot.py`, replace:
```python
from app.utils.slack import get_slack_config
config = await get_slack_config(db)
if not config or not config.bot_token_encrypted:
    ...
bot_token = config.bot_token_encrypted
channel_id = config.leadership_channel_id
```

With:
```python
from app.utils.slack import get_slack_bot_token, get_slack_leadership_channel
bot_token = await get_slack_bot_token(db)
channel_id = await get_slack_leadership_channel(db)
if not bot_token:
    ...
```

**Step 5: Update all affected tests**

- `test_slack_admin_api.py`: Remove tests for GET/PUT `/admin/slack/config`. Update test_alert tests to set up token via `OAuthTokenDB` + `IntegrationSettingDB` instead of `SlackConfigDB`.
- `test_check_business_alerts_job.py`: Update fixtures that create `SlackConfigDB` records.
- `test_check_dependabot_job.py`: Same.
- `test_slack_models.py`: Remove `SlackConfigDB` tests if any.

**Step 6: Run all affected tests**

Run: `pushd backend > /dev/null && python -m pytest tests/test_slack_admin_api.py tests/test_check_business_alerts_job.py tests/test_check_dependabot_job.py tests/test_slack_models.py tests/test_integrations_admin_api.py -v && popd > /dev/null`
Expected: ALL PASS

**Step 7: Run full test suite**

Run: `pushd backend > /dev/null && python -m pytest --tb=short -q && popd > /dev/null`
Expected: ALL ~970 tests PASS

**Step 8: Commit**

```bash
git add -A
git commit -m "refactor: migrate Slack token reads to oauth_tokens + integration_settings"
```

---

### Task 7: Remove old Slack config endpoints from `main.py` router mounting (if needed)

**Files:**
- Modify: `backend/app/main.py`

**Step 1: Verify**

Check if `slack_router` mount in `main.py` still has routes after removing `/config` endpoints. It should — it still has `/admin/slack/...` for alerts-related Slack config. Only the `/admin/slack/config`, `/admin/slack/test`, `/admin/slack/channels` are moved to integrations_admin.

Remove those 3 endpoints from `slack_admin.py` router. Keep the `alerts_router` and `templates_router`.

**Step 2: Run full backend tests**

Run: `pushd backend > /dev/null && python -m pytest --tb=short -q && popd > /dev/null`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add backend/app/api/slack_admin.py backend/app/main.py
git commit -m "refactor: remove old Slack config/test/channels endpoints"
```

---

### Task 8: Frontend — integrations API service

**Files:**
- Create: `frontend/src/services/api/integrations.ts`
- Modify: `frontend/src/hooks/queryKeys.ts`

**Step 1: Create the API service**

```typescript
import type { SlackChannel } from '../../types';
import api from './client';

export interface ProviderStatus {
  connected: boolean;
  expires_at: string | null;
  token_type: string | null;
  site_url: string | null;
  created_at: string | null;
}

export interface AllIntegrationsStatus {
  jira: ProviderStatus;
  google_workspace: ProviderStatus;
  github: ProviderStatus;
  slack: ProviderStatus;
  slack_settings: {
    leadership_channel_id: string | null;
  };
}

export interface SlackTestResult {
  ok: boolean;
  team?: string;
  bot_id?: string;
  error?: string;
}

export const integrationsApi = {
  getStatus: async (): Promise<AllIntegrationsStatus> => {
    const response = await api.get<AllIntegrationsStatus>('/admin/integrations/status');
    return response.data;
  },

  saveGitHubToken: async (token: string): Promise<ProviderStatus> => {
    const response = await api.put<ProviderStatus>('/admin/integrations/github', { token });
    return response.data;
  },

  deleteGitHub: async (): Promise<void> => {
    await api.delete('/admin/integrations/github');
  },

  saveSlackToken: async (token: string): Promise<ProviderStatus> => {
    const response = await api.put<ProviderStatus>('/admin/integrations/slack', { token });
    return response.data;
  },

  deleteSlack: async (): Promise<void> => {
    await api.delete('/admin/integrations/slack');
  },

  updateSlackSettings: async (data: {
    leadership_channel_id?: string;
  }): Promise<{ leadership_channel_id: string | null }> => {
    const response = await api.put('/admin/integrations/slack/settings', data);
    return response.data;
  },

  getSlackChannels: async (): Promise<SlackChannel[]> => {
    const response = await api.get<SlackChannel[]>('/admin/integrations/slack/channels');
    return response.data;
  },

  testSlackConnection: async (): Promise<SlackTestResult> => {
    const response = await api.post<SlackTestResult>('/admin/integrations/slack/test');
    return response.data;
  },
};
```

**Step 2: Add query keys**

In `frontend/src/hooks/queryKeys.ts`, add:

```typescript
integrations: {
  status: ['integrations', 'status'] as const,
  slackChannels: ['integrations', 'slack', 'channels'] as const,
},
```

**Step 3: Commit**

```bash
git add frontend/src/services/api/integrations.ts frontend/src/hooks/queryKeys.ts
git commit -m "feat: add integrations API service and query keys"
```

---

### Task 9: Frontend — IntegrationsTab with 4 provider cards

**Files:**
- Modify: `frontend/src/components/Settings/IntegrationsTab.tsx`
- Create: `frontend/src/components/Settings/GitHubCard.tsx`
- Create: `frontend/src/components/Settings/JiraCard.tsx`
- Modify: `frontend/src/components/Settings/SlackTab.tsx` (adapt to new API)
- Modify: `frontend/src/pages/ISOConfig.tsx` (minor: wrap in card layout)

**Context:**
- Current `IntegrationsTab.tsx` renders `<ISOConfig />` and `<SlackTab />` in a `space-y-6` container
- Each card should show: provider name, connection status, provider-specific controls
- Use existing Tailwind patterns from the project (check other cards/sections for styling reference)
- Use `@/services/api/integrations` for API calls
- Use `queryKeys.integrations.status` for React Query

**Step 1: Create `GitHubCard.tsx`**

Component shows:
- Status badge (connected/disconnected)
- If connected: expiration date with warning if <30 days, disconnect button
- If disconnected: PAT input field (password type with show/hide toggle), save button
- Uses `integrationsApi.saveGitHubToken()`, `integrationsApi.deleteGitHub()`
- Invalidates `queryKeys.integrations.status` on mutations

**Step 2: Create `JiraCard.tsx`**

Component shows:
- Status badge (connected/disconnected)
- If connected: site URL, disconnect button
- If disconnected: "Connect" button that redirects to `/api/oauth/jira/authorize`
- No disconnect endpoint exists yet for Jira — add `DELETE /oauth/jira/disconnect` endpoint in `backend/app/api/oauth.py` that deletes the Jira token from `oauth_tokens`

**Step 3: Adapt `SlackTab.tsx`**

Replace `slackApi` calls with `integrationsApi` equivalents:
- `slackApi.getConfig()` → use `integrationsApi.getStatus()` (slack portion)
- `slackApi.updateConfig({ bot_token })` → `integrationsApi.saveSlackToken(token)`
- `slackApi.updateConfig({ leadership_channel_id })` → `integrationsApi.updateSlackSettings({ leadership_channel_id })`
- `slackApi.testConnection()` → `integrationsApi.testSlackConnection()`
- `slackApi.getChannels()` → `integrationsApi.getSlackChannels()`
- Invalidate `queryKeys.integrations.status` instead of `queryKeys.slack.status`

**Step 4: Update `IntegrationsTab.tsx`**

```tsx
import { useQuery } from '@tanstack/react-query';
import { integrationsApi } from '@/services/api/integrations';
import { queryKeys } from '@/hooks/queryKeys';
import GitHubCard from './GitHubCard';
import JiraCard from './JiraCard';
import SlackTab from './SlackTab';
import ISOConfig from '@/pages/ISOConfig';

export default function IntegrationsTab(): JSX.Element {
  const { data: status, isLoading } = useQuery({
    queryKey: queryKeys.integrations.status,
    queryFn: integrationsApi.getStatus,
  });

  return (
    <div className="space-y-6">
      <JiraCard status={status?.jira} />
      <ISOConfig />
      <GitHubCard status={status?.github} />
      <SlackTab status={status?.slack} slackSettings={status?.slack_settings} />
    </div>
  );
}
```

**Step 5: Run frontend tests**

Run: `pushd frontend > /dev/null && npm test -- --run && popd > /dev/null`
Expected: PASS (some tests may need updating if they reference old SlackTab API)

**Step 6: Commit**

```bash
git add frontend/src/components/Settings/IntegrationsTab.tsx frontend/src/components/Settings/GitHubCard.tsx frontend/src/components/Settings/JiraCard.tsx frontend/src/components/Settings/SlackTab.tsx frontend/src/pages/ISOConfig.tsx
git commit -m "feat: unified integrations page with 4 provider cards"
```

---

### Task 10: Add Jira disconnect endpoint

**Files:**
- Modify: `backend/app/api/oauth.py`
- Test: Add to `backend/tests/test_oauth_api.py`

**Step 1: Write the failing test**

```python
class TestJiraDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_jira(self, client: AsyncClient, db_session) -> None:
        from app.core.token_encryption import encrypt_token
        from app.models.oauth import OAuthTokenDB

        token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("test"),
            refresh_token=encrypt_token("refresh"),
            token_type="Bearer",
        )
        db_session.add(token)
        await db_session.commit()

        response = await client.delete("/api/oauth/jira/disconnect")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_disconnect_jira_when_not_connected(self, client: AsyncClient) -> None:
        response = await client.delete("/api/oauth/jira/disconnect")
        assert response.status_code == 404
```

**Step 2: Add endpoint to `oauth.py`**

```python
@router.delete("/jira/disconnect")
@limiter.limit("10/minute")
async def disconnect_jira(
    request: Request, current_user: AdminUser, db: DBSession
) -> dict[str, str]:
    deleted = await IntegrationTokenService.delete_token(db, "jira")
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Jira token found")
    return {"status": "disconnected"}
```

Add import for `AdminUser` and `IntegrationTokenService`.

**Step 3: Run tests**

Run: `pushd backend > /dev/null && python -m pytest tests/test_oauth_api.py -v && popd > /dev/null`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/api/oauth.py backend/tests/test_oauth_api.py
git commit -m "feat: add Jira disconnect endpoint"
```

---

### Task 11: Cleanup — remove unused code and old Slack API service

**Files:**
- Delete or clean: `frontend/src/services/api/slack.ts` (remove config/test/channels functions, keep if other code uses slackApi)
- Modify: `frontend/src/hooks/queryKeys.ts` (remove `slack.status` and `slack.channels` if no longer used)
- Verify no remaining imports of `SlackConfigDB` or `get_slack_config` (old)
- Remove `backend/app/models/slack.py` `SlackConfigDB` class

**Step 1: Search for remaining references**

Run grep for `SlackConfigDB`, `slack_config`, `slackApi.getConfig`, `slackApi.updateConfig` across the codebase. Remove or update all references.

**Step 2: Run full test suites**

Backend: `pushd backend > /dev/null && python -m pytest --tb=short -q && popd > /dev/null`
Frontend: `pushd frontend > /dev/null && npm test -- --run && popd > /dev/null`

Expected: ALL PASS

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: remove old Slack config code and unused references"
```

---

### Task 12: Final verification

**Step 1: Lint backend**

Run: `pushd backend > /dev/null && ruff check app/ && black --check app/ && popd > /dev/null`

**Step 2: Lint frontend**

Run: `pushd frontend > /dev/null && npm run lint && npm run build && popd > /dev/null`

**Step 3: Full backend test suite**

Run: `pushd backend > /dev/null && python -m pytest --tb=short -q && popd > /dev/null`
Expected: ALL ~970+ tests PASS

**Step 4: Full frontend test suite**

Run: `pushd frontend > /dev/null && npm test -- --run && popd > /dev/null`
Expected: ALL ~340+ tests PASS

**Step 5: Commit any lint fixes**

```bash
git add -A
git commit -m "style: lint fixes for unified integrations"
```
