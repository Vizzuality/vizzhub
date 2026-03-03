"""Cost dimension calculator (P_cost)."""

from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.services.calculators.base import BaseCalculator, WeightedComponent


class CostCalculator(BaseCalculator):
    """
    P_cost: Budget adherence score.

    Components:
    - CPI normalized to ideal (1.0 = on budget, capped at 1) - weight 0.7
    - Budget variance inverted (1 - overrun%, floored at 0) - weight 0.3

    Missing data handling:
    - If CPI missing: score based on variance only
    - If variance missing: score based on CPI only
    - If both missing: returns None
    """

    dimension_name = "cost"
    weight_group = "cost"

    def calculate(self, indicators: IndicatorsCreate) -> int | None:
        cpi_ideal = self._get_ideal("cpi")

        cpi_normalized = self._normalize_to_ideal(indicators.cpi, cpi_ideal)
        variance_normalized = (
            None
            if indicators.budget_variance is None
            else max(0.0, 1.0 - indicators.budget_variance)
        )

        components = [
            WeightedComponent(
                name="cpi",
                weight=self._get_weight("cpi"),
                value=cpi_normalized,
            ),
            WeightedComponent(
                name="variance",
                weight=self._get_weight("variance"),
                value=variance_normalized,
            ),
        ]

        return self._to_score(self._weighted_average(components))
