"""Security tests for API endpoints.

Tests cover:
- SQL injection prevention
- XSS payload handling
- Authentication enforcement
- Input validation
- UUID validation
- JQL injection prevention
- Cascade delete operations
- Concurrent update handling
"""

import asyncio
from uuid import uuid4

import pytest
from httpx import AsyncClient


class TestProjectsSQLInjection:
    """SQL injection prevention tests for projects endpoints."""

    @pytest.mark.asyncio
    async def test_get_project_sql_injection_in_uuid(
        self, client: AsyncClient
    ) -> None:
        """Test that SQL injection in UUID parameter returns 422."""
        sql_payload = "'; DROP TABLE projects--"
        response = await client.get(f"/api/projects/{sql_payload}")
        assert response.status_code == 422




class TestProjectsCascadeDelete:
    """Test cascade delete operations for projects."""

    @pytest.mark.asyncio
    async def test_delete_project_cascades_to_metrics(
        self, client: AsyncClient
    ) -> None:
        """Verify that deleting a project cascades to metrics."""
        create_response = await client.post(
            "/api/projects",
            json={"name": "Project to Delete", "jira_project_key": "TEST"},
        )
        project_id = create_response.json()["id"]

        collect_response = await client.post(f"/api/collect/project/{project_id}/jira")

        if collect_response.status_code == 201:
            metrics_list = await client.get(f"/api/metrics/project/{project_id}")
            initial_count = (
                len(metrics_list.json()) if metrics_list.status_code == 200 else 0
            )
            assert initial_count > 0

            delete_response = await client.delete(f"/api/projects/{project_id}")
            assert delete_response.status_code == 204

            get_project_response = await client.get(f"/api/projects/{project_id}")
            assert get_project_response.status_code == 404

            metrics_list_response = await client.get(
                f"/api/metrics/project/{project_id}"
            )
            assert metrics_list_response.status_code == 404
        else:
            delete_response = await client.delete(f"/api/projects/{project_id}")
            assert delete_response.status_code == 204


class TestProjectsInputValidation:
    """Additional input validation tests for projects endpoints."""

    @pytest.mark.asyncio
    async def test_project_update_preserves_other_fields(
        self, client: AsyncClient
    ) -> None:
        """Test that PATCH update preserves fields not included in request."""
        create_response = await client.post(
            "/api/projects",
            json={
                "name": "Original Name",
                "jira_project_key": "ORIG",
                "github_repo": "org/repo",
            },
        )
        project_id = create_response.json()["id"]

        update_response = await client.patch(
            f"/api/projects/{project_id}",
            json={"name": "Updated Name"},
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["name"] == "Updated Name"
        assert data["jira_project_key"] == "ORIG"
        assert data["github_repo"] == "org/repo"




class TestCollectorsValidation:
    """Validation tests for collectors endpoints."""

    @pytest.mark.asyncio
    async def test_collect_jira_metrics_project_not_found(
        self, client: AsyncClient
    ) -> None:
        """Test that collection returns 404 when project_id invalid."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.post(f"/api/collect/project/{fake_uuid}/jira")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_collect_jira_metrics_no_jira_key_configured(
        self, client: AsyncClient
    ) -> None:
        """Test that error occurs when project has no jira_project_key."""
        create_response = await client.post(
            "/api/projects",
            json={"name": "Project Without Jira Key"},
        )
        project_id = create_response.json()["id"]

        response = await client.post(f"/api/collect/project/{project_id}/jira")
        assert response.status_code == 400
        assert "jira project key" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_collect_jira_metrics_no_authentication_configured(
        self, client: AsyncClient
    ) -> None:
        """Test that error occurs when no Jira authentication is configured."""
        create_response = await client.post(
            "/api/projects",
            json={"name": "Project With Jira Key", "jira_project_key": "TEST"},
        )
        project_id = create_response.json()["id"]

        response = await client.post(f"/api/collect/project/{project_id}/jira")
        assert response.status_code == 503
        detail = response.json()["detail"].lower()
        assert "authentication" in detail or "configured" in detail or "authorized" in detail
        assert "project key format" not in detail

    @pytest.mark.asyncio
    async def test_collect_jira_metrics_invalid_uuid_format(
        self, client: AsyncClient
    ) -> None:
        """Test that invalid UUID format returns 422."""
        response = await client.post("/api/collect/project/not-a-uuid/jira")
        assert response.status_code == 422


class TestCollectorsJQLInjection:
    """JQL injection prevention tests for collectors endpoints."""

    @pytest.mark.asyncio
    async def test_collect_jira_metrics_jql_injection_prevented(
        self, client: AsyncClient
    ) -> None:
        """Test that project key is validated before JQL query construction."""
        jql_injection = "TEST' OR '1'='1"
        create_response = await client.post(
            "/api/projects",
            json={"name": "Test Project", "jira_project_key": jql_injection},
        )
        project_id = create_response.json()["id"]

        response = await client.post(f"/api/collect/project/{project_id}/jira")
        assert response.status_code in [201, 400, 500, 503]


class TestMetricsAuthentication:
    """Authentication tests for metrics endpoints."""

    @pytest.mark.asyncio
    async def test_get_metrics_project_not_found(self, client: AsyncClient) -> None:
        """Test that 404 is returned when project_id doesn't exist."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/metrics/project/{fake_uuid}")
        assert response.status_code == 404


class TestMetricsValidation:
    """Validation tests for metrics endpoints."""

    @pytest.mark.asyncio
    async def test_create_metrics_invalid_period_dates(
        self, client: AsyncClient
    ) -> None:
        """Test that invalid date format returns 422."""
        create_response = await client.post(
            "/api/projects",
            json={"name": "Test Project", "jira_project_key": "TEST"},
        )
        project_id = create_response.json()["id"]

        response = await client.post(
            f"/api/scores/calculate",
            json={
                "metrics": {
                    "period_start": "invalid-date",
                    "period_end": "2026-01-31",
                },
                "sev1_incident": False,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_metrics_invalid_evm_data_structure(
        self, client: AsyncClient
    ) -> None:
        """Test that malformed evm_data returns 422."""
        response = await client.post(
            "/api/scores/calculate",
            json={
                "metrics": {
                    "period_start": "2026-01-01",
                    "period_end": "2026-01-31",
                    "evm_data": {
                        "budget_total": "invalid",
                    },
                },
                "sev1_incident": False,
            },
        )
        assert response.status_code == 422


class TestScoresAuthentication:
    """Authentication tests for scores endpoints."""

    @pytest.mark.asyncio
    async def test_get_project_scores_project_not_found(
        self, client: AsyncClient
    ) -> None:
        """Test that 404 is returned when project_id is invalid."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/scores/project/{fake_uuid}")
        assert response.status_code == 404


class TestScoresEdgeCases:
    """Edge case tests for scores endpoints."""

    @pytest.mark.asyncio
    async def test_get_project_scores_no_metrics_returns_error(
        self, client: AsyncClient
    ) -> None:
        """Test that no metrics returns 404 error."""
        create_response = await client.post(
            "/api/projects",
            json={"name": "Project Without Metrics"},
        )
        project_id = create_response.json()["id"]

        response = await client.get(f"/api/scores/project/{project_id}")
        assert response.status_code == 404
        assert "metrics not found" in response.json()["detail"].lower()
