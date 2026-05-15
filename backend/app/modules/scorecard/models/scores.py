from typing import Literal

from pydantic import BaseModel, Field


class DimensionScores(BaseModel):
    """Individual dimension scores (0-100 or None if no data)."""

    p_time: int | None = Field(None, ge=0, le=100, description="Schedule adherence score")
    p_cost: int | None = Field(None, ge=0, le=100, description="Budget adherence score")
    p_quality: int | None = Field(None, ge=0, le=100, description="Product quality score")
    p_value: int | None = Field(None, ge=0, le=100, description="Strategic value score")
    p_satisfaction: int | None = Field(None, ge=0, le=100, description="Client satisfaction score")
    p_flow: int | None = Field(None, ge=0, le=100, description="Flow & predictability score")
    p_engineering: int | None = Field(None, ge=0, le=100, description="Engineering maturity score")
    p_risk: int | None = Field(None, ge=0, le=100, description="Risk posture score")


DoraLevel = Literal["Elite", "High", "Medium", "Low"]


class DoraMetricDetail(BaseModel):
    """Detail for a single DORA metric."""

    value: float = Field(..., description="Raw metric value")
    level: DoraLevel = Field(..., description="DORA classification level")
    score: int = Field(..., ge=0, le=100, description="Score based on level")
    no_incidents: bool | None = Field(None, description="True if MTTR has no incidents")


class DoraScore(BaseModel):
    """DORA metrics score using official DORA thresholds."""

    score: int | None = Field(None, ge=0, le=100, description="DORA score 0-100")
    classification: DoraLevel | None = Field(None, description="Overall classification (weakest link)")
    metrics: dict[str, DoraMetricDetail] = Field(
        default_factory=dict,
        description="Individual DORA metric details with level classification",
    )
    available_metrics: int = Field(0, description="Number of DORA metrics with data")


class FinalScore(BaseModel):
    """Final weighted aggregate score.

    `score` is None when no dimension has data — distinguishes "brand-new
    project, no measurements yet" from "every dimension genuinely scored 0".
    """

    score: int | None = Field(None, ge=0, le=100)
    dimensions: DimensionScores
    weights_applied: dict[str, float]
    dora: DoraScore | None = Field(None, description="Separate DORA score")
