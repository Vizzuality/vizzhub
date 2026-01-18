"""Tests for normalization functions."""

import pytest

from app.services.normalizers.base import (
    NEUTRAL_VALUE,
    normalize_budget_variance,
    normalize_count_to_ratio,
    normalize_governance_compliance,
    normalize_higher_is_better,
    normalize_lower_is_better,
    normalize_ratio_to_target,
    normalize_strict_zero_target,
)


class TestHigherIsBetter:
    def test_normal_value(self) -> None:
        assert normalize_higher_is_better(0.8) == 0.8

    def test_exceeds_cap(self) -> None:
        assert normalize_higher_is_better(1.5) == 1.0

    def test_none_returns_neutral(self) -> None:
        assert normalize_higher_is_better(None) == NEUTRAL_VALUE

    def test_none_returns_zero_when_no_neutral(self) -> None:
        assert normalize_higher_is_better(None, neutral_on_missing=False) == 0.0

    def test_negative_returns_zero(self) -> None:
        assert normalize_higher_is_better(-0.5) == 0.0


class TestLowerIsBetter:
    def test_at_target(self) -> None:
        assert normalize_lower_is_better(3.0, 3.0) == 1.0

    def test_below_target(self) -> None:
        assert normalize_lower_is_better(1.5, 3.0) == 1.0

    def test_above_target(self) -> None:
        assert normalize_lower_is_better(6.0, 3.0) == 0.5

    def test_zero_value(self) -> None:
        assert normalize_lower_is_better(0.0, 3.0) == 1.0

    def test_none_returns_neutral(self) -> None:
        assert normalize_lower_is_better(None, 3.0) == NEUTRAL_VALUE


class TestRatioToTarget:
    def test_at_target(self) -> None:
        assert normalize_ratio_to_target(1.0, 1.0) == 1.0

    def test_below_target(self) -> None:
        assert normalize_ratio_to_target(0.8, 1.0) == 0.8

    def test_above_target_capped(self) -> None:
        assert normalize_ratio_to_target(1.2, 1.0) == 1.0

    def test_none_returns_neutral(self) -> None:
        assert normalize_ratio_to_target(None, 1.0) == NEUTRAL_VALUE


class TestStrictZeroTarget:
    def test_zero_value_returns_one(self) -> None:
        assert normalize_strict_zero_target(0) == 1.0

    def test_positive_value_returns_zero(self) -> None:
        assert normalize_strict_zero_target(1) == 0.0

    def test_none_returns_neutral(self) -> None:
        assert normalize_strict_zero_target(None) == NEUTRAL_VALUE


class TestBudgetVariance:
    def test_on_budget(self) -> None:
        assert normalize_budget_variance(100, 100) == 0.0

    def test_under_budget(self) -> None:
        assert normalize_budget_variance(80, 100) == 0.0

    def test_over_budget(self) -> None:
        assert normalize_budget_variance(120, 100) == pytest.approx(0.2)

    def test_zero_budget(self) -> None:
        assert normalize_budget_variance(100, 0) == 0.0

    def test_none_returns_neutral(self) -> None:
        assert normalize_budget_variance(None, 100) == NEUTRAL_VALUE


class TestGovernanceCompliance:
    def test_no_exceptions(self) -> None:
        assert normalize_governance_compliance(0, 2) == 1.0

    def test_at_limit(self) -> None:
        assert normalize_governance_compliance(2, 2) == 0.0

    def test_half_limit(self) -> None:
        assert normalize_governance_compliance(1, 2) == 0.5

    def test_over_limit(self) -> None:
        assert normalize_governance_compliance(3, 2) == 0.0


class TestCountToRatio:
    def test_no_violations(self) -> None:
        assert normalize_count_to_ratio(0, 0.02, 100) == 1.0

    def test_at_limit(self) -> None:
        assert normalize_count_to_ratio(2, 0.02, 100) == 0.0

    def test_half_limit(self) -> None:
        assert normalize_count_to_ratio(1, 0.02, 100) == 0.5
