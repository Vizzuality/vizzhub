"""Shared Pydantic schemas for wiki-style page content and versions.

Used by both Playbook and ISO Docs modules.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PageContentBase(BaseModel):
    """Base page content — modules extend with their own fields."""

    model_config = ConfigDict(from_attributes=True)

    node_id: UUID
    title: str
    content: str
    version: int
    created_by_id: UUID | None
    created_at: datetime


class PageSave(BaseModel):
    content: str
    expected_version: int = Field(ge=0)


class PageSaveResponse(BaseModel):
    node_id: UUID
    version: int
    conflict: bool = False


class VersionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    created_by_id: UUID | None
    created_by_name: str | None = None
    created_at: datetime
    lines_added: int = 0
    lines_removed: int = 0


class VersionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    node_id: UUID
    content: str
    version: int
    created_by_id: UUID | None
    created_at: datetime
