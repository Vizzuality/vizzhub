from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScoresDB(Base):
    """SQLAlchemy model for dimension scores."""

    __tablename__ = "scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    indicators_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("indicators.id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )

    p_time: Mapped[int] = mapped_column(nullable=False)
    p_cost: Mapped[int] = mapped_column(nullable=False)
    p_quality: Mapped[int] = mapped_column(nullable=False)
    p_value: Mapped[int] = mapped_column(nullable=False)
    p_satisfaction: Mapped[int] = mapped_column(nullable=False)
    p_flow: Mapped[int] = mapped_column(nullable=False)
    p_engineering: Mapped[int] = mapped_column(nullable=False)
    p_risk: Mapped[int] = mapped_column(nullable=False)
    final_score: Mapped[int] = mapped_column(nullable=False)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


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

    class Config:
        from_attributes = True
