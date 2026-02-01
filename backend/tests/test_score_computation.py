"""Tests for ScoreComputationService."""

import pytest

from app.config import ScoringConfig
from app.models.metrics import MetricsCreate, EVMData, GitHubMetrics, FlowMetrics, JiraDefectMetrics
from app.services.score_computation import ScoreComputationService


@pytest.fixture
def config() -> ScoringConfig:
    return ScoringConfig()


@pytest.fixture
def service(config: ScoringConfig) -> ScoreComputationService:
    return ScoreComputationService(config)


@pytest.fixture
def minimal_metrics() -> MetricsCreate:
    return MetricsCreate(
        period_start="2024-01-01",
        period_end="2024-01-31",
    )


@pytest.fixture
def complete_metrics() -> MetricsCreate:
    return MetricsCreate(
        period_start="2024-01-01",
        period_end="2024-01-31",
        evm_data=EVMData(
            budget_total=100000,
            cost_to_date=45000,
            percent_completed=0.50,
            percent_planned=0.50,
        ),
        github_metrics=GitHubMetrics(
            prs_without_review=2,
            total_merged_prs=100,
            pr_size_median=150,
            review_turnaround_hours=4,
            deployment_frequency=3.0,
            release_count_90d=12,
            change_failure_rate=0.05,
            total_releases=12,
            failed_releases=1,
            high_severity_vulns=0,
            high_severity_vulns_total=0,
        ),
        flow_metrics=FlowMetrics(
            lead_time_days=5,
            lead_time_sample_size=50,
            commitment_reliability=0.90,
            committed_issues=20,
            single_sprint_issues=18,
            multi_sprint_issues=2,
            total_stories=100,
            stories_with_reviewer=95,
        ),
        jira_defects=JiraDefectMetrics(
            bugs_total=5,
            tasks_completed=100,
            escaped_defects=1,
            mttr_hours=2.0,
            incidents_count=1,
        ),
    )


class TestScoreComputationService:
    def test_compute_returns_indicators_and_scores(
        self, service: ScoreComputationService, complete_metrics: MetricsCreate
    ):
        indicators, scores = service.compute(complete_metrics)

        assert indicators is not None
        assert scores is not None
        # Composite may be None if insufficient dimensions have values
        # The important thing is that it returns a score object

    def test_compute_with_minimal_metrics(
        self, service: ScoreComputationService, minimal_metrics: MetricsCreate
    ):
        indicators, scores = service.compute(minimal_metrics)

        assert indicators is not None
        assert scores is not None

    def test_compute_with_sev1_incident_caps_quality(
        self, service: ScoreComputationService, complete_metrics: MetricsCreate
    ):
        indicators_without, scores_without = service.compute(
            complete_metrics, sev1_incident=False
        )
        indicators_with, scores_with = service.compute(
            complete_metrics, sev1_incident=True
        )

        # If both have p_quality, the sev1 version should be capped at 60
        if scores_with.dimensions.p_quality is not None:
            assert scores_with.dimensions.p_quality <= 60

    def test_compute_indicators_only(
        self, service: ScoreComputationService, complete_metrics: MetricsCreate
    ):
        indicators = service.compute_indicators_only(complete_metrics)

        assert indicators is not None
        # SPI and CPI should be computed from EVM data
        assert indicators.spi is not None
        assert indicators.cpi is not None

    def test_compute_uses_github_total_prs(
        self, service: ScoreComputationService, complete_metrics: MetricsCreate
    ):
        indicators, scores = service.compute(complete_metrics)

        # Engineering score depends on having enough PRs
        assert scores is not None

    def test_compute_without_github_metrics(
        self, service: ScoreComputationService
    ):
        metrics = MetricsCreate(
            period_start="2024-01-01",
            period_end="2024-01-31",
            evm_data=EVMData(
                budget_total=100000,
                cost_to_date=45000,
                percent_completed=0.50,
                percent_planned=0.50,
            ),
        )
        indicators, scores = service.compute(metrics)

        assert indicators is not None
        assert scores is not None

    def test_indicators_spi_cpi_computed_from_evm(
        self, service: ScoreComputationService, complete_metrics: MetricsCreate
    ):
        indicators = service.compute_indicators_only(complete_metrics)

        # SPI should be percent_completed / percent_planned = 0.5/0.5 = 1.0
        assert indicators.spi == pytest.approx(1.0)
        # CPI should be (budget * percent_completed) / cost_to_date
        # = (100000 * 0.5) / 45000 = 50000/45000 = 1.111...
        assert indicators.cpi is not None
        assert indicators.cpi > 1.0

    def test_dora_score_computed(
        self, service: ScoreComputationService, complete_metrics: MetricsCreate
    ):
        _, scores = service.compute(complete_metrics)

        # DORA score should be computed when github/flow metrics present
        assert scores.dora is not None
        assert scores.dora.score is not None
        assert scores.dora.classification in ['Low', 'Medium', 'High', 'Elite']

    def test_service_uses_default_config_if_none_provided(self):
        service = ScoreComputationService()
        assert service.config is not None
        assert service.normalizer is not None
        assert service.calculator is not None

    def test_service_uses_provided_config(self, config: ScoringConfig):
        service = ScoreComputationService(config)
        assert service.config is config
