# ISO Phase 2: Google Workspace OAuth Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable admins to connect Google Workspace via OAuth so the ISO collector can read Directory API data (users, groups, roles).

**Architecture:** Follow the existing Jira OAuth pattern. New service in `app/modules/iso/services/` (not extending shared `OAuthService`). Reuse `OAuthTokenDB` with `provider="google_workspace"`, `OAuthStateManager` for CSRF, and `SessionMiddleware` for state. Domain stored in `OAuthTokenDB.site_url`. Endpoints in `app/modules/iso/api/config.py`, wired through ISO module router.

**Tech Stack:** httpx (async HTTP), `OAuthTokenDB` (existing model), `OAuthStateManager` (existing CSRF), Google OAuth 2.0 endpoints

**Design doc:** `docs/plans/2026-02-22-iso-google-workspace-collector-design.md` (Authentication section, Phase 2 tasks)

---

### Task 1: Add Google Workspace OAuth settings to config

**Files:**
- Modify: `backend/app/config.py` (Settings class, ~line 41)
- Test: `backend/tests/test_iso_oauth.py` (new file)

**Step 1: Write the failing test**

Create `backend/tests/test_iso_oauth.py`:
```python
"""Tests for ISO Google Workspace OAuth."""

import pytest
from app.config import get_settings


class TestGoogleWorkspaceConfig:
    def test_config_has_google_workspace_fields(self) -> None:
        settings = get_settings()
        assert hasattr(settings, "google_workspace_client_id")
        assert hasattr(settings, "google_workspace_client_secret")
        assert hasattr(settings, "google_workspace_redirect_uri")
        assert settings.google_workspace_client_id == ""
        assert settings.google_workspace_client_secret == ""
        assert settings.google_workspace_redirect_uri == ""
```

**Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_oauth.py::TestGoogleWorkspaceConfig -v && popd > /dev/null`
Expected: AttributeError

**Step 3: Add settings**

In `backend/app/config.py`, add after the GitHub section (~line 41):
```python
# Google Workspace Admin SDK (ISO module)
google_workspace_client_id: str = ""
google_workspace_client_secret: str = ""
google_workspace_redirect_uri: str = ""
```

Note: Scopes are hardcoded in the service (not configurable), since they're fixed by the collector's requirements.

**Step 4: Run test to verify it passes**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_oauth.py -v && popd > /dev/null`

**Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_iso_oauth.py
git commit -m "feat(iso): add Google Workspace OAuth config settings"
```

---

### Task 2: Create GoogleWorkspaceOAuth service

**Files:**
- Create: `backend/app/modules/iso/services/google_workspace_oauth.py`
- Modify: `backend/tests/test_iso_oauth.py`

This is the core service. It follows the Jira `OAuthService` pattern but lives in the ISO module.

**Step 1: Write the failing tests**

Add to `backend/tests/test_iso_oauth.py`:
```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth import OAuthTokenDB


class TestGoogleWorkspaceOAuthService:
    def test_authorization_url_contains_required_params(self) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        url = GoogleWorkspaceOAuth.get_authorization_url(state="test-state")
        assert "accounts.google.com" in url
        assert "test-state" in url
        assert "response_type=code" in url
        assert "access_type=offline" in url
        assert "admin.directory.user.readonly" in url

    def test_authorization_url_includes_domain_in_login_hint(self) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        url = GoogleWorkspaceOAuth.get_authorization_url(
            state="s", domain="empresa.com"
        )
        assert "empresa.com" in url

    @pytest.mark.asyncio
    async def test_exchange_code_stores_token(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "ya29.test-access-token",
            "refresh_token": "1//test-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/admin.directory.user.readonly",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            token = await GoogleWorkspaceOAuth.exchange_code_for_token(
                code="test-code",
                domain="empresa.com",
                db=db_session,
            )

        assert token.provider == "google_workspace"
        assert token.access_token == "ya29.test-access-token"
        assert token.refresh_token == "1//test-refresh-token"
        assert token.site_url == "empresa.com"
        assert token.expires_at is not None

    @pytest.mark.asyncio
    async def test_exchange_code_replaces_existing_token(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        existing = OAuthTokenDB(
            provider="google_workspace",
            access_token="old-token",
            site_url="old-domain.com",
        )
        db_session.add(existing)
        await db_session.flush()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            token = await GoogleWorkspaceOAuth.exchange_code_for_token(
                code="code", domain="new-domain.com", db=db_session,
            )

        assert token.access_token == "new-token"
        assert token.site_url == "new-domain.com"

    @pytest.mark.asyncio
    async def test_refresh_token(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        existing = OAuthTokenDB(
            provider="google_workspace",
            access_token="expired-token",
            refresh_token="valid-refresh",
            site_url="empresa.com",
        )
        db_session.add(existing)
        await db_session.flush()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "refreshed-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            refreshed = await GoogleWorkspaceOAuth.refresh_token(db_session)

        assert refreshed is not None
        assert refreshed.access_token == "refreshed-token"

    @pytest.mark.asyncio
    async def test_refresh_returns_none_when_no_token(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        result = await GoogleWorkspaceOAuth.refresh_token(db_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_valid_token_returns_token(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )
        from datetime import timedelta

        existing = OAuthTokenDB(
            provider="google_workspace",
            access_token="valid-token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            site_url="empresa.com",
        )
        db_session.add(existing)
        await db_session.flush()

        token = await GoogleWorkspaceOAuth.get_valid_token(db_session)
        assert token == "valid-token"

    @pytest.mark.asyncio
    async def test_get_valid_token_returns_none_when_no_token(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        token = await GoogleWorkspaceOAuth.get_valid_token(db_session)
        assert token is None

    @pytest.mark.asyncio
    async def test_disconnect_removes_token(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        existing = OAuthTokenDB(
            provider="google_workspace",
            access_token="some-token",
            site_url="empresa.com",
        )
        db_session.add(existing)
        await db_session.flush()

        await GoogleWorkspaceOAuth.disconnect(db_session)

        token = await GoogleWorkspaceOAuth.get_valid_token(db_session)
        assert token is None

    @pytest.mark.asyncio
    async def test_get_status_connected(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )
        from datetime import timedelta

        existing = OAuthTokenDB(
            provider="google_workspace",
            access_token="token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            site_url="empresa.com",
        )
        db_session.add(existing)
        await db_session.flush()

        status = await GoogleWorkspaceOAuth.get_status(db_session)
        assert status["connected"] is True
        assert status["domain"] == "empresa.com"

    @pytest.mark.asyncio
    async def test_get_status_disconnected(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        status = await GoogleWorkspaceOAuth.get_status(db_session)
        assert status["connected"] is False
        assert status["domain"] is None
```

**Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_oauth.py::TestGoogleWorkspaceOAuthService -v && popd > /dev/null`

**Step 3: Write the service**

`backend/app/modules/iso/services/google_workspace_oauth.py`:
```python
"""Google Workspace OAuth service for ISO module."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.oauth import OAuthTokenDB

logger = logging.getLogger(__name__)

PROVIDER = "google_workspace"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = " ".join([
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
    "https://www.googleapis.com/auth/admin.directory.group.readonly",
    "https://www.googleapis.com/auth/admin.directory.group.member.readonly",
    "https://www.googleapis.com/auth/admin.directory.rolemanagement.readonly",
])


class GoogleWorkspaceOAuth:
    @staticmethod
    def get_authorization_url(state: str, domain: str | None = None) -> str:
        settings = get_settings()
        params = {
            "client_id": settings.google_workspace_client_id,
            "redirect_uri": settings.google_workspace_redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        if domain:
            params["hd"] = domain
            params["login_hint"] = f"admin@{domain}"
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code_for_token(
        code: str, domain: str, db: AsyncSession
    ) -> OAuthTokenDB:
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.google_workspace_client_id,
                    "client_secret": settings.google_workspace_client_secret,
                    "code": code,
                    "redirect_uri": settings.google_workspace_redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

        expires_in = token_data.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == PROVIDER)
        )
        existing = result.scalar_one_or_none()
        if existing:
            await db.delete(existing)

        oauth_token = OAuthTokenDB(
            provider=PROVIDER,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=token_data.get("scope"),
            site_url=domain,
        )
        db.add(oauth_token)
        await db.flush()
        await db.refresh(oauth_token)

        logger.info("Google Workspace OAuth token stored for domain %s", domain)
        return oauth_token

    @staticmethod
    async def refresh_token(db: AsyncSession) -> OAuthTokenDB | None:
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == PROVIDER)
        )
        token = result.scalar_one_or_none()
        if not token or not token.refresh_token:
            return None

        settings = get_settings()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.google_workspace_client_id,
                    "client_secret": settings.google_workspace_client_secret,
                    "refresh_token": token.refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

        expires_in = token_data.get("expires_in")
        if expires_in:
            token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        token.access_token = token_data["access_token"]
        if "refresh_token" in token_data:
            token.refresh_token = token_data["refresh_token"]

        await db.commit()
        await db.refresh(token)

        logger.info("Google Workspace OAuth token refreshed")
        return token

    @staticmethod
    async def get_valid_token(db: AsyncSession) -> str | None:
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == PROVIDER)
        )
        token = result.scalar_one_or_none()
        if not token:
            return None

        if token.expires_at:
            buffer = timedelta(minutes=5)
            if token.expires_at - buffer <= datetime.now(timezone.utc):
                refreshed = await GoogleWorkspaceOAuth.refresh_token(db)
                if refreshed:
                    return refreshed.access_token
                return None

        return token.access_token

    @staticmethod
    async def disconnect(db: AsyncSession) -> None:
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == PROVIDER)
        )
        token = result.scalar_one_or_none()
        if token:
            await db.delete(token)
            await db.flush()
            logger.info("Google Workspace OAuth disconnected")

    @staticmethod
    async def get_status(db: AsyncSession) -> dict[str, Any]:
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == PROVIDER)
        )
        token = result.scalar_one_or_none()
        if not token:
            return {"connected": False, "domain": None}
        return {"connected": True, "domain": token.site_url}
```

**Step 4: Run test to verify it passes**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_oauth.py -v && popd > /dev/null`

**Step 5: Commit**

```bash
git add backend/app/modules/iso/services/google_workspace_oauth.py backend/tests/test_iso_oauth.py
git commit -m "feat(iso): add GoogleWorkspaceOAuth service"
```

---

### Task 3: Create ISO config API endpoints

**Files:**
- Create: `backend/app/modules/iso/api/config.py`
- Modify: `backend/tests/test_iso_oauth.py`

**Step 1: Write the failing tests**

Add to `backend/tests/test_iso_oauth.py`:
```python
class TestIsoConfigEndpoints:
    @pytest.mark.asyncio
    async def test_status_disconnected(self, client: AsyncClient) -> None:
        response = await client.get("/api/iso/config/google-workspace")
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["domain"] is None

    @pytest.mark.asyncio
    async def test_authorize_redirects(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/iso/config/google-workspace/authorize",
            params={"domain": "test.com"},
            follow_redirects=False,
        )
        assert response.status_code == 307
        location = response.headers["location"]
        assert "accounts.google.com" in location
        assert "test.com" in location

    @pytest.mark.asyncio
    async def test_authorize_requires_domain(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/iso/config/google-workspace/authorize",
            follow_redirects=False,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_callback_rejects_missing_state(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/iso/config/google-workspace/callback",
            params={"code": "test-code"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, client: AsyncClient) -> None:
        response = await client.delete("/api/iso/config/google-workspace/disconnect")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_status_after_connect(self, client: AsyncClient, db_session) -> None:
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="test-token",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        response = await client.get("/api/iso/config/google-workspace")
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["domain"] == "empresa.com"

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, client: AsyncClient, db_session) -> None:
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="test-token",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        response = await client.delete("/api/iso/config/google-workspace/disconnect")
        assert response.status_code == 200

        status_response = await client.get("/api/iso/config/google-workspace")
        assert status_response.json()["connected"] is False
```

**Step 2: Run test to verify it fails**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_oauth.py::TestIsoConfigEndpoints -v && popd > /dev/null`

**Step 3: Write the endpoints**

`backend/app/modules/iso/api/config.py`:
```python
"""ISO module configuration endpoints — Google Workspace OAuth."""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.oauth_state import OAuthStateManager
from app.database import get_db
from app.modules.iso.services.google_workspace_oauth import GoogleWorkspaceOAuth

logger = logging.getLogger(__name__)

router = APIRouter()

DBSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/google-workspace")
async def get_google_workspace_status(db: DBSession) -> dict:
    return await GoogleWorkspaceOAuth.get_status(db)


@router.get("/google-workspace/authorize")
async def authorize_google_workspace(
    request: Request,
    domain: str = Query(..., description="Google Workspace domain"),
    db: DBSession = None,
) -> RedirectResponse:
    state = OAuthStateManager.generate_state()
    request.session["oauth_state"] = state
    request.session["gw_domain"] = domain

    url = GoogleWorkspaceOAuth.get_authorization_url(state=state, domain=domain)
    return RedirectResponse(url=url, status_code=307)


@router.get("/google-workspace/callback")
async def google_workspace_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(""),
    db: DBSession = None,
) -> dict:
    session_state = request.session.get("oauth_state")
    if not session_state or session_state != state:
        logger.warning("OAuth state mismatch in Google Workspace callback")
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    if not OAuthStateManager.validate_state(state):
        logger.warning("OAuth state expired or already used")
        raise HTTPException(status_code=400, detail="State expired or already used")

    domain = request.session.get("gw_domain", "")
    token = await GoogleWorkspaceOAuth.exchange_code_for_token(
        code=code, domain=domain, db=db
    )

    request.session.pop("oauth_state", None)
    request.session.pop("gw_domain", None)

    return {"status": "success", "message": "Google Workspace connected"}


@router.delete("/google-workspace/disconnect")
async def disconnect_google_workspace(db: DBSession) -> dict:
    await GoogleWorkspaceOAuth.disconnect(db)
    return {"status": "success", "message": "Google Workspace disconnected"}
```

Note: You'll need to add the missing imports at the top:
```python
from typing import Annotated
from fastapi import Depends
```

**Step 4: Run test to verify it passes**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_oauth.py::TestIsoConfigEndpoints -v && popd > /dev/null`

**Step 5: Commit**

```bash
git add backend/app/modules/iso/api/config.py backend/tests/test_iso_oauth.py
git commit -m "feat(iso): add Google Workspace OAuth API endpoints"
```

---

### Task 4: Wire config router to ISO module router

**Files:**
- Modify: `backend/app/modules/iso/router.py`
- Modify: `backend/tests/test_iso_oauth.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_iso_oauth.py`:
```python
class TestIsoConfigRouterWiring:
    @pytest.mark.asyncio
    async def test_config_endpoint_accessible_via_iso_prefix(self, client: AsyncClient) -> None:
        response = await client.get("/api/iso/config/google-workspace")
        assert response.status_code == 200
```

Note: This may already pass if Task 3 endpoints work via the ISO prefix. If it passes, the wiring is correct.

**Step 2: Update router.py**

`backend/app/modules/iso/router.py`:
```python
from fastapi import APIRouter

from app.modules.iso.api import config as config_router

router = APIRouter()
router.include_router(config_router.router, prefix="/config", tags=["iso-config"])
```

**Step 3: Run all ISO OAuth tests**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest tests/test_iso_oauth.py -v && popd > /dev/null`

**Step 4: Commit**

```bash
git add backend/app/modules/iso/router.py backend/tests/test_iso_oauth.py
git commit -m "feat(iso): wire config sub-router to ISO module router"
```

---

### Task 5: Run full test suite — verify no regressions

**Step 1: Run all backend tests**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && pytest --tb=short -q && popd > /dev/null`
Expected: 845+ tests pass (including new ISO OAuth tests)

**Step 2: Lint**

Run: `pushd /Volumes/Work/Dev/project-score-card/backend > /dev/null && ruff check app/modules/iso/ && black --check app/modules/iso/ && popd > /dev/null`

Fix any issues, then commit if needed:
```bash
git commit -m "fix(iso): lint fixes for Phase 2 OAuth"
```
