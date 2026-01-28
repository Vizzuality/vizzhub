"""
DORA Score Calculator

Calculates a separate DORA score based on the 4 official DORA metrics:
1. Deployment Frequency
2. Lead Time for Changes
3. Change Failure Rate
4. Mean Time to Recovery (MTTR)

This score is displayed separately and does NOT affect the main project score.
The individual metrics already contribute to P_flow and P_quality dimensions.
"""

from dataclasses import dataclass

from app.config import ScoringConfig
from app.models.indicators import IndicatorsCreate


@dataclass(frozen=True)
class DoraMetric:
    """Definition of a DORA metric for scoring."""

    name: str
    indicator_attr: str
    target_key: str
    lower_is_better: bool = False


class DoraScoreCalculator:
    """Calculate DORA score from 4 official DORA metrics."""

    METRICS = (
        DoraMetric("deployment_frequency", "deployment_frequency", "deployment_frequency"),
        DoraMetric("lead_time", "lead_time_days", "lead_time_days", lower_is_better=True),
        DoraMetric("change_failure_rate", "change_failure_rate", "change_failure_rate", lower_is_better=True),
        DoraMetric("mttr", "mttr_hours", "mttr_hours", lower_is_better=True),
    )

    def __init__(self, config: ScoringConfig) -> None:
        self.config = config

    def calculate(self, indicators: IndicatorsCreate) -> dict:
        """
        Calculate DORA score and classification.

        Returns:
            dict with score (0-100), classification, and individual metric scores
        """
        scores: dict[str, float | None] = {}

        for metric in self.METRICS:
            value = getattr(indicators, metric.indicator_attr)
            if value is not None:
                target = self.config.get_target(metric.target_key)
                scores[metric.name] = self._normalize(value, target, metric.lower_is_better)
            else:
                scores[metric.name] = None

        valid_scores = [s for s in scores.values() if s is not None]

        if not valid_scores:
            return {
                "score": None,
                "classification": None,
                "metrics": scores,
                "available_metrics": 0,
            }

        avg_score = sum(valid_scores) / len(valid_scores)
        final_score = round(avg_score * 100)

        return {
            "score": final_score,
            "classification": self._get_classification(final_score),
            "metrics": scores,
            "available_metrics": len(valid_scores),
        }

    def _normalize(self, value: float, target: float, lower_is_better: bool) -> float:
        """Normalize a metric value to 0-1 scale."""
        if lower_is_better:
            if value == 0:
                return 1.0
            return min(1.0, target / value)
        return min(1.0, value / target)

    def _get_classification(self, score: int) -> str:
        """
        Classify DORA performance level.

        Based on DORA research benchmarks:
        - Elite: Top performers (85-100)
        - High: Above average (70-84)
        - Medium: Average (50-69)
        - Low: Below average (0-49)
        """
        if score >= 85:
            return "Elite"
        elif score >= 70:
            return "High"
        elif score >= 50:
            return "Medium"
        else:
            return "Low"
