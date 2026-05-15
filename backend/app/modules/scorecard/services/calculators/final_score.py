"""
Final score calculator.

Weighted aggregate of all dimension scores.
"""

from typing import Callable

from app.config import ScoringConfig, get_scoring_config
from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.models.scores import DimensionScores, DoraScore, FinalScore
from app.modules.scorecard.services.calculators.dimensions import (
    CostCalculator,
    EngineeringCalculator,
    FlowCalculator,
    QualityCalculator,
    RiskCalculator,
    SatisfactionCalculator,
    TimeCalculator,
    ValueCalculator,
)
from app.modules.scorecard.services.calculators.dora import DoraScoreCalculator


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
        self.dora_calc = DoraScoreCalculator(self.config)

    def calculate_all(
        self,
        indicators: IndicatorsCreate,
        sev1_incident: bool = False,
        total_prs: int | None = None,
    ) -> FinalScore:
        """
        Calculate all dimension scores and final weighted score.

        Dimensions with no data (None) are excluded and their weights
        are redistributed among available dimensions.

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

        dimension_names = [
            "time", "cost", "quality", "value",
            "satisfaction", "flow", "engineering", "risk",
        ]
        dimension_scores = [
            dimensions.p_time, dimensions.p_cost, dimensions.p_quality, dimensions.p_value,
            dimensions.p_satisfaction, dimensions.p_flow, dimensions.p_engineering, dimensions.p_risk,
        ]

        config_weights = {name: self.config.get_global_weight(name) for name in dimension_names}

        available: list[tuple[str, int, float]] = [
            (name, score, config_weights[name])
            for name, score in zip(dimension_names, dimension_scores)
            if score is not None
        ]
        available_names = {name for name, _, _ in available}

        dora_result = self.dora_calc.calculate(indicators)
        dora_score = DoraScore(
            score=dora_result["score"],
            classification=dora_result["classification"],
            metrics=dora_result["metrics"],
            available_metrics=dora_result["available_metrics"],
        )

        if not available:
            return FinalScore(
                score=None,
                dimensions=dimensions,
                weights_applied=dict.fromkeys(dimension_names, 0.0),
                dora=dora_score,
            )

        total_weight = sum(w for _, _, w in available)
        weights = {
            name: (
                config_weights[name] / total_weight
                if total_weight > 0 and name in available_names
                else 0.0
            )
            for name in dimension_names
        }
        final = sum(weights[name] * score for name, score, _ in available)

        return FinalScore(
            score=round(min(100, max(0, final))),
            dimensions=dimensions,
            weights_applied=weights,
            dora=dora_score,
        )

    def calculate_single_dimension(
        self,
        dimension: str,
        indicators: IndicatorsCreate,
        sev1_incident: bool = False,
        total_prs: int | None = None,
    ) -> int | None:
        """Calculate a single dimension score."""
        calculators: dict[str, Callable[[], int | None]] = {
            "time": lambda: self.time_calc.calculate(indicators),
            "cost": lambda: self.cost_calc.calculate(indicators),
            "quality": lambda: self.quality_calc.calculate(indicators, sev1_incident),
            "value": lambda: self.value_calc.calculate(indicators),
            "satisfaction": lambda: self.satisfaction_calc.calculate(indicators),
            "flow": lambda: self.flow_calc.calculate(indicators),
            "engineering": lambda: self.engineering_calc.calculate(indicators),
            "risk": lambda: self.risk_calc.calculate(indicators, total_prs),
        }

        calc = calculators.get(dimension)
        if calc is None:
            raise ValueError(f"Unknown dimension: {dimension}")
        return calc()
