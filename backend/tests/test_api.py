"""Tests for API endpoints."""

import pytest
from httpx import AsyncClient


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_create_project_with_all_fields(self, client: AsyncClient) -> None:
        """Create project with all fields populated."""
        response = await client.post(
            "/api/projects",
            json={
                "name": "Test Project",
                "jira_project_key": "TEST",
                "github_repo": "org/repo",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Project"
        assert data["jira_project_key"] == "TEST"
        assert data["github_repo"] == "org/repo"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_create_project_with_dates(self, client: AsyncClient) -> None:
        """Create project with start_date and end_date."""
        response = await client.post(
            "/api/projects",
            json={
                "name": "Dated Project",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Dated Project"
        assert data["start_date"] == "2026-01-01"
        assert data["end_date"] == "2026-12-31"

    @pytest.mark.asyncio
    async def test_create_project_with_minimal_fields(
        self, client: AsyncClient
    ) -> None:
        """Create project with only required name field."""
        response = await client.post(
            "/api/projects",
            json={"name": "Minimal Project"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Project"
        assert data["jira_project_key"] is None
        assert data["github_repo"] is None

    @pytest.mark.asyncio
    async def test_create_project_empty_name_validation_error(
        self, client: AsyncClient
    ) -> None:
        """Creating project with empty name should return 422."""
        response = await client.post(
            "/api/projects",
            json={"name": ""},
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_create_project_missing_name_validation_error(
        self, client: AsyncClient
    ) -> None:
        """Creating project without name should return 422."""
        response = await client.post(
            "/api/projects",
            json={"jira_project_key": "TEST"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_project_invalid_github_repo_format(
        self, client: AsyncClient
    ) -> None:
        """Invalid github_repo format should return 422."""
        response = await client.post(
            "/api/projects",
            json={
                "name": "Test Project",
                "github_repo": "invalid-format",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_project_invalid_github_repo_with_slashes(
        self, client: AsyncClient
    ) -> None:
        """GitHub repo with multiple slashes should return 422."""
        response = await client.post(
            "/api/projects",
            json={
                "name": "Test Project",
                "github_repo": "org/repo/extra",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_project_name_too_long(self, client: AsyncClient) -> None:
        """Name exceeding 255 characters should return 422."""
        response = await client.post(
            "/api/projects",
            json={"name": "x" * 256},
        )
        assert response.status_code == 422


class TestListProjects:
    @pytest.mark.asyncio
    async def test_list_projects_returns_all(self, client: AsyncClient) -> None:
        """List all projects returns correct count."""
        await client.post("/api/projects", json={"name": "Project 1"})
        await client.post("/api/projects", json={"name": "Project 2"})

        response = await client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, client: AsyncClient) -> None:
        """List projects returns empty list when no projects."""
        response = await client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestGetProject:
    @pytest.mark.asyncio
    async def test_get_project_success(self, client: AsyncClient) -> None:
        """Get single project by ID."""
        create_response = await client.post(
            "/api/projects",
            json={"name": "Test Project", "jira_project_key": "TEST"},
        )
        project_id = create_response.json()["id"]

        response = await client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project_id
        assert data["name"] == "Test Project"
        assert data["jira_project_key"] == "TEST"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client: AsyncClient) -> None:
        """Get non-existent project returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/projects/{fake_uuid}")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert fake_uuid in data["detail"]

    @pytest.mark.asyncio
    async def test_get_project_invalid_uuid(self, client: AsyncClient) -> None:
        """Get project with invalid UUID format returns 422."""
        response = await client.get("/api/projects/not-a-uuid")
        assert response.status_code == 422


class TestUpdateProject:
    @pytest.mark.asyncio
    async def test_patch_project_partial_update(self, client: AsyncClient) -> None:
        """PATCH updates only provided fields."""
        create_response = await client.post(
            "/api/projects",
            json={
                "name": "Original Name",
                "jira_project_key": "ORIG",
                "github_repo": "org/original",
            },
        )
        project_id = create_response.json()["id"]

        response = await client.patch(
            f"/api/projects/{project_id}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["jira_project_key"] == "ORIG"
        assert data["github_repo"] == "org/original"

    @pytest.mark.asyncio
    async def test_patch_project_update_all_fields(self, client: AsyncClient) -> None:
        """PATCH can update all fields at once."""
        create_response = await client.post(
            "/api/projects",
            json={"name": "Original Name"},
        )
        project_id = create_response.json()["id"]

        response = await client.patch(
            f"/api/projects/{project_id}",
            json={
                "name": "New Name",
                "jira_project_key": "NEW",
                "github_repo": "new-org/new-repo",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["jira_project_key"] == "NEW"
        assert data["github_repo"] == "new-org/new-repo"

    @pytest.mark.asyncio
    async def test_patch_project_not_found(self, client: AsyncClient) -> None:
        """PATCH non-existent project returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.patch(
            f"/api/projects/{fake_uuid}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_project_invalid_github_repo(
        self, client: AsyncClient
    ) -> None:
        """PATCH with invalid github_repo returns 422."""
        create_response = await client.post(
            "/api/projects",
            json={"name": "Test Project"},
        )
        project_id = create_response.json()["id"]

        response = await client.patch(
            f"/api/projects/{project_id}",
            json={"github_repo": "invalid"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_project_empty_name(self, client: AsyncClient) -> None:
        """PATCH with empty name returns 422."""
        create_response = await client.post(
            "/api/projects",
            json={"name": "Test Project"},
        )
        project_id = create_response.json()["id"]

        response = await client.patch(
            f"/api/projects/{project_id}",
            json={"name": ""},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_project_empty_body(self, client: AsyncClient) -> None:
        """PATCH with empty body returns project unchanged."""
        create_response = await client.post(
            "/api/projects",
            json={"name": "Test Project"},
        )
        project_id = create_response.json()["id"]

        response = await client.patch(
            f"/api/projects/{project_id}",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Project"


class TestReplaceProject:
    @pytest.mark.asyncio
    async def test_put_replaces_all_fields(self, client: AsyncClient) -> None:
        """PUT replaces all fields including setting unspecified optional fields to null."""
        create_response = await client.post(
            "/api/projects",
            json={
                "name": "Original Project",
                "jira_project_key": "ORIG",
                "start_date": "2026-01-01",
            },
        )
        project_id = create_response.json()["id"]

        response = await client.put(
            f"/api/projects/{project_id}",
            json={
                "name": "Replaced Project",
                "jira_project_key": "REPL",
                "github_repo": "org/new-repo",
                "start_date": "2026-06-01",
                "end_date": "2026-12-31",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Replaced Project"
        assert data["jira_project_key"] == "REPL"
        assert data["github_repo"] == "org/new-repo"
        assert data["start_date"] == "2026-06-01"
        assert data["end_date"] == "2026-12-31"

    @pytest.mark.asyncio
    async def test_put_clears_unspecified_optional_fields(
        self, client: AsyncClient
    ) -> None:
        """PUT with minimal fields clears optional fields."""
        create_response = await client.post(
            "/api/projects",
            json={
                "name": "Original",
                "jira_project_key": "ORIG",
                "github_repo": "org/repo",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
        project_id = create_response.json()["id"]

        response = await client.put(
            f"/api/projects/{project_id}",
            json={"name": "Only Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Only Name"
        assert data["jira_project_key"] is None
        assert data["github_repo"] is None
        assert data["start_date"] is None
        assert data["end_date"] is None

    @pytest.mark.asyncio
    async def test_put_project_not_found(self, client: AsyncClient) -> None:
        """PUT non-existent project returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.put(
            f"/api/projects/{fake_uuid}",
            json={"name": "New Name"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_put_project_requires_name(self, client: AsyncClient) -> None:
        """PUT without name returns 422."""
        create_response = await client.post(
            "/api/projects",
            json={"name": "Test"},
        )
        project_id = create_response.json()["id"]

        response = await client.put(
            f"/api/projects/{project_id}",
            json={"jira_project_key": "TEST"},
        )
        assert response.status_code == 422


class TestDeleteProject:
    @pytest.mark.asyncio
    async def test_delete_project_success(self, client: AsyncClient) -> None:
        """Delete existing project returns 204."""
        create_response = await client.post(
            "/api/projects",
            json={"name": "To Delete"},
        )
        project_id = create_response.json()["id"]

        response = await client.delete(f"/api/projects/{project_id}")
        assert response.status_code == 204

        get_response = await client.get(f"/api/projects/{project_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project_not_found(self, client: AsyncClient) -> None:
        """Delete non-existent project returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(f"/api/projects/{fake_uuid}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project_removes_from_list(
        self, client: AsyncClient
    ) -> None:
        """Deleted project no longer appears in list."""
        await client.post("/api/projects", json={"name": "Project 1"})
        create_response = await client.post(
            "/api/projects", json={"name": "Project 2"}
        )
        project_id = create_response.json()["id"]

        list_before = await client.get("/api/projects")
        assert len(list_before.json()) == 2

        await client.delete(f"/api/projects/{project_id}")

        list_after = await client.get("/api/projects")
        assert len(list_after.json()) == 1
        assert all(p["id"] != project_id for p in list_after.json())


@pytest.mark.asyncio
async def test_get_config(client: AsyncClient) -> None:
    response = await client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "targets" in data
    assert "global_weights" in data
    assert "constants" in data


@pytest.mark.asyncio
async def test_validate_config(client: AsyncClient) -> None:
    response = await client.get("/api/config/validate")
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True


@pytest.mark.asyncio
async def test_calculate_scores_adhoc(client: AsyncClient) -> None:
    response = await client.post(
        "/api/scores/calculate",
        json={
            "metrics": {
                "period_start": "2024-01-01",
                "period_end": "2024-01-31",
                "evm_data": {
                    "budget_total": 100000,
                    "cost_to_date": 90000,
                    "percent_completed": 0.9,
                    "percent_planned": 0.9,
                },
                "github_metrics": {
                    "prs_without_review": 1,
                    "total_merged_prs": 50,
                    "pr_review_ratio": 0.98,
                    "high_severity_vulns": 0,
                },
            },
            "sev1_incident": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "indicators" in data
    assert "scores" in data
    assert "final_score" in data["scores"]
    assert 0 <= data["scores"]["final_score"] <= 100
