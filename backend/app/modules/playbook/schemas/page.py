"""Pydantic schemas for playbook page content and versions."""

from app.core.schemas.page import (  # noqa: F401
    PageContentBase,
    PageSave,
    PageSaveResponse,
    VersionDetailResponse,
    VersionListItem,
)


class PageContentResponse(PageContentBase):
    is_public: bool
