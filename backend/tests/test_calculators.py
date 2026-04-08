"""Tests for dimension calculators."""

import pytest

from app.config import ScoringConfig
from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.services.calculators.dimensions import (
    CostCalculator,
    EngineeringCalculator,
    FlowCalculator,
    QualityCalculator,
    RiskCalculator,
    SatisfactionCalculator,
    TimeCalculator,
    ValueCalculator,
)
from app.modules.scorecard.services.calculators.final_score import FinalScoreCalculator


@pytest.fixture
def config(scoring_config: ScoringConfig) -> ScoringConfig:
    """Use the scoring_config fixture from conftest."""
    return scoring_config


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


class TestNormalizeToIdeal:
    """Tests for the _normalize_to_ideal method in BaseCalculator."""

    def test_value_at_ideal_returns_one(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        result = calc._normalize_to_ideal(1.0, 1.0)
        assert result == pytest.approx(1.0)

    def test_value_below_ideal_returns_fraction(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        result = calc._normalize_to_ideal(0.8, 1.0)
        assert result == pytest.approx(0.8)

    def test_value_above_ideal_capped_at_one(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        result = calc._normalize_to_ideal(1.2, 1.0)
        assert result == pytest.approx(1.0)

    def test_none_value_returns_none(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        result = calc._normalize_to_ideal(None, 1.0)
        assert result is None

    def test_zero_ideal_with_positive_value_returns_one(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        result = calc._normalize_to_ideal(0.5, 0.0)
        assert result == pytest.approx(1.0)

    def test_zero_ideal_with_none_value_returns_none(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        result = calc._normalize_to_ideal(None, 0.0)
        assert result is None

    def test_negative_value_floored_at_zero(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        result = calc._normalize_to_ideal(-0.5, 1.0)
        assert result == pytest.approx(0.0)

    def test_negative_ideal_with_positive_value_returns_one(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        result = calc._normalize_to_ideal(0.5, -1.0)
        assert result == pytest.approx(1.0)

    def test_zero_value_with_zero_ideal_returns_none(self, config: ScoringConfig) -> None:
        calc = TimeCalculator(config)
        result = calc._normalize_to_ideal(0.0, 0.0)
        assert result is None


class TestGetIdeal:
    """Tests for the get_ideal method in ScoringConfig."""

    def test_get_ideal_spi(self, config: ScoringConfig) -> None:
        result = config.get_ideal("spi")
        assert result == pytest.approx(1.0)

    def test_get_ideal_cpi(self, config: ScoringConfig) -> None:
        result = config.get_ideal("cpi")
        assert result == pytest.approx(1.0)

    def test_get_ideal_missing_returns_default(self, config: ScoringConfig) -> None:
        result = config.get_ideal("nonexistent")
        assert result == pytest.approx(1.0)


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
        # SPI=0.8 vs ideal=1.0 → normalized=0.8 (reflects actual performance)
        # milestones=1.0 vs target=0.85 → normalized=1.0 (capped)
        # Score = 0.6*0.8 + 0.4*1.0 = 0.88 → 88
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
        # CPI=0.8 vs ideal=1.0 → normalized=0.8 (reflects actual performance)
        # variance=0.0 → normalized=1.0
        # Score = 0.7*0.8 + 0.3*1.0 = 0.86 → 86
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
            defect_density=12.0,  # 2x target (6%) → 0.5
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
        # client=0.9 vs target=0.85 → normalized=1.0 (capped)
        # pm=0.8 vs target=0.85 → normalized=0.941
        # Score = 0.9 * 1.0 + 0.1 * 0.941 = 0.9941 → 99
        indicators = IndicatorsCreate(client_satisfaction=0.9, pm_satisfaction=0.8)
        score = calc.calculate(indicators)
        assert score == 99

    def test_pm_only(self, config: ScoringConfig) -> None:
        calc = SatisfactionCalculator(config)
        # pm=0.8 vs target=0.85 → normalized=0.941
        # 100% weight redistributed to PM → 94
        indicators = IndicatorsCreate(pm_satisfaction=0.8)
        score = calc.calculate(indicators)
        assert score == 94

    def test_client_only(self, config: ScoringConfig) -> None:
        calc = SatisfactionCalculator(config)
        # client=0.9 vs target=0.85 → normalized=1.0 (capped)
        # 100% weight redistributed to client → 100
        indicators = IndicatorsCreate(client_satisfaction=0.9)
        score = calc.calculate(indicators)
        assert score == 100

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
        indicators = IndicatorsCreate(lead_time_days=5.0)  # Target is 10 days
        score = calc.calculate(indicators)
        assert score == 100  # 5 < 10 → fully meets target

    def test_partial_data_redistributes_weights(self, config: ScoringConfig) -> None:
        calc = FlowCalculator(config)
        indicators = IndicatorsCreate(
            lead_time_days=5.0,  # Target 10 days → 1.0 (under target)
            commitment_reliability=1.0,
        )
        score = calc.calculate(indicators)
        assert score == 100

    def test_slow_lead_time_lowers_score(self, config: ScoringConfig) -> None:
        calc = FlowCalculator(config)
        indicators = IndicatorsCreate(
            lead_time_days=20.0,  # 2x target (10 days) → 0.5
            commitment_reliability=1.0,
            pr_size_median=200.0,  # Under target → 1.0
            review_turnaround_hours=12.0,  # Under target → 1.0
            deployment_frequency=1.0,  # Meets target → 1.0
        )
        score = calc.calculate(indicators)
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
        # test_maturity=0.8 vs target=0.6 → normalized=1.0 (capped, exceeds target)
        # 100% weight redistributed to test maturity → 100
        indicators = IndicatorsCreate(test_maturity=0.8)
        score = calc.calculate(indicators)
        assert score == 100

    def test_partial_data_redistributes_weights(self, config: ScoringConfig) -> None:
        calc = EngineeringCalculator(config)
        indicators = IndicatorsCreate(
            test_maturity=1.0,  # weight 0.5, vs target=0.6 → 1.0
            arch_checklist=1.0,  # weight 0.3, vs target=1.0 → 1.0
        )
        score = calc.calculate(indicators)
        assert score == 100  # Both components at 100%

    def test_low_test_maturity_lowers_score(self, config: ScoringConfig) -> None:
        calc = EngineeringCalculator(config)
        # test_maturity=0.3 vs target=0.6 → normalized=0.5
        # pr_review=1.0 → 1.0
        # arch_checklist=1.0 vs target=1.0 → 1.0
        # Score = 0.5 * 0.5 + 0.2 * 1.0 + 0.3 * 1.0 = 0.25 + 0.2 + 0.3 = 0.75 → 75
        indicators = IndicatorsCreate(
            test_maturity=0.3,  # weight 0.5, half of target
            pr_review_ratio=1.0,  # weight 0.2
            arch_checklist=1.0,  # weight 0.3
        )
        score = calc.calculate(indicators)
        assert score == 75


class TestRiskCalculator:
    def test_no_risk(
        self, config: ScoringConfig, perfect_indicators: IndicatorsCreate
    ) -> None:
        calc = RiskCalculator(config)
        score = calc.calculate(perfect_indicators, total_prs=100)
        assert score == 100

    def test_high_vuln_gradual_penalty(self, config: ScoringConfig) -> None:
        calc = RiskCalculator(config)
        indicators = IndicatorsCreate(prs_without_review=0, high_vulns=1)
        score = calc.calculate(indicators, total_prs=100)
        # target=5: vuln_score = max(0, 1 - 1/5) = 0.8
        # 0.5 * 1.0 (perfect PR review) + 0.5 * 0.8 = 90
        assert score == 90

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

    def test_zero_total_prs_returns_none_for_pr_component(
        self, config: ScoringConfig
    ) -> None:
        """When total_prs=0, PR review component is None (no data, not perfect)."""
        calc = RiskCalculator(config)
        indicators = IndicatorsCreate(prs_without_review=0, high_vulns=0)
        # With total_prs=0, PR review component = None, only vulns available
        score = calc.calculate(indicators, total_prs=0)
        assert score == 100  # Weight redistributed to vulns only (which is 0 = perfect)

    def test_zero_total_prs_no_vulns_data_returns_none(
        self, config: ScoringConfig
    ) -> None:
        """When total_prs=0 and no vuln data, score is None (muted in UI)."""
        calc = RiskCalculator(config)
        indicators = IndicatorsCreate(prs_without_review=0)  # No high_vulns
        score = calc.calculate(indicators, total_prs=0)
        assert score is None  # Both components are None

    def test_some_prs_without_review(self, config: ScoringConfig) -> None:
        calc = RiskCalculator(config)
        # Target is 10% of total PRs, with 100 PRs that's 10 PRs allowed
        indicators = IndicatorsCreate(prs_without_review=10, high_vulns=0)
        score = calc.calculate(indicators, total_prs=100)
        # 0.5 * 0.0 (10/10 = at target = 0) + 0.5 * 1.0 (no vulns) = 0.5
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
