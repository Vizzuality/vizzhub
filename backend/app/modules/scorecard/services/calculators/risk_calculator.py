"""Risk dimension calculator (P_risk)."""

from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.services.calculators.base import BaseCalculator, WeightedComponent


class RiskCalculator(BaseCalculator):
    """
    P_risk: Risk posture score.

    Components:
    - PRs without review (0.5) - lower is better, target ~10% of total PRs
      (see config `target_pr_no_review_ratio`)
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
            return None
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
