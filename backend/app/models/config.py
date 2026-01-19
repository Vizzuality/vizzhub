from decimal import Decimal
from pydantic import BaseModel
from sqlalchemy import String, Text, Index
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ConfigParameter(Base):
    """Configuration parameter with metadata."""

    __tablename__ = "config_parameters"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[Decimal] = mapped_column(NUMERIC(10, 4))
    unit: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("idx_config_category", "category"),)


class TargetsConfig(BaseModel):
    """Target values for normalization."""

    defect_density: float
    escaped_rate: float
    mttr_hours: float
    spi: float
    cpi: float
    lead_time_days: float
    flow_efficiency: float
    high_vuln_count: int
    gov_exceptions: int
    pr_no_review_ratio: float


class GlobalWeights(BaseModel):
    """Global dimension weights."""

    time: float
    cost: float
    quality: float
    value: float
    satisfaction: float
    flow: float
    engineering: float
    risk: float


class ConstantsConfig(BaseModel):
    """System constants."""

    sev1_cap: int
    grace_days: int


class ScoringConfigModel(BaseModel):
    """Complete scoring configuration."""

    targets: TargetsConfig
    global_weights: GlobalWeights
    constants: ConstantsConfig
    weight_validation: dict[str, bool]
