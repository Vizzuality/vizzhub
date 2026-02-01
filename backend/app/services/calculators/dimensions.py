"""
Dimension calculators for Project Scorecard.

Each dimension calculator:
1. Accepts normalized indicators
2. Applies weights from config
3. Returns 0-100 score or None if no data
4. Excludes missing data and redistributes weights
"""

from app.models.indicators import IndicatorsCreate
from app.services.calculators.base import BaseCalculator, WeightedComponent


class TimeCalculator(BaseCalculator):
    """
    P_time: Schedule adherence score.

    Components:
    - SPI normalized to ideal (1.0 = on schedule, capped at 1) - weight 0.6
    - On-time milestones ratio normalized to target (85%) - weight 0.4

    Missing data handling:
    - If SPI missing: score based on milestones only
    - If milestones missing: score based on SPI only
    - If both missing: returns None
    """

    dimension_name = "time"
    weight_group = "time"

    def calculate(self, indicators: IndicatorsCreate) -> int | None:
        spi_ideal = self._get_ideal("spi")
        milestones_target = self._get_target("milestones_on_time") / 100

        components = [
            WeightedComponent(
                name="spi",
                weight=self._get_weight("spi"),
                value=self._normalize_to_ideal(indicators.spi, spi_ideal),
            ),
            WeightedComponent(
                name="milestones",
                weight=self._get_weight("milestones"),
                value=self._normalize_to_target(
                    indicators.on_time_milestones, milestones_target
                ),
            ),
        ]

        return self._to_score(self._weighted_average(components))


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


class ValueCalculator(BaseCalculator):
    """
    P_value: Strategic/business value score.

    Components:
    - OKR Impact score (categorical → numeric)
      - Low: 0.25 (25 points)
      - Medium: 0.55 (55 points)
      - High: 0.80 (80 points)
      - Transformational: 1.0 (100 points)

    Note: ROI was intentionally removed to avoid double-counting with CPI/SPI.

    Missing data handling:
    - If okr_impact is None: returns None
    """

    dimension_name = "value"
    weight_group = "value"

    def calculate(self, indicators: IndicatorsCreate) -> int | None:
        if indicators.okr_impact is None:
            return None
        return self._to_score(indicators.okr_impact)


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


class RiskCalculator(BaseCalculator):
    """
    P_risk: Risk posture score.

    Components:
    - PRs without review (0.5) - lower is better, target 2% of total PRs
    - High vulnerabilities >30d (0.5) - strict zero tolerance (target=0)

    Special logic:
    - PR ratio needs total_prs to calculate percentage
    - High vulns: if target=0, any value > 0 = score 0 (strict mode)

    Missing data handling:
    - Missing components are excluded and weights redistributed
    - If all components missing: returns None
    """

    dimension_name = "risk"
    weight_group = "risk"

    def calculate(
        self,
        indicators: IndicatorsCreate,
        total_prs: int | None = None,
    ) -> int | None:
        pr_target = self._get_target("pr_no_review_ratio")
        vuln_target = int(self._get_target("high_vuln_count"))

        pr_norm = self._calculate_pr_review_score(
            indicators.prs_without_review, total_prs, pr_target
        )
        vuln_norm = self._calculate_vuln_score(indicators.high_vulns, vuln_target)

        components = [
            WeightedComponent(
                name="pr_no_review",
                weight=self._get_weight("pr_no_review"),
                value=pr_norm,
            ),
            WeightedComponent(
                name="high_vulns",
                weight=self._get_weight("high_vulns"),
                value=vuln_norm,
            ),
        ]

        return self._to_score(self._weighted_average(components))

    def _calculate_pr_review_score(
        self,
        prs_without_review: int | None,
        total_prs: int | None,
        pr_target: float,
    ) -> float | None:
        """Calculate PR review score. Returns None if data is missing.

        When total_prs=0, returns None (no data) instead of assuming perfect score.
        This ensures P_risk shows as muted in the UI when there's no PR activity.
        """
        if prs_without_review is None:
            return None
        if total_prs is None or total_prs <= 0:
            return None  # No PRs = no data, not "perfect"
        max_allowed = total_prs * pr_target / 100
        if max_allowed <= 0:
            return 1.0 if prs_without_review == 0 else 0.0
        return max(0.0, 1.0 - prs_without_review / max_allowed)

    def _calculate_vuln_score(
        self,
        high_vulns: int | None,
        vuln_target: int,
    ) -> float | None:
        """Calculate vulnerability score. Strict zero mode if target=0."""
        if high_vulns is None:
            return None
        if vuln_target == 0:
            return 1.0 if high_vulns == 0 else 0.0
        return max(0.0, 1.0 - high_vulns / vuln_target)
