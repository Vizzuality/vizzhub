"""Flow dimension calculator (P_flow)."""

from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.services.calculators.base import BaseCalculator, WeightedComponent


class FlowCalculator(BaseCalculator):
    """
    P_flow: Delivery flow & predictability score.

    Components:
    - Lead time (0.35) - lower is better, target 3 days
    - Commitment reliability (0.25) - higher is better, target 100%
    - PR size (0.15) - lower is better, target 400 lines
    - Review turnaround (0.10) - lower is better, target 24h
    - Deployment frequency (0.15) - higher is better, target 1/day

    Missing data handling:
    - Missing components are excluded and weights redistributed
    - If all components missing: returns None
    """

    dimension_name = "flow"
    weight_group = "flow"

    def calculate(self, indicators: IndicatorsCreate) -> int | None:
        lt_target = self._get_target("lead_time_days")
        pr_size_target = self._get_target("pr_size_lines")
        review_turnaround_target = self._get_target("review_turnaround_hours")
        deployment_freq_target = self._get_target("deployment_frequency")

        components = [
            WeightedComponent(
                name="lead_time",
                weight=self._get_weight("lead_time"),
                value=self._normalize_to_target(
                    indicators.lead_time_days, lt_target, lower_is_better=True
                ),
            ),
            WeightedComponent(
                name="commitment_reliability",
                weight=self._get_weight("commitment_reliability"),
                value=indicators.commitment_reliability,
            ),
            WeightedComponent(
                name="pr_size",
                weight=self._get_weight("pr_size"),
                value=self._normalize_to_target(
                    indicators.pr_size_median, pr_size_target, lower_is_better=True
                ),
            ),
            WeightedComponent(
                name="review_turnaround",
                weight=self._get_weight("review_turnaround"),
                value=self._normalize_to_target(
                    indicators.review_turnaround_hours,
                    review_turnaround_target,
                    lower_is_better=True,
                ),
            ),
            WeightedComponent(
                name="deployment_frequency",
                weight=self._get_weight("deployment_frequency"),
                value=self._normalize_to_target(
                    indicators.deployment_frequency, deployment_freq_target, lower_is_better=False
                ),
            ),
        ]

        return self._to_score(self._weighted_average(components))
