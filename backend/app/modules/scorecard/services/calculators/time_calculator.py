"""Time dimension calculator (P_time)."""

from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.services.calculators.base import BaseCalculator, WeightedComponent


class TimeCalculator(BaseCalculator):
    """
    P_time: Schedule adherence score.

    Components:
    - SPI normalized to ideal (1.0 = on schedule, capped at 1) - weight 0.6
    - On-time milestones ratio normalized to target (85%) - weight 0.4

    Missing data handling:
    - If SPI missing: score based on milestones only
    - If milestones missing: score based on SPI only
    - If both missing: returns None
    """

    dimension_name = "time"
    weight_group = "time"

    def calculate(self, indicators: IndicatorsCreate) -> int | None:
        spi_ideal = self._get_ideal("spi")
        milestones_target = self._get_target("milestones_on_time") / 100

        components = [
            WeightedComponent(
                name="spi",
                weight=self._get_weight("spi"),
                value=self._normalize_to_ideal(indicators.spi, spi_ideal),
            ),
            WeightedComponent(
                name="milestones",
                weight=self._get_weight("milestones"),
                value=self._normalize_to_target(
                    indicators.on_time_milestones, milestones_target
                ),
            ),
        ]

        return self._to_score(self._weighted_average(components))
