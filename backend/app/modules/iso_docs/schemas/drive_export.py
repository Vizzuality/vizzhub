"""Schemas for Google Drive export."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DriveFolderRequest(BaseModel):
    folder_id: str = Field(..., min_length=1, max_length=255)


class DriveExportResponse(BaseModel):
    job_id: UUID


class DriveStatusResponse(BaseModel):
    connected: bool
    last_export_at: datetime | None = None
    root_folder_id: str | None = None
    exported_doc_count: int = 0
