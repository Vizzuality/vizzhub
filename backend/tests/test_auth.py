"""Tests for authentication functionality."""

from datetime import UTC, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from httpx import AsyncClient
from jose import jwt

from app.core.auth import COOKIE_NAME, TokenData, create_access_token, get_cookie_settings


def _make_request(cookies: dict[str, str] | None = None) -> MagicMock:
    """Create a mock Request with the given cookies."""
    request = MagicMock()
    request.cookies = cookies or {}
    return request


def test_create_access_token_basic():
    """Test creating a basic JWT access token."""
    token_data = {"sub": "test-user-123", "roles": ["user"]}
    token = create_access_token(data=token_data)

    assert isinstance(token, str)
    assert len(token) > 0


def test_create_access_token_with_expiration():
    """Test creating a JWT token with custom expiration."""
    token_data = {"sub": "test-user-123", "roles": ["user", "admin"]}
    expires_delta = timedelta(hours=1)
    token = create_access_token(data=token_data, expires_delta=expires_delta)

    assert isinstance(token, str)
    assert len(token) > 0


def test_token_data_model():
    """Test TokenData model validation."""
    token_data = TokenData(user_id="user-123", roles=["user", "admin"])

    assert token_data.user_id == "user-123"
    assert token_data.roles == ["user", "admin"]


def test_token_data_model_default_roles():
    """Test TokenData model with default empty roles."""
    token_data = TokenData(user_id="user-123")

    assert token_data.user_id == "user-123"
    assert token_data.roles == []


def test_get_cookie_settings_debug_mode():
    """Cookie settings should have Secure=false in debug mode."""
    with patch("app.core.auth.settings") as mock_settings:
        mock_settings.debug = True
        mock_settings.jwt_expire_hours = 24
        settings = get_cookie_settings()

    assert settings["key"] == COOKIE_NAME
    assert settings["httponly"] is True
    assert settings["secure"] is False
    assert settings["samesite"] == "lax"
    assert settings["path"] == "/api"
    assert settings["max_age"] == 24 * 3600


def test_get_cookie_settings_production_mode():
    """Cookie settings should have Secure=true in production mode."""
    with patch("app.core.auth.settings") as mock_settings:
        mock_settings.debug = False
        mock_settings.jwt_expire_hours = 24
        settings = get_cookie_settings()

    assert settings["secure"] is True


@pytest.mark.asyncio
async def test_development_mode_bypass_allows_access_without_token(
    client: AsyncClient,
) -> None:
    """Test that development mode allows API access without authentication token."""
    response = await client.get("/api/projects")

    assert response.status_code != 401


@pytest.mark.asyncio
async def test_health_endpoint_does_not_require_auth(client: AsyncClient) -> None:
    """Test that health check endpoint works without authentication."""
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


class TestTokenCreation:
    """Test JWT token creation and validation."""

    def test_create_access_token_raises_error_when_jwt_secret_missing(self) -> None:
        """create_access_token should raise ValueError if JWT_SECRET_KEY not set."""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.jwt_secret_key = ""
            mock_settings.jwt_expire_hours = 24

            with pytest.raises(ValueError) as exc_info:
                create_access_token({"sub": "user-123"})

            assert "JWT_SECRET_KEY not configured" in str(exc_info.value)


class TestProductionMode:
    """Test authentication in production mode (DEBUG=false)."""

    @pytest.mark.asyncio
    async def test_get_current_user_production_mode_requires_token(self) -> None:
        """Production mode should require token when DEBUG=false."""
        from app.core.auth import get_current_user

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False

            with pytest.raises(Exception) as exc_info:
                await get_current_user(_make_request(), None)

            assert exc_info.value.status_code == 401
            assert "Authentication required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_production_mode_validates_token(self) -> None:
        """Production mode should validate token from Bearer header."""
        from app.core.auth import get_current_user

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "test-secret-key-production"

            token = jwt.encode(
                {"sub": "prod-user-123", "roles": ["user"]},
                "test-secret-key-production",
                algorithm="HS256",
            )
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

            user = await get_current_user(_make_request(), credentials)

        assert user.user_id == "prod-user-123"
        assert "user" in user.roles

    @pytest.mark.asyncio
    async def test_production_mode_no_bypass_without_token(self) -> None:
        """Production mode should enforce auth without token."""
        from app.core.auth import get_current_user

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False

            with pytest.raises(Exception) as exc_info:
                await get_current_user(_make_request(), None)

            assert exc_info.value.status_code == 401


class TestCookieAuth:
    """Test JWT extraction from httpOnly cookie."""

    @pytest.mark.asyncio
    async def test_token_read_from_cookie(self) -> None:
        """get_current_user should accept token from cookie."""
        from app.core.auth import get_current_user

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "test-secret"

            token = jwt.encode(
                {"sub": "cookie-user", "roles": ["user"]},
                "test-secret",
                algorithm="HS256",
            )
            request = _make_request({COOKIE_NAME: token})

            user = await get_current_user(request, None)

        assert user.user_id == "cookie-user"

    @pytest.mark.asyncio
    async def test_cookie_takes_precedence_over_header(self) -> None:
        """When both cookie and header are present, cookie wins."""
        from app.core.auth import get_current_user

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "test-secret"

            cookie_token = jwt.encode(
                {"sub": "cookie-user", "roles": ["user"]},
                "test-secret",
                algorithm="HS256",
            )
            header_token = jwt.encode(
                {"sub": "header-user", "roles": ["user"]},
                "test-secret",
                algorithm="HS256",
            )
            request = _make_request({COOKIE_NAME: cookie_token})
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=header_token)

            user = await get_current_user(request, credentials)

        assert user.user_id == "cookie-user"

    @pytest.mark.asyncio
    async def test_falls_back_to_header_when_no_cookie(self) -> None:
        """When no cookie is present, Bearer header is used."""
        from app.core.auth import get_current_user

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "test-secret"

            token = jwt.encode(
                {"sub": "header-user", "roles": ["user"]},
                "test-secret",
                algorithm="HS256",
            )
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

            user = await get_current_user(_make_request(), credentials)

        assert user.user_id == "header-user"


class TestTokenValidation:
    """Test JWT token validation edge cases."""

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token_rejected(self) -> None:
        """Expired JWT should be rejected."""
        from datetime import datetime, timedelta

        from app.core.auth import get_current_user

        expired_payload = {
            "sub": "user-123",
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired_token)

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "test-secret"

            with pytest.raises(Exception) as exc_info:
                await get_current_user(_make_request(), credentials)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_signature_rejected(self) -> None:
        """Token with wrong signature should be rejected."""
        from app.core.auth import get_current_user

        token = jwt.encode({"sub": "user-123"}, "wrong-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "correct-secret"

            with pytest.raises(Exception) as exc_info:
                await get_current_user(_make_request(), credentials)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_missing_sub_claim_rejected(self) -> None:
        """Token without 'sub' claim should be rejected."""
        from app.core.auth import get_current_user

        token = jwt.encode({"roles": ["user"]}, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "test-secret"

            with pytest.raises(Exception) as exc_info:
                await get_current_user(_make_request(), credentials)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_malformed_token_rejected(self) -> None:
        """Malformed JWT should be rejected."""
        from app.core.auth import get_current_user

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="not-a-valid-jwt-token"
        )

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "test-secret"

            with pytest.raises(Exception) as exc_info:
                await get_current_user(_make_request(), credentials)

            assert exc_info.value.status_code == 401


class TestPermissionAuthorization:
    """Test permission-based authorization."""

    def test_require_permission_allows_user_with_permission(self) -> None:
        """User with required permission should get access."""
        from app.core.auth import TokenData
        from app.core.permissions import require_permission

        user = TokenData(
            user_id="admin-user",
            roles=["admin", "user"],
            permissions=["*"],
        )

        checker = require_permission("*")
        result = checker(user)

        assert result.user_id == "admin-user"

    def test_require_permission_denies_user_without_permission(self) -> None:
        """User without required permission should get 403."""
        from app.core.auth import TokenData
        from app.core.permissions import require_permission

        user = TokenData(
            user_id="regular-user",
            roles=["user"],
            permissions=["scorecard:view", "tracker:view"],
        )

        checker = require_permission("*")

        with pytest.raises(Exception) as exc_info:
            checker(user)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_dev_bypass_includes_permissions(self) -> None:
        """Dev bypass mock user should include wildcard permission and admin role."""
        from app.core.auth import get_current_user

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = True
            user = await get_current_user(_make_request(), None)

        assert user.permissions == ["*"]
        assert "admin" in user.roles
        assert "user" in user.roles

    @pytest.mark.asyncio
    async def test_development_mode_logs_security_warning(self, caplog) -> None:
        """Dev bypass should log warning message."""
        import logging

        from app.core.auth import get_current_user

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = True

            with caplog.at_level(logging.WARNING):
                user = await get_current_user(_make_request(), None)

            assert any("auth_bypass_dev_mode" in str(record.message) for record in caplog.records)
            assert user.user_id == "00000000-0000-0000-0000-000000000001"
