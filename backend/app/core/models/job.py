"""Job model for async task tracking."""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class JobType(str, Enum):
    """Types of async jobs."""

    CAPTURE_HISTORY = "capture_history"


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """Async job tracking model."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type: Mapped[JobType] = mapped_column(String(50), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        String(20), default=JobStatus.PENDING, nullable=False
    )

    # Identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None, nullable=True)

    # Context
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        default=None,
        nullable=True,
    )
    created_by: Mapped[str | None] = mapped_column(
        String(255), default=None, nullable=True
    )

    # Input/Output
    params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, default=None, nullable=True)

    # Progress
    progress: Mapped[int] = mapped_column(default=0, nullable=False)
    progress_message: Mapped[str | None] = mapped_column(
        String(500), default=None, nullable=True
    )

    # Logs and errors
    logs: Mapped[str | None] = mapped_column(Text, default=None, nullable=True)
    error_message: Mapped[str | None] = mapped_column(
        String(1000), default=None, nullable=True
    )
    error_traceback: Mapped[str | None] = mapped_column(
        Text, default=None, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )

    # ARQ reference
    arq_job_id: Mapped[str | None] = mapped_column(
        String(100), default=None, nullable=True
    )

    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_project_id", "project_id"),
        Index("ix_jobs_created_at", "created_at"),
    )
