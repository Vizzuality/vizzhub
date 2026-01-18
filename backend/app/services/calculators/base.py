"""
Base calculator interface for dimension scores.

Design Principles:
1. Calculators accept normalized indicators (0-1 scale)
2. Apply weights from configuration
3. Return 0-100 scores
4. Handle missing data with neutral (0.5)
5. Weights must sum to 1 within each group
"""

from abc import ABC, abstractmethod

from app.config import ScoringConfig, get_scoring_config
from app.models.indicators import IndicatorsCreate
from app.services.normalizers.base import NEUTRAL_VALUE


class BaseCalculator(ABC):
    """Abstract base class for dimension calculators."""

    dimension_name: str = ""
    weight_group: str = ""

    def __init__(self, config: ScoringConfig | None = None):
        self.config = config or get_scoring_config()

    @abstractmethod
    def calculate(self, indicators: IndicatorsCreate) -> int:
        """
        Calculate dimension score from normalized indicators.

        Args:
            indicators: Normalized indicator values (0-1 scale)

        Returns:
            Dimension score (0-100)
        """
        pass

    def _get_weight(self, name: str) -> float:
        """Get weight from configuration."""
        return self.config.get_weight(self.weight_group, name)

    def _get_target(self, name: str) -> float:
        """Get target from configuration."""
        return self.config.get_target(name)

    def _safe_value(self, value: float | None) -> float:
        """Return value or neutral if None."""
        return value if value is not None else NEUTRAL_VALUE

    def _normalize_to_target(
        self,
        value: float | None,
        target: float,
        lower_is_better: bool = False,
    ) -> float:
        """
        Normalize a value to its target, returning 0-1.

        Args:
            value: Raw value
            target: Target value
            lower_is_better: If True, use inverted normalization

        Returns:
            Normalized value 0-1
        """
        if value is None:
            return NEUTRAL_VALUE
        if lower_is_better:
            if value <= 0:
                return 1.0
            return min(1.0, target / max(value, 0.001))
        else:
            if target <= 0:
                return 1.0 if value > 0 else NEUTRAL_VALUE
            return min(1.0, value / target)

    def _to_score(self, normalized: float) -> int:
        """Convert normalized value (0-1) to score (0-100)."""
        return round(min(100, max(0, normalized * 100)))
