"""Pydantic schemas for ISO doc notes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    node_id: UUID
    content: str
    done: bool
    done_at: datetime | None
    done_by_id: UUID | None
    done_by_name: str | None = None
    created_by_id: UUID | None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminNoteResponse(NoteResponse):
    node_title: str
    node_slug: str | None


class NoteCreate(BaseModel):
    content: str = Field(min_length=1)


class NoteUpdate(BaseModel):
    content: str | None = Field(None, min_length=1)
    done: bool | None = None
