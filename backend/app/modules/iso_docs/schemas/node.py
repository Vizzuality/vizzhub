"""Pydantic schemas for ISO doc tree nodes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    type: str = Field(pattern=r"^(page|group|registry|widget)$")
    parent_id: UUID | None = None
    registry_type_id: UUID | None = None
    widget_key: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def validate_widget_key(self) -> NodeCreate:
        if self.type == "widget" and not self.widget_key:
            raise ValueError("widget_key is required for widget nodes")
        if self.type != "widget" and self.widget_key:
            raise ValueError("widget_key is only allowed for widget nodes")
        return self


class NodeUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
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
    registry_type_id: UUID | None = None
    widget_key: str | None = None
    created_by_id: UUID | None
    updated_by_id: UUID | None
    created_at: datetime
    updated_at: datetime
