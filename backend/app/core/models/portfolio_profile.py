"""Portfolio per-entity profile: dual-anchor (project XOR program) narrative fields (core)."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class PortfolioProfileDB(Base):
    __tablename__ = "portfolio_profile"

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(project_id, program_id) = 1", name="ck_portfolio_profile_one_anchor"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    program_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=True,
    )
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    web_copy: Mapped[str | None] = mapped_column(Text, nullable=True)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_story: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    main_partner: Mapped[str | None] = mapped_column(Text, nullable=True)
    on_website: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_batch: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    # DB-generated full-text vector over the narrative fields (migration 099).
    search_vector = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(objective,'') || ' ' || "
            "coalesce(short_description,'') || ' ' || coalesce(impact_story,'') || ' ' || "
            "coalesce(web_copy,'') || ' ' || coalesce(main_partner,''))",
            persisted=True,
        ),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
