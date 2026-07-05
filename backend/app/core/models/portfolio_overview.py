"""Portfolio Overview import: staging rows + per-project profile (core)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ProgramAction(StrEnum):
    INHERIT = "inherit"
    LINK = "link"
    CREATE = "create"
    NONE = "none"


class PortfolioOverviewStagingDB(Base):
    __tablename__ = "portfolio_overview_staging"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    import_batch: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    main_partner: Mapped[str | None] = mapped_column(Text, nullable=True)
    on_website: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    client_type_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_area_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_update: Mapped[str | None] = mapped_column(String(64), nullable=True)
    web_copy: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_story: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_old_project: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    matched_program_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("programs.id", ondelete="SET NULL"), nullable=True
    )
    matched_project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    program_action: Mapped[ProgramAction | None] = mapped_column(
        SAEnum(
            ProgramAction,
            name="portfolio_program_action",
            create_type=False,
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=True,
    )
    decided_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    new_program_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
    impact_story: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    main_partner: Mapped[str | None] = mapped_column(Text, nullable=True)
    on_website: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_batch: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
