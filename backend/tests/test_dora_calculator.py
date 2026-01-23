"""Tests for DORA Score Calculator."""

import pytest

from app.config import ScoringConfig
from app.models.indicators import IndicatorsCreate
from app.services.calculators.dora import DoraScoreCalculator


@pytest.fixture
def config() -> ScoringConfig:
    return ScoringConfig()


@pytest.fixture
def elite_indicators() -> IndicatorsCreate:
    """Indicators that should yield Elite DORA classification."""
    return IndicatorsCreate(
        deployment_frequency=2.0,  # >1/day = Elite
        lead_time_days=1.0,  # <3 days = Elite
        change_failure_rate=0.0,  # 0% = Elite
        mttr_hours=1.0,  # <24h = Elite
    )


class TestDoraScoreCalculator:
    def test_all_elite_metrics_returns_100(
        self, config: ScoringConfig, elite_indicators: IndicatorsCreate
    ) -> None:
        """All elite DORA metrics should yield score 100 and Elite classification."""
        calc = DoraScoreCalculator(config)
        result = calc.calculate(elite_indicators)

        assert result["score"] == 100
        assert result["classification"] == "Elite"
        assert result["available_metrics"] == 4

    def test_missing_all_metrics_returns_none(self, config: ScoringConfig) -> None:
        """Missing all DORA metrics should return None score."""
        indicators = IndicatorsCreate()
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["score"] is None
        assert result["classification"] is None
        assert result["available_metrics"] == 0

    def test_partial_metrics_calculates_average(self, config: ScoringConfig) -> None:
        """Should average available metrics when some are missing."""
        indicators = IndicatorsCreate(
            deployment_frequency=2.0,  # Elite (100%)
            lead_time_days=1.0,  # Elite (100%)
            change_failure_rate=None,
            mttr_hours=None,
        )
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["score"] == 100
        assert result["available_metrics"] == 2
        assert result["metrics"]["deployment_frequency"] == 1.0
        assert result["metrics"]["lead_time"] == 1.0
        assert result["metrics"]["change_failure_rate"] is None
        assert result["metrics"]["mttr"] is None

    def test_zero_change_failure_rate_returns_perfect(
        self, config: ScoringConfig
    ) -> None:
        """Zero CFR should return perfect score (1.0)."""
        indicators = IndicatorsCreate(change_failure_rate=0.0)
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["metrics"]["change_failure_rate"] == 1.0

    def test_zero_mttr_returns_perfect(self, config: ScoringConfig) -> None:
        """Zero MTTR should return perfect score (1.0)."""
        indicators = IndicatorsCreate(mttr_hours=0.0)
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["metrics"]["mttr"] == 1.0

    def test_high_cfr_returns_low_score(self, config: ScoringConfig) -> None:
        """High change failure rate should return low score."""
        indicators = IndicatorsCreate(change_failure_rate=30.0)  # 30% vs 15% target
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["metrics"]["change_failure_rate"] == 0.5  # 15/30

    def test_slow_lead_time_returns_low_score(self, config: ScoringConfig) -> None:
        """Slow lead time should return low score."""
        indicators = IndicatorsCreate(lead_time_days=9.0)  # 9 days vs 3 day target
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["metrics"]["lead_time"] == pytest.approx(0.333, rel=0.01)


class TestDoraClassification:
    def test_elite_threshold(self, config: ScoringConfig) -> None:
        """Score 85-100 should be Elite."""
        calc = DoraScoreCalculator(config)
        assert calc._get_classification(100) == "Elite"
        assert calc._get_classification(85) == "Elite"

    def test_high_threshold(self, config: ScoringConfig) -> None:
        """Score 70-84 should be High."""
        calc = DoraScoreCalculator(config)
        assert calc._get_classification(84) == "High"
        assert calc._get_classification(70) == "High"

    def test_medium_threshold(self, config: ScoringConfig) -> None:
        """Score 50-69 should be Medium."""
        calc = DoraScoreCalculator(config)
        assert calc._get_classification(69) == "Medium"
        assert calc._get_classification(50) == "Medium"

    def test_low_threshold(self, config: ScoringConfig) -> None:
        """Score 0-49 should be Low."""
        calc = DoraScoreCalculator(config)
        assert calc._get_classification(49) == "Low"
        assert calc._get_classification(0) == "Low"
