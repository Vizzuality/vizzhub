"""DevstackEntry database model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DevstackEntryDB(Base):
    """A Claude Code artifact (skill, command, plugin, config, or agent) in the devstack catalog."""

    __tablename__ = "devstack_entries"
    __table_args__ = (
        UniqueConstraint("name", name="uq_devstack_entries_name"),
        CheckConstraint(
            "type IN ('skill', 'command', 'plugin', 'config', 'agent')",
            name="ck_devstack_entries_type",
        ),
        CheckConstraint(
            "install_method IN ('github', 'npm')",
            name="ck_devstack_entries_install_method",
        ),
        CheckConstraint(
            "origin IN ('internal', 'external')",
            name="ck_devstack_entries_origin",
        ),
        CheckConstraint(
            "install_method != 'github' OR url IS NOT NULL",
            name="ck_devstack_entries_github_url",
        ),
        CheckConstraint(
            "install_method != 'npm' OR package IS NOT NULL",
            name="ck_devstack_entries_npm_package",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(20))
    install_method: Mapped[str] = mapped_column(String(20))
    url: Mapped[str | None] = mapped_column(Text)
    package: Mapped[str | None] = mapped_column(String(200))
    package_version: Mapped[str | None] = mapped_column(String(50))
    required: Mapped[bool] = mapped_column(Boolean, server_default="false")
    origin: Mapped[str] = mapped_column(String(20), server_default="internal")
    tech: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    github_sha: Mapped[str | None] = mapped_column(String(40))
    created_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    updated_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
