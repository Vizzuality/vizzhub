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


class FinalScore(BaseModel):
    """Final weighted aggregate score."""

    score: int = Field(..., ge=0, le=100)
    dimensions: DimensionScores
    weights_applied: dict[str, float]


class ScoreResult(BaseModel):
    """Complete scoring result."""

    id: UUID
    project_id: UUID
    indicators_id: UUID
    dimensions: DimensionScores
    final_score: int = Field(..., ge=0, le=100)
    created_at: datetime

    model_config = {"from_attributes": True}
