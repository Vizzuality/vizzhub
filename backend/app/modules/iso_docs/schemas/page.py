"""Pydantic schemas for ISO doc page content and versions."""

from uuid import UUID

from pydantic import BaseModel

from app.core.schemas.page import (  # noqa: F401
    PageContentBase as PageContentResponse,
    PageSave,
    PageSaveResponse,
    VersionDetailResponse,
    VersionListItem,
)


class SearchResultItem(BaseModel):
    node_id: UUID
    title: str
    snippet: str
    code: str | None = None
