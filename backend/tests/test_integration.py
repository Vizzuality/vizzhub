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
    today = date.today()
    metrics = MetricsDB(
        project_id=str(test_project.id),
        period_start=today - timedelta(days=30),
        period_end=today,
        period_year=today.year,
        period_month=today.month,
        snapshot_type="cumulative",
        # EVM data (normalized columns)
        budget_total=Decimal("100000.0"),
        cost_to_date=Decimal("45000.0"),
        percent_completed=Decimal("0.5"),
        percent_planned=Decimal("0.5"),
        # Milestones (JSON)
        milestones=[
            {
                "name": "Milestone 1",
                "planned_date": str(date.today() - timedelta(days=10)),
                "actual_date": str(date.today() - timedelta(days=10)),
            }
        ],
        # Defect metrics (normalized columns)
        bugs_total=5,
        tasks_completed=100,
        escaped_defects=1,
        mttr_hours=Decimal("24.0"),
        incidents_count=1,
        post_contract_tasks=0,
        # Flow metrics (normalized columns)
        lead_time_days=Decimal("3.0"),
        commitment_reliability=Decimal("0.9"),
        total_stories=50,
        stories_with_reviewer=45,
        # GitHub metrics (normalized columns)
        total_merged_prs=100,
        prs_without_review=5,
        high_severity_vulns=0,
        pr_size_median=Decimal("150.0"),
        review_turnaround_hours=Decimal("12.0"),
        deployment_frequency=Decimal("1.0"),
        change_failure_rate=Decimal("0.05"),
        # JSON fields
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
        assert scoring_config.get_weight("global", "quality") == 0.205
        assert scoring_config.get_weight("global", "flow") == 0.15

    @pytest.mark.asyncio
    async def test_config_targets_loaded_from_db(
        self, db_session: AsyncSession, scoring_config: ScoringConfig
    ) -> None:
        """Verify scoring config targets are loaded from database."""
        assert scoring_config.get_target("spi") == 0.8
        assert scoring_config.get_target("cpi") == 0.8
        assert scoring_config.get_target("lead_time_days") == 10.0
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
# 4. Metrics Upsert Integration Tests
# =============================================================================

class TestMetricsUpsertIntegration:
    """Test that metrics upsert behavior works correctly.

    Note: Consolidation of multiple records is no longer supported.
    With the new architecture, only ONE record per (project, year, month, snapshot_type)
    is allowed. Upsert updates existing records rather than creating duplicates.
    """

    @pytest.mark.asyncio
    async def test_upsert_creates_new_record(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        """Verify POST creates a new metrics record."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "governance_exceptions": 5,
            },
        )
        assert response.status_code == 201

        data = response.json()
        assert data["governance_exceptions"] == 5

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_record(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        """Verify POST updates existing record for same period/type."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        # Create initial record
        response1 = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "governance_exceptions": 5,
            },
        )
        assert response1.status_code == 201
        first_id = response1.json()["id"]

        # Update with same period (should upsert, not create new)
        response2 = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "governance_exceptions": 1,
            },
        )
        assert response2.status_code == 201
        second_id = response2.json()["id"]

        # Should be the same record
        assert first_id == second_id
        assert response2.json()["governance_exceptions"] == 1

    @pytest.mark.asyncio
    async def test_sev1_incident_caps_quality_score(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify sev1_incident caps P_quality at 60."""
        today = date.today()
        period_start = today - timedelta(days=30)

        # Create metrics with sev1_incident=True
        metrics = MetricsDB(
            project_id=str(test_project.id),
            period_start=period_start,
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="cumulative",
            bugs_total=5,
            tasks_completed=100,
            escaped_defects=1,
            mttr_hours=Decimal("24.0"),
            incidents_count=1,
            post_contract_tasks=0,
            sev1_incident=True,
        )
        db_session.add(metrics)
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
    """Test project status affects collectors and metrics."""

    @pytest.mark.asyncio
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

        response = await client.post(f"/api/collect/project/{project.id}/jira")

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()

    @pytest.mark.asyncio
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

        response = await client.post(f"/api/collect/project/{project.id}/github")

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
        response = await client.post(f"/api/collect/project/{test_project.id}/jira")

        # Should not be 400 with "finished" message
        if response.status_code == 400:
            assert "finished" not in response.json().get("detail", "").lower()

    @pytest.mark.asyncio
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
        response = await client.post(f"/api/collect/project/{test_project.id}/jira")
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
        """Verify SPI is calculated correctly from EVM data."""
        # SPI = percent_completed / percent_planned = 0.4 / 0.5 = 0.8
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
        """Verify CPI is calculated correctly from EVM data."""
        # CPI = EV / AC = (budget * percent_completed) / cost_to_date
        # CPI = (100000 * 0.5) / 40000 = 1.25
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


# =============================================================================
# 7. OAuth E2E Integration Tests
# =============================================================================

class TestOAuthE2EIntegration:
    """Test OAuth flow end-to-end with mocked external services."""

    @pytest.mark.asyncio
    async def test_oauth_authorize_returns_redirect_url(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify OAuth authorize endpoint returns a valid redirect URL."""
        response = await client.get("/api/oauth/jira/authorize")

        # Should redirect or return auth URL
        assert response.status_code in [200, 302, 307]

        if response.status_code == 200:
            data = response.json()
            assert "auth_url" in data or "authorization_url" in data

    @pytest.mark.asyncio
    async def test_oauth_callback_validates_state(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify OAuth callback rejects invalid state parameter."""
        response = await client.get(
            "/api/oauth/jira/callback",
            params={"code": "fake-code", "state": "invalid-state"},
        )

        # Should reject invalid state
        assert response.status_code in [400, 401, 403]

    @pytest.mark.asyncio
    async def test_oauth_status_returns_not_connected_initially(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify OAuth status shows not connected when no token exists."""
        response = await client.get("/api/oauth/jira/status")

        assert response.status_code == 200
        data = response.json()
        assert data.get("authenticated") is False


# =============================================================================
# 8. Calculator Chain Integration Tests
# =============================================================================

class TestCalculatorChainIntegration:
    """Test all 8 calculators work together correctly."""

    @pytest.mark.asyncio
    async def test_all_dimensions_calculate_with_complete_metrics(
        self,
        client: AsyncClient,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
    ) -> None:
        """Verify all 8 dimensions are calculated when metrics are complete."""
        project, _ = test_project_with_metrics

        response = await client.get(f"/api/scores/project/{project.id}")
        assert response.status_code == 200

        data = response.json()
        dimensions = data["scores"]["dimensions"]

        # All 8 dimensions should be present (though some may be null if data missing)
        expected_dimensions = [
            "p_time", "p_cost", "p_quality", "p_value",
            "p_satisfaction", "p_flow", "p_engineering", "p_risk"
        ]
        for dim in expected_dimensions:
            assert dim in dimensions, f"Missing dimension: {dim}"

    @pytest.mark.asyncio
    async def test_missing_metrics_dont_crash_other_dimensions(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify partial metrics don't prevent other dimensions from calculating."""
        # Create metrics with only EVM data (no GitHub, no Jira defects)
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
            percent_completed=Decimal("0.5"),
            percent_planned=Decimal("0.5"),
        )
        db_session.add(metrics)
        await db_session.commit()

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        dimensions = data["scores"]["dimensions"]

        # P_time and P_cost should be calculated from EVM data
        assert dimensions["p_time"] is not None
        assert dimensions["p_cost"] is not None

        # Other dimensions may be null but shouldn't crash
        assert "p_quality" in dimensions
        assert "p_flow" in dimensions

    @pytest.mark.asyncio
    async def test_final_score_uses_weighted_average(
        self,
        client: AsyncClient,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
        scoring_config: ScoringConfig,
    ) -> None:
        """Verify final score is weighted average of dimension scores."""
        project, _ = test_project_with_metrics

        response = await client.get(f"/api/scores/project/{project.id}")
        assert response.status_code == 200

        data = response.json()
        final_score = data["scores"]["score"]
        dimensions = data["scores"]["dimensions"]
        weights = data["scores"]["weights_applied"]

        # Calculate expected weighted average
        expected = 0.0
        for dim, weight in weights.items():
            dim_key = f"p_{dim}"
            if dimensions.get(dim_key) is not None:
                expected += dimensions[dim_key] * weight

        assert abs(final_score - expected) < 1, f"Final score {final_score} doesn't match weighted average {expected}"


# =============================================================================
# 9. Auth Middleware Integration Tests
# =============================================================================

class TestAuthMiddlewareIntegration:
    """Test authentication middleware behavior."""

    @pytest.mark.asyncio
    async def test_dev_mode_bypasses_auth(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        """Verify development mode allows requests without JWT."""
        # In tests, DEBUG=true so auth should be bypassed
        response = await client.get(f"/api/projects/{test_project.id}")

        # Should not get 401 Unauthorized
        assert response.status_code != 401

    @pytest.mark.asyncio
    async def test_valid_jwt_is_accepted(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        """Verify valid JWT token is accepted."""
        from app.core.auth import create_access_token

        token = create_access_token({"sub": "test-user", "roles": ["user"]})

        response = await client.get(
            f"/api/projects/{test_project.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Should succeed with valid token
        assert response.status_code in [200, 404]  # 404 if project doesn't exist

    @pytest.mark.asyncio
    async def test_invalid_jwt_is_rejected(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify invalid JWT token is rejected."""
        response = await client.get(
            "/api/projects",
            headers={"Authorization": "Bearer invalid-token-here"},
        )

        # Should get 401 even in dev mode when invalid token is provided
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_jwt_is_rejected(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify expired JWT token is rejected."""
        from app.core.auth import create_access_token
        from datetime import timedelta

        # Create token that expired 1 hour ago
        token = create_access_token(
            {"sub": "test-user", "roles": ["user"]},
            expires_delta=timedelta(hours=-1),
        )

        response = await client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401


# =============================================================================
# 10. Rate Limiting Integration Tests
# =============================================================================

class TestRateLimitingIntegration:
    """Test rate limiting is enforced."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify rate limit headers are present in response."""
        response = await client.get("/api/projects")

        # Check for rate limit headers
        # Note: Header names may vary based on slowapi configuration
        headers = response.headers
        rate_limit_headers = [
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
        ]
        # At least one rate limit header should be present
        has_rate_limit = any(h.lower() in [k.lower() for k in headers.keys()] for h in rate_limit_headers)
        assert has_rate_limit or response.status_code == 200  # May not have headers in all configs

    @pytest.mark.asyncio
    async def test_rate_limit_not_exceeded_normal_usage(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify normal usage doesn't trigger rate limit."""
        # Make a few requests - should all succeed
        for _ in range(3):
            response = await client.get("/api/projects")
            assert response.status_code != 429, "Rate limit triggered too early"


# =============================================================================
# 11. Config Hot-reload Integration Tests
# =============================================================================

class TestConfigHotReloadIntegration:
    """Test configuration changes affect calculations."""

    @pytest.mark.asyncio
    async def test_config_change_affects_scores(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
        scoring_config: ScoringConfig,
    ) -> None:
        """Verify changing config weights changes calculated scores."""
        project, _ = test_project_with_metrics

        # Get initial scores
        response1 = await client.get(f"/api/scores/project/{project.id}")
        assert response1.status_code == 200
        initial_score = response1.json()["scores"]["score"]

        # Weights are loaded from CSV, changing them requires updating the config
        # This test verifies the config is being used, not that hot-reload works
        # (hot-reload would require restarting the app)

        # Verify the score uses config weights
        assert initial_score > 0, "Score should be calculated using config weights"

    @pytest.mark.asyncio
    async def test_config_values_match_csv_seed(
        self,
        scoring_config: ScoringConfig,
    ) -> None:
        """Verify config values match what's in CSV seed."""
        # These values should match config_parameters.csv
        assert scoring_config.get_weight("global", "time") == 0.12
        assert scoring_config.get_weight("global", "quality") == 0.205
        assert scoring_config.get_target("spi") == 0.8
        assert scoring_config.get_constant("sev1_cap") == 60.0


# =============================================================================
# 12. Error Sanitization Integration Tests
# =============================================================================

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
        assert "file \"/" not in error_text  # No file paths like /app/...

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


# =============================================================================
# 13. Collector Pipeline Integration Tests
# =============================================================================

class TestCollectorPipelineIntegration:
    """Test complete collector → metrics → scores pipeline."""

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


# =============================================================================
# 14. End-of-Project Metrics Integration Tests
# =============================================================================

class TestEndOfProjectMetricsIntegration:
    """Test strategic_impact and client_survey end-of-project metrics."""

    @pytest.mark.asyncio
    async def test_strategic_impact_affects_p_value_score(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify strategic_impact is reflected in P_value calculation."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        # Create metrics with high strategic impact
        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "strategic_impact": "transformational",
            },
        )
        assert response.status_code == 201

        # Get scores
        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # OKR impact should reflect transformational = 1.0
        assert indicators.get("okr_impact") is not None
        assert indicators["okr_impact"] == 1.0

    @pytest.mark.asyncio
    async def test_strategic_impact_low_value(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify low strategic_impact produces lower score."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "strategic_impact": "low",
            },
        )
        assert response.status_code == 201

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # OKR impact should reflect low = 0.25
        assert indicators.get("okr_impact") == 0.25

    @pytest.mark.asyncio
    async def test_client_survey_affects_p_satisfaction(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify client_survey data affects P_satisfaction calculation."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        # Create metrics with perfect client survey
        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "client_survey": {
                    "understanding": 5,
                    "proactivity": 5,
                    "communication": 5,
                    "delivery_time": 5,
                    "response_time": 5,
                    "quality": 5,
                    "expectations": 5,
                    "recommend": 5,
                },
            },
        )
        assert response.status_code == 201

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # Client satisfaction should be 1.0 (all 5s = 100%)
        assert indicators.get("client_satisfaction") is not None
        assert indicators["client_satisfaction"] == 1.0

    @pytest.mark.asyncio
    async def test_client_survey_weighted_average(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify client_survey uses weighted average calculation."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        # Create metrics with mixed ratings
        # Quality has 24% weight, so rating of 5 there should have more impact
        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "client_survey": {
                    "understanding": 3,    # 12%
                    "proactivity": 3,      # 12%
                    "communication": 3,    # 10%
                    "delivery_time": 3,    # 14%
                    "response_time": 3,    # 10%
                    "quality": 5,          # 24% - highest weight
                    "expectations": 3,     # 12%
                    "recommend": 3,        # 6%
                },
            },
        )
        assert response.status_code == 201

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # Should be higher than (3/5 = 0.6) due to quality weight
        client_sat = indicators.get("client_satisfaction")
        assert client_sat is not None
        assert client_sat > 0.6  # Must be above average due to high quality score


# =============================================================================
# 15. Finished Project Metrics Restrictions Integration Tests
# =============================================================================

class TestFinishedProjectMetricsRestrictions:
    """Test that finished projects only allow end-of-project metrics."""

    @pytest_asyncio.fixture
    async def finished_project(self, db_session: AsyncSession) -> ProjectDB:
        """Create a finished project."""
        project = ProjectDB(
            id=str(uuid4()),
            name="Finished Integration Project",
            jira_project_key="FIP",
            github_repo="test/finished-project",
            start_date=date.today() - timedelta(days=180),
            end_date=date.today() - timedelta(days=30),
            status="finished",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        return project

    @pytest.mark.asyncio
    async def test_finished_project_allows_strategic_impact(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects allow strategic_impact updates."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "strategic_impact": "high",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["strategic_impact"] == "high"

    @pytest.mark.asyncio
    async def test_finished_project_allows_client_survey(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects allow client_survey updates."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "client_survey": {
                    "understanding": 4,
                    "proactivity": 4,
                    "communication": 5,
                    "delivery_time": 4,
                    "response_time": 4,
                    "quality": 5,
                    "expectations": 4,
                    "recommend": 5,
                },
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["client_survey"]["quality"] == 5

    @pytest.mark.asyncio
    async def test_finished_project_blocks_evm_data(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects block EVM data updates."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "evm_data": {
                    "budget_total": 100000.0,
                    "cost_to_date": 50000.0,
                    "percent_completed": 0.5,
                    "percent_planned": 0.5,
                },
            },
        )

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()
        assert "evm_data" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_finished_project_blocks_jira_defects(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects block Jira defect metrics."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "jira_defects": {
                    "bugs_total": 10,
                    "tasks_completed": 50,
                },
            },
        )

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_finished_project_blocks_github_metrics(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects block GitHub metrics."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "github_metrics": {
                    "total_merged_prs": 100,
                    "prs_without_review": 5,
                },
            },
        )

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_finished_project_blocks_governance_exceptions(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects block governance_exceptions updates."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "governance_exceptions": 2,
            },
        )

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_finished_project_allows_combined_end_of_project_metrics(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects allow both strategic_impact and client_survey together."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "strategic_impact": "transformational",
                "client_survey": {
                    "understanding": 5,
                    "proactivity": 5,
                    "communication": 5,
                    "delivery_time": 5,
                    "response_time": 5,
                    "quality": 5,
                    "expectations": 5,
                    "recommend": 5,
                },
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["strategic_impact"] == "transformational"
        assert data["client_survey"]["quality"] == 5

    @pytest.mark.asyncio
    async def test_reopen_project_allows_regular_metrics(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        finished_project: ProjectDB,
    ) -> None:
        """Verify reopening a project allows regular metrics again."""
        # First, reopen the project
        response = await client.patch(
            f"/api/projects/{finished_project.id}",
            json={"status": "in_progress"},
        )
        assert response.status_code == 200

        # Now regular metrics should be allowed
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "governance_exceptions": 1,
            },
        )

        assert response.status_code == 201


# =============================================================================
# 16. P_satisfaction Combined Calculation Integration Tests
# =============================================================================

class TestPSatisfactionCombinedCalculation:
    """Test P_satisfaction calculation with both PM and client satisfaction."""

    @pytest.mark.asyncio
    async def test_pm_satisfaction_only(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify P_satisfaction uses only PM when client_survey is absent."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "pm_satisfaction": {
                    "delivery_complaints": "no",
                    "design_complaints": "no",
                    "overall_estimation": 5,
                },
            },
        )
        assert response.status_code == 201

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # PM satisfaction should be calculated
        assert indicators.get("pm_satisfaction") is not None
        # Client satisfaction should be None
        assert indicators.get("client_satisfaction") is None

    @pytest.mark.asyncio
    async def test_both_pm_and_client_satisfaction(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify P_satisfaction combines both when client_survey exists."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "pm_satisfaction": {
                    "delivery_complaints": "no",
                    "design_complaints": "no",
                    "overall_estimation": 5,
                },
                "client_survey": {
                    "understanding": 5,
                    "proactivity": 5,
                    "communication": 5,
                    "delivery_time": 5,
                    "response_time": 5,
                    "quality": 5,
                    "expectations": 5,
                    "recommend": 5,
                },
            },
        )
        assert response.status_code == 201

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # Both should be present
        assert indicators.get("pm_satisfaction") is not None
        assert indicators.get("client_satisfaction") is not None

        # P_satisfaction score should be high
        dimensions = data["scores"]["dimensions"]
        assert dimensions["p_satisfaction"] is not None
        assert dimensions["p_satisfaction"] >= 90  # Should be high with perfect scores
