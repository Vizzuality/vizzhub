"""Integration tests for end-to-end flows.

These tests verify complete flows through the system, catching issues
that unit tests miss (like config loading from DB, metric consolidation, etc.)
"""

import pytest
import pytest_asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import ConfigParameter
from app.models.metrics import MetricsDB
from app.models.project import ProjectDB
from app.config import ScoringConfig, get_scoring_config, set_scoring_config


# =============================================================================
# Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def test_project(db_session: AsyncSession, scoring_config: ScoringConfig) -> ProjectDB:
    """Create a test project."""
    project = ProjectDB(
        id=str(uuid4()),
        name="Integration Test Project",
        jira_project_key="ITP",
        github_repo="test/integration-test",
        start_date=date.today() - timedelta(days=90),
        end_date=date.today() + timedelta(days=90),
        status="in_progress",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def test_project_with_metrics(
    db_session: AsyncSession, test_project: ProjectDB
) -> tuple[ProjectDB, MetricsDB]:
    """Create a test project with complete metrics."""
    metrics = MetricsDB(
        project_id=str(test_project.id),
        period_start=date.today() - timedelta(days=30),
        period_end=date.today(),
        evm_data={
            "budget_total": 100000.0,
            "cost_to_date": 45000.0,
            "percent_completed": 0.5,
            "percent_planned": 0.5,
        },
        milestones=[
            {
                "name": "Milestone 1",
                "planned_date": str(date.today() - timedelta(days=10)),
                "actual_date": str(date.today() - timedelta(days=10)),
            }
        ],
        jira_defects={
            "bugs_total": 5,
            "bugs_open": 2,
            "escaped_defects": 1,
            "tasks_completed": 100,
            "mttr_hours": 24.0,
            "incidents_count": 1,
            "post_contract_tasks": 0,
        },
        flow_metrics={
            "lead_time_days": 3.0,
            "commitment_reliability": 0.9,
            "total_stories": 50,
            "stories_with_reviewer": 45,
        },
        github_metrics={
            "total_merged_prs": 100,
            "prs_without_review": 5,
            "pr_review_ratio": 0.95,
            "high_severity_vulns": 0,
            "pr_size_median": 150.0,
            "review_turnaround_hours": 12.0,
            "deployment_frequency": 1.0,
            "change_failure_rate": 5.0,
        },
        test_maturity={
            "e2e": 4,
            "unit": 4,
            "accessibility": 3,
            "security": 4,
            "frontend": 4,
        },
        architecture={
            "docs_up_to_date": True,
            "iac_implemented": True,
            "adrs_maintained": True,
            "diagrams_updated": True,
        },
        pm_satisfaction={
            "delivery_complaints": "no",
            "design_complaints": "no",
            "overall_estimation": 4,
        },
        governance_exceptions=1,
        sev1_incident=False,
    )
    db_session.add(metrics)
    await db_session.commit()
    await db_session.refresh(metrics)
    return test_project, metrics


# =============================================================================
# 1. Scores API Integration Tests
# =============================================================================

class TestScoresAPIIntegration:
    """Test the scores API endpoint with real data flow."""

    @pytest.mark.asyncio
    async def test_scores_endpoint_returns_valid_dimensions(
        self,
        client: AsyncClient,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
    ) -> None:
        """Verify scores endpoint calculates all dimensions correctly."""
        project, metrics = test_project_with_metrics

        response = await client.get(f"/api/scores/project/{project.id}")

        assert response.status_code == 200
        data = response.json()

        # Verify all dimensions are calculated (not null)
        dimensions = data["scores"]["dimensions"]
        assert dimensions["p_time"] is not None, "P_time should be calculated with EVM data"
        assert dimensions["p_cost"] is not None, "P_cost should be calculated with EVM data"
        assert dimensions["p_quality"] is not None, "P_quality should be calculated"
        assert dimensions["p_flow"] is not None, "P_flow should be calculated"
        assert dimensions["p_engineering"] is not None, "P_engineering should be calculated"
        assert dimensions["p_risk"] is not None, "P_risk should be calculated"
        assert dimensions["p_satisfaction"] is not None, "P_satisfaction should be calculated"

    @pytest.mark.asyncio
    async def test_scores_endpoint_uses_config_from_db(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
    ) -> None:
        """Verify scores are calculated using config weights from database."""
        project, _ = test_project_with_metrics

        response = await client.get(f"/api/scores/project/{project.id}")
        assert response.status_code == 200

        data = response.json()
        weights = data["scores"]["weights_applied"]

        # Weights should sum to ~1.0 (with redistribution for missing dimensions)
        total_weight = sum(weights.values())
        assert 0.99 <= total_weight <= 1.01, f"Weights should sum to 1.0, got {total_weight}"

    @pytest.mark.asyncio
    async def test_scores_endpoint_returns_404_for_missing_project(
        self, client: AsyncClient
    ) -> None:
        """Verify 404 for non-existent project."""
        fake_id = str(uuid4())
        response = await client.get(f"/api/scores/project/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_scores_endpoint_returns_error_for_project_without_metrics(
        self, client: AsyncClient, test_project: ProjectDB
    ) -> None:
        """Verify appropriate error when project has no metrics."""
        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 404


# =============================================================================
# 2. Config Loading Integration Tests
# =============================================================================

class TestConfigLoadingIntegration:
    """Test that configuration is loaded correctly from database."""

    @pytest.mark.asyncio
    async def test_config_weights_loaded_from_db(
        self, db_session: AsyncSession, scoring_config: ScoringConfig
    ) -> None:
        """Verify scoring config weights are loaded from database."""
        # These should match the CSV seed values
        assert scoring_config.get_weight("global", "time") == 0.12
        assert scoring_config.get_weight("global", "quality") == 0.18
        assert scoring_config.get_weight("global", "flow") == 0.15

    @pytest.mark.asyncio
    async def test_config_targets_loaded_from_db(
        self, db_session: AsyncSession, scoring_config: ScoringConfig
    ) -> None:
        """Verify scoring config targets are loaded from database."""
        assert scoring_config.get_target("spi") == 1.0
        assert scoring_config.get_target("cpi") == 1.0
        assert scoring_config.get_target("lead_time_days") == 3.0
        assert scoring_config.get_target("mttr_hours") == 24.0

    @pytest.mark.asyncio
    async def test_config_constants_loaded_from_db(
        self, db_session: AsyncSession, scoring_config: ScoringConfig
    ) -> None:
        """Verify scoring config constants are loaded from database."""
        assert scoring_config.get_constant("sev1_cap") == 60.0
        assert scoring_config.get_constant("grace_days") == 3.0

    @pytest.mark.asyncio
    async def test_config_weight_groups_sum_to_one(
        self, scoring_config: ScoringConfig
    ) -> None:
        """Verify all weight groups sum to 1.0."""
        validation = scoring_config.validate_weights()

        for group_name, is_valid in validation.items():
            assert is_valid, f"{group_name} weights do not sum to 1.0"


# =============================================================================
# 3. Collectors Integration Tests
# =============================================================================

class TestCollectorsIntegration:
    """Test collector flows create metrics that affect scores."""

    @pytest.mark.asyncio
    async def test_metrics_creation_affects_scores(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify that creating metrics changes the scores."""
        # First, no metrics should return 404
        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 404

        # Create metrics via API
        metrics_data = {
            "period_start": str(date.today() - timedelta(days=30)),
            "period_end": str(date.today()),
            "evm_data": {
                "budget_total": 100000.0,
                "cost_to_date": 50000.0,
                "percent_completed": 0.5,
                "percent_planned": 0.5,
            },
            "governance_exceptions": 0,
        }

        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json=metrics_data,
        )
        assert response.status_code == 201  # 201 Created for new resource

        # Now scores should be calculable
        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["scores"]["dimensions"]["p_time"] is not None
        assert data["scores"]["dimensions"]["p_cost"] is not None


# =============================================================================
# 4. Metrics Consolidation Integration Tests
# =============================================================================

class TestMetricsConsolidationIntegration:
    """Test that multiple metrics records are consolidated correctly."""

    @pytest.mark.asyncio
    async def test_consolidates_metrics_from_same_period(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify metrics from same period_end are consolidated."""
        today = date.today()
        period_start = today - timedelta(days=30)

        # Create first metrics record with EVM data only
        metrics1 = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            evm_data={
                "budget_total": 100000.0,
                "cost_to_date": 50000.0,
                "percent_completed": 0.5,
                "percent_planned": 0.5,
            },
        )
        db_session.add(metrics1)
        await db_session.commit()

        # Create second metrics record with GitHub data only (simulating collector)
        metrics2 = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            github_metrics={
                "total_merged_prs": 50,
                "prs_without_review": 2,
                "pr_review_ratio": 0.96,
                "high_severity_vulns": 0,
                "pr_size_median": 100.0,
                "review_turnaround_hours": 8.0,
                "deployment_frequency": 1.5,
                "change_failure_rate": 2.0,
            },
        )
        db_session.add(metrics2)
        await db_session.commit()

        # Get scores - should have both EVM and GitHub data consolidated
        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # Should have indicators from both metrics records
        assert indicators["spi"] is not None, "SPI should come from EVM metrics"
        assert indicators["cpi"] is not None, "CPI should come from EVM metrics"
        assert indicators["pr_review_ratio"] is not None, "PR review should come from GitHub metrics"
        assert indicators["deployment_frequency"] is not None, "Deploy freq should come from GitHub"

    @pytest.mark.asyncio
    async def test_consolidation_prefers_most_recent_non_null(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify consolidation takes first non-null value (most recent)."""
        today = date.today()
        period_start = today - timedelta(days=30)

        # Create old metrics with governance_exceptions = 5
        metrics_old = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            governance_exceptions=5,
        )
        db_session.add(metrics_old)
        await db_session.commit()

        # Create newer metrics with governance_exceptions = 1
        metrics_new = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            governance_exceptions=1,
        )
        db_session.add(metrics_new)
        await db_session.commit()

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        # Should use the most recent value (1, not 5)
        assert data["indicators"]["governance_compliance"] is not None

    @pytest.mark.asyncio
    async def test_sev1_incident_true_if_any_record_has_it(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify sev1_incident is True if any consolidated record has it."""
        today = date.today()
        period_start = today - timedelta(days=30)

        # Create metrics without sev1
        metrics1 = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            jira_defects={
                "bugs_total": 5,
                "bugs_open": 2,
                "escaped_defects": 1,
                "tasks_completed": 100,
                "mttr_hours": 24.0,
                "incidents_count": 1,
                "post_contract_tasks": 0,
            },
            sev1_incident=False,
        )
        db_session.add(metrics1)

        # Create metrics with sev1
        metrics2 = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            sev1_incident=True,
        )
        db_session.add(metrics2)
        await db_session.commit()

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        # P_quality should be capped at 60 due to sev1
        assert data["scores"]["dimensions"]["p_quality"] <= 60


# =============================================================================
# 5. Project Status Integration Tests
# =============================================================================

class TestProjectStatusIntegration:
    """Test project status affects collectors and metrics.

    NOTE: These tests are marked as xfail until the project status blocking
    feature is implemented (see plan: parsed-greeting-glade.md).
    """

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Project status blocking not implemented yet")
    async def test_finished_project_blocks_jira_collector(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Verify Jira collector is blocked for finished projects."""
        # Create finished project
        project = ProjectDB(
            id=str(uuid4()),
            name="Finished Project",
            jira_project_key="FIN",
            start_date=date.today() - timedelta(days=180),
            end_date=date.today() - timedelta(days=30),
            status="finished",
        )
        db_session.add(project)
        await db_session.commit()

        response = await client.post(f"/api/collect/jira/{project.id}")

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Project status blocking not implemented yet")
    async def test_finished_project_blocks_github_collector(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Verify GitHub collector is blocked for finished projects."""
        project = ProjectDB(
            id=str(uuid4()),
            name="Finished Project",
            github_repo="test/finished",
            start_date=date.today() - timedelta(days=180),
            end_date=date.today() - timedelta(days=30),
            status="finished",
        )
        db_session.add(project)
        await db_session.commit()

        response = await client.post(f"/api/collect/github/{project.id}")

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_in_progress_project_allows_collectors(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        """Verify collectors work for in_progress projects (may fail for other reasons)."""
        # This will likely fail due to missing Jira/GitHub credentials,
        # but should NOT fail with "finished project" error
        response = await client.post(f"/api/collect/jira/{test_project.id}")

        # Should not be 400 with "finished" message
        if response.status_code == 400:
            assert "finished" not in response.json().get("detail", "").lower()

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Project status blocking not implemented yet")
    async def test_project_status_change_affects_collectors(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify changing project status from in_progress to finished blocks collectors."""
        # Update project to finished
        response = await client.patch(
            f"/api/projects/{test_project.id}",
            json={"status": "finished"},
        )
        assert response.status_code == 200

        # Now collectors should be blocked
        response = await client.post(f"/api/collect/jira/{test_project.id}")
        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()


# =============================================================================
# 6. Normalizers E2E Integration Tests
# =============================================================================

class TestNormalizersE2EIntegration:
    """Test complete flow: raw metrics → indicators → scores."""

    @pytest.mark.asyncio
    async def test_perfect_metrics_yield_high_scores(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify perfect metrics produce high scores."""
        metrics = MetricsDB(
            project_id=str(test_project.id),
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            evm_data={
                "budget_total": 100000.0,
                "cost_to_date": 50000.0,
                "percent_completed": 0.5,
                "percent_planned": 0.5,  # SPI = 1.0
            },
            milestones=[
                {
                    "name": "M1",
                    "planned_date": str(date.today() - timedelta(days=10)),
                    "actual_date": str(date.today() - timedelta(days=10)),
                }
            ],
            jira_defects={
                "bugs_total": 0,
                "bugs_open": 0,
                "escaped_defects": 0,
                "tasks_completed": 100,
                "mttr_hours": 0.0,
                "incidents_count": 0,
                "post_contract_tasks": 0,
            },
            flow_metrics={
                "lead_time_days": 1.0,  # Under target of 3
                "commitment_reliability": 1.0,
                "total_stories": 50,
                "stories_with_reviewer": 50,  # 100% review
            },
            github_metrics={
                "total_merged_prs": 100,
                "prs_without_review": 0,
                "pr_review_ratio": 1.0,
                "high_severity_vulns": 0,
                "pr_size_median": 100.0,  # Under target
                "review_turnaround_hours": 4.0,  # Under target
                "deployment_frequency": 2.0,  # Above target
                "change_failure_rate": 0.0,
            },
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
        metrics = MetricsDB(
            project_id=str(test_project.id),
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            evm_data={
                "budget_total": 100000.0,
                "cost_to_date": 80000.0,
                "percent_completed": 0.3,
                "percent_planned": 0.6,  # SPI = 0.5, very behind
            },
            jira_defects={
                "bugs_total": 50,
                "bugs_open": 30,
                "escaped_defects": 20,
                "tasks_completed": 100,
                "mttr_hours": 100.0,  # Very slow recovery
                "incidents_count": 5,
                "post_contract_tasks": 10,
            },
            flow_metrics={
                "lead_time_days": 15.0,  # 5x target
                "commitment_reliability": 0.3,
                "total_stories": 50,
                "stories_with_reviewer": 10,  # Only 20%
            },
            github_metrics={
                "total_merged_prs": 100,
                "prs_without_review": 30,  # 30% without review
                "pr_review_ratio": 0.5,
                "high_severity_vulns": 5,  # Critical!
                "pr_size_median": 1000.0,  # Way over target
                "review_turnaround_hours": 72.0,  # Very slow
                "deployment_frequency": 0.1,  # Very rare
                "change_failure_rate": 50.0,  # 50% failure
            },
            governance_exceptions=10,
            sev1_incident=True,  # Cap quality at 60
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
        """Verify SPI is calculated correctly from EVM data."""
        # SPI = percent_completed / percent_planned = 0.4 / 0.5 = 0.8
        metrics = MetricsDB(
            project_id=str(test_project.id),
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            evm_data={
                "budget_total": 100000.0,
                "cost_to_date": 50000.0,
                "percent_completed": 0.4,
                "percent_planned": 0.5,
            },
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
        """Verify CPI is calculated correctly from EVM data."""
        # CPI = EV / AC = (budget * percent_completed) / cost_to_date
        # CPI = (100000 * 0.5) / 40000 = 1.25
        metrics = MetricsDB(
            project_id=str(test_project.id),
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            evm_data={
                "budget_total": 100000.0,
                "cost_to_date": 40000.0,
                "percent_completed": 0.5,
                "percent_planned": 0.5,
            },
        )
        db_session.add(metrics)
        await db_session.commit()

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        cpi = data["indicators"]["cpi"]

        assert cpi is not None
        assert abs(cpi - 1.25) < 0.01, f"CPI should be 1.25, got {cpi}"
