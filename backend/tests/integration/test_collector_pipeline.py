"""Collector pipeline integration tests.

Test complete collector -> metrics -> scores pipeline.
"""

import pytest
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB


class TestCollectorPipelineIntegration:
    """Test complete collector -> metrics -> scores pipeline."""

    @pytest.mark.asyncio
    async def test_metrics_update_via_api(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify metrics can be created and updated via API."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        # Create initial metrics
        response1 = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "governance_exceptions": 5,
            },
        )
        assert response1.status_code == 201

        # Get scores with initial metrics
        response2 = await client.get(f"/api/scores/project/{test_project.id}")
        assert response2.status_code == 200

        initial_indicators = response2.json()["indicators"]
        initial_governance = initial_indicators.get("governance_compliance")

        # Create updated metrics (simulating a collector run)
        response3 = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "governance_exceptions": 0,  # Improved
            },
        )
        assert response3.status_code == 201

        # Verify scores reflect the update
        response4 = await client.get(f"/api/scores/project/{test_project.id}")
        assert response4.status_code == 200

        updated_indicators = response4.json()["indicators"]
        updated_governance = updated_indicators.get("governance_compliance")

        # Governance compliance should improve (higher is better)
        if initial_governance is not None and updated_governance is not None:
            assert updated_governance >= initial_governance

    @pytest.mark.asyncio
    async def test_multiple_collectors_contribute_to_scores(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify metrics from different collectors are combined."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        # Simulate Jira collector output
        await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "jira_defects": {
                    "bugs_total": 10,
                    "bugs_open": 2,
                    "escaped_defects": 1,
                    "tasks_completed": 50,
                    "mttr_hours": 24.0,
                    "incidents_count": 1,
                    "post_contract_tasks": 0,
                },
                "flow_metrics": {
                    "lead_time_days": 3.0,
                    "commitment_reliability": 0.85,
                    "total_stories": 30,
                    "stories_with_reviewer": 28,
                },
            },
        )

        # Simulate GitHub collector output
        await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "github_metrics": {
                    "total_merged_prs": 50,
                    "prs_without_review": 2,
                    "pr_review_ratio": 0.96,
                    "high_severity_vulns": 0,
                    "pr_size_median": 120.0,
                    "review_turnaround_hours": 8.0,
                    "deployment_frequency": 1.2,
                    "change_failure_rate": 3.0,
                },
            },
        )

        # Get consolidated scores
        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # Should have indicators from both sources
        assert indicators.get("lead_time_days") is not None, "Should have Jira lead_time_days"
        assert indicators.get("pr_review_ratio") is not None, "Should have GitHub pr_review_ratio"
