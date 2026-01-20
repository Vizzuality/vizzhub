from decimal import Decimal, InvalidOperation
from pydantic import BaseModel, ConfigDict, field_validator, ValidationInfo
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


class ConfigParameterResponse(BaseModel):
    id: int
    category: str
    name: str
    value: Decimal
    unit: str | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class ConfigParameterUpdate(BaseModel):
    name: str
    value: Decimal
    notes: str | None = None

    @field_validator('value', mode='before')
    @classmethod
    def validate_value(cls, v: any, info: ValidationInfo) -> Decimal:
        """Validate and convert value to Decimal with user-friendly error messages."""
        # Get parameter name from the data being validated
        name = info.data.get('name', 'unknown') if info.data else 'unknown'

        # Handle string values
        if isinstance(v, str):
            # Remove whitespace
            v = v.strip()

            # Check if empty
            if not v:
                raise ValueError(
                    f"Parameter '{name}': Value cannot be empty. "
                    f"Please enter a numeric value (e.g., 0.5, 100, 3.14)."
                )

            # Try to convert to Decimal
            try:
                return Decimal(v)
            except InvalidOperation:
                raise ValueError(
                    f"Parameter '{name}': Expected a numeric value, got '{v}' instead. "
                    f"Please enter a valid number (e.g., 0.5, 100, 3.14)."
                )

        # Handle numeric types
        if isinstance(v, (int, float)):
            return Decimal(str(v))

        # Handle Decimal (already correct type)
        if isinstance(v, Decimal):
            return v

        # Invalid type
        raise ValueError(
            f"Parameter '{name}': Expected a numeric value, got {type(v).__name__} instead. "
            f"Please enter a valid number."
        )
