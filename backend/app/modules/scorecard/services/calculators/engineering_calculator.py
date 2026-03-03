"""Engineering dimension calculator (P_engineering)."""

from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.services.calculators.base import BaseCalculator, WeightedComponent


class EngineeringCalculator(BaseCalculator):
    """
    P_engineering: Engineering discipline score.

    Components:
    - Test maturity (0.5) - higher is better, target 60%
    - PR review ratio (0.2) - higher is better, target 100%
    - Architecture checklist (0.3) - higher is better, target 100%

    Missing data handling:
    - Missing components are excluded and weights redistributed
    - If all components missing: returns None
    """

    dimension_name = "engineering"
    weight_group = "engineering"

    def calculate(self, indicators: IndicatorsCreate) -> int | None:
        test_maturity_target = self._get_target("test_maturity") / 100
        architecture_target = self._get_target("architecture") / 100

        components = [
            WeightedComponent(
                name="test_maturity",
                weight=self._get_weight("test_maturity"),
                value=self._normalize_to_target(
                    indicators.test_maturity, test_maturity_target
                ),
            ),
            WeightedComponent(
                name="pr_review",
                weight=self._get_weight("pr_review"),
                value=indicators.pr_review_ratio,
            ),
            WeightedComponent(
                name="architecture",
                weight=self._get_weight("architecture"),
                value=self._normalize_to_target(
                    indicators.arch_checklist, architecture_target
                ),
            ),
        ]

        return self._to_score(self._weighted_average(components))
