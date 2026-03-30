"""ISO documentation tree node — page or group."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class IsoDocNodeDB(Base):
    """Tree node: either a page (has content) or a group (container only)."""

    __tablename__ = "iso_doc_nodes"
    __table_args__ = (
        UniqueConstraint("parent_id", "slug", name="uq_iso_doc_nodes_parent_slug"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(
        Enum("page", "group", name="iso_doc_node_type"), nullable=False
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("iso_doc_nodes.id", ondelete="CASCADE"),
        nullable=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    children: Mapped[list[IsoDocNodeDB]] = relationship(
        "IsoDocNodeDB",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="IsoDocNodeDB.position",
        lazy="selectin",
    )
    parent: Mapped[IsoDocNodeDB | None] = relationship(
        "IsoDocNodeDB",
        back_populates="children",
        remote_side=[id],
        lazy="selectin",
    )
