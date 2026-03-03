"""Tests for DORA Score Calculator using official DORA thresholds."""

import pytest

from app.config import ScoringConfig
from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.services.calculators.dora import DoraScoreCalculator


@pytest.fixture
def config(scoring_config: ScoringConfig) -> ScoringConfig:
    """Use the scoring_config fixture from conftest."""
    return scoring_config


@pytest.fixture
def elite_indicators() -> IndicatorsCreate:
    """Indicators that should yield Elite DORA classification."""
    return IndicatorsCreate(
        deployment_frequency=2.0,  # >1/day = Elite
        lead_time_days=0.03,  # <1 hour = Elite
        change_failure_rate=0.0,  # 0% = Elite
        mttr_hours=0.5,  # <1h = Elite
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
        assert all(m["level"] == "Elite" for m in result["metrics"].values())

    def test_missing_all_metrics_returns_none(self, config: ScoringConfig) -> None:
        """Missing all DORA metrics should return None score."""
        indicators = IndicatorsCreate()
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["score"] is None
        assert result["classification"] is None
        assert result["available_metrics"] == 0
        assert result["metrics"] == {}

    def test_partial_metrics_calculates_average(self, config: ScoringConfig) -> None:
        """Should average available metrics when some are missing."""
        indicators = IndicatorsCreate(
            deployment_frequency=2.0,  # Elite (100)
            lead_time_days=0.03,  # Elite (100)
            change_failure_rate=None,
            mttr_hours=None,
        )
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["score"] == 100
        assert result["available_metrics"] == 2
        assert result["metrics"]["deployment_frequency"]["level"] == "Elite"
        assert result["metrics"]["lead_time"]["level"] == "Elite"
        assert "change_failure_rate" not in result["metrics"]
        assert "mttr" not in result["metrics"]

    def test_zero_change_failure_rate_returns_elite(
        self, config: ScoringConfig
    ) -> None:
        """Zero CFR should return Elite classification (0-5%)."""
        indicators = IndicatorsCreate(change_failure_rate=0.0)
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["metrics"]["change_failure_rate"]["level"] == "Elite"
        assert result["metrics"]["change_failure_rate"]["score"] == 100

    def test_zero_mttr_returns_elite_no_incidents(self, config: ScoringConfig) -> None:
        """Zero MTTR should return Elite with no_incidents flag."""
        indicators = IndicatorsCreate(mttr_hours=0.0)
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["metrics"]["mttr"]["level"] == "Elite"
        assert result["metrics"]["mttr"]["score"] == 100
        assert result["metrics"]["mttr"]["no_incidents"] is True

    def test_high_cfr_returns_low(self, config: ScoringConfig) -> None:
        """High change failure rate (>15%) should return Low classification."""
        indicators = IndicatorsCreate(change_failure_rate=30.0)  # 30%
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["metrics"]["change_failure_rate"]["level"] == "Low"
        assert result["metrics"]["change_failure_rate"]["score"] == 25

    def test_slow_lead_time_returns_low(self, config: ScoringConfig) -> None:
        """Slow lead time (>1 week) should return Low classification."""
        indicators = IndicatorsCreate(lead_time_days=30.0)  # 30 days
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["metrics"]["lead_time"]["level"] == "Low"
        assert result["metrics"]["lead_time"]["score"] == 25


class TestDoraClassificationThresholds:
    """Test that each metric classifies correctly at threshold boundaries."""

    def test_deployment_frequency_thresholds(self, config: ScoringConfig) -> None:
        """Test deployment frequency classification thresholds."""
        calc = DoraScoreCalculator(config)

        # Elite: >= 1/day
        result = calc.calculate(IndicatorsCreate(deployment_frequency=1.0))
        assert result["metrics"]["deployment_frequency"]["level"] == "Elite"

        # High: >= 1/week (1/7 = 0.143)
        result = calc.calculate(IndicatorsCreate(deployment_frequency=0.143))
        assert result["metrics"]["deployment_frequency"]["level"] == "High"

        # Medium: >= 1/month (1/30 = 0.033)
        result = calc.calculate(IndicatorsCreate(deployment_frequency=0.034))
        assert result["metrics"]["deployment_frequency"]["level"] == "Medium"

        # Low: < 1/month
        result = calc.calculate(IndicatorsCreate(deployment_frequency=0.01))
        assert result["metrics"]["deployment_frequency"]["level"] == "Low"

    def test_lead_time_thresholds(self, config: ScoringConfig) -> None:
        """Test lead time classification thresholds."""
        calc = DoraScoreCalculator(config)

        # Elite: < 1 hour (< 1/24 day)
        result = calc.calculate(IndicatorsCreate(lead_time_days=0.03))
        assert result["metrics"]["lead_time"]["level"] == "Elite"

        # High: < 1 day
        result = calc.calculate(IndicatorsCreate(lead_time_days=0.5))
        assert result["metrics"]["lead_time"]["level"] == "High"

        # Medium: < 1 week
        result = calc.calculate(IndicatorsCreate(lead_time_days=3.0))
        assert result["metrics"]["lead_time"]["level"] == "Medium"

        # Low: >= 1 week
        result = calc.calculate(IndicatorsCreate(lead_time_days=10.0))
        assert result["metrics"]["lead_time"]["level"] == "Low"

    def test_change_failure_rate_thresholds(self, config: ScoringConfig) -> None:
        """Test change failure rate classification thresholds."""
        calc = DoraScoreCalculator(config)

        # Elite: 0-5%
        result = calc.calculate(IndicatorsCreate(change_failure_rate=5.0))
        assert result["metrics"]["change_failure_rate"]["level"] == "Elite"

        # High: 5-10%
        result = calc.calculate(IndicatorsCreate(change_failure_rate=10.0))
        assert result["metrics"]["change_failure_rate"]["level"] == "High"

        # Medium: 10-15%
        result = calc.calculate(IndicatorsCreate(change_failure_rate=15.0))
        assert result["metrics"]["change_failure_rate"]["level"] == "Medium"

        # Low: > 15%
        result = calc.calculate(IndicatorsCreate(change_failure_rate=16.0))
        assert result["metrics"]["change_failure_rate"]["level"] == "Low"

    def test_mttr_thresholds(self, config: ScoringConfig) -> None:
        """Test MTTR classification thresholds."""
        calc = DoraScoreCalculator(config)

        # Elite: < 1 hour (or 0 = no incidents)
        result = calc.calculate(IndicatorsCreate(mttr_hours=0.5))
        assert result["metrics"]["mttr"]["level"] == "Elite"

        # High: < 1 day (24 hours)
        result = calc.calculate(IndicatorsCreate(mttr_hours=12.0))
        assert result["metrics"]["mttr"]["level"] == "High"

        # Medium: < 1 week (168 hours)
        result = calc.calculate(IndicatorsCreate(mttr_hours=100.0))
        assert result["metrics"]["mttr"]["level"] == "Medium"

        # Low: >= 1 week
        result = calc.calculate(IndicatorsCreate(mttr_hours=200.0))
        assert result["metrics"]["mttr"]["level"] == "Low"


class TestDoraOverallClassification:
    """Test overall classification is determined by weakest link."""

    def test_weakest_link_determines_classification(
        self, config: ScoringConfig
    ) -> None:
        """Overall classification should be the weakest metric."""
        indicators = IndicatorsCreate(
            deployment_frequency=2.0,  # Elite
            lead_time_days=0.03,  # Elite
            change_failure_rate=0.0,  # Elite
            mttr_hours=200.0,  # Low (>1 week)
        )
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        # Even with 3 Elite metrics, one Low makes overall Low
        assert result["classification"] == "Low"
        # Score is average: (100 + 100 + 100 + 25) / 4 = 81.25 ≈ 81
        assert result["score"] == 81

    def test_all_high_gives_high_classification(self, config: ScoringConfig) -> None:
        """All High metrics should give High classification."""
        indicators = IndicatorsCreate(
            deployment_frequency=0.2,  # High (between 1/week and 1/day)
            lead_time_days=0.5,  # High (< 1 day)
            change_failure_rate=8.0,  # High (5-10%)
            mttr_hours=12.0,  # High (< 24h)
        )
        calc = DoraScoreCalculator(config)
        result = calc.calculate(indicators)

        assert result["classification"] == "High"
        assert result["score"] == 75  # All High = 75 each
