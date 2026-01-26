"""Tests for dimension calculators."""

import pytest

from app.config import ScoringConfig
from app.models.indicators import IndicatorsCreate
from app.services.calculators.dimensions import (
    CostCalculator,
    EngineeringCalculator,
    FlowCalculator,
    QualityCalculator,
    RiskCalculator,
    SatisfactionCalculator,
    TimeCalculator,
    ValueCalculator,
)
from app.services.calculators.final_score import FinalScoreCalculator


@pytest.fixture
def config() -> ScoringConfig:
    return ScoringConfig()


@pytest.fixture
def perfect_indicators() -> IndicatorsCreate:
    return IndicatorsCreate(
        spi=1.0,
        on_time_milestones=1.0,
        cpi=1.0,
        budget_variance=0.0,
        defect_density=0.0,
        escaped_rate=0.0,
        mttr_hours=0.0,
        governance_compliance=1.0,
        lead_time_days=1.0,
        flow_efficiency=0.5,
        commitment_reliability=1.0,
        pr_review_ratio=1.0,
        prs_without_review=0,
        high_vulns=0,
        test_maturity=1.0,
        arch_checklist=1.0,
        story_review_ratio=1.0,
        okr_impact=1.0,
        pm_satisfaction=1.0,
        client_satisfaction=1.0,
        pr_size_median=100.0,
        review_turnaround_hours=4.0,
        deployment_frequency=2.0,
        change_failure_rate=0.0,
        post_contract_tasks=0,
    )


@pytest.fixture
def neutral_indicators() -> IndicatorsCreate:
    return IndicatorsCreate()


class TestTimeCalculator:
    def test_perfect_score(
        self, config: ScoringConfig, perfect_indicators: IndicatorsCreate
    ) -> None:
        calc = TimeCalculator(config)
        score = calc.calculate(perfect_indicators)
        assert score == 100

    def test_no_data_returns_none(
        self, config: ScoringConfig, neutral_indicators: IndicatorsCreate
    ) -> None:
        calc = TimeCalculator(config)
        score = calc.calculate(neutral_indicators)
        assert score is None

    def test_only_spi_available(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        indicators = IndicatorsCreate(spi=1.0, on_time_milestones=None)
        score = calc.calculate(indicators)
        assert score == 100

    def test_only_milestones_available(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        indicators = IndicatorsCreate(spi=None, on_time_milestones=0.85)
        score = calc.calculate(indicators)
        assert score == 100

    def test_partial_spi_with_perfect_milestones(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        indicators = IndicatorsCreate(spi=0.8, on_time_milestones=1.0)
        score = calc.calculate(indicators)
        assert score == 88

    def test_low_milestones_with_perfect_spi(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        indicators = IndicatorsCreate(spi=1.0, on_time_milestones=0.5)
        score = calc.calculate(indicators)
        assert score == 84


class TestCostCalculator:
    def test_perfect_score(
        self, config: ScoringConfig, perfect_indicators: IndicatorsCreate
    ) -> None:
        calc = CostCalculator(config)
        score = calc.calculate(perfect_indicators)
        assert score == 100

    def test_over_budget_penalty(self, config: ScoringConfig) -> None:
        calc = CostCalculator(config)
        indicators = IndicatorsCreate(cpi=1.0, budget_variance=0.5)
        score = calc.calculate(indicators)
        assert score == 85

    def test_no_data_returns_none(self, config: ScoringConfig) -> None:
        calc = CostCalculator(config)
        indicators = IndicatorsCreate()
        score = calc.calculate(indicators)
        assert score is None

    def test_only_cpi_available(self, config: ScoringConfig) -> None:
        calc = CostCalculator(config)
        indicators = IndicatorsCreate(cpi=1.0, budget_variance=None)
        score = calc.calculate(indicators)
        assert score == 100

    def test_only_variance_available(self, config: ScoringConfig) -> None:
        calc = CostCalculator(config)
        indicators = IndicatorsCreate(cpi=None, budget_variance=0.0)
        score = calc.calculate(indicators)
        assert score == 100

    def test_low_cpi_with_good_variance(self, config: ScoringConfig) -> None:
        calc = CostCalculator(config)
        indicators = IndicatorsCreate(cpi=0.8, budget_variance=0.0)
        score = calc.calculate(indicators)
        assert score == 86


class TestQualityCalculator:
    def test_perfect_score(
        self, config: ScoringConfig, perfect_indicators: IndicatorsCreate
    ) -> None:
        calc = QualityCalculator(config)
        score = calc.calculate(perfect_indicators)
        assert score == 100

    def test_sev1_cap(
        self, config: ScoringConfig, perfect_indicators: IndicatorsCreate
    ) -> None:
        calc = QualityCalculator(config)
        score = calc.calculate(perfect_indicators, sev1_incident=True)
        assert score == 60

    def test_no_data_returns_none(self, config: ScoringConfig) -> None:
        calc = QualityCalculator(config)
        indicators = IndicatorsCreate()
        score = calc.calculate(indicators)
        assert score is None

    def test_sev1_with_no_data_returns_none(self, config: ScoringConfig) -> None:
        calc = QualityCalculator(config)
        indicators = IndicatorsCreate()
        score = calc.calculate(indicators, sev1_incident=True)
        assert score is None

    def test_partial_data_redistributes_weights(self, config: ScoringConfig) -> None:
        calc = QualityCalculator(config)
        indicators = IndicatorsCreate(
            defect_density=0.0,
            escaped_rate=0.0,
            governance_compliance=1.0,
        )
        score = calc.calculate(indicators)
        assert score == 100

    def test_only_story_review_available(self, config: ScoringConfig) -> None:
        calc = QualityCalculator(config)
        indicators = IndicatorsCreate(story_review_ratio=0.8)
        score = calc.calculate(indicators)
        assert score == 80

    def test_high_defect_density_lowers_score(self, config: ScoringConfig) -> None:
        calc = QualityCalculator(config)
        indicators = IndicatorsCreate(
            defect_density=6.0,
            escaped_rate=0.0,
            mttr_hours=0.0,
            story_review_ratio=1.0,
            governance_compliance=1.0,
            pr_review_ratio=1.0,
            change_failure_rate=0.0,
            post_contract_tasks=0,
        )
        score = calc.calculate(indicators)
        assert score == 98


class TestValueCalculator:
    def test_transformational_impact(self, config: ScoringConfig) -> None:
        calc = ValueCalculator(config)
        indicators = IndicatorsCreate(okr_impact=1.0)
        score = calc.calculate(indicators)
        assert score == 100

    def test_high_impact(self, config: ScoringConfig) -> None:
        calc = ValueCalculator(config)
        indicators = IndicatorsCreate(okr_impact=0.80)
        score = calc.calculate(indicators)
        assert score == 80

    def test_medium_impact(self, config: ScoringConfig) -> None:
        calc = ValueCalculator(config)
        indicators = IndicatorsCreate(okr_impact=0.55)
        score = calc.calculate(indicators)
        assert score == 55

    def test_low_impact(self, config: ScoringConfig) -> None:
        calc = ValueCalculator(config)
        indicators = IndicatorsCreate(okr_impact=0.25)
        score = calc.calculate(indicators)
        assert score == 25

    def test_no_data_returns_none(self, config: ScoringConfig) -> None:
        calc = ValueCalculator(config)
        indicators = IndicatorsCreate()
        score = calc.calculate(indicators)
        assert score is None


class TestSatisfactionCalculator:
    def test_with_client_survey(self, config: ScoringConfig) -> None:
        calc = SatisfactionCalculator(config)
        indicators = IndicatorsCreate(client_satisfaction=0.9, pm_satisfaction=0.8)
        score = calc.calculate(indicators)
        assert score == 89  # 0.9 * 0.9 + 0.8 * 0.1 = 0.89

    def test_pm_only(self, config: ScoringConfig) -> None:
        calc = SatisfactionCalculator(config)
        indicators = IndicatorsCreate(pm_satisfaction=0.8)
        score = calc.calculate(indicators)
        assert score == 80  # 100% weight redistributed to PM

    def test_client_only(self, config: ScoringConfig) -> None:
        calc = SatisfactionCalculator(config)
        indicators = IndicatorsCreate(client_satisfaction=0.9)
        score = calc.calculate(indicators)
        assert score == 90  # 100% weight redistributed to client

    def test_no_data_returns_none(self, config: ScoringConfig) -> None:
        calc = SatisfactionCalculator(config)
        indicators = IndicatorsCreate()
        score = calc.calculate(indicators)
        assert score is None

    def test_perfect_score(self, config: ScoringConfig) -> None:
        calc = SatisfactionCalculator(config)
        indicators = IndicatorsCreate(client_satisfaction=1.0, pm_satisfaction=1.0)
        score = calc.calculate(indicators)
        assert score == 100


class TestFlowCalculator:
    def test_perfect_flow(
        self, config: ScoringConfig, perfect_indicators: IndicatorsCreate
    ) -> None:
        calc = FlowCalculator(config)
        score = calc.calculate(perfect_indicators)
        assert score == 100

    def test_no_data_returns_none(self, config: ScoringConfig) -> None:
        calc = FlowCalculator(config)
        indicators = IndicatorsCreate()
        score = calc.calculate(indicators)
        assert score is None

    def test_only_lead_time_available(self, config: ScoringConfig) -> None:
        calc = FlowCalculator(config)
        indicators = IndicatorsCreate(lead_time_days=1.5)  # Target is 3 days
        score = calc.calculate(indicators)
        assert score == 100  # 1.5 < 3 → fully meets target

    def test_partial_data_redistributes_weights(self, config: ScoringConfig) -> None:
        calc = FlowCalculator(config)
        indicators = IndicatorsCreate(
            lead_time_days=3.0,  # Target 3 days → 1.0
            commitment_reliability=1.0,
        )
        score = calc.calculate(indicators)
        assert score == 100

    def test_slow_lead_time_lowers_score(self, config: ScoringConfig) -> None:
        calc = FlowCalculator(config)
        indicators = IndicatorsCreate(
            lead_time_days=6.0,  # 2x target → 0.5
            commitment_reliability=1.0,
            pr_size_median=200.0,  # Under target → 1.0
            review_turnaround_hours=12.0,  # Under target → 1.0
            deployment_frequency=1.0,  # Meets target → 1.0
        )
        score = calc.calculate(indicators)
        # 0.35 * 0.5 + 0.25 * 1.0 + 0.15 * 1.0 + 0.10 * 1.0 + 0.15 * 1.0 = 0.825
        assert score == 82


class TestEngineeringCalculator:
    def test_perfect_engineering(
        self, config: ScoringConfig, perfect_indicators: IndicatorsCreate
    ) -> None:
        calc = EngineeringCalculator(config)
        score = calc.calculate(perfect_indicators)
        assert score == 100

    def test_no_data_returns_none(self, config: ScoringConfig) -> None:
        calc = EngineeringCalculator(config)
        indicators = IndicatorsCreate()
        score = calc.calculate(indicators)
        assert score is None

    def test_only_test_maturity_available(self, config: ScoringConfig) -> None:
        calc = EngineeringCalculator(config)
        indicators = IndicatorsCreate(test_maturity=0.8)
        score = calc.calculate(indicators)
        assert score == 80  # 100% weight redistributed to test maturity

    def test_partial_data_redistributes_weights(self, config: ScoringConfig) -> None:
        calc = EngineeringCalculator(config)
        indicators = IndicatorsCreate(
            test_maturity=1.0,  # weight 0.5
            arch_checklist=1.0,  # weight 0.3
        )
        score = calc.calculate(indicators)
        assert score == 100  # Both components at 100%

    def test_low_test_maturity_lowers_score(self, config: ScoringConfig) -> None:
        calc = EngineeringCalculator(config)
        indicators = IndicatorsCreate(
            test_maturity=0.6,  # weight 0.5
            pr_review_ratio=1.0,  # weight 0.2
            arch_checklist=1.0,  # weight 0.3
        )
        score = calc.calculate(indicators)
        # 0.5 * 0.6 + 0.2 * 1.0 + 0.3 * 1.0 = 0.80
        assert score == 80


class TestRiskCalculator:
    def test_no_risk(
        self, config: ScoringConfig, perfect_indicators: IndicatorsCreate
    ) -> None:
        calc = RiskCalculator(config)
        score = calc.calculate(perfect_indicators, total_prs=100)
        assert score == 100

    def test_high_vuln_strict_penalty(self, config: ScoringConfig) -> None:
        calc = RiskCalculator(config)
        indicators = IndicatorsCreate(prs_without_review=0, high_vulns=1)
        score = calc.calculate(indicators, total_prs=100)
        assert score == 50  # 0.5 * 1.0 (no PRs without review) + 0.5 * 0.0 (strict zero)

    def test_no_data_returns_none(self, config: ScoringConfig) -> None:
        calc = RiskCalculator(config)
        indicators = IndicatorsCreate()
        score = calc.calculate(indicators)
        assert score is None

    def test_only_vulns_available(self, config: ScoringConfig) -> None:
        calc = RiskCalculator(config)
        indicators = IndicatorsCreate(high_vulns=0)
        score = calc.calculate(indicators)
        assert score == 100  # Weight redistributed to vulns only

    def test_only_prs_without_review_available(self, config: ScoringConfig) -> None:
        calc = RiskCalculator(config)
        indicators = IndicatorsCreate(prs_without_review=0)
        score = calc.calculate(indicators, total_prs=100)
        assert score == 100  # Weight redistributed to PRs only

    def test_some_prs_without_review(self, config: ScoringConfig) -> None:
        calc = RiskCalculator(config)
        # Target is 2% of total PRs, with 100 PRs that's 2 PRs allowed
        indicators = IndicatorsCreate(prs_without_review=2, high_vulns=0)
        score = calc.calculate(indicators, total_prs=100)
        # 0.5 * 0.0 (2/2 = at target = 0) + 0.5 * 1.0 (no vulns) = 0.5
        assert score == 50


class TestFinalScoreCalculator:
    def test_perfect_final_score(
        self, config: ScoringConfig, perfect_indicators: IndicatorsCreate
    ) -> None:
        calc = FinalScoreCalculator(config)
        result = calc.calculate_all(perfect_indicators, total_prs=100)
        assert result.score == 100
        assert result.dimensions.p_time == 100
        assert result.dimensions.p_cost == 100
        assert result.dimensions.p_quality == 100

    def test_no_data_final_score(
        self, config: ScoringConfig, neutral_indicators: IndicatorsCreate
    ) -> None:
        calc = FinalScoreCalculator(config)
        result = calc.calculate_all(neutral_indicators)
        assert result.dimensions.p_time is None
        assert result.dimensions.p_cost is None
        assert result.dimensions.p_quality is None
        assert result.dimensions.p_value is None
        assert result.dimensions.p_satisfaction is None
        assert result.dimensions.p_flow is None
        assert result.dimensions.p_engineering is None
        assert result.dimensions.p_risk is None
        assert result.score == 0  # No data means score is 0

    def test_weights_redistributed_for_available_dimensions(
        self, config: ScoringConfig
    ) -> None:
        calc = FinalScoreCalculator(config)
        indicators = IndicatorsCreate()
        result = calc.calculate_all(indicators)
        total_weight = sum(result.weights_applied.values())
        assert abs(total_weight - 1.0) < 0.001

    def test_partial_data_excludes_missing(self, config: ScoringConfig) -> None:
        calc = FinalScoreCalculator(config)
        indicators = IndicatorsCreate(spi=1.0, on_time_milestones=1.0)
        result = calc.calculate_all(indicators)
        assert result.dimensions.p_time == 100
        assert result.score > 50
