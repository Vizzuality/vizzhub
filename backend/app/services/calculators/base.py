"""
Base calculator interface for dimension scores.

Design Principles:
1. Calculators accept normalized indicators (0-1 scale)
2. Apply weights from configuration
3. Return 0-100 scores
4. Exclude missing data and redistribute weights (not neutral 0.5)
5. Weights must sum to 1 within each group
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config import ScoringConfig, get_scoring_config
from app.models.indicators import IndicatorsCreate


@dataclass
class WeightedComponent:
    """A component with its weight and normalized value."""

    name: str
    weight: float
    value: float | None


class BaseCalculator(ABC):
    """Abstract base class for dimension calculators."""

    dimension_name: str = ""
    weight_group: str = ""

    def __init__(self, config: ScoringConfig | None = None):
        self.config = config or get_scoring_config()

    @abstractmethod
    def calculate(self, indicators: IndicatorsCreate) -> int | None:
        """
        Calculate dimension score from normalized indicators.

        Args:
            indicators: Normalized indicator values (0-1 scale)

        Returns:
            Dimension score (0-100) or None if no data available
        """
        pass

    def _get_weight(self, name: str) -> float:
        """Get weight from configuration."""
        return self.config.get_weight(self.weight_group, name)

    def _get_target(self, name: str) -> float:
        """Get target from configuration."""
        return self.config.get_target(name)

    def _get_ideal(self, name: str) -> float:
        """Get ideal value from configuration."""
        return self.config.get_ideal(name)

    def _normalize_to_target(
        self,
        value: float | None,
        target: float,
        lower_is_better: bool = False,
    ) -> float | None:
        """
        Normalize a value to its target, returning 0-1 or None if missing.

        Args:
            value: Raw value
            target: Target value
            lower_is_better: If True, use inverted normalization

        Returns:
            Normalized value 0-1 or None if value is missing
        """
        if value is None:
            return None
        if lower_is_better:
            if value <= 0:
                return 1.0
            return min(1.0, target / max(value, 0.001))
        else:
            if target <= 0:
                return 1.0 if value > 0 else None
            return min(1.0, value / target)

    def _normalize_to_ideal(
        self,
        value: float | None,
        ideal: float,
    ) -> float | None:
        """
        Normalize a ratio metric to its ideal value for accurate scoring.

        Used for metrics like SPI and CPI where:
        - Ideal = 1.0 (exactly on schedule/budget)
        - Target = 0.8 (minimum acceptable, for color coding)
        - Score = value / ideal (SPI=0.85 → 85 points, not 100)

        Args:
            value: Raw ratio value (e.g., SPI, CPI)
            ideal: The ideal value representing 100% score (typically 1.0)

        Returns:
            Normalized value 0-1 or None if value is missing
        """
        if value is None:
            return None
        if ideal <= 0:
            return 1.0 if value > 0 else None
        return min(1.0, max(0.0, value / ideal))

    def _weighted_average(self, components: list[WeightedComponent]) -> float | None:
        """
        Calculate weighted average, excluding missing components.

        Missing components (value=None) are excluded and their weights
        are redistributed among available components.

        Args:
            components: List of weighted components

        Returns:
            Weighted average (0-1) or None if all components are missing
        """
        available = [(c.weight, c.value) for c in components if c.value is not None]

        if not available:
            return None

        total_weight = sum(w for w, _ in available)
        if total_weight <= 0:
            return None

        weighted_sum = sum(w * v for w, v in available)
        return weighted_sum / total_weight

    def _to_score(self, normalized: float | None) -> int | None:
        """Convert normalized value (0-1) to score (0-100)."""
        if normalized is None:
            return None
        return round(min(100, max(0, normalized * 100)))
