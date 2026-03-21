"""ECB exchange rate storage — one row per (date, currency)."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Date, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ExchangeRateDB(Base):
    """Daily ECB exchange rate for a single currency (EUR-based)."""

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("rate_date", "currency_code", name="uq_exchange_rates_date_currency"),
        Index("ix_exchange_rates_currency_date", "currency_code", "rate_date"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExchangeRate(BaseModel):
    """Pydantic schema for exchange rate responses."""

    id: UUID
    rate_date: date
    currency_code: str
    rate: float
    fetched_at: datetime

    model_config = {"from_attributes": True}
