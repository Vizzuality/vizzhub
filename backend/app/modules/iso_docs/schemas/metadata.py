"""Pydantic schemas for ISO doc metadata."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChangelogEntry(BaseModel):
    version: str
    date: str
    author: str
    description: str


class MetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    node_id: UUID
    code: str | None
    standard: list[str] | None
    clauses: list[str] | None
    category: str | None
    classification: str
    doc_version: str | None
    status: str | None
    document_date: date | None
    original_filename: str | None
    guidance: str | None
    changelog: list[ChangelogEntry] | None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _derive_doc_version(self) -> MetadataResponse:
        if self.changelog:
            self.doc_version = self.changelog[-1].version
        return self


class MetadataUpdate(BaseModel):
    code: str | None = Field(None, max_length=50)
    standard: list[str] | None = None
    clauses: list[str] | None = None
    classification: str | None = Field(
        None,
        pattern=r"^(internal_use|confidential)$",
    )
    status: str | None = Field(
        None,
        pattern=r"^(draft|approved|under_review)$",
    )
    document_date: date | None = None
    original_filename: str | None = Field(None, max_length=500)
    guidance: str | None = None
    changelog: list[ChangelogEntry] | None = None


class MetadataSearchResult(BaseModel):
    node_id: UUID
    title: str
    code: str | None
    standard: list[str] | None
    clauses: list[str] | None
    category: str | None
    status: str | None
