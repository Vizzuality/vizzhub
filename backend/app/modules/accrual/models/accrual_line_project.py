"""AccrualLineProjectDB — M:N link between accrual lines and tracker projects.

A line links to 0..N projects; a project carries 0..N lines. No per-project €
split: the line is the reporting unit (per-project burn/cost lives in tracker).
A ``share`` column is intentionally omitted — add it only if a per-project
rollup is ever needed (deferred, probably never; see docs/accrual_lines_design.md).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AccrualLineProjectDB(Base):
    """Join row linking one accrual line to one tracker project."""

    __tablename__ = "accrual_line_projects"
    __table_args__ = (Index("ix_accrual_line_projects_project", "project_id"),)

    line_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accrual_lines.id", ondelete="CASCADE"),
        primary_key=True,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
