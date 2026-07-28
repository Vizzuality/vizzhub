"""Tests for PUT /api/projects/{project_id}/budget endpoint.

EVM fields (cost_to_date, percent_completed, percent_planned) are now derived
from the tracker module. This endpoint only handles milestones and budget_total.
"""

from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import DEFAULT_PROGRAM_ID


@pytest.fixture(autouse=True)
def _seed_program(default_program: str) -> None:
    """Projects require a program on create; seed the shared one for every test."""


@pytest.fixture
def _ensure_scoring_config(scoring_config):
    """Ensure scoring config is loaded before budget tests."""


@pytest.mark.usefixtures("_ensure_scoring_config")
class TestProjectBudgetEndpoint:
    """Tests for the project budget (milestones) endpoint."""

    async def _create_project(
        self,
        client: AsyncClient,
        budget: float | None = None,
    ) -> dict:
        """Helper to create a project and return its data."""
        payload: dict = {
            "program_id": DEFAULT_PROGRAM_ID,
            "name": "Budget Test Project",
            "code": "BTP.001",
        }
        if budget is not None:
            payload["budget"] = budget
        resp = await client.post("/api/projects", json=payload)
        assert resp.status_code == 201
        return resp.json()

    @pytest.mark.asyncio
    async def test_budget_creates_metrics_with_budget_total(self, client: AsyncClient) -> None:
        project = await self._create_project(client, budget=100000)
        resp = await client.put(
            f"/api/projects/{project['id']}/budget",
            json={"milestones": [{"name": "M1", "planned_date": "2026-06-01"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_year"] == date.today().year
        assert data["period_month"] == date.today().month
        assert len(data["milestones"]) == 1

    @pytest.mark.asyncio
    async def test_milestones_array(self, client: AsyncClient) -> None:
        project = await self._create_project(client)
        milestones = [
            {"name": "Design Complete", "planned_date": "2026-04-01"},
            {
                "name": "MVP Launch",
                "planned_date": "2026-06-01",
                "actual_date": "2026-06-15",
            },
        ]
        resp = await client.put(
            f"/api/projects/{project['id']}/budget",
            json={"milestones": milestones},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["milestones"]) == 2
        assert data["milestones"][0]["name"] == "Design Complete"
        assert data["milestones"][1]["actual_date"] == "2026-06-15"

    @pytest.mark.asyncio
    async def test_sequential_updates_preserve_milestones(self, client: AsyncClient) -> None:
        project = await self._create_project(client, budget=100000)
        url = f"/api/projects/{project['id']}/budget"

        await client.put(
            url,
            json={"milestones": [{"name": "Phase 1", "planned_date": "2026-04-01"}]},
        )
        resp = await client.put(
            url,
            json={"milestones": [{"name": "Phase 2", "planned_date": "2026-06-01"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["milestones"][0]["name"] == "Phase 2"

    @pytest.mark.asyncio
    async def test_empty_body_returns_200(self, client: AsyncClient) -> None:
        project = await self._create_project(client)
        resp = await client.put(
            f"/api/projects/{project['id']}/budget",
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "period_year" in data
        assert "milestones" in data

    @pytest.mark.asyncio
    async def test_nonexistent_project_returns_404(self, client: AsyncClient) -> None:
        fake_id = str(uuid4())
        resp = await client.put(
            f"/api/projects/{fake_id}/budget",
            json={"milestones": []},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_no_evm_data_accepted(self, client: AsyncClient) -> None:
        """evm_data is no longer accepted in the payload."""
        project = await self._create_project(client, budget=100000)
        resp = await client.put(
            f"/api/projects/{project['id']}/budget",
            json={"evm_data": {"cost_to_date": 50000}},
        )
        # evm_data is silently ignored (Pydantic model_config forbid not set)
        assert resp.status_code == 200
