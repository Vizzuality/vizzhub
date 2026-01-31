"""
DORA Score Calculator

Calculates a DORA score based on the 4 official DORA metrics using
standard DORA thresholds from the State of DevOps reports:

1. Deployment Frequency
2. Lead Time for Changes
3. Change Failure Rate
4. Mean Time to Recovery (MTTR)

Each metric is classified individually (Elite/High/Medium/Low) based on
official DORA benchmarks. The overall classification is determined by
the lowest performing metric (weakest link approach).

This score is displayed separately and does NOT affect the main project score.
The individual metrics already contribute to P_flow and P_quality dimensions.
"""

from app.config import ScoringConfig
from app.models.indicators import IndicatorsCreate


# Classification levels with numeric values for scoring
ELITE = "Elite"
HIGH = "High"
MEDIUM = "Medium"
LOW = "Low"

LEVEL_SCORES = {ELITE: 100, HIGH: 75, MEDIUM: 50, LOW: 25}
LEVEL_ORDER = [LOW, MEDIUM, HIGH, ELITE]


class DoraScoreCalculator:
    """Calculate DORA score using official DORA thresholds.

    Thresholds based on DORA State of DevOps reports (2019-2024):
    https://dora.dev/research/

    Deployment Frequency:
        Elite: On-demand (multiple deploys per day)
        High: Between once per day and once per week
        Medium: Between once per week and once per month
        Low: Less than once per month

    Lead Time for Changes:
        Elite: Less than one hour
        High: Between one hour and one day
        Medium: Between one day and one week
        Low: More than one week

    Change Failure Rate:
        Elite: 0-5%
        High: 5-10%
        Medium: 10-15%
        Low: More than 15%

    Time to Restore (MTTR):
        Elite: Less than one hour
        High: Less than one day
        Medium: Between one day and one week
        Low: More than one week
    """

    def __init__(self, config: ScoringConfig) -> None:
        self.config = config

    def calculate(self, indicators: IndicatorsCreate) -> dict:
        """Calculate DORA score and classification using official thresholds.

        Returns:
            dict with:
            - score: 0-100 based on average of metric level scores
            - classification: Overall level (weakest link)
            - metrics: Per-metric values and classifications
            - available_metrics: Count of metrics with data
        """
        metrics: dict[str, dict] = {}

        # Deployment Frequency (deploys per day)
        if indicators.deployment_frequency is not None:
            level = self._classify_deployment_frequency(indicators.deployment_frequency)
            metrics["deployment_frequency"] = {
                "value": indicators.deployment_frequency,
                "level": level,
                "score": LEVEL_SCORES[level],
            }

        # Lead Time (days)
        if indicators.lead_time_days is not None:
            level = self._classify_lead_time(indicators.lead_time_days)
            metrics["lead_time"] = {
                "value": indicators.lead_time_days,
                "level": level,
                "score": LEVEL_SCORES[level],
            }

        # Change Failure Rate (percentage)
        if indicators.change_failure_rate is not None:
            level = self._classify_change_failure_rate(indicators.change_failure_rate)
            metrics["change_failure_rate"] = {
                "value": indicators.change_failure_rate,
                "level": level,
                "score": LEVEL_SCORES[level],
            }

        # MTTR (hours) - treat 0 as "no incidents" = Elite
        if indicators.mttr_hours is not None:
            level = self._classify_mttr(indicators.mttr_hours)
            metrics["mttr"] = {
                "value": indicators.mttr_hours,
                "level": level,
                "score": LEVEL_SCORES[level],
                "no_incidents": indicators.mttr_hours == 0,
            }

        if not metrics:
            return {
                "score": None,
                "classification": None,
                "metrics": {},
                "available_metrics": 0,
            }

        # Calculate overall score as average of level scores
        level_scores = [m["score"] for m in metrics.values()]
        avg_score = round(sum(level_scores) / len(level_scores))

        # Overall classification is the weakest link (lowest level)
        levels = [m["level"] for m in metrics.values()]
        min_level_index = min(LEVEL_ORDER.index(level) for level in levels)
        overall_classification = LEVEL_ORDER[min_level_index]

        return {
            "score": avg_score,
            "classification": overall_classification,
            "metrics": metrics,
            "available_metrics": len(metrics),
        }

    def _classify_deployment_frequency(self, deploys_per_day: float) -> str:
        """Classify deployment frequency.

        Elite: Multiple per day (>1)
        High: Daily to weekly (1/7 to 1)
        Medium: Weekly to monthly (1/30 to 1/7)
        Low: Less than monthly (<1/30)
        """
        if deploys_per_day >= 1.0:
            return ELITE
        elif deploys_per_day >= 1 / 7:  # At least once per week
            return HIGH
        elif deploys_per_day >= 1 / 30:  # At least once per month
            return MEDIUM
        else:
            return LOW

    def _classify_lead_time(self, days: float) -> str:
        """Classify lead time for changes.

        Elite: Less than 1 hour (<1/24 day)
        High: Less than 1 day
        Medium: Less than 1 week
        Low: More than 1 week
        """
        hours = days * 24
        if hours < 1:
            return ELITE
        elif days < 1:
            return HIGH
        elif days < 7:
            return MEDIUM
        else:
            return LOW

    def _classify_change_failure_rate(self, rate_percent: float) -> str:
        """Classify change failure rate.

        Elite: 0-5%
        High: 5-10%
        Medium: 10-15%
        Low: >15%
        """
        if rate_percent <= 5:
            return ELITE
        elif rate_percent <= 10:
            return HIGH
        elif rate_percent <= 15:
            return MEDIUM
        else:
            return LOW

    def _classify_mttr(self, hours: float) -> str:
        """Classify mean time to recovery.

        Elite: Less than 1 hour (or no incidents)
        High: Less than 1 day (24 hours)
        Medium: Less than 1 week (168 hours)
        Low: More than 1 week
        """
        if hours == 0:  # No incidents = Elite
            return ELITE
        elif hours < 1:
            return ELITE
        elif hours < 24:
            return HIGH
        elif hours < 168:
            return MEDIUM
        else:
            return LOW
