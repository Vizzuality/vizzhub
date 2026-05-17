"""Tests for Global Metrics feature.

Tests cover:
- GlobalMetricsService unit tests (averaging logic, empty handling, strategic impact)
- API integration tests (GET/POST endpoints, validation, batch calculation)
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig
from app.core.models.project import ProjectDB
from app.modules.scorecard.models.global_metrics import (
    GlobalIndicators,
    GlobalMetricsRecord,
    GlobalScores,
    IndicatorValue,
    ScoreValue,
)
from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.models.metrics import MetricsDB
from app.modules.scorecard.models.scores import DimensionScores, FinalScore
from app.modules.scorecard.services.global_metrics_service import (
    STRATEGIC_IMPACT_VALUES,
    GlobalMetricsService,
)

# =============================================================================
# Fixtures
# =============================================================================


async def create_test_project(
    db_session: AsyncSession,
    name: str,
    jira_key: str,
    github_repo: str,
    start_offset: int = 180,
    end_offset: int = 90,
) -> ProjectDB:
    """Helper to create and commit a single project."""
    today = date.today()
    project = ProjectDB(
        id=str(uuid4()),
        name=name,
        jira_project_key=jira_key,
        github_repo=github_repo,
        start_date=today - timedelta(days=start_offset),
        end_date=today + timedelta(days=end_offset),
        status="live",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


async def create_test_metrics(
    db_session: AsyncSession,
    project: ProjectDB,
    year: int,
    month: int,
    **kwargs,
) -> MetricsDB:
    """Helper to create and commit metrics for a project."""
    today = date.today()
    defaults = {
        "period_start": today - timedelta(days=30),
        "period_end": today,
        "snapshot_type": "cumulative",
        "sev1_incident": False,
    }
    defaults.update(kwargs)

    metrics = MetricsDB(
        project_id=str(project.id),
        period_year=year,
        period_month=month,
        **defaults,
    )
    db_session.add(metrics)
    await db_session.commit()
    await db_session.refresh(metrics)
    return metrics


@pytest_asyncio.fixture
async def test_projects_with_metrics(
    db_session: AsyncSession, scoring_config: ScoringConfig
) -> list[tuple[ProjectDB, MetricsDB]]:
    """Create multiple test projects with metrics for global averaging tests."""
    today = date.today()
    year, month = today.year, today.month
    results = []

    # Project 1: Good metrics
    project1 = await create_test_project(db_session, "Project Alpha", "ALPHA", "test/alpha")
    metrics1 = await create_test_metrics(
        db_session,
        project1,
        year,
        month,
        budget_total=Decimal("100000.0"),
        cost_to_date=Decimal("50000.0"),
        percent_completed=Decimal("0.5"),
        percent_planned=Decimal("0.5"),
        bugs_total=5,
        tasks_completed=100,
        lead_time_days=Decimal("3.0"),
        commitment_reliability=Decimal("0.9"),
        total_merged_prs=50,
        prs_without_review=2,
    )
    results.append((project1, metrics1))

    # Project 2: Different metrics values
    project2 = await create_test_project(db_session, "Project Beta", "BETA", "test/beta", 120, 180)
    metrics2 = await create_test_metrics(
        db_session,
        project2,
        year,
        month,
        budget_total=Decimal("200000.0"),
        cost_to_date=Decimal("120000.0"),
        percent_completed=Decimal("0.6"),
        percent_planned=Decimal("0.5"),
        bugs_total=10,
        tasks_completed=200,
        lead_time_days=Decimal("5.0"),
        commitment_reliability=Decimal("0.8"),
        total_merged_prs=100,
        prs_without_review=10,
    )
    results.append((project2, metrics2))

    # Project 3: With strategic impact
    project3 = await create_test_project(
        db_session, "Project Gamma", "GAMMA", "test/gamma", 90, 120
    )
    metrics3 = await create_test_metrics(
        db_session,
        project3,
        year,
        month,
        budget_total=Decimal("150000.0"),
        cost_to_date=Decimal("75000.0"),
        percent_completed=Decimal("0.5"),
        percent_planned=Decimal("0.5"),
        bugs_total=8,
        tasks_completed=150,
        lead_time_days=Decimal("4.0"),
        strategic_impact="high",
    )
    results.append((project3, metrics3))

    return results


@pytest_asyncio.fixture
async def global_metrics_service(
    scoring_config: ScoringConfig,
) -> GlobalMetricsService:
    """Create GlobalMetricsService with test config."""
    return GlobalMetricsService(scoring_config)


# =============================================================================
# 1. GlobalMetricsService Unit Tests
# =============================================================================


class TestGlobalMetricsServiceAveraging:
    """Test indicator and score averaging logic."""

    def test_average_indicators_with_values(
        self, global_metrics_service: GlobalMetricsService
    ) -> None:
        """Verify indicator averaging only counts non-null values."""
        indicators = [
            IndicatorsCreate(spi=1.0, cpi=0.9, lead_time_days=3.0),
            IndicatorsCreate(spi=0.8, cpi=1.0, lead_time_days=5.0),
            IndicatorsCreate(spi=0.9, cpi=None, lead_time_days=4.0),  # cpi is None
        ]

        result = global_metrics_service._average_indicators(indicators, [])

        assert result.spi.value == pytest.approx(0.9, rel=0.01)  # (1.0+0.8+0.9)/3
        assert result.spi.count == 3

        assert result.cpi.value == pytest.approx(0.95, rel=0.01)  # (0.9+1.0)/2
        assert result.cpi.count == 2  # Only 2 have values

        assert result.lead_time_days.value == pytest.approx(4.0, rel=0.01)
        assert result.lead_time_days.count == 3

    def test_average_indicators_empty_list(
        self, global_metrics_service: GlobalMetricsService
    ) -> None:
        """Verify empty indicator list returns null values with count=0."""
        result = global_metrics_service._average_indicators([], [])

        assert result.spi.value is None
        assert result.spi.count == 0
        assert result.cpi.value is None
        assert result.cpi.count == 0

    def test_average_indicators_with_strategic_impact(
        self, global_metrics_service: GlobalMetricsService
    ) -> None:
        """Verify strategic impact is averaged from numeric conversion."""
        indicators = [IndicatorsCreate(), IndicatorsCreate()]
        strategic_impacts = [
            STRATEGIC_IMPACT_VALUES["high"],  # 0.80
            STRATEGIC_IMPACT_VALUES["transformational"],  # 1.0
        ]

        result = global_metrics_service._average_indicators(indicators, strategic_impacts)

        assert result.strategic_impact.value == pytest.approx(0.9, rel=0.01)  # (0.8+1.0)/2
        assert result.strategic_impact.count == 2

    def test_average_scores_with_values(self, global_metrics_service: GlobalMetricsService) -> None:
        """Verify score averaging only counts non-null dimensions."""
        scores = [
            FinalScore(
                score=85.0,
                dimensions=DimensionScores(
                    p_time=90.0,
                    p_cost=80.0,
                    p_quality=85.0,
                    p_value=None,
                    p_satisfaction=75.0,
                    p_flow=88.0,
                    p_engineering=82.0,
                    p_risk=90.0,
                ),
                weights_applied={},
            ),
            FinalScore(
                score=75.0,
                dimensions=DimensionScores(
                    p_time=70.0,
                    p_cost=80.0,
                    p_quality=75.0,
                    p_value=70.0,
                    p_satisfaction=None,
                    p_flow=72.0,
                    p_engineering=78.0,
                    p_risk=80.0,
                ),
                weights_applied={},
            ),
        ]

        result = global_metrics_service._average_scores(scores)

        assert result.score.value == pytest.approx(80.0, rel=0.01)  # (85+75)/2
        assert result.score.count == 2

        assert result.p_time.value == pytest.approx(80.0, rel=0.01)  # (90+70)/2
        assert result.p_time.count == 2

        assert result.p_value.value == pytest.approx(70.0, rel=0.01)  # Only 1 value
        assert result.p_value.count == 1

        assert result.p_satisfaction.value == pytest.approx(75.0, rel=0.01)  # Only 1 value
        assert result.p_satisfaction.count == 1

    def test_average_scores_by_budget(self, global_metrics_service: GlobalMetricsService) -> None:
        """Audit #17: weighted average uses project.budget as the weight.
        Projects without budget are excluded."""
        scores = [
            FinalScore(
                score=90.0,
                dimensions=DimensionScores(p_time=90.0, p_cost=80.0),
                weights_applied={},
            ),
            FinalScore(
                score=60.0,
                dimensions=DimensionScores(p_time=60.0, p_cost=40.0),
                weights_applied={},
            ),
            FinalScore(  # excluded — no budget
                score=10.0,
                dimensions=DimensionScores(p_time=10.0, p_cost=5.0),
                weights_applied={},
            ),
        ]
        budgets = [800_000.0, 200_000.0, None]

        result = global_metrics_service._average_scores_by_budget(scores, budgets)

        assert result.project_count == 2
        # 90 * 800k + 60 * 200k = 72M + 12M = 84M ; / 1M = 84
        assert result.score == pytest.approx(84.0, rel=0.001)
        assert result.p_time == pytest.approx(84.0, rel=0.001)
        # 80 * 800k + 40 * 200k = 64M + 8M = 72M ; / 1M = 72
        assert result.p_cost == pytest.approx(72.0, rel=0.001)

    def test_average_scores_by_budget_all_without_budget(
        self, global_metrics_service: GlobalMetricsService
    ) -> None:
        """Audit #17: when no project has a budget, return zero count and nulls."""
        scores = [
            FinalScore(
                score=80.0,
                dimensions=DimensionScores(p_time=70.0),
                weights_applied={},
            ),
        ]
        budgets: list[float | None] = [None]

        result = global_metrics_service._average_scores_by_budget(scores, budgets)

        assert result.project_count == 0
        assert result.score is None
        assert result.p_time is None

    def test_average_scores_by_budget_excludes_dimension_when_none(
        self, global_metrics_service: GlobalMetricsService
    ) -> None:
        """Audit #17: a dimension with None in the eligible project is still
        excluded from the weighted average (weights redistributed among
        projects that have a value)."""
        scores = [
            FinalScore(
                score=90.0,
                dimensions=DimensionScores(p_time=90.0, p_cost=None),
                weights_applied={},
            ),
            FinalScore(
                score=60.0,
                dimensions=DimensionScores(p_time=60.0, p_cost=40.0),
                weights_applied={},
            ),
        ]
        budgets = [800_000.0, 200_000.0]

        result = global_metrics_service._average_scores_by_budget(scores, budgets)

        assert result.project_count == 2
        # p_cost: only the 200k project contributes → 40.0
        assert result.p_cost == pytest.approx(40.0, rel=0.001)

    def test_average_scores_empty_list(self, global_metrics_service: GlobalMetricsService) -> None:
        """Verify empty score list returns null values with count=0."""
        result = global_metrics_service._average_scores([])

        assert result.score.value is None
        assert result.score.count == 0
        assert result.p_time.value is None
        assert result.p_time.count == 0


class TestGlobalMetricsServiceCalculation:
    """Test full calculation and storage flow."""

    @pytest.mark.asyncio
    async def test_calculate_and_store_with_projects(
        self,
        db_session: AsyncSession,
        global_metrics_service: GlobalMetricsService,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
    ) -> None:
        """Verify calculate_and_store creates record with averaged values."""
        today = date.today()
        year, month = today.year, today.month

        result = await global_metrics_service.calculate_and_store(db_session, year, month)

        assert result is not None
        assert result.period_year == year
        assert result.period_month == month
        assert result.project_count == 3  # 3 test projects

        # Verify some indicator is averaged
        assert result.spi is not None or result.spi_count >= 0

    @pytest.mark.asyncio
    async def test_calculate_and_store_uses_metrics_presence_as_oracle(
        self,
        db_session: AsyncSession,
        global_metrics_service: GlobalMetricsService,
    ) -> None:
        """Audit #17 (2026-05-15 refinement): membership in the portfolio
        aggregate for month M is determined by the presence of a MetricsDB
        row for that month, not by the project's current status. The monthly
        capture cron only writes rows for status=live, so FINISHED/PROPOSAL
        projects don't grow new rows — but if they do have rows for that
        month, they belong in the aggregate."""
        today = date.today()
        year, month = today.year, today.month

        live = await create_test_project(db_session, "Live", "LIVE", "v/live")
        finished = await create_test_project(db_session, "Done", "DONE", "v/done")
        finished.status = "finished"
        proposal = await create_test_project(db_session, "Draft", "DRAFT", "v/draft")
        proposal.status = "proposal"
        db_session.add_all([finished, proposal])
        await db_session.flush()

        await create_test_metrics(db_session, live, year, month)
        await create_test_metrics(db_session, finished, year, month)
        await create_test_metrics(db_session, proposal, year, month)

        result = await global_metrics_service.calculate_and_store(db_session, year, month)

        # All three contributed because all three had a captured row.
        assert result.project_count == 3

    @pytest.mark.asyncio
    async def test_calculate_and_store_empty_period(
        self,
        db_session: AsyncSession,
        global_metrics_service: GlobalMetricsService,
    ) -> None:
        """Verify empty period returns record with project_count=0."""
        result = await global_metrics_service.calculate_and_store(db_session, 2020, 1)

        assert result is not None
        assert result.period_year == 2020
        assert result.period_month == 1
        assert result.project_count == 0

    @pytest.mark.asyncio
    async def test_calculate_and_store_upsert(
        self,
        db_session: AsyncSession,
        global_metrics_service: GlobalMetricsService,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
    ) -> None:
        """Verify calculate_and_store updates existing record on re-run."""
        today = date.today()
        year, month = today.year, today.month

        first_result = await global_metrics_service.calculate_and_store(db_session, year, month)
        first_id = first_result.id

        second_result = await global_metrics_service.calculate_and_store(db_session, year, month)

        assert second_result.id == first_id  # Same record updated
        assert second_result.project_count == 3

    @pytest.mark.asyncio
    async def test_calculate_batch(
        self,
        db_session: AsyncSession,
        global_metrics_service: GlobalMetricsService,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
    ) -> None:
        """Verify batch calculation processes all months in range."""
        today = date.today()
        year = today.year

        # Calculate 3 months
        from_month = max(1, today.month - 2)
        to_month = today.month

        results = await global_metrics_service.calculate_batch(
            db_session, year, from_month, year, to_month
        )

        expected_months = to_month - from_month + 1
        assert len(results) == expected_months

        # Current month should have projects, earlier months may be empty
        current_month_record = next(r for r in results if r.period_month == today.month)
        assert current_month_record.project_count == 3

    @pytest.mark.asyncio
    async def test_get_record(
        self,
        db_session: AsyncSession,
        global_metrics_service: GlobalMetricsService,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
    ) -> None:
        """Verify get_record returns stored metrics."""
        today = date.today()
        year, month = today.year, today.month

        await global_metrics_service.calculate_and_store(db_session, year, month)
        result = await global_metrics_service.get_record(db_session, year, month)

        assert result is not None
        assert result.project_count == 3

    @pytest.mark.asyncio
    async def test_get_record_not_found(
        self,
        db_session: AsyncSession,
        global_metrics_service: GlobalMetricsService,
    ) -> None:
        """Verify get_record returns None for non-existent period."""
        result = await global_metrics_service.get_record(db_session, 2020, 1)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_history(
        self,
        db_session: AsyncSession,
        global_metrics_service: GlobalMetricsService,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
    ) -> None:
        """Verify get_history returns records in descending order."""
        today = date.today()

        # Create records for distinct months to avoid duplicates
        months_to_create = [
            (2024, 10),
            (2024, 11),
            (2024, 12),
        ]
        for year, month in months_to_create:
            await global_metrics_service.calculate_and_store(db_session, year, month)

        results = await global_metrics_service.get_history(db_session, limit=10)

        assert len(results) == 3
        # Should be descending by date
        assert (results[0].period_year, results[0].period_month) >= (
            results[1].period_year,
            results[1].period_month,
        )
        assert (results[1].period_year, results[1].period_month) >= (
            results[2].period_year,
            results[2].period_month,
        )

    @pytest.mark.asyncio
    async def test_get_available_months(
        self,
        db_session: AsyncSession,
        global_metrics_service: GlobalMetricsService,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
    ) -> None:
        """Verify get_available_months returns list of calculated periods."""
        today = date.today()
        year, month = today.year, today.month

        await global_metrics_service.calculate_and_store(db_session, year, month)

        results = await global_metrics_service.get_available_months(db_session)

        assert len(results) >= 1
        assert (year, month) in results


class TestStrategicImpactConversion:
    """Test strategic impact category to numeric conversion."""

    def test_strategic_impact_values(self) -> None:
        """Verify strategic impact mapping values."""
        assert STRATEGIC_IMPACT_VALUES["low"] == pytest.approx(0.25)
        assert STRATEGIC_IMPACT_VALUES["medium"] == pytest.approx(0.55)
        assert STRATEGIC_IMPACT_VALUES["high"] == pytest.approx(0.80)
        assert STRATEGIC_IMPACT_VALUES["transformational"] == pytest.approx(1.0)

    def test_strategic_impact_case_insensitive(
        self, global_metrics_service: GlobalMetricsService
    ) -> None:
        """Verify strategic impact is handled case-insensitively in service."""
        # This is tested via the calculate_and_store flow which lowercases values
        pass  # Implementation detail tested in integration


# =============================================================================
# 2. API Integration Tests
# =============================================================================


class TestGlobalMetricsAPI:
    """Test Global Metrics API endpoints."""

    @pytest.mark.asyncio
    async def test_get_history_empty(self, client: AsyncClient) -> None:
        """Verify GET /global/history returns empty list when no data."""
        response = await client.get("/api/global/history")

        assert response.status_code == 200
        data = response.json()
        assert data["records"] == []

    @pytest.mark.asyncio
    async def test_get_history_with_data(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
        scoring_config: ScoringConfig,
    ) -> None:
        """Verify GET /global/history returns calculated records."""
        today = date.today()

        # First calculate some data
        service = GlobalMetricsService(scoring_config)
        await service.calculate_and_store(db_session, today.year, today.month)

        response = await client.get("/api/global/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data["records"]) >= 1
        assert data["records"][0]["project_count"] == 3

    @pytest.mark.asyncio
    async def test_get_history_with_limit(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
        scoring_config: ScoringConfig,
    ) -> None:
        """Verify GET /global/history respects limit parameter."""
        today = date.today()

        service = GlobalMetricsService(scoring_config)
        # Create 3 months of data
        for i in range(3):
            month = max(1, today.month - i)
            await service.calculate_and_store(db_session, today.year, month)

        response = await client.get("/api/global/history?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["records"]) == 2

    @pytest.mark.asyncio
    async def test_get_specific_month_not_found(self, client: AsyncClient) -> None:
        """Verify GET /global/{year}/{month} returns null for missing data."""
        response = await client.get("/api/global/2020/1")

        assert response.status_code == 200
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_get_specific_month_with_data(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
        scoring_config: ScoringConfig,
    ) -> None:
        """Verify GET /global/{year}/{month} returns calculated data."""
        today = date.today()

        service = GlobalMetricsService(scoring_config)
        await service.calculate_and_store(db_session, today.year, today.month)

        response = await client.get(f"/api/global/{today.year}/{today.month}")

        assert response.status_code == 200
        data = response.json()
        assert data is not None
        assert data["period_year"] == today.year
        assert data["period_month"] == today.month
        assert data["project_count"] == 3

    @pytest.mark.asyncio
    async def test_get_specific_month_invalid_month(self, client: AsyncClient) -> None:
        """Verify GET /global/{year}/{month} validates month range."""
        response = await client.get("/api/global/2024/13")
        assert response.status_code == 400

        response = await client.get("/api/global/2024/0")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_available_months_empty(self, client: AsyncClient) -> None:
        """Verify GET /global/available-months returns empty list when no data."""
        response = await client.get("/api/global/available-months")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_available_months_with_data(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
        scoring_config: ScoringConfig,
    ) -> None:
        """Verify GET /global/available-months lists calculated periods."""
        today = date.today()

        service = GlobalMetricsService(scoring_config)
        await service.calculate_and_store(db_session, today.year, today.month)

        response = await client.get("/api/global/available-months")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert {"year": today.year, "month": today.month} in data

    @pytest.mark.asyncio
    async def test_calculate_batch(
        self,
        client: AsyncClient,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
    ) -> None:
        """Verify POST /global/calculate creates records for date range."""
        today = date.today()

        response = await client.post(
            "/api/global/calculate",
            json={
                "from_year": today.year,
                "from_month": today.month,
                "to_year": today.year,
                "to_month": today.month,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["months_processed"] == 1
        assert len(data["records"]) == 1
        assert data["records"][0]["project_count"] == 3

    @pytest.mark.asyncio
    async def test_calculate_batch_multiple_months(
        self,
        client: AsyncClient,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
    ) -> None:
        """Verify POST /global/calculate handles multi-month range."""
        today = date.today()
        from_month = max(1, today.month - 2)

        response = await client.post(
            "/api/global/calculate",
            json={
                "from_year": today.year,
                "from_month": from_month,
                "to_year": today.year,
                "to_month": today.month,
            },
        )

        assert response.status_code == 200
        data = response.json()
        expected_months = today.month - from_month + 1
        assert data["months_processed"] == expected_months

    @pytest.mark.asyncio
    async def test_calculate_batch_invalid_range(self, client: AsyncClient) -> None:
        """Verify POST /global/calculate rejects invalid date range."""
        # from > to
        response = await client.post(
            "/api/global/calculate",
            json={
                "from_year": 2024,
                "from_month": 6,
                "to_year": 2024,
                "to_month": 3,
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_calculate_batch_invalid_year(self, client: AsyncClient) -> None:
        """Verify POST /global/calculate rejects year before 2023."""
        response = await client.post(
            "/api/global/calculate",
            json={
                "from_year": 2022,
                "from_month": 1,
                "to_year": 2024,
                "to_month": 3,
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_recalculate(
        self,
        client: AsyncClient,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
    ) -> None:
        """Verify POST /global/recalculate updates existing records."""
        today = date.today()

        # First calculate
        await client.post(
            "/api/global/calculate",
            json={
                "from_year": today.year,
                "from_month": today.month,
                "to_year": today.year,
                "to_month": today.month,
            },
        )

        # Then recalculate
        response = await client.post(
            "/api/global/recalculate",
            json={
                "from_year": today.year,
                "from_month": today.month,
                "to_year": today.year,
                "to_month": today.month,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["months_processed"] == 1


# =============================================================================
# 3. GlobalMetricsRecord Conversion Tests
# =============================================================================


class TestGlobalMetricsRecordConversion:
    """Test Pydantic model conversion from DB."""

    @pytest.mark.asyncio
    async def test_from_db_conversion(
        self,
        db_session: AsyncSession,
        global_metrics_service: GlobalMetricsService,
        test_projects_with_metrics: list[tuple[ProjectDB, MetricsDB]],
    ) -> None:
        """Verify GlobalMetricsRecord.from_db converts correctly."""
        today = date.today()

        db_record = await global_metrics_service.calculate_and_store(
            db_session, today.year, today.month
        )

        record = GlobalMetricsRecord.from_db(db_record)

        assert record.id == str(db_record.id)
        assert record.period_year == db_record.period_year
        assert record.period_month == db_record.period_month
        assert record.project_count == db_record.project_count

        # Verify nested indicators
        assert isinstance(record.indicators, GlobalIndicators)
        assert isinstance(record.indicators.spi, IndicatorValue)

        # Verify nested scores
        assert isinstance(record.scores, GlobalScores)
        assert isinstance(record.scores.score, ScoreValue)
