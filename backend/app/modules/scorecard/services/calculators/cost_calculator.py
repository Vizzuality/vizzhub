"""Cost dimension calculator (P_cost)."""

from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.services.calculators.base import BaseCalculator, WeightedComponent
from app.modules.scorecard.services.normalizers.base import normalize_cost_variance


class CostCalculator(BaseCalculator):
    """
    P_cost: Budget adherence score.

    Components:
    - CPI normalized to ideal (1.0 = on budget, capped at 1) - weight 0.7
    - Signed Cost Variance % scored on a piecewise-linear normalizer
      (>= 0 = 100, <= -target = 0) - weight 0.3 (audit #18: replaces the
      clamped overrun-only budget_variance with the EVM-standard signed
      CV / BAC; under-budget and on-plan are now distinguishable, and
      progress is accounted for).

    Missing data handling:
    - If CPI missing: score based on cost variance only
    - If cost variance missing: score based on CPI only
    - If both missing: returns None
    """

    dimension_name = "cost"
    weight_group = "cost"

    def calculate(self, indicators: IndicatorsCreate) -> int | None:
        cpi_ideal = self._get_ideal("cpi")

        cpi_normalized = self._normalize_to_ideal(indicators.cpi, cpi_ideal)
        cv_target = self._get_target("cost_variance")
        cv_normalized = normalize_cost_variance(indicators.cost_variance_pct, cv_target)

        components = [
            WeightedComponent(
                name="cpi",
                weight=self._get_weight("cpi"),
                value=cpi_normalized,
            ),
            WeightedComponent(
                name="variance",
                weight=self._get_weight("variance"),
                value=cv_normalized,
            ),
        ]

        return self._to_score(self._weighted_average(components))
