from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DimensionScores(BaseModel):
    """Individual dimension scores (0-100)."""

    p_time: int = Field(..., ge=0, le=100, description="Schedule adherence score")
    p_cost: int = Field(..., ge=0, le=100, description="Budget adherence score")
    p_quality: int = Field(..., ge=0, le=100, description="Product quality score")
    p_value: int = Field(..., ge=0, le=100, description="Strategic value score")
    p_satisfaction: int = Field(..., ge=0, le=100, description="Client satisfaction score")
    p_flow: int = Field(..., ge=0, le=100, description="Flow & predictability score")
    p_engineering: int = Field(..., ge=0, le=100, description="Engineering maturity score")
    p_risk: int = Field(..., ge=0, le=100, description="Risk posture score")


class DoraScore(BaseModel):
    """DORA metrics score (separate from main score)."""

    score: int | None = Field(None, ge=0, le=100, description="DORA score 0-100")
    classification: str | None = Field(None, description="Elite/High/Medium/Low")
    metrics: dict[str, float | None] = Field(
        default_factory=dict,
        description="Individual DORA metric scores (0-1)",
    )
    available_metrics: int = Field(0, description="Number of DORA metrics with data")


class FinalScore(BaseModel):
    """Final weighted aggregate score."""

    score: int = Field(..., ge=0, le=100)
    dimensions: DimensionScores
    weights_applied: dict[str, float]
    dora: DoraScore | None = Field(None, description="Separate DORA score")


class ScoreResult(BaseModel):
    """Complete scoring result."""

    id: UUID
    project_id: UUID
    indicators_id: UUID
    dimensions: DimensionScores
    final_score: int = Field(..., ge=0, le=100)
    created_at: datetime

    model_config = {"from_attributes": True}
