"""
Indicator normalizer service.

Transforms raw metrics into normalized indicators (0-1 scale).
"""

from datetime import date

from app.config import ScoringConfig, get_scoring_config
from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.models.metrics import (
    ArchitectureChecklist,
    ClientSurvey,
    ComplaintStatus,
    EVMData,
    FlowMetrics,
    GitHubMetrics,
    JiraDefectMetrics,
    MetricsCreate,
    Milestone,
    PMSatisfaction,
    StrategicImpact,
    TestMaturity,
)
from app.modules.scorecard.services.normalizers.base import (
    normalize_budget_variance,
    normalize_governance_compliance,
)


class IndicatorNormalizer:
    """Normalizes raw metrics into indicators."""

    def __init__(self, config: ScoringConfig | None = None):
        self.config = config or get_scoring_config()

    def normalize_all(self, metrics: MetricsCreate) -> IndicatorsCreate:
        """Normalize all metrics into indicators."""
        return IndicatorsCreate(
            spi=self._normalize_spi(metrics.evm_data),
            on_time_milestones=self._normalize_milestones(metrics.milestones),
            cpi=self._normalize_cpi(metrics.evm_data),
            budget_variance=self._calculate_budget_variance(metrics.evm_data),
            defect_density=self._calculate_defect_density(metrics.jira_defects),
            escaped_rate=self._calculate_escaped_rate(metrics.jira_defects),
            mttr_hours=self._get_mttr(metrics.jira_defects),
            governance_compliance=self._normalize_governance(
                metrics.governance_exceptions
            ),
            lead_time_days=self._get_lead_time(metrics.flow_metrics),
            commitment_reliability=self._get_commitment_reliability(
                metrics.flow_metrics
            ),
            pr_review_ratio=self._get_pr_review_ratio(metrics.github_metrics),
            prs_without_review=self._get_prs_without_review(metrics.github_metrics),
            high_vulns=self._get_high_vulns(metrics.github_metrics),
            test_maturity=self._normalize_test_maturity(metrics.test_maturity),
            arch_checklist=self._normalize_architecture(metrics.architecture),
            story_review_ratio=self._calculate_story_review_ratio(metrics.flow_metrics),
            okr_impact=self._normalize_okr_impact(metrics.strategic_impact),
            pm_satisfaction=self._normalize_pm_satisfaction(metrics.pm_satisfaction),
            client_satisfaction=self._normalize_client_survey(metrics.client_survey),
            pr_size_median=self._get_pr_size_median(metrics.github_metrics),
            review_turnaround_hours=self._get_review_turnaround_hours(metrics.github_metrics),
            deployment_frequency=self._get_deployment_frequency(metrics.github_metrics),
            change_failure_rate=self._get_change_failure_rate(metrics.github_metrics),
            post_contract_tasks=self._get_post_contract_tasks(metrics.jira_defects),
        )

    def _normalize_spi(self, evm: EVMData | None) -> float | None:
        """Calculate SPI from EVM data."""
        if evm is None:
            return None
        if evm.percent_planned <= 0:
            return None
        return evm.percent_completed / evm.percent_planned

    def _normalize_cpi(self, evm: EVMData | None) -> float | None:
        """Calculate CPI from EVM data."""
        if evm is None:
            return None
        if evm.cost_to_date <= 0:
            return None
        ev = evm.budget_total * evm.percent_completed
        return ev / evm.cost_to_date

    def _calculate_budget_variance(self, evm: EVMData | None) -> float | None:
        """Calculate budget overrun percentage."""
        if evm is None or evm.cost_to_date is None or evm.budget_total is None:
            return None
        if evm.cost_to_date <= 0:
            return None
        return normalize_budget_variance(evm.cost_to_date, evm.budget_total, False)

    def _normalize_milestones(self, milestones: list[Milestone] | None) -> float | None:
        """Calculate on-time milestone ratio.

        A milestone is considered:
        - Due: if it has actual_date OR today > planned_date + grace_days
        - On-time: if actual_date <= planned_date + grace_days
        - Late: if actual_date > planned_date + grace_days OR (due but no actual_date)

        Returns ratio of on-time milestones (0-1).
        """
        if not milestones:
            return None

        from datetime import timedelta

        grace_days = int(self.config.get_constant("grace_days"))
        today = date.today()

        total_due = 0
        on_time_count = 0

        for ms in milestones:
            grace_date = ms.planned_date + timedelta(days=grace_days)

            is_due = ms.actual_date is not None or today > grace_date
            if not is_due:
                continue

            total_due += 1

            if ms.actual_date is not None and ms.actual_date <= grace_date:
                on_time_count += 1

        if total_due == 0:
            return None

        return on_time_count / total_due

    def _calculate_defect_density(
        self, jira: JiraDefectMetrics | None
    ) -> float | None:
        """Calculate defect density per 100 tasks.

        Returns None when there are no completed tasks: defect density is
        undefined, not zero. Excluded from the weighted average upstream.
        """
        if jira is None:
            return None
        if jira.tasks_completed <= 0:
            return None
        return (jira.bugs_total / jira.tasks_completed) * 100

    def _calculate_escaped_rate(self, jira: JiraDefectMetrics | None) -> float | None:
        """Calculate escaped defect rate per 100 tasks.

        Returns None when there are no completed tasks: the rate is undefined.
        """
        if jira is None:
            return None
        if jira.tasks_completed <= 0:
            return None
        return (jira.escaped_defects / jira.tasks_completed) * 100

    def _get_mttr(self, jira: JiraDefectMetrics | None) -> float | None:
        """Get MTTR in hours.

        Returns None when there are no incidents: MTTR cannot be measured
        without data. Zero would mislead as 'perfect repair time'.
        """
        if jira is None:
            return None
        if jira.incidents_count == 0:
            return None
        return jira.mttr_hours

    def _normalize_governance(self, exceptions: int | None) -> float | None:
        """Normalize governance compliance."""
        if exceptions is None:
            return None
        target = int(self.config.get_target("gov_exceptions"))
        return normalize_governance_compliance(exceptions, target, False)

    def _get_lead_time(self, flow: FlowMetrics | None) -> float | None:
        """Get lead time in days."""
        if flow is None:
            return None
        return flow.lead_time_days

    def _get_commitment_reliability(self, flow: FlowMetrics | None) -> float | None:
        """Get commitment reliability ratio."""
        if flow is None:
            return None
        return flow.commitment_reliability

    def _get_pr_review_ratio(self, github: GitHubMetrics | None) -> float | None:
        """Get PR review ratio."""
        if github is None:
            return None
        return github.pr_review_ratio

    def _get_prs_without_review(self, github: GitHubMetrics | None) -> int | None:
        """Get count of PRs without review."""
        if github is None:
            return None
        return github.prs_without_review

    def _get_high_vulns(self, github: GitHubMetrics | None) -> int | None:
        """Get count of high severity vulnerabilities >30d."""
        if github is None:
            return None
        return github.high_severity_vulns

    def _normalize_test_maturity(self, test: TestMaturity | None) -> float | None:
        """Calculate weighted test maturity score.

        Missing fields are excluded (None) and weights are redistributed
        among available components. Returns None when no field is rated.
        """
        if test is None:
            return None

        field_mapping = [
            (test.e2e, "e2e"),
            (test.unit, "unit"),
            (test.accessibility, "accessibility"),
            (test.security, "security"),
            (test.frontend, "frontend"),
        ]

        total = 0.0
        weight_sum = 0.0
        for value, key in field_mapping:
            if value is None:
                continue
            weight = self.config.get_weight("test_maturity", key)
            total += (value / 5.0) * weight
            weight_sum += weight

        if weight_sum <= 0:
            return None

        return round(total / weight_sum, 2) if weight_sum < 1.0 else round(total, 2)

    def _normalize_architecture(self, arch: ArchitectureChecklist | None) -> float | None:
        """Calculate architecture checklist score (0-1)."""
        if arch is None:
            return None

        count = sum([
            arch.docs_up_to_date,
            arch.iac_implemented,
            arch.adrs_maintained,
            arch.diagrams_updated,
        ])
        return count / 4.0

    def _calculate_story_review_ratio(self, flow: FlowMetrics | None) -> float | None:
        """Calculate story review ratio."""
        if flow is None:
            return None
        if flow.total_stories <= 0:
            return None
        return min(1.0, max(0.0, flow.stories_with_reviewer / flow.total_stories))

    def _normalize_okr_impact(self, impact: StrategicImpact | None) -> float | None:
        """Map strategic impact to numeric score.

        Returns None if the value is not in the mapping (defensive — the
        enum exhausts the mapping, but a stray value should be excluded
        from the weighted average rather than neutralized).
        """
        if impact is None:
            return None

        mapping = {
            StrategicImpact.LOW: 0.25,
            StrategicImpact.MEDIUM: 0.55,
            StrategicImpact.HIGH: 0.80,
            StrategicImpact.TRANSFORMATIONAL: 1.0,
        }
        return mapping.get(impact)

    def _normalize_pm_satisfaction(self, pm: PMSatisfaction | None) -> float | None:
        """Calculate PM satisfaction estimation score.

        Each component (delivery complaints, design complaints, overall
        estimation) is excluded when not provided (ComplaintStatus.NA or
        overall_estimation=None). Weights are redistributed among the
        available components. Returns None when nothing was rated.
        """
        if pm is None:
            return None

        complaint_scores = {
            ComplaintStatus.NO: 1.0,
            ComplaintStatus.YES: 0.4,
        }

        delivery = complaint_scores.get(pm.delivery_complaints)
        design = complaint_scores.get(pm.design_complaints)
        overall = pm.overall_estimation / 5.0 if pm.overall_estimation is not None else None

        components: list[tuple[float | None, float]] = [
            (delivery, 0.3),
            (design, 0.3),
            (overall, 0.4),
        ]

        total = 0.0
        weight_sum = 0.0
        for value, weight in components:
            if value is None:
                continue
            total += value * weight
            weight_sum += weight

        if weight_sum <= 0:
            return None

        return round(total / weight_sum, 2) if weight_sum < 1.0 else round(total, 2)

    def _normalize_client_survey(self, survey: ClientSurvey | None) -> float | None:
        """Calculate weighted client survey score."""
        if survey is None:
            return None

        field_mapping = [
            (survey.understanding, "understanding"),
            (survey.proactivity, "proactivity"),
            (survey.communication, "communication"),
            (survey.delivery_time, "time"),
            (survey.response_time, "response"),
            (survey.quality, "quality"),
            (survey.expectations, "expectations"),
            (survey.recommend, "recommend"),
        ]

        total = 0.0
        weight_sum = 0.0

        for value, key in field_mapping:
            weight = self.config.get_weight("client_survey", key)
            if value is not None:
                total += (value / 5.0) * weight
                weight_sum += weight

        if weight_sum <= 0:
            return None

        return round(total / weight_sum, 2) if weight_sum < 1.0 else round(total, 2)

    def _get_pr_size_median(self, github: GitHubMetrics | None) -> float | None:
        """Get median PR size in lines."""
        if github is None:
            return None
        return github.pr_size_median

    def _get_review_turnaround_hours(self, github: GitHubMetrics | None) -> float | None:
        """Get median review turnaround time in hours."""
        if github is None:
            return None
        return github.review_turnaround_hours

    def _get_deployment_frequency(self, github: GitHubMetrics | None) -> float | None:
        """Get deployment frequency (releases per day)."""
        if github is None:
            return None
        return github.deployment_frequency

    def _get_change_failure_rate(self, github: GitHubMetrics | None) -> float | None:
        """Get change failure rate (%)."""
        if github is None:
            return None
        return github.change_failure_rate

    def _get_post_contract_tasks(self, jira: JiraDefectMetrics | None) -> int | None:
        """Get count of tasks created after contract end + 30 days."""
        if jira is None:
            return None
        return jira.post_contract_tasks
