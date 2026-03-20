"""Tests for PUT /api/projects/{project_id}/budget endpoint."""

from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.fixture
def _ensure_scoring_config(scoring_config):
    """Ensure scoring config is loaded before budget tests."""


@pytest.mark.usefixtures("_ensure_scoring_config")
class TestProjectBudgetEndpoint:
    """Tests for the project budget (EVM + milestones) endpoint."""

    async def _create_project(
        self, client: AsyncClient, budget: float | None = None,
    ) -> dict:
        """Helper to create a project and return its data."""
        payload: dict = {"name": "Budget Test Project", "code": "BTP.001"}
        if budget is not None:
            payload["budget"] = budget
        resp = await client.post("/api/projects", json=payload)
        assert resp.status_code == 201
        return resp.json()

    @pytest.mark.asyncio
    async def test_budget_creates_metrics_if_none_exist(
        self, client: AsyncClient
    ) -> None:
        project = await self._create_project(client, budget=100000)
        resp = await client.put(
            f"/api/projects/{project['id']}/budget",
            json={"evm_data": {"cost_to_date": 50000}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_year"] == date.today().year
        assert data["period_month"] == date.today().month
        assert data["evm_data"]["budget_total"] == 100000

    @pytest.mark.asyncio
    async def test_partial_evm_budget_from_project(self, client: AsyncClient) -> None:
        project = await self._create_project(client, budget=50000)
        resp = await client.put(
            f"/api/projects/{project['id']}/budget",
            json={"evm_data": {"cost_to_date": 10000}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["evm_data"]["budget_total"] == 50000
        assert data["evm_data"]["cost_to_date"] == 10000

    @pytest.mark.asyncio
    async def test_full_evm_all_fields(self, client: AsyncClient) -> None:
        project = await self._create_project(client, budget=200000)
        evm = {
            "cost_to_date": 80000,
            "percent_completed": 0.4,
            "percent_planned": 0.5,
        }
        resp = await client.put(
            f"/api/projects/{project['id']}/budget",
            json={"evm_data": evm},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["evm_data"]["budget_total"] == 200000
        assert data["evm_data"]["cost_to_date"] == 80000
        assert data["evm_data"]["percent_completed"] == pytest.approx(0.4)
        assert data["evm_data"]["percent_planned"] == pytest.approx(0.5)

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
    async def test_evm_and_milestones_together(self, client: AsyncClient) -> None:
        project = await self._create_project(client, budget=300000)
        resp = await client.put(
            f"/api/projects/{project['id']}/budget",
            json={
                "evm_data": {"cost_to_date": 100000},
                "milestones": [
                    {"name": "Phase 1", "planned_date": "2026-03-15"},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["evm_data"]["budget_total"] == 300000
        assert len(data["milestones"]) == 1

    @pytest.mark.asyncio
    async def test_sequential_updates_preserve_fields(
        self, client: AsyncClient
    ) -> None:
        project = await self._create_project(client, budget=100000)
        url = f"/api/projects/{project['id']}/budget"

        await client.put(url, json={"evm_data": {"cost_to_date": 20000}})
        resp = await client.put(
            url, json={"evm_data": {"cost_to_date": 40000}}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["evm_data"]["budget_total"] == 100000
        assert data["evm_data"]["cost_to_date"] == 40000

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
        assert "evm_data" in data

    @pytest.mark.asyncio
    async def test_nonexistent_project_returns_404(
        self, client: AsyncClient
    ) -> None:
        fake_id = str(uuid4())
        resp = await client.put(
            f"/api/projects/{fake_id}/budget",
            json={"evm_data": {"cost_to_date": 1000}},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_negative_evm_rejected(self, client: AsyncClient) -> None:
        project = await self._create_project(client)
        resp = await client.put(
            f"/api/projects/{project['id']}/budget",
            json={"evm_data": {"cost_to_date": -5000}},
        )
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_percent_over_one_rejected(self, client: AsyncClient) -> None:
        project = await self._create_project(client)
        resp = await client.put(
            f"/api/projects/{project['id']}/budget",
            json={"evm_data": {"percent_completed": 1.5}},
        )
        assert resp.status_code in (400, 422)
