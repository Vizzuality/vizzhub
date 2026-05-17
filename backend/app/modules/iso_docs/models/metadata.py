"""ISO documentation metadata — one-to-one with page nodes."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class IsoDocMetadataDB(Base):
    """ISO-specific metadata for a documentation page."""

    __tablename__ = "iso_doc_metadata"
    __table_args__ = (UniqueConstraint("node_id", name="uq_iso_doc_metadata_node"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    node_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("iso_doc_nodes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    standard: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    clauses: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    category: Mapped[str | None] = mapped_column(
        Enum(
            "manual",
            "policy",
            "procedure",
            "plan",
            "record",
            "report",
            name="iso_doc_category",
            create_type=False,
        ),
        nullable=True,
    )
    doc_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str | None] = mapped_column(
        Enum("draft", "approved", "under_review", name="iso_doc_status", create_type=False),
        nullable=True,
    )
    classification: Mapped[str] = mapped_column(
        Enum(
            "internal_use",
            "confidential",
            name="iso_doc_classification",
            create_type=False,
        ),
        nullable=False,
        server_default="internal_use",
    )
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    changelog: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
