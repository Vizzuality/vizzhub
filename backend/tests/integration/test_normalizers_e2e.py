"""E2E integration tests for normalizers.

Tests the complete flow: raw metrics -> indicators -> scores.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scorecard.models.metrics import MetricsDB
from app.core.models.project import ProjectDB


class TestNormalizersE2EIntegration:
    """Test complete flow: raw metrics -> indicators -> scores."""

    @pytest.mark.asyncio
    async def test_perfect_metrics_yield_high_scores(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify perfect metrics produce high scores."""
        today = date.today()
        metrics = MetricsDB(
            project_id=str(test_project.id),
            period_start=today - timedelta(days=30),
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="cumulative",
            # EVM data (SPI = 1.0)
            budget_total=Decimal("100000.0"),
            cost_to_date=Decimal("50000.0"),
            percent_completed=Decimal("0.5"),
            percent_planned=Decimal("0.5"),
            # Milestones (JSON)
            milestones=[
                {
                    "name": "M1",
                    "planned_date": str(date.today() - timedelta(days=10)),
                    "actual_date": str(date.today() - timedelta(days=10)),
                }
            ],
            # Defect metrics
            bugs_total=0,
            tasks_completed=100,
            escaped_defects=0,
            mttr_hours=Decimal("0.0"),
            incidents_count=0,
            post_contract_tasks=0,
            # Flow metrics
            lead_time_days=Decimal("1.0"),
            commitment_reliability=Decimal("1.0"),
            total_stories=50,
            stories_with_reviewer=50,
            # GitHub metrics
            total_merged_prs=100,
            prs_without_review=0,
            high_severity_vulns=0,
            pr_size_median=Decimal("100.0"),
            review_turnaround_hours=Decimal("4.0"),
            deployment_frequency=Decimal("2.0"),
            change_failure_rate=Decimal("0.0"),
            # JSON fields
            test_maturity={"e2e": 5, "unit": 5, "accessibility": 5, "security": 5, "frontend": 5},
            architecture={
                "docs_up_to_date": True,
                "iac_implemented": True,
                "adrs_maintained": True,
                "diagrams_updated": True,
            },
            pm_satisfaction={
                "delivery_complaints": "no",
                "design_complaints": "no",
                "overall_estimation": 5,
            },
            governance_exceptions=0,
            sev1_incident=False,
        )
        db_session.add(metrics)
        await db_session.commit()

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        dimensions = data["scores"]["dimensions"]

        # All scores should be high (>= 80)
        assert dimensions["p_time"] >= 80, f"P_time {dimensions['p_time']} should be >= 80"
        assert dimensions["p_cost"] >= 80, f"P_cost {dimensions['p_cost']} should be >= 80"
        assert dimensions["p_quality"] >= 80, f"P_quality {dimensions['p_quality']} should be >= 80"
        assert dimensions["p_flow"] >= 80, f"P_flow {dimensions['p_flow']} should be >= 80"
        assert dimensions["p_engineering"] >= 80, f"P_engineering {dimensions['p_engineering']} should be >= 80"
        assert dimensions["p_risk"] == 100, f"P_risk {dimensions['p_risk']} should be 100"

        # Final score should be high
        assert data["scores"]["score"] >= 80

    @pytest.mark.asyncio
    async def test_poor_metrics_yield_low_scores(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify poor metrics produce low scores."""
        today = date.today()
        metrics = MetricsDB(
            project_id=str(test_project.id),
            period_start=today - timedelta(days=30),
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="cumulative",
            # EVM data (SPI = 0.5, very behind)
            budget_total=Decimal("100000.0"),
            cost_to_date=Decimal("80000.0"),
            percent_completed=Decimal("0.3"),
            percent_planned=Decimal("0.6"),
            # Defect metrics
            bugs_total=50,
            tasks_completed=100,
            escaped_defects=20,
            mttr_hours=Decimal("100.0"),
            incidents_count=5,
            post_contract_tasks=10,
            # Flow metrics
            lead_time_days=Decimal("15.0"),
            commitment_reliability=Decimal("0.3"),
            total_stories=50,
            stories_with_reviewer=10,
            # GitHub metrics
            total_merged_prs=100,
            prs_without_review=30,
            high_severity_vulns=5,
            pr_size_median=Decimal("1000.0"),
            review_turnaround_hours=Decimal("72.0"),
            deployment_frequency=Decimal("0.1"),
            change_failure_rate=Decimal("0.5"),
            governance_exceptions=10,
            sev1_incident=True,
        )
        db_session.add(metrics)
        await db_session.commit()

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        dimensions = data["scores"]["dimensions"]

        # Quality capped at 60 due to sev1
        assert dimensions["p_quality"] <= 60

        # Risk should be 0 due to vulns
        assert dimensions["p_risk"] == 0

        # Final score should be low
        assert data["scores"]["score"] < 60

    @pytest.mark.asyncio
    async def test_spi_calculation_from_evm(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify SPI is calculated correctly from EVM data.

        SPI = percent_completed / percent_planned = 0.4 / 0.5 = 0.8
        """
        today = date.today()
        metrics = MetricsDB(
            project_id=str(test_project.id),
            period_start=today - timedelta(days=30),
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="cumulative",
            budget_total=Decimal("100000.0"),
            cost_to_date=Decimal("50000.0"),
            percent_completed=Decimal("0.4"),
            percent_planned=Decimal("0.5"),
        )
        db_session.add(metrics)
        await db_session.commit()

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        spi = data["indicators"]["spi"]

        assert spi is not None
        assert abs(spi - 0.8) < 0.01, f"SPI should be 0.8, got {spi}"

    @pytest.mark.asyncio
    async def test_cpi_calculation_from_evm(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify CPI is calculated correctly from EVM data.

        CPI = EV / AC = (budget * percent_completed) / cost_to_date
        CPI = (100000 * 0.5) / 40000 = 1.25
        """
        today = date.today()
        metrics = MetricsDB(
            project_id=str(test_project.id),
            period_start=today - timedelta(days=30),
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="cumulative",
            budget_total=Decimal("100000.0"),
            cost_to_date=Decimal("40000.0"),
            percent_completed=Decimal("0.5"),
            percent_planned=Decimal("0.5"),
        )
        db_session.add(metrics)
        await db_session.commit()

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        cpi = data["indicators"]["cpi"]

        assert cpi is not None
        assert abs(cpi - 1.25) < 0.01, f"CPI should be 1.25, got {cpi}"
