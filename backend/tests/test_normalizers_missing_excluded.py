"""Regression tests for the "missing indicators are excluded, not neutralized" rule.

CLAUDE.md states: when an indicator's input data is absent, the normalizer
MUST return None so the weighted average drops it and redistributes the
weight, rather than substituting a NEUTRAL_VALUE (0.5/0.75) or zero
("perfect score"). Reference implementation: `_normalize_client_survey`.

These tests pin the rule for the six normalizers flagged by the
2026-05-15 calculations audit (#14).
"""

from typing import cast

import pytest

from app.modules.scorecard.models.metrics import (
    ComplaintStatus,
    JiraDefectMetrics,
    PMSatisfaction,
    StrategicImpact,
)
from app.modules.scorecard.models.metrics import TestMaturity as TestMaturityModel
from app.modules.scorecard.services.normalizers.indicators import IndicatorNormalizer


@pytest.fixture
def normalizer(scoring_config) -> IndicatorNormalizer:
    # Pass config explicitly so xdist workers don't depend on the global
    # singleton (other tests can mutate set_scoring_config out from under us).
    return IndicatorNormalizer(config=scoring_config)


class TestDefectDensityNone:
    def test_tasks_completed_zero_returns_none(
        self, normalizer: IndicatorNormalizer
    ) -> None:
        jira = JiraDefectMetrics(
            bugs_total=3, tasks_completed=0, escaped_defects=0,
            mttr_hours=None, incidents_count=0,
        )
        assert normalizer._calculate_defect_density(jira) is None

    def test_real_data_returns_value(self, normalizer: IndicatorNormalizer) -> None:
        jira = JiraDefectMetrics(
            bugs_total=3, tasks_completed=300, escaped_defects=0,
            mttr_hours=None, incidents_count=0,
        )
        assert normalizer._calculate_defect_density(jira) == pytest.approx(1.0)


class TestEscapedRateNone:
    def test_tasks_completed_zero_returns_none(
        self, normalizer: IndicatorNormalizer
    ) -> None:
        jira = JiraDefectMetrics(
            bugs_total=0, tasks_completed=0, escaped_defects=2,
            mttr_hours=None, incidents_count=0,
        )
        assert normalizer._calculate_escaped_rate(jira) is None

    def test_real_data_returns_rate(self, normalizer: IndicatorNormalizer) -> None:
        jira = JiraDefectMetrics(
            bugs_total=0, tasks_completed=200, escaped_defects=4,
            mttr_hours=None, incidents_count=0,
        )
        assert normalizer._calculate_escaped_rate(jira) == pytest.approx(2.0)


class TestMttrNone:
    def test_zero_incidents_returns_none(
        self, normalizer: IndicatorNormalizer
    ) -> None:
        jira = JiraDefectMetrics(
            bugs_total=0, tasks_completed=10, escaped_defects=0,
            mttr_hours=None, incidents_count=0,
        )
        assert normalizer._get_mttr(jira) is None


class TestTestMaturityWeightRedistribution:
    def test_all_none_returns_none(self, normalizer: IndicatorNormalizer) -> None:
        test = TestMaturityModel()
        result = normalizer._normalize_test_maturity(test)
        assert result is None

    def test_partial_data_redistributes_weights(
        self, normalizer: IndicatorNormalizer
    ) -> None:
        """If only e2e is rated at 5/5, the indicator should be 1.0,
        not whatever weight e2e carries (which would imply the missing
        fields scored 0). With NEUTRAL_VALUE substitution the old impl
        returned ~0.55."""
        test = TestMaturityModel(e2e=5, unit=None, accessibility=None,
                            security=None, frontend=None)
        result = normalizer._normalize_test_maturity(test)
        assert result == pytest.approx(1.0)

    def test_full_data_keeps_total(self, normalizer: IndicatorNormalizer) -> None:
        test = TestMaturityModel(e2e=5, unit=5, accessibility=5, security=5, frontend=5)
        result = normalizer._normalize_test_maturity(test)
        assert result == pytest.approx(1.0)

    def test_all_zeros_yields_zero(
        self, normalizer: IndicatorNormalizer
    ) -> None:
        """All five fields rated 0/5 → 0.0 (weights still sum to 1.0,
        so no redistribution path)."""
        test = TestMaturityModel(e2e=0, unit=0, accessibility=0, security=0, frontend=0)
        result = normalizer._normalize_test_maturity(test)
        assert result == pytest.approx(0.0)


class TestPmSatisfactionWeightRedistribution:
    def test_all_na_returns_none(self, normalizer: IndicatorNormalizer) -> None:
        pm = PMSatisfaction(
            delivery_complaints=ComplaintStatus.NA,
            design_complaints=ComplaintStatus.NA,
            overall_estimation=None,
        )
        assert normalizer._normalize_pm_satisfaction(pm) is None

    def test_only_overall_rated(self, normalizer: IndicatorNormalizer) -> None:
        """overall=5/5 alone should yield 1.0 (weight redistributed),
        not 0.4*0.75 + 0.3*0.75 + 0.4 = 0.85 from the old NEUTRAL impl."""
        pm = PMSatisfaction(
            delivery_complaints=ComplaintStatus.NA,
            design_complaints=ComplaintStatus.NA,
            overall_estimation=5,
        )
        result = normalizer._normalize_pm_satisfaction(pm)
        assert result == pytest.approx(1.0)

    def test_only_delivery_rated_no_complaints(
        self, normalizer: IndicatorNormalizer
    ) -> None:
        pm = PMSatisfaction(
            delivery_complaints=ComplaintStatus.NO,
            design_complaints=ComplaintStatus.NA,
            overall_estimation=None,
        )
        result = normalizer._normalize_pm_satisfaction(pm)
        assert result == pytest.approx(1.0)

    def test_full_data_keeps_total(self, normalizer: IndicatorNormalizer) -> None:
        pm = PMSatisfaction(
            delivery_complaints=ComplaintStatus.NO,
            design_complaints=ComplaintStatus.NO,
            overall_estimation=5,
        )
        result = normalizer._normalize_pm_satisfaction(pm)
        assert result == pytest.approx(1.0)


class TestOkrImpactNone:
    def test_known_value(self, normalizer: IndicatorNormalizer) -> None:
        assert normalizer._normalize_okr_impact(
            StrategicImpact.HIGH
        ) == pytest.approx(0.80)

    def test_none_input_returns_none(
        self, normalizer: IndicatorNormalizer
    ) -> None:
        assert normalizer._normalize_okr_impact(None) is None

    def test_unknown_enum_value_returns_none(
        self, normalizer: IndicatorNormalizer
    ) -> None:
        """Defensive: if a stray non-mapped value ever reaches the
        normalizer, it should be excluded, not neutralized to 0.5."""
        bogus = cast(StrategicImpact, "not-in-enum")
        assert normalizer._normalize_okr_impact(bogus) is None
