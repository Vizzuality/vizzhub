"""Pydantic schemas for playbook tree nodes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    type: str = Field(pattern=r"^(page|group)$")
    parent_id: UUID | None = None


class NodeUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    is_public: bool | None = None
    parent_id: UUID | None = None


class ReorderItem(BaseModel):
    id: UUID
    parent_id: UUID | None = None
    position: int = Field(ge=0)


class ReorderRequest(BaseModel):
    items: list[ReorderItem] = Field(min_length=1)


class NodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str
    type: str
    parent_id: UUID | None
    position: int
    is_public: bool
    created_by_id: UUID | None
    updated_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


class TreeNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str
    type: str
    parent_id: UUID | None
    position: int
    is_public: bool
    children: list[TreeNodeResponse] = []


TreeNodeResponse.model_rebuild()
