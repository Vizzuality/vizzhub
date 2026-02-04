"""Tests for authentication functionality.

NOTE: These tests verify JWT token creation and development mode bypass.
TODO: Add tests for Google OAuth once implemented.
"""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.auth import TokenData, create_access_token


def test_create_access_token_basic():
    """Test creating a basic JWT access token."""
    # Create token with user data
    token_data = {"sub": "test-user-123", "roles": ["user"]}
    token = create_access_token(data=token_data)

    # Verify token is a non-empty string
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_access_token_with_expiration():
    """Test creating a JWT token with custom expiration."""
    # Create token with 1 hour expiration
    token_data = {"sub": "test-user-123", "roles": ["user", "admin"]}
    expires_delta = timedelta(hours=1)
    token = create_access_token(data=token_data, expires_delta=expires_delta)

    # Verify token is created
    assert isinstance(token, str)
    assert len(token) > 0


def test_token_data_model():
    """Test TokenData model validation."""
    # Create valid token data
    token_data = TokenData(user_id="user-123", roles=["user", "admin"])

    assert token_data.user_id == "user-123"
    assert token_data.roles == ["user", "admin"]


def test_token_data_model_default_roles():
    """Test TokenData model with default empty roles."""
    # Create token data without roles
    token_data = TokenData(user_id="user-123")

    assert token_data.user_id == "user-123"
    assert token_data.roles == []


@pytest.mark.asyncio
async def test_development_mode_bypass_allows_access_without_token(
    client: AsyncClient,
) -> None:
    """Test that development mode allows API access without authentication token."""
    # In development mode (DEBUG=true), requests without auth should succeed
    response = await client.get("/api/projects")

    # Should not get 401 Unauthorized in development mode
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_health_endpoint_does_not_require_auth(client: AsyncClient) -> None:
    """Test that health check endpoint works without authentication."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


class TestTokenCreation:
    """Test JWT token creation and validation."""

    def test_create_access_token_raises_error_when_jwt_secret_missing(self) -> None:
        """create_access_token should raise ValueError if JWT_SECRET_KEY not set."""
        from unittest.mock import patch

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
        from unittest.mock import patch

        from app.core.auth import get_current_user

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False

            # No credentials provided
            with pytest.raises(Exception) as exc_info:
                await get_current_user(None)

            # Should raise 401 Unauthorized
            assert exc_info.value.status_code == 401
            assert "Authentication required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_production_mode_validates_token(self) -> None:
        """Production mode should validate token when DEBUG=false."""
        from unittest.mock import MagicMock, patch

        from fastapi.security import HTTPAuthorizationCredentials

        from app.core.auth import get_current_user

        # Create valid token
        token = create_access_token({"sub": "prod-user-123", "roles": ["user"]})

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "test-secret-key-production"

            # Re-encode with matching secret
            from jose import jwt

            token = jwt.encode(
                {"sub": "prod-user-123", "roles": ["user"]},
                "test-secret-key-production",
                algorithm="HS256",
            )
            credentials.credentials = token

            user = await get_current_user(credentials)

        assert user.user_id == "prod-user-123"
        assert "user" in user.roles

    @pytest.mark.asyncio
    async def test_production_mode_no_bypass_without_token(self) -> None:
        """Production mode should enforce auth without token."""
        from unittest.mock import patch

        from app.core.auth import get_current_user

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False

            with pytest.raises(Exception) as exc_info:
                await get_current_user(None)

            # Must require authentication
            assert exc_info.value.status_code == 401


class TestTokenValidation:
    """Test JWT token validation edge cases."""

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token_rejected(self) -> None:
        """Expired JWT should be rejected."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        from fastapi.security import HTTPAuthorizationCredentials
        from jose import jwt

        from app.core.auth import get_current_user

        # Create expired token
        expired_payload = {
            "sub": "user-123",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=expired_token
        )

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "test-secret"

            with pytest.raises(Exception) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_signature_rejected(self) -> None:
        """Token with wrong signature should be rejected."""
        from unittest.mock import patch

        from fastapi.security import HTTPAuthorizationCredentials
        from jose import jwt

        from app.core.auth import get_current_user

        # Create token with one secret
        token = jwt.encode({"sub": "user-123"}, "wrong-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Try to validate with different secret
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "correct-secret"

            with pytest.raises(Exception) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_missing_sub_claim_rejected(self) -> None:
        """Token without 'sub' claim should be rejected."""
        from unittest.mock import patch

        from fastapi.security import HTTPAuthorizationCredentials
        from jose import jwt

        from app.core.auth import get_current_user

        # Create token without "sub" claim
        token = jwt.encode({"roles": ["user"]}, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "test-secret"

            with pytest.raises(Exception) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_malformed_token_rejected(self) -> None:
        """Malformed JWT should be rejected."""
        from unittest.mock import patch

        from fastapi.security import HTTPAuthorizationCredentials

        from app.core.auth import get_current_user

        # Completely invalid token
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="not-a-valid-jwt-token"
        )

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.jwt_secret_key = "test-secret"

            with pytest.raises(Exception) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == 401


class TestRoleAuthorization:
    """Test role-based authorization."""

    @pytest.mark.asyncio
    async def test_require_role_allows_user_with_role(self) -> None:
        """User with required role should get access."""
        from app.core.auth import TokenData, require_role

        # Create user with admin role
        user = TokenData(user_id="admin-user", roles=["admin", "user"])

        # Check admin role requirement
        role_checker = require_role("admin")
        result = await role_checker(user)

        assert result.user_id == "admin-user"

    @pytest.mark.asyncio
    async def test_require_role_denies_user_without_role(self) -> None:
        """User without role should get 403."""
        from app.core.auth import TokenData, require_role

        # Create user without admin role
        user = TokenData(user_id="regular-user", roles=["user"])

        # Check admin role requirement
        role_checker = require_role("admin")

        with pytest.raises(Exception) as exc_info:
            await role_checker(user)

        assert exc_info.value.status_code == 403
        assert "admin" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_development_mode_logs_security_warning(self, caplog) -> None:
        """Dev bypass should log warning message."""
        import logging
        from unittest.mock import patch

        from app.core.auth import get_current_user

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.debug = True

            with caplog.at_level(logging.WARNING):
                user = await get_current_user(None)

            # Should log security warning
            assert any("SECURITY" in record.message for record in caplog.records)
            assert any("Development mode" in record.message for record in caplog.records)
            assert user.user_id == "dev-user-id"
