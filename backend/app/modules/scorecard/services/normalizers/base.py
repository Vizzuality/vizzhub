"""
Normalization patterns for Project Scorecard.

Design Principles:
1. All ratios normalized to 0-1 before weighting
2. "Lower is better" metrics use inverted normalization
3. Missing indicators are excluded by the calculator layer
   (`BaseCalculator._weighted_average` drops `None` values and
   redistributes weights). Disabled tools, missing collectors,
   absent data sources all flow through as `None` and are excluded —
   never zeroed (no penalty) and never neutralized at 0.5.

Normalization Patterns:
- "Higher is better" (direct): normalized = min(1, value)
- "Lower is better" (inverted): normalized = min(1, target / max(value, 0.001))
- Missing data: return None so the calculator can exclude it
- Strict zero target: if target=0 and value>0, return 0
"""

NEUTRAL_VALUE = 0.5
MIN_DENOMINATOR = 0.001


def normalize_higher_is_better(
    value: float | None,
    cap: float = 1.0,
    neutral_on_missing: bool = True,
) -> float:
    """
    Normalize a metric where higher values are better.

    Examples: PR review ratio, flow efficiency, commitment reliability

    Args:
        value: The raw value to normalize
        cap: Maximum normalized value (default 1.0)
        neutral_on_missing: Return neutral if value is None

    Returns:
        Normalized value between 0 and cap
    """
    if value is None:
        return NEUTRAL_VALUE if neutral_on_missing else 0.0
    return min(cap, max(0.0, value))


def normalize_lower_is_better(
    value: float | None,
    target: float,
    neutral_on_missing: bool = True,
) -> float:
    """
    Normalize a metric where lower values are better (inverted).

    Examples: Defect density, escaped rate, MTTR, lead time

    Formula: normalized = min(1, target / max(value, 0.001))

    Args:
        value: The raw value to normalize
        target: The target value (at or below this gives score of 1)
        neutral_on_missing: Return neutral if value is None

    Returns:
        Normalized value between 0 and 1
    """
    if value is None:
        return NEUTRAL_VALUE if neutral_on_missing else 0.0
    if value <= 0:
        return 1.0
    return min(1.0, target / max(value, MIN_DENOMINATOR))


def normalize_ratio_to_target(
    value: float | None,
    target: float,
    neutral_on_missing: bool = True,
) -> float:
    """
    Normalize a ratio metric to its target.

    Examples: SPI to SPI_t, CPI to CPI_t, flow efficiency to FE_t

    Formula: normalized = min(1, value / target)

    Args:
        value: The raw ratio value
        target: The target ratio (e.g., 1.0 for SPI)
        neutral_on_missing: Return neutral if value is None

    Returns:
        Normalized value between 0 and 1
    """
    if value is None:
        return NEUTRAL_VALUE if neutral_on_missing else 0.0
    if target <= 0:
        return 1.0 if value > 0 else NEUTRAL_VALUE
    return min(1.0, max(0.0, value / target))


def normalize_strict_zero_target(
    value: float | int | None,
    neutral_on_missing: bool = True,
) -> float:
    """
    Normalize a metric with strict zero tolerance.

    When target = 0, any deviation results in 0 score.
    Used for non-negotiable targets like security vulnerabilities.

    Examples: High severity vulnerabilities >30d (HighVuln_t = 0)

    Args:
        value: The raw value
        neutral_on_missing: Return neutral if value is None

    Returns:
        1.0 if value is 0 or None (when neutral), 0.0 otherwise
    """
    if value is None:
        return NEUTRAL_VALUE if neutral_on_missing else 0.0
    return 1.0 if value == 0 else 0.0


def normalize_budget_variance(
    actual_cost: float | None,
    budget: float | None,
    neutral_on_missing: bool = True,
) -> float:
    """
    DEPRECATED: clamped overrun-only budget variance.

    Kept temporarily for legacy fixtures / external callers. New code MUST
    use `normalize_cost_variance` with the signed CV / BAC indicator from
    `IndicatorsCreate.cost_variance_pct`. This function clamps to >= 0 so
    under-budget projects look identical to on-budget ones, and ignores
    progress entirely (a project 30% spent with 10% delivered scored as on
    plan). Replaced via audit finding #18 / migration 072.

    Formula: max(0, actual_cost/budget - 1)
    Result 0 means on/under budget, positive means overrun.

    Args:
        actual_cost: Actual cost to date
        budget: Total budget (Planned Value)
        neutral_on_missing: Return neutral if values are None

    Returns:
        Overrun percentage (0 = on budget, 0.1 = 10% over)
    """
    if actual_cost is None or budget is None:
        return NEUTRAL_VALUE if neutral_on_missing else 0.0
    if budget <= 0:
        return 0.0
    return max(0.0, actual_cost / budget - 1.0)


def normalize_cost_variance(
    cv_pct: float | None,
    target: float,
    neutral_on_missing: bool = False,
) -> float | None:
    """
    Normalize signed EVM Cost Variance percentage to a 0-1 score.

    CV_pct = (EV - AC) / BAC = percent_completed - cost_to_date / budget_total

    Sign convention (input):
    - cv_pct > 0  → ahead: more value delivered than money spent (GOOD).
    - cv_pct = 0  → on plan.
    - cv_pct < 0  → behind: overrun relative to value delivered (BAD).

    Scoring (output, piecewise-linear):
    - cv_pct >= 0           → 1.0
    - cv_pct <= -|target|   → 0.0
    - linear in between

    Missing handling matches the scorecard "missing excluded" rule by
    default (returns None so the calculator drops the component and
    redistributes weights). `neutral_on_missing=True` is an opt-in for the
    rare legacy caller that still wants a neutral fallback.

    Args:
        cv_pct: Signed Cost Variance over budget (e.g. -0.10 = 10% overrun).
        target: Absolute tolerance for under-delivery (e.g. 0.10).
        neutral_on_missing: Legacy opt-in for neutral fallback on None.

    Returns:
        Score 0..1 where 1 = good (on/under cost), 0 = at-or-worse-than
        target overrun. None when input is None and neutral is not opted
        into.
    """
    if cv_pct is None:
        if neutral_on_missing:
            return NEUTRAL_VALUE
        return None
    if cv_pct >= 0:
        return 1.0
    tolerance = abs(target)
    if tolerance <= 0:
        return 0.0
    if cv_pct <= -tolerance:
        return 0.0
    return 1.0 + cv_pct / tolerance


def normalize_governance_compliance(
    exceptions: int | None,
    target_max: int,
    neutral_on_missing: bool = True,
) -> float:
    """
    Normalize governance compliance based on exceptions.

    Formula: max(0, 1 - exceptions/target)

    Args:
        exceptions: Number of governance exceptions
        target_max: Maximum allowed exceptions (GovExc_t)
        neutral_on_missing: Return neutral if value is None

    Returns:
        Compliance score 0-1 (1 = full compliance)
    """
    if exceptions is None:
        return NEUTRAL_VALUE if neutral_on_missing else 0.0
    if target_max <= 0:
        return 1.0 if exceptions == 0 else 0.0
    return max(0.0, 1.0 - exceptions / target_max)


def normalize_count_to_ratio(
    value: int | None,
    target: float,
    total: int | None = None,
    neutral_on_missing: bool = True,
) -> float:
    """
    Normalize a count metric to a percentage target.

    Used for PRs without review where target is a percentage but value is a count.

    Formula: max(0, 1 - count / (total * target / 100))

    Args:
        value: The count value
        target: Target percentage (e.g., 2 for 2%)
        total: Total count for ratio calculation
        neutral_on_missing: Return neutral if value is None

    Returns:
        Normalized score 0-1
    """
    if value is None:
        return NEUTRAL_VALUE if neutral_on_missing else 0.0
    if total is None or total <= 0:
        return 1.0 if value == 0 else NEUTRAL_VALUE
    max_allowed = total * target / 100
    if max_allowed <= 0:
        return 1.0 if value == 0 else 0.0
    return max(0.0, 1.0 - value / max_allowed)
