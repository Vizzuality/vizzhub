"""Unit tests for ScoringConfig weight-group validation.

Covers the new ``validate_weights_with_totals`` API surface and the
backward-compatible ``validate_weights`` view. Integration coverage of
the DB→warning flow lives in ``integration/test_config_loading.py``."""

from decimal import Decimal

from app.config import ScoringConfig


def _balanced_global_payload() -> dict[str, Decimal]:
    """Build a parameter dict where Global Weights sum to exactly 1.0.

    Only the leaves we exercise need values; everything else falls back
    to 0 and that's fine because the test asserts per-group outcomes,
    not the full config catalog.
    """
    return {
        "weight_global_time": Decimal("0.125"),
        "weight_global_cost": Decimal("0.125"),
        "weight_global_quality": Decimal("0.125"),
        "weight_global_value": Decimal("0.125"),
        "weight_global_satisfaction": Decimal("0.125"),
        "weight_global_flow": Decimal("0.125"),
        "weight_global_engineering": Decimal("0.125"),
        "weight_global_risk": Decimal("0.125"),
    }


def test_validate_weights_with_totals_reports_actual_sum_for_broken_group() -> None:
    payload = _balanced_global_payload()
    # Knock the global sum down to 0.875 so the group fails.
    payload["weight_global_risk"] = Decimal("0.0")
    config = ScoringConfig(payload)

    results = config.validate_weights_with_totals()

    passed, total = results["Global Weights"]
    assert passed is False
    assert total == 0.875


def test_validate_weights_with_totals_passes_when_group_sums_to_one() -> None:
    config = ScoringConfig(_balanced_global_payload())

    passed, total = config.validate_weights_with_totals()["Global Weights"]

    assert passed is True
    assert abs(total - 1.0) < 1e-9


def test_validate_weights_backward_compat_shape() -> None:
    """The legacy bool-only view stays available for the /config endpoint."""
    config = ScoringConfig(_balanced_global_payload())

    legacy = config.validate_weights()

    assert legacy["Global Weights"] is True
    assert isinstance(legacy["Time Weights"], bool)


def test_validate_weights_groups_covered() -> None:
    """All declared groups appear in both views — guards against a future
    edit that forgets to keep the two methods in sync."""
    config = ScoringConfig({})

    legacy_keys = set(config.validate_weights().keys())
    full_keys = set(config.validate_weights_with_totals().keys())

    assert legacy_keys == full_keys
    expected = {
        "Global Weights", "Time Weights", "Cost Weights", "Quality Weights",
        "Value Weights", "Satisfaction Weights", "Client Survey Weights",
        "Flow Weights", "Engineering Weights", "Risk Weights",
        "Test Maturity Weights",
    }
    assert legacy_keys == expected
