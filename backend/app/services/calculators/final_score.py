"""
Final score calculator.

Weighted aggregate of all dimension scores.
"""

from app.config import ScoringConfig, get_scoring_config
from app.models.indicators import IndicatorsCreate
from app.models.scores import DimensionScores, FinalScore
from app.services.calculators.dimensions import (
    CostCalculator,
    EngineeringCalculator,
    FlowCalculator,
    QualityCalculator,
    RiskCalculator,
    SatisfactionCalculator,
    TimeCalculator,
    ValueCalculator,
)


class FinalScoreCalculator:
    """
    Calculates final weighted score from all dimensions.

    Formula:
    Final = W_time * P_time + W_cost * P_cost + W_quality * P_quality +
            W_value * P_value + W_satisfaction * P_satisfaction +
            W_flow * P_flow + W_engineering * P_engineering + W_risk * P_risk

    All global weights must sum to 1.
    """

    def __init__(self, config: ScoringConfig | None = None):
        self.config = config or get_scoring_config()

        self.time_calc = TimeCalculator(self.config)
        self.cost_calc = CostCalculator(self.config)
        self.quality_calc = QualityCalculator(self.config)
        self.value_calc = ValueCalculator(self.config)
        self.satisfaction_calc = SatisfactionCalculator(self.config)
        self.flow_calc = FlowCalculator(self.config)
        self.engineering_calc = EngineeringCalculator(self.config)
        self.risk_calc = RiskCalculator(self.config)

    def calculate_all(
        self,
        indicators: IndicatorsCreate,
        sev1_incident: bool = False,
        total_prs: int | None = None,
    ) -> FinalScore:
        """
        Calculate all dimension scores and final weighted score.

        Args:
            indicators: Normalized indicator values
            sev1_incident: Whether a Sev1 incident occurred (caps P_quality)
            total_prs: Total merged PRs for P_risk calculation

        Returns:
            FinalScore with all dimensions and weighted total
        """
        dimensions = DimensionScores(
            p_time=self.time_calc.calculate(indicators),
            p_cost=self.cost_calc.calculate(indicators),
            p_quality=self.quality_calc.calculate(indicators, sev1_incident),
            p_value=self.value_calc.calculate(indicators),
            p_satisfaction=self.satisfaction_calc.calculate(indicators),
            p_flow=self.flow_calc.calculate(indicators),
            p_engineering=self.engineering_calc.calculate(indicators),
            p_risk=self.risk_calc.calculate(indicators, total_prs),
        )

        weights = {
            "time": self.config.get_global_weight("time"),
            "cost": self.config.get_global_weight("cost"),
            "quality": self.config.get_global_weight("quality"),
            "value": self.config.get_global_weight("value"),
            "satisfaction": self.config.get_global_weight("satisfaction"),
            "flow": self.config.get_global_weight("flow"),
            "engineering": self.config.get_global_weight("engineering"),
            "risk": self.config.get_global_weight("risk"),
        }

        final = (
            weights["time"] * dimensions.p_time
            + weights["cost"] * dimensions.p_cost
            + weights["quality"] * dimensions.p_quality
            + weights["value"] * dimensions.p_value
            + weights["satisfaction"] * dimensions.p_satisfaction
            + weights["flow"] * dimensions.p_flow
            + weights["engineering"] * dimensions.p_engineering
            + weights["risk"] * dimensions.p_risk
        )

        return FinalScore(
            score=round(min(100, max(0, final))),
            dimensions=dimensions,
            weights_applied=weights,
        )

    def calculate_single_dimension(
        self,
        dimension: str,
        indicators: IndicatorsCreate,
        **kwargs: bool | int | None,
    ) -> int:
        """Calculate a single dimension score."""
        calculators = {
            "time": lambda: self.time_calc.calculate(indicators),
            "cost": lambda: self.cost_calc.calculate(indicators),
            "quality": lambda: self.quality_calc.calculate(
                indicators, kwargs.get("sev1_incident", False)
            ),
            "value": lambda: self.value_calc.calculate(indicators),
            "satisfaction": lambda: self.satisfaction_calc.calculate(indicators),
            "flow": lambda: self.flow_calc.calculate(indicators),
            "engineering": lambda: self.engineering_calc.calculate(indicators),
            "risk": lambda: self.risk_calc.calculate(
                indicators, kwargs.get("total_prs")
            ),
        }

        calc = calculators.get(dimension)
        if calc is None:
            raise ValueError(f"Unknown dimension: {dimension}")
        return calc()
