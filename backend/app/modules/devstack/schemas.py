"""Pydantic schemas for the devstack module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.devstack.constants import EntryOrigin, EntryType, InstallMethod


class EntryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    type: EntryType
    install_method: InstallMethod
    url: str | None = None
    package: str | None = Field(None, max_length=200)
    package_version: str | None = Field(None, max_length=50)
    required: bool = False
    origin: EntryOrigin = EntryOrigin.INTERNAL
    tech: list[str] = Field(default_factory=list)
    active: bool = True


class EntryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, min_length=1)
    type: EntryType | None = None
    install_method: InstallMethod | None = None
    url: str | None = None
    package: str | None = Field(None, max_length=200)
    package_version: str | None = Field(None, max_length=50)
    required: bool | None = None
    origin: EntryOrigin | None = None
    tech: list[str] | None = None
    active: bool | None = None


class EntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    type: str
    install_method: str
    url: str | None = None
    package: str | None = None
    package_version: str | None = None
    required: bool
    origin: str
    tech: list = []
    active: bool
    created_by_id: UUID | None = None
    updated_by_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class UserPrefUpdate(BaseModel):
    enabled: bool


class UserPrefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    entry_id: UUID
    enabled: bool
    last_synced_sha: str | None = None
    last_synced_at: datetime | None = None
