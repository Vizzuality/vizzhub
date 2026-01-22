"""
Dimension calculators for Project Scorecard.

Each dimension calculator:
1. Accepts normalized indicators
2. Applies weights from config
3. Returns 0-100 score
4. Handles missing data with neutral (0.5)
"""

from app.models.indicators import IndicatorsCreate
from app.services.calculators.base import BaseCalculator
from app.services.normalizers.base import NEUTRAL_VALUE


class TimeCalculator(BaseCalculator):
    """
    P_time: Schedule adherence score.

    Components:
    - SPI normalized to target (capped at 1)
    - On-time milestones ratio (already 0-1)
    """

    dimension_name = "time"
    weight_group = "time"

    def calculate(self, indicators: IndicatorsCreate) -> int:
        w_spi = self._get_weight("spi")
        w_milestones = self._get_weight("milestones")
        spi_target = self._get_target("spi")

        spi_normalized = self._normalize_to_target(indicators.spi, spi_target)
        milestones_normalized = self._safe_value(indicators.on_time_milestones)

        score = w_spi * spi_normalized + w_milestones * milestones_normalized
        return self._to_score(score)


class CostCalculator(BaseCalculator):
    """
    P_cost: Budget adherence score.

    Components:
    - CPI normalized to target (capped at 1)
    - Budget variance inverted (1 - overrun%, floored at 0)
    """

    dimension_name = "cost"
    weight_group = "cost"

    def calculate(self, indicators: IndicatorsCreate) -> int:
        w_cpi = self._get_weight("cpi")
        w_variance = self._get_weight("variance")
        cpi_target = self._get_target("cpi")

        cpi_normalized = self._normalize_to_target(indicators.cpi, cpi_target)
        variance_normalized = (
            NEUTRAL_VALUE
            if indicators.budget_variance is None
            else max(0.0, 1.0 - indicators.budget_variance)
        )

        score = w_cpi * cpi_normalized + w_variance * variance_normalized
        return self._to_score(score)


class QualityCalculator(BaseCalculator):
    """
    P_quality: Product & delivery quality score.

    Components:
    - Defect density (inverted, lower is better)
    - Governance compliance (direct, higher is better)
    - Escaped rate (inverted, lower is better)
    - MTTR (inverted, lower is better)
    - PR review ratio (direct, higher is better)
    - Story review ratio (direct, higher is better)
    - Change failure rate (inverted, lower is better) - DORA metric

    Special rule: If Sev1 incident occurred, cap score at Sev1_cap (60).
    """

    dimension_name = "quality"
    weight_group = "quality"

    def calculate(
        self,
        indicators: IndicatorsCreate,
        sev1_incident: bool = False,
    ) -> int:
        w_defect = self._get_weight("defect_density")
        w_escaped = self._get_weight("escaped_rate")
        w_mttr = self._get_weight("mttr")
        w_story_review = self._get_weight("story_review")
        w_governance = self._get_weight("governance")
        w_pr_review = self._get_weight("pr_review")
        w_cfr = self._get_weight("change_failure_rate")

        defect_target = self._get_target("defect_density")
        escaped_target = self._get_target("escaped_rate")
        mttr_target = self._get_target("mttr_hours")
        cfr_target = self._get_target("change_failure_rate")

        defect_norm = self._normalize_to_target(
            indicators.defect_density, defect_target, lower_is_better=True
        )
        escaped_norm = self._normalize_to_target(
            indicators.escaped_rate, escaped_target, lower_is_better=True
        )
        mttr_norm = self._normalize_to_target(
            indicators.mttr_hours, mttr_target, lower_is_better=True
        )
        governance_norm = self._safe_value(indicators.governance_compliance)
        pr_review_norm = self._safe_value(indicators.pr_review_ratio)
        story_review_norm = self._safe_value(indicators.story_review_ratio)
        cfr_norm = self._normalize_to_target(
            indicators.change_failure_rate, cfr_target, lower_is_better=True
        )

        score = (
            w_defect * defect_norm
            + w_escaped * escaped_norm
            + w_mttr * mttr_norm
            + w_governance * governance_norm
            + w_pr_review * pr_review_norm
            + w_story_review * story_review_norm
            + w_cfr * cfr_norm
        )

        final_score = self._to_score(score)

        if sev1_incident:
            sev1_cap = int(self.config.get_constant("sev1_cap"))
            final_score = min(final_score, sev1_cap)

        return final_score


class ValueCalculator(BaseCalculator):
    """
    P_value: Strategic/business value score.

    Components:
    - OKR Impact score (categorical → numeric)

    Note: ROI was intentionally removed to avoid double-counting with CPI/SPI.
    """

    dimension_name = "value"
    weight_group = "value"

    def calculate(self, indicators: IndicatorsCreate) -> int:
        okr_impact = self._safe_value(indicators.okr_impact)
        return self._to_score(okr_impact)


class SatisfactionCalculator(BaseCalculator):
    """
    P_satisfaction: Client satisfaction score.

    Components:
    - Client survey (if available, weighted 80%)
    - PM estimation (weighted 20%, or 100% if no survey)
    """

    dimension_name = "satisfaction"
    weight_group = "satisfaction"

    def calculate(self, indicators: IndicatorsCreate) -> int:
        w_client = self._get_weight("client_survey")
        w_pm = self._get_weight("pm_estimation")

        pm_score = self._safe_value(indicators.pm_satisfaction)

        if indicators.client_satisfaction is None:
            return self._to_score(pm_score)

        client_score = indicators.client_satisfaction
        score = w_client * client_score + w_pm * pm_score
        return self._to_score(score)


class FlowCalculator(BaseCalculator):
    """
    P_flow: Delivery flow & predictability score.

    Components:
    - Lead time (inverted, lower is better)
    - Commitment reliability (direct, higher is better)
    - PR size (inverted, lower is better)
    - Review turnaround (inverted, lower is better)
    - Deployment frequency (direct, higher is better)
    """

    dimension_name = "flow"
    weight_group = "flow"

    def calculate(self, indicators: IndicatorsCreate) -> int:
        w_lead_time = self._get_weight("lead_time")
        w_commitment = self._get_weight("commitment_reliability")
        w_pr_size = self._get_weight("pr_size")
        w_review_turnaround = self._get_weight("review_turnaround")
        w_deployment_freq = self._get_weight("deployment_frequency")

        lt_target = self._get_target("lead_time_days")
        pr_size_target = self._get_target("pr_size_lines")
        review_turnaround_target = self._get_target("review_turnaround_hours")
        deployment_freq_target = self._get_target("deployment_frequency")

        lead_time_norm = self._normalize_to_target(
            indicators.lead_time_days, lt_target, lower_is_better=True
        )
        commitment_norm = self._safe_value(indicators.commitment_reliability)
        pr_size_norm = self._normalize_to_target(
            indicators.pr_size_median, pr_size_target, lower_is_better=True
        )
        review_turnaround_norm = self._normalize_to_target(
            indicators.review_turnaround_hours, review_turnaround_target, lower_is_better=True
        )
        deployment_freq_norm = self._normalize_to_target(
            indicators.deployment_frequency, deployment_freq_target, lower_is_better=False
        )

        score = (
            w_lead_time * lead_time_norm
            + w_commitment * commitment_norm
            + w_pr_size * pr_size_norm
            + w_review_turnaround * review_turnaround_norm
            + w_deployment_freq * deployment_freq_norm
        )
        return self._to_score(score)


class EngineeringCalculator(BaseCalculator):
    """
    P_engineering: Engineering discipline score.

    Components:
    - Test maturity (already 0-1)
    - PR review ratio (already 0-1)
    - Architecture checklist (0-4, normalized to 0-1)
    """

    dimension_name = "engineering"
    weight_group = "engineering"

    def calculate(self, indicators: IndicatorsCreate) -> int:
        w_test = self._get_weight("test_maturity")
        w_pr = self._get_weight("pr_review")
        w_arch = self._get_weight("architecture")

        test_norm = self._safe_value(indicators.test_maturity)
        pr_norm = self._safe_value(indicators.pr_review_ratio)
        arch_norm = self._safe_value(indicators.arch_checklist)

        score = w_test * test_norm + w_pr * pr_norm + w_arch * arch_norm
        return self._to_score(score)


class RiskCalculator(BaseCalculator):
    """
    P_risk: Risk posture score.

    Components:
    - PRs without review (inverted, normalized to target)
    - High vulnerabilities >30d (inverted, strict mode if target=0)
    """

    dimension_name = "risk"
    weight_group = "risk"

    def calculate(
        self,
        indicators: IndicatorsCreate,
        total_prs: int | None = None,
    ) -> int:
        w_pr = self._get_weight("pr_no_review")
        w_vuln = self._get_weight("high_vulns")

        pr_target = self._get_target("pr_no_review_ratio")
        vuln_target = int(self._get_target("high_vuln_count"))

        if indicators.prs_without_review is None:
            pr_norm = NEUTRAL_VALUE
        elif total_prs is None or total_prs <= 0:
            pr_norm = 1.0 if indicators.prs_without_review == 0 else NEUTRAL_VALUE
        else:
            # pr_target is now in percentage format (e.g., 2 means 2%)
            max_allowed = total_prs * pr_target / 100
            if max_allowed <= 0:
                pr_norm = 1.0 if indicators.prs_without_review == 0 else 0.0
            else:
                pr_norm = max(0.0, 1.0 - indicators.prs_without_review / max_allowed)

        if indicators.high_vulns is None:
            vuln_norm = NEUTRAL_VALUE
        elif vuln_target == 0:
            vuln_norm = 1.0 if indicators.high_vulns == 0 else 0.0
        else:
            vuln_norm = max(0.0, 1.0 - indicators.high_vulns / vuln_target)

        score = w_pr * pr_norm + w_vuln * vuln_norm
        return self._to_score(score)
