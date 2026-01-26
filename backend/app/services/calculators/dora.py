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

from app.config import ScoringConfig
from app.models.indicators import IndicatorsCreate


class DoraScoreCalculator:
    """Calculate DORA score from 4 official DORA metrics."""

    def __init__(self, config: ScoringConfig) -> None:
        self.config = config

    def calculate(self, indicators: IndicatorsCreate) -> dict:
        """
        Calculate DORA score and classification.

        Returns:
            dict with score (0-100), classification, and individual metric scores
        """
        scores = {}
        available_metrics = 0

        # 1. Deployment Frequency (higher is better)
        # Target: 1 per day, Elite: >1/day
        if indicators.deployment_frequency is not None:
            target = self.config.get_target("deployment_frequency")
            scores["deployment_frequency"] = min(1.0, indicators.deployment_frequency / target)
            available_metrics += 1
        else:
            scores["deployment_frequency"] = None

        # 2. Lead Time for Changes (lower is better)
        # Target: 3 days, Elite: <1 day
        if indicators.lead_time_days is not None:
            target = self.config.get_target("lead_time_days")
            scores["lead_time"] = min(1.0, target / max(indicators.lead_time_days, 0.001))
            available_metrics += 1
        else:
            scores["lead_time"] = None

        # 3. Change Failure Rate (lower is better)
        # Target: 15%, Elite: <15%
        if indicators.change_failure_rate is not None:
            target = self.config.get_target("change_failure_rate")
            if indicators.change_failure_rate == 0:
                scores["change_failure_rate"] = 1.0
            else:
                scores["change_failure_rate"] = min(1.0, target / indicators.change_failure_rate)
            available_metrics += 1
        else:
            scores["change_failure_rate"] = None

        # 4. Mean Time to Recovery (lower is better)
        # Target: 24 hours, Elite: <1 hour
        if indicators.mttr_hours is not None:
            target = self.config.get_target("mttr_hours")
            if indicators.mttr_hours == 0:
                scores["mttr"] = 1.0
            else:
                scores["mttr"] = min(1.0, target / indicators.mttr_hours)
            available_metrics += 1
        else:
            scores["mttr"] = None

        # Calculate overall DORA score
        if available_metrics == 0:
            return {
                "score": None,
                "classification": None,
                "metrics": scores,
                "available_metrics": 0,
            }

        valid_scores = [s for s in scores.values() if s is not None]
        avg_score = sum(valid_scores) / len(valid_scores)
        final_score = round(avg_score * 100)

        # DORA classification based on score
        classification = self._get_classification(final_score)

        return {
            "score": final_score,
            "classification": classification,
            "metrics": scores,
            "available_metrics": available_metrics,
        }

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
