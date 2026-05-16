"""Tests for normalization functions."""

import pytest

from app.modules.scorecard.services.normalizers.base import (
    NEUTRAL_VALUE,
    normalize_budget_variance,
    normalize_cost_variance,
    normalize_count_to_ratio,
    normalize_governance_compliance,
    normalize_higher_is_better,
    normalize_lower_is_better,
    normalize_ratio_to_target,
    normalize_strict_zero_target,
)


class TestHigherIsBetter:
    """Tests for normalize_higher_is_better function."""

    def test_normal_value(self) -> None:
        assert normalize_higher_is_better(0.8) == pytest.approx(0.8)

    def test_exceeds_cap(self) -> None:
        assert normalize_higher_is_better(1.5) == pytest.approx(1.0)

    def test_none_returns_neutral(self) -> None:
        assert normalize_higher_is_better(None) == pytest.approx(NEUTRAL_VALUE)

    def test_none_returns_zero_when_no_neutral(self) -> None:
        assert normalize_higher_is_better(None, neutral_on_missing=False) == pytest.approx(0.0)

    def test_negative_returns_zero(self) -> None:
        assert normalize_higher_is_better(-0.5) == pytest.approx(0.0)

    def test_zero_value_returns_zero(self) -> None:
        """Zero is a valid input and should be clamped to 0."""
        assert normalize_higher_is_better(0.0) == pytest.approx(0.0)

    def test_exactly_at_cap(self) -> None:
        """Value exactly at cap should not be capped."""
        assert normalize_higher_is_better(1.0, cap=1.0) == pytest.approx(1.0)

    def test_custom_cap(self) -> None:
        """Custom cap should be respected."""
        assert normalize_higher_is_better(0.6, cap=0.8) == pytest.approx(0.6)
        assert normalize_higher_is_better(1.0, cap=0.8) == pytest.approx(0.8)


class TestLowerIsBetter:
    """Tests for normalize_lower_is_better function."""

    def test_at_target(self) -> None:
        assert normalize_lower_is_better(3.0, 3.0) == pytest.approx(1.0)

    def test_below_target(self) -> None:
        assert normalize_lower_is_better(1.5, 3.0) == pytest.approx(1.0)

    def test_above_target(self) -> None:
        assert normalize_lower_is_better(6.0, 3.0) == pytest.approx(0.5)

    def test_zero_value(self) -> None:
        assert normalize_lower_is_better(0.0, 3.0) == pytest.approx(1.0)

    def test_none_returns_neutral(self) -> None:
        assert normalize_lower_is_better(None, 3.0) == pytest.approx(NEUTRAL_VALUE)

    def test_none_returns_zero_when_no_neutral(self) -> None:
        """When neutral_on_missing=False, None should return 0.0."""
        assert normalize_lower_is_better(None, 3.0, neutral_on_missing=False) == pytest.approx(0.0)

    def test_negative_value_returns_one(self) -> None:
        """Negative values should be treated as perfect score (edge case)."""
        assert normalize_lower_is_better(-1.0, 3.0) == pytest.approx(1.0)

    def test_near_zero_target(self) -> None:
        """Near-zero targets should still work correctly."""
        assert normalize_lower_is_better(0.1, 0.01) == pytest.approx(0.1)

    def test_zero_target(self) -> None:
        """Zero target with non-zero value should return target/value ratio."""
        assert normalize_lower_is_better(5.0, 0.0) == pytest.approx(0.0)


class TestRatioToTarget:
    """Tests for normalize_ratio_to_target function."""

    def test_at_target(self) -> None:
        assert normalize_ratio_to_target(1.0, 1.0) == pytest.approx(1.0)

    def test_below_target(self) -> None:
        assert normalize_ratio_to_target(0.8, 1.0) == pytest.approx(0.8)

    def test_above_target_capped(self) -> None:
        assert normalize_ratio_to_target(1.2, 1.0) == pytest.approx(1.0)

    def test_none_returns_neutral(self) -> None:
        assert normalize_ratio_to_target(None, 1.0) == pytest.approx(NEUTRAL_VALUE)

    def test_none_returns_zero_when_no_neutral(self) -> None:
        """When neutral_on_missing=False, None should return 0.0."""
        assert normalize_ratio_to_target(None, 1.0, neutral_on_missing=False) == pytest.approx(0.0)

    def test_zero_target_with_positive_value(self) -> None:
        """Zero target with positive value should return 1.0 (line 95)."""
        assert normalize_ratio_to_target(0.5, 0.0) == pytest.approx(1.0)

    def test_zero_target_with_zero_value(self) -> None:
        """Zero target with zero value should return NEUTRAL_VALUE (line 95)."""
        assert normalize_ratio_to_target(0.0, 0.0) == pytest.approx(NEUTRAL_VALUE)

    def test_negative_value_clamped_to_zero(self) -> None:
        """Negative values should be clamped to 0.0."""
        assert normalize_ratio_to_target(-0.5, 1.0) == pytest.approx(0.0)

    def test_exactly_zero_value(self) -> None:
        """Zero value with positive target should return 0.0."""
        assert normalize_ratio_to_target(0.0, 1.0) == pytest.approx(0.0)


class TestStrictZeroTarget:
    """Tests for normalize_strict_zero_target function."""

    def test_zero_value_returns_one(self) -> None:
        assert normalize_strict_zero_target(0) == pytest.approx(1.0)

    def test_positive_value_returns_zero(self) -> None:
        assert normalize_strict_zero_target(1) == pytest.approx(0.0)

    def test_none_returns_neutral(self) -> None:
        assert normalize_strict_zero_target(None) == pytest.approx(NEUTRAL_VALUE)

    def test_none_returns_zero_when_no_neutral(self) -> None:
        """When neutral_on_missing=False, None should return 0.0."""
        assert normalize_strict_zero_target(None, neutral_on_missing=False) == pytest.approx(0.0)

    def test_float_zero_returns_one(self) -> None:
        """Float zero should be treated same as int zero."""
        assert normalize_strict_zero_target(0.0) == pytest.approx(1.0)

    def test_very_small_positive_float_returns_zero(self) -> None:
        """Even very small non-zero values fail strict zero check."""
        assert normalize_strict_zero_target(0.0001) == pytest.approx(0.0)

    def test_negative_value_returns_zero(self) -> None:
        """Negative values violate strict zero target."""
        assert normalize_strict_zero_target(-1) == pytest.approx(0.0)

    def test_large_value_returns_zero(self) -> None:
        """Any non-zero value fails strict zero target."""
        assert normalize_strict_zero_target(1000) == pytest.approx(0.0)


class TestBudgetVariance:
    """Tests for normalize_budget_variance function."""

    def test_on_budget(self) -> None:
        assert normalize_budget_variance(100, 100) == pytest.approx(0.0)

    def test_under_budget(self) -> None:
        assert normalize_budget_variance(80, 100) == pytest.approx(0.0)

    def test_over_budget(self) -> None:
        assert normalize_budget_variance(120, 100) == pytest.approx(0.2)

    def test_zero_budget(self) -> None:
        assert normalize_budget_variance(100, 0) == pytest.approx(0.0)

    def test_none_returns_neutral(self) -> None:
        assert normalize_budget_variance(None, 100) == pytest.approx(NEUTRAL_VALUE)

    def test_none_actual_cost_returns_neutral(self) -> None:
        """None actual cost should return neutral."""
        assert normalize_budget_variance(None, 100) == pytest.approx(NEUTRAL_VALUE)

    def test_none_budget_returns_neutral(self) -> None:
        """None budget should return neutral."""
        assert normalize_budget_variance(100, None) == pytest.approx(NEUTRAL_VALUE)

    def test_both_none_returns_neutral(self) -> None:
        """Both None should return neutral."""
        assert normalize_budget_variance(None, None) == pytest.approx(NEUTRAL_VALUE)

    def test_none_returns_zero_when_no_neutral(self) -> None:
        """When neutral_on_missing=False, None should return 0.0."""
        assert normalize_budget_variance(None, 100, neutral_on_missing=False) == pytest.approx(0.0)
        assert normalize_budget_variance(100, None, neutral_on_missing=False) == pytest.approx(0.0)

    def test_zero_actual_cost(self) -> None:
        """Zero actual cost should return 0 variance (under budget)."""
        assert normalize_budget_variance(0, 100) == pytest.approx(0.0)


class TestCostVariance:
    """Tests for normalize_cost_variance — signed EVM CV / BAC normalizer."""

    def test_positive_returns_one(self) -> None:
        """Ahead of plan (CV% > 0) → perfect score."""
        assert normalize_cost_variance(0.10, 0.10) == pytest.approx(1.0)

    def test_zero_returns_one(self) -> None:
        """On plan (CV% == 0) → perfect score."""
        assert normalize_cost_variance(0.0, 0.10) == pytest.approx(1.0)

    def test_at_negative_target_returns_zero(self) -> None:
        """Exactly at the overrun tolerance → 0."""
        assert normalize_cost_variance(-0.10, 0.10) == pytest.approx(0.0)

    def test_beyond_negative_target_returns_zero(self) -> None:
        """Worse than tolerance still floors at 0."""
        assert normalize_cost_variance(-0.50, 0.10) == pytest.approx(0.0)

    def test_linear_in_between(self) -> None:
        """Halfway to the overrun tolerance → 0.5."""
        assert normalize_cost_variance(-0.05, 0.10) == pytest.approx(0.5)

    def test_handles_negative_target(self) -> None:
        """Target magnitude is taken absolute — negative target works too."""
        assert normalize_cost_variance(-0.05, -0.10) == pytest.approx(0.5)

    def test_zero_target_clamps_negative_to_zero(self) -> None:
        """Zero tolerance: any overrun scores 0."""
        assert normalize_cost_variance(-0.01, 0.0) == pytest.approx(0.0)

    def test_none_returns_none_by_default(self) -> None:
        """Missing input excludes the indicator (per CLAUDE.md rule)."""
        assert normalize_cost_variance(None, 0.10) is None

    def test_none_neutral_opt_in(self) -> None:
        """Legacy callers can opt into neutral fallback."""
        assert normalize_cost_variance(None, 0.10, neutral_on_missing=True) == pytest.approx(
            NEUTRAL_VALUE
        )


class TestGovernanceCompliance:
    """Tests for normalize_governance_compliance function."""

    def test_no_exceptions(self) -> None:
        assert normalize_governance_compliance(0, 2) == pytest.approx(1.0)

    def test_at_limit(self) -> None:
        assert normalize_governance_compliance(2, 2) == pytest.approx(0.0)

    def test_half_limit(self) -> None:
        assert normalize_governance_compliance(1, 2) == pytest.approx(0.5)

    def test_over_limit(self) -> None:
        assert normalize_governance_compliance(3, 2) == pytest.approx(0.0)

    def test_none_returns_neutral(self) -> None:
        """None exceptions should return neutral (line 168)."""
        assert normalize_governance_compliance(None, 2) == pytest.approx(NEUTRAL_VALUE)

    def test_none_returns_zero_when_no_neutral(self) -> None:
        """When neutral_on_missing=False, None should return 0.0 (line 168)."""
        assert normalize_governance_compliance(None, 2, neutral_on_missing=False) == pytest.approx(0.0)

    def test_zero_target_with_no_exceptions(self) -> None:
        """Zero target with zero exceptions should return 1.0 (line 170)."""
        assert normalize_governance_compliance(0, 0) == pytest.approx(1.0)

    def test_zero_target_with_exceptions(self) -> None:
        """Zero target with any exceptions should return 0.0 (line 170)."""
        assert normalize_governance_compliance(1, 0) == pytest.approx(0.0)


class TestCountToRatio:
    """Tests for normalize_count_to_ratio function.

    Note: target is now in percentage format (e.g., 2 means 2%).
    Formula: max_allowed = total * target / 100
    """

    def test_no_violations(self) -> None:
        # 2% of 100 = 2 allowed, 0 violations = perfect score
        assert normalize_count_to_ratio(0, 2, 100) == pytest.approx(1.0)

    def test_at_limit(self) -> None:
        # 2% of 100 = 2 allowed, 2 violations = 0 score
        assert normalize_count_to_ratio(2, 2, 100) == pytest.approx(0.0)

    def test_half_limit(self) -> None:
        # 2% of 100 = 2 allowed, 1 violation = 0.5 score
        assert normalize_count_to_ratio(1, 2, 100) == pytest.approx(0.5)

    def test_none_value_returns_neutral(self) -> None:
        """None value should return neutral (line 197)."""
        assert normalize_count_to_ratio(None, 2, 100) == pytest.approx(NEUTRAL_VALUE)

    def test_none_value_returns_zero_when_no_neutral(self) -> None:
        """When neutral_on_missing=False, None should return 0.0 (line 197)."""
        assert normalize_count_to_ratio(None, 2, 100, neutral_on_missing=False) == pytest.approx(0.0)

    def test_none_total_with_zero_value(self) -> None:
        """None total with zero value should return 1.0 (line 199)."""
        assert normalize_count_to_ratio(0, 2, None) == pytest.approx(1.0)

    def test_none_total_with_positive_value(self) -> None:
        """None total with positive value should return NEUTRAL_VALUE (line 199)."""
        assert normalize_count_to_ratio(5, 2, None) == pytest.approx(NEUTRAL_VALUE)

    def test_zero_total_with_zero_value(self) -> None:
        """Zero total with zero value should return 1.0 (line 199)."""
        assert normalize_count_to_ratio(0, 2, 0) == pytest.approx(1.0)

    def test_zero_total_with_positive_value(self) -> None:
        """Zero total with positive value should return NEUTRAL_VALUE (line 199)."""
        assert normalize_count_to_ratio(5, 2, 0) == pytest.approx(NEUTRAL_VALUE)

    def test_zero_target_with_zero_value(self) -> None:
        """Zero target with zero value should return 1.0 (line 202)."""
        assert normalize_count_to_ratio(0, 0.0, 100) == pytest.approx(1.0)

    def test_zero_target_with_positive_value(self) -> None:
        """Zero target with positive value should return 0.0 (line 202)."""
        assert normalize_count_to_ratio(5, 0.0, 100) == pytest.approx(0.0)

    def test_over_limit(self) -> None:
        """Values over limit should be clamped to 0.0."""
        # 2% of 100 = 2 allowed, 10 violations = 0 score
        assert normalize_count_to_ratio(10, 2, 100) == pytest.approx(0.0)

    def test_fractional_calculations(self) -> None:
        """Fractional compliance should be calculated correctly."""
        # 10% of 100 = 10 allowed, 1 violation = 1 - 1/10 = 0.9
        result = normalize_count_to_ratio(1, 10, 100)
        expected = max(0.0, 1.0 - 1 / 10)
        assert result == pytest.approx(expected)
