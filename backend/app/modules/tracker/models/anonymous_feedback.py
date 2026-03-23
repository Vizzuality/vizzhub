"""Anonymous feedback — no FK, no timestamps, untraceable."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnonymousFeedbackDB(Base):
    __tablename__ = "anonymous_feedback"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(String(2000), nullable=False)
