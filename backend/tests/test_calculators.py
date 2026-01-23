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

    def test_neutral_score(
        self, config: ScoringConfig, neutral_indicators: IndicatorsCreate
    ) -> None:
        calc = TimeCalculator(config)
        score = calc.calculate(neutral_indicators)
        assert score == 50


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
        assert score < 100


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


class TestValueCalculator:
    def test_transformational_impact(self, config: ScoringConfig) -> None:
        calc = ValueCalculator(config)
        indicators = IndicatorsCreate(okr_impact=1.0)
        score = calc.calculate(indicators)
        assert score == 100

    def test_low_impact(self, config: ScoringConfig) -> None:
        calc = ValueCalculator(config)
        indicators = IndicatorsCreate(okr_impact=0.25)
        score = calc.calculate(indicators)
        assert score == 25


class TestSatisfactionCalculator:
    def test_with_client_survey(self, config: ScoringConfig) -> None:
        calc = SatisfactionCalculator(config)
        indicators = IndicatorsCreate(client_satisfaction=0.9, pm_satisfaction=0.8)
        score = calc.calculate(indicators)
        assert score == 88

    def test_pm_only(self, config: ScoringConfig) -> None:
        calc = SatisfactionCalculator(config)
        indicators = IndicatorsCreate(pm_satisfaction=0.8)
        score = calc.calculate(indicators)
        assert score == 80


class TestFlowCalculator:
    def test_perfect_flow(
        self, config: ScoringConfig, perfect_indicators: IndicatorsCreate
    ) -> None:
        calc = FlowCalculator(config)
        score = calc.calculate(perfect_indicators)
        assert score == 100


class TestEngineeringCalculator:
    def test_perfect_engineering(
        self, config: ScoringConfig, perfect_indicators: IndicatorsCreate
    ) -> None:
        calc = EngineeringCalculator(config)
        score = calc.calculate(perfect_indicators)
        assert score == 100


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

    def test_neutral_final_score(
        self, config: ScoringConfig, neutral_indicators: IndicatorsCreate
    ) -> None:
        calc = FinalScoreCalculator(config)
        result = calc.calculate_all(neutral_indicators)
        assert result.score == 50

    def test_weights_sum_to_one(self, config: ScoringConfig) -> None:
        calc = FinalScoreCalculator(config)
        indicators = IndicatorsCreate()
        result = calc.calculate_all(indicators)
        total_weight = sum(result.weights_applied.values())
        assert abs(total_weight - 1.0) < 0.001
