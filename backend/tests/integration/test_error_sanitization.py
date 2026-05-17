"""Integration tests for error response sanitization.

These tests verify that error responses don't leak sensitive information
like internal file paths, tracebacks, or implementation details.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.models.project import ProjectDB


class TestErrorSanitizationIntegration:
    """Test error responses don't leak sensitive information."""

    @pytest.mark.asyncio
    async def test_404_doesnt_leak_internal_paths(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify 404 errors don't expose internal file paths."""
        response = await client.get(f"/api/projects/{uuid4()}")

        assert response.status_code == 404
        error_text = response.text.lower()

        # Should not contain internal paths
        assert "/app/" not in error_text
        assert "/home/" not in error_text
        assert "/volumes/" not in error_text
        assert "traceback" not in error_text

    @pytest.mark.asyncio
    async def test_validation_error_is_descriptive(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        """Verify validation errors are helpful but not leaky."""
        # Send invalid data - missing required fields
        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={},  # Missing period_start and period_end
        )

        assert response.status_code in [400, 422]  # 400 or 422 depending on handler
        data = response.json()

        # Should have detail about the validation error
        assert "detail" in data or "errors" in data

        # Should not contain internal implementation details
        error_text = str(data).lower()
        assert "traceback" not in error_text
        assert 'file "/' not in error_text  # No file paths like /app/...

    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_clean_error(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify invalid UUID doesn't cause internal error leak."""
        response = await client.get("/api/projects/not-a-valid-uuid")

        # Should be 422 (validation error) or 400 (bad request), not 500
        assert response.status_code in [400, 404, 422]

        error_text = response.text.lower()
        assert "internal server error" not in error_text
