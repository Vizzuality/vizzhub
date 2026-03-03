"""Score computation service - centralizes indicator normalization and score calculation."""

from app.config import ScoringConfig, get_scoring_config
from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.models.metrics import MetricsCreate
from app.modules.scorecard.models.scores import FinalScore
from app.modules.scorecard.services.calculators.final_score import FinalScoreCalculator
from app.modules.scorecard.services.normalizers.indicators import IndicatorNormalizer


class ScoreComputationService:
    """Centralizes the pattern of normalizing metrics and computing scores.

    This service encapsulates the common pattern used across multiple endpoints:
    1. Create normalizer and calculator with config
    2. Normalize metrics to indicators
    3. Extract total_prs from github_metrics
    4. Calculate scores with sev1_incident and total_prs
    """

    def __init__(self, config: ScoringConfig | None = None):
        self.config = config or get_scoring_config()
        self.normalizer = IndicatorNormalizer(self.config)
        self.calculator = FinalScoreCalculator(self.config)

    def compute(
        self,
        metrics: MetricsCreate,
        sev1_incident: bool = False,
    ) -> tuple[IndicatorsCreate, FinalScore]:
        """Compute indicators and scores from metrics.

        Args:
            metrics: The metrics to compute scores for
            sev1_incident: Whether a Sev1 incident occurred (caps P_quality)

        Returns:
            Tuple of (indicators, scores)
        """
        indicators = self.normalizer.normalize_all(metrics)

        total_prs = None
        if metrics.github_metrics:
            total_prs = metrics.github_metrics.total_merged_prs

        scores = self.calculator.calculate_all(
            indicators,
            sev1_incident=sev1_incident,
            total_prs=total_prs,
        )

        return indicators, scores

    def compute_indicators_only(self, metrics: MetricsCreate) -> IndicatorsCreate:
        """Compute only indicators from metrics (no scores).

        Args:
            metrics: The metrics to normalize

        Returns:
            Normalized indicators
        """
        return self.normalizer.normalize_all(metrics)
