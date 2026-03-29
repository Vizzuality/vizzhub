"""Tests for security headers middleware.

This module tests the SecurityHeadersMiddleware which adds security headers
to all HTTP responses to protect against various web vulnerabilities.
"""

import pytest
from httpx import AsyncClient


class TestSecurityHeadersMiddleware:
    """Test security headers are added to all responses."""

    @pytest.mark.asyncio
    async def test_security_headers_middleware_adds_x_content_type_options(
        self, client: AsyncClient
    ) -> None:
        """X-Content-Type-Options: nosniff header should be added."""
        response = await client.get("/health/live")

        assert response.status_code == 200
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_security_headers_middleware_adds_x_frame_options(
        self, client: AsyncClient
    ) -> None:
        """X-Frame-Options: DENY header should be added."""
        response = await client.get("/health/live")

        assert response.status_code == 200
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

    @pytest.mark.asyncio
    async def test_security_headers_middleware_adds_x_xss_protection(
        self, client: AsyncClient
    ) -> None:
        """X-XSS-Protection header should be added."""
        response = await client.get("/health/live")

        assert response.status_code == 200
        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

    @pytest.mark.asyncio
    async def test_security_headers_middleware_adds_content_security_policy(
        self, client: AsyncClient
    ) -> None:
        """Content-Security-Policy header should be added."""
        response = await client.get("/health/live")

        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers

        csp = response.headers["Content-Security-Policy"]
        # Verify key CSP directives
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    @pytest.mark.asyncio
    async def test_security_headers_middleware_adds_referrer_policy(
        self, client: AsyncClient
    ) -> None:
        """Referrer-Policy header should be added."""
        response = await client.get("/health/live")

        assert response.status_code == 200
        assert "Referrer-Policy" in response.headers
        assert (
            response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        )

    @pytest.mark.asyncio
    async def test_security_headers_middleware_adds_permissions_policy(
        self, client: AsyncClient
    ) -> None:
        """Permissions-Policy header should be added."""
        response = await client.get("/health/live")

        assert response.status_code == 200
        assert "Permissions-Policy" in response.headers

        permissions = response.headers["Permissions-Policy"]
        # Verify restricted permissions
        assert "geolocation=()" in permissions
        assert "microphone=()" in permissions
        assert "camera=()" in permissions

    @pytest.mark.asyncio
    async def test_security_headers_middleware_adds_hsts_in_production(
        self, client: AsyncClient
    ) -> None:
        """HSTS header should be added when DEBUG=false (production mode)."""
        response = await client.get("/health/live")

        # In test environment with DEBUG=true, HSTS should NOT be present
        # This test documents the expected production behavior

        # Check if we're in debug mode
        from app.config import get_settings

        settings = get_settings()

        if not settings.debug:
            # Production mode - HSTS should be present
            assert "Strict-Transport-Security" in response.headers
            hsts = response.headers["Strict-Transport-Security"]
            assert "max-age=31536000" in hsts
            assert "includeSubDomains" in hsts
        else:
            # Development mode - HSTS should NOT be present
            assert "Strict-Transport-Security" not in response.headers

    @pytest.mark.asyncio
    async def test_security_headers_middleware_no_hsts_in_development(
        self, client: AsyncClient
    ) -> None:
        """HSTS header should NOT be added when DEBUG=true (development mode)."""
        from app.config import get_settings

        settings = get_settings()

        # This test assumes we're running in debug mode
        if settings.debug:
            response = await client.get("/health/live")

            assert response.status_code == 200
            # HSTS should not be present in development
            assert "Strict-Transport-Security" not in response.headers

    @pytest.mark.asyncio
    async def test_security_headers_middleware_applied_to_all_responses(
        self, client: AsyncClient
    ) -> None:
        """Security headers should be on every endpoint response."""
        # Test multiple endpoints
        endpoints = [
            "/health/live",
            "/api/projects",
            "/api/config",
        ]

        for endpoint in endpoints:
            response = await client.get(endpoint)

            # Should have security headers regardless of status code
            assert "X-Content-Type-Options" in response.headers
            assert "X-Frame-Options" in response.headers
            assert "Content-Security-Policy" in response.headers


class TestSecurityHeadersContent:
    """Test specific security header content and values."""

    @pytest.mark.asyncio
    async def test_csp_prevents_inline_scripts(self, client: AsyncClient) -> None:
        """CSP should prevent inline script execution."""
        response = await client.get("/health/live")

        csp = response.headers.get("Content-Security-Policy", "")

        # script-src should be 'self' only (no 'unsafe-inline')
        assert "script-src 'self'" in csp
        assert "script-src 'self' 'unsafe-inline'" not in csp

    @pytest.mark.asyncio
    async def test_csp_allows_inline_styles(self, client: AsyncClient) -> None:
        """CSP should allow inline styles for compatibility."""
        response = await client.get("/health/live")

        csp = response.headers.get("Content-Security-Policy", "")

        # style-src should allow 'unsafe-inline'
        assert "style-src 'self' 'unsafe-inline'" in csp

    @pytest.mark.asyncio
    async def test_csp_prevents_framing(self, client: AsyncClient) -> None:
        """CSP should prevent framing via frame-ancestors."""
        response = await client.get("/health/live")

        csp = response.headers.get("Content-Security-Policy", "")

        # frame-ancestors should be 'none'
        assert "frame-ancestors 'none'" in csp

    @pytest.mark.asyncio
    async def test_permissions_policy_disables_dangerous_features(
        self, client: AsyncClient
    ) -> None:
        """Permissions-Policy should disable dangerous browser features."""
        response = await client.get("/health/live")

        permissions = response.headers.get("Permissions-Policy", "")

        # All dangerous features should be disabled (empty allowlist)
        dangerous_features = ["geolocation", "microphone", "camera", "payment", "usb"]

        for feature in dangerous_features:
            assert f"{feature}=()" in permissions
