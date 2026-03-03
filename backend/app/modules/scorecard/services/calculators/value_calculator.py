"""Value dimension calculator (P_value)."""

from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.services.calculators.base import BaseCalculator


class ValueCalculator(BaseCalculator):
    """
    P_value: Strategic/business value score.

    Components:
    - OKR Impact score (categorical -> numeric)
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
