"""Quality dimension calculator (P_quality)."""

from app.models.indicators import IndicatorsCreate
from app.services.calculators.base import BaseCalculator, WeightedComponent


class QualityCalculator(BaseCalculator):
    """
    P_quality: Product & delivery quality score.

    Components (8 total):
    - Defect density (0.05) - lower is better, target 3%
    - Escaped rate (0.15) - lower is better, target 1%
    - MTTR (0.05) - lower is better, target 24h
    - Story review (0.25) - higher is better
    - Governance (0.20) - higher is better (compliance score)
    - PR review (0.10) - higher is better
    - Change failure rate (0.15) - lower is better, target 15%
    - Post-contract tasks (0.05) - lower is better, target 3

    Special rule: If Sev1 incident occurred, cap score at Sev1_cap (60).

    Missing data handling:
    - Missing components are excluded and weights redistributed
    - If all components missing: returns None
    """

    dimension_name = "quality"
    weight_group = "quality"

    def calculate(
        self,
        indicators: IndicatorsCreate,
        sev1_incident: bool = False,
    ) -> int | None:
        defect_target = self._get_target("defect_density")
        escaped_target = self._get_target("escaped_rate")
        mttr_target = self._get_target("mttr_hours")
        cfr_target = self._get_target("change_failure_rate")
        post_contract_target = self._get_target("post_contract_tasks")

        components = [
            WeightedComponent(
                name="defect_density",
                weight=self._get_weight("defect_density"),
                value=self._normalize_to_target(
                    indicators.defect_density, defect_target, lower_is_better=True
                ),
            ),
            WeightedComponent(
                name="escaped_rate",
                weight=self._get_weight("escaped_rate"),
                value=self._normalize_to_target(
                    indicators.escaped_rate, escaped_target, lower_is_better=True
                ),
            ),
            WeightedComponent(
                name="mttr",
                weight=self._get_weight("mttr"),
                value=self._normalize_to_target(
                    indicators.mttr_hours, mttr_target, lower_is_better=True
                ),
            ),
            WeightedComponent(
                name="story_review",
                weight=self._get_weight("story_review"),
                value=indicators.story_review_ratio,
            ),
            WeightedComponent(
                name="governance",
                weight=self._get_weight("governance"),
                value=indicators.governance_compliance,
            ),
            WeightedComponent(
                name="pr_review",
                weight=self._get_weight("pr_review"),
                value=indicators.pr_review_ratio,
            ),
            WeightedComponent(
                name="change_failure_rate",
                weight=self._get_weight("change_failure_rate"),
                value=self._normalize_to_target(
                    indicators.change_failure_rate, cfr_target, lower_is_better=True
                ),
            ),
            WeightedComponent(
                name="post_contract_tasks",
                weight=self._get_weight("post_contract_tasks"),
                value=self._normalize_to_target(
                    indicators.post_contract_tasks, post_contract_target, lower_is_better=True
                ),
            ),
        ]

        final_score = self._to_score(self._weighted_average(components))

        if final_score is not None and sev1_incident:
            sev1_cap = int(self.config.get_constant("sev1_cap"))
            final_score = min(final_score, sev1_cap)

        return final_score
