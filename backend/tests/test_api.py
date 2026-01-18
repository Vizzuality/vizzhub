"""Tests for API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient) -> None:
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
    assert "id" in data


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient) -> None:
    await client.post(
        "/api/projects",
        json={"name": "Project 1"},
    )
    await client.post(
        "/api/projects",
        json={"name": "Project 2"},
    )

    response = await client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


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
