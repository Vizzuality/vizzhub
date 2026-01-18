from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class OAuthTokenDB(Base):
    """SQLAlchemy model for OAuth tokens."""

    __tablename__ = "oauth_tokens"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'jira' or 'github'
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_type: Mapped[str] = mapped_column(String(50), default="Bearer")
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Jira-specific fields
    cloud_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    site_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now()
    )


class OAuthToken(BaseModel):
    """Schema for OAuth token responses."""

    id: UUID
    provider: str
    token_type: str
    expires_at: datetime | None
    scope: str | None
    cloud_id: str | None
    site_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
