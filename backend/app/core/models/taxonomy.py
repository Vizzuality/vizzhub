"""Controlled-vocabulary taxonomies, terms and entity associations (core)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Cardinality(StrEnum):
    SINGLE = "single"
    MULTI = "multi"


class TaxonomyDB(Base):
    __tablename__ = "taxonomies"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cardinality: Mapped[Cardinality] = mapped_column(
        SAEnum(
            Cardinality,
            name="taxonomy_cardinality",
            create_type=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=Cardinality.MULTI,
    )
    allows_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TaxonomyTermDB(Base):
    __tablename__ = "taxonomy_terms"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    taxonomy_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("taxonomies.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("taxonomy_id", "slug", name="uq_taxonomy_terms_tax_slug"),)


class EntityTermDB(Base):
    __tablename__ = "entity_terms"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    term_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("taxonomy_terms.id", ondelete="CASCADE"), nullable=False
    )
    taxonomy_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("taxonomies.id", ondelete="CASCADE"), nullable=False
    )
    program_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"), nullable=True
    )
    project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    assigned_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Partial unique indexes for "one primary per (entity, taxonomy)" live in the
    # migration (raw SQL) — postgresql_where on model columns is fragile under create_all.
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(program_id, project_id) = 1", name="ck_entity_terms_one_entity"
        ),
    )


class TaxonomyTerm(BaseModel):
    id: UUID
    taxonomy_id: UUID
    slug: str
    name: str
    description: str | None = None
    sort_order: int
    is_active: bool
    model_config = {"from_attributes": True}


class Taxonomy(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str | None = None
    cardinality: Cardinality
    allows_primary: bool
    is_active: bool
    sort_order: int
    terms: list[TaxonomyTerm] = Field(default_factory=list)
    model_config = {"from_attributes": True}
