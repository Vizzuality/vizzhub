"""Pydantic schemas for ISO registries."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FormulaSpec(BaseModel):
    operation: Literal["multiply", "sum"]
    fields: list[str]


class ConditionalFormatRange(BaseModel):
    min: float
    max: float
    color: str
    label: str | None = None


class ColumnDef(BaseModel):
    key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=255)
    type: Literal["string", "number", "date", "boolean", "select", "user", "computed", "attachment", "url"]
    required: bool = False
    options: list[str] | None = None
    option_colors: dict[str, str] | None = None
    width: int | None = None
    formula: FormulaSpec | None = None
    conditional_format: list[ConditionalFormatRange] | None = None


class RegistryTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_yearly: bool = False
    schema_: list[ColumnDef] = Field(alias="schema", min_length=1)


class RegistryTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_yearly: bool | None = None
    schema_: list[ColumnDef] | None = Field(None, alias="schema")


class RegistryTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    name: str
    slug: str
    description: str | None
    is_yearly: bool
    default_sort_key: str | None = None
    schema_: list[ColumnDef] = Field(alias="schema")
    created_at: datetime
    updated_at: datetime


class RegistryRowCreate(BaseModel):
    year: int | None = None
    data: dict[str, Any]


class RegistryRowUpdate(BaseModel):
    data: dict[str, Any]


class RegistryRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    node_id: UUID
    year: int | None
    row_index: int
    data: dict[str, Any]
    created_by_id: UUID | None
    updated_by_id: UUID | None
    created_at: datetime
    updated_at: datetime
    attachments: list[AttachmentResponse] = []

    @field_validator("attachments", mode="before")
    @classmethod
    def default_attachments(cls, v):  # noqa: N805
        return v or []


class RegistryRowReorder(BaseModel):
    row_ids: list[UUID]


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    row_id: UUID
    node_id: UUID | None
    field_key: str | None
    filename: str
    s3_key: str
    url: str | None = None
    content_type: str
    size_bytes: int
    uploaded_by_id: UUID | None
    created_at: datetime


RegistryRowResponse.model_rebuild()
