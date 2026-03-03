"""Satisfaction dimension calculator (P_satisfaction)."""

from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.services.calculators.base import BaseCalculator, WeightedComponent


class SatisfactionCalculator(BaseCalculator):
    """
    P_satisfaction: Client satisfaction score.

    Components:
    - Client survey (weighted 90% when available) - target 80%
    - PM estimation (weighted 10% when survey available, 100% when not) - target 90%

    During development: No client survey available, so PM estimation is 100%
    At end of project: Client survey available, weights are 90% client + 10% PM

    Missing data handling:
    - If client survey missing: PM estimation = 100% weight
    - If PM estimation missing: Client survey = 100% weight (if available)
    - If both missing: returns None
    """

    dimension_name = "satisfaction"
    weight_group = "satisfaction"

    def calculate(self, indicators: IndicatorsCreate) -> int | None:
        client_satisfaction_target = self._get_target("client_satisfaction") / 100
        pm_satisfaction_target = self._get_target("pm_satisfaction") / 100

        components = [
            WeightedComponent(
                name="client_survey",
                weight=self._get_weight("client_survey"),
                value=self._normalize_to_target(
                    indicators.client_satisfaction, client_satisfaction_target
                ),
            ),
            WeightedComponent(
                name="pm_estimation",
                weight=self._get_weight("pm_estimation"),
                value=self._normalize_to_target(
                    indicators.pm_satisfaction, pm_satisfaction_target
                ),
            ),
        ]

        return self._to_score(self._weighted_average(components))
