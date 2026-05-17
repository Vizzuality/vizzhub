"""Pydantic schemas for the devstack module."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.modules.devstack.constants import EntryOrigin, EntryType, InstallMethod

# How long an entry can go without a successful refresh before it's
# flagged stale. The cron runs daily and a single failed round shouldn't
# trip the flag, so we allow ~3x the refresh cadence before complaining.
STALE_AFTER = timedelta(hours=72)

_NPM_PACKAGE_RE = re.compile(r"^(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$")


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
    featured: bool = False

    @field_validator("package")
    @classmethod
    def validate_npm_package(cls, v: str | None, info) -> str | None:
        if v is None:
            return v
        method = info.data.get("install_method")
        if method == InstallMethod.NPM and not _NPM_PACKAGE_RE.match(v):
            raise ValueError("Invalid npm package name format")
        return v


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
    featured: bool | None = None

    @field_validator("package")
    @classmethod
    def validate_npm_package(cls, v: str | None, info) -> str | None:
        if v is None:
            return v
        method = info.data.get("install_method")
        if method == InstallMethod.NPM and not _NPM_PACKAGE_RE.match(v):
            raise ValueError("Invalid npm package name format")
        return v


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
    tech: list[str] = Field(default_factory=list)
    active: bool
    github_sha: str | None = None
    latest_package_version: str | None = None
    featured: bool
    install_count: int = 0
    last_installed_at: datetime | None = None
    last_fetch_ok_at: datetime | None = None
    deprecated: bool = False
    deprecation_message: str | None = None
    vulnerabilities: dict | None = None
    created_by_id: UUID | None = None
    updated_by_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def stale(self) -> bool:
        """True when the catalog entry hasn't refreshed inside STALE_AFTER.

        claude_plugin entries are never auto-refreshed (no SHA / no npm
        registry), so they're considered fresh forever — flagging them
        would just be noise.
        """
        if self.install_method == "claude_plugin":
            return False
        if self.last_fetch_ok_at is None:
            # Brand-new rows get a grace period equal to STALE_AFTER so a
            # freshly-seeded catalog doesn't immediately scream.
            return datetime.now(UTC) - self.created_at > STALE_AFTER
        return datetime.now(UTC) - self.last_fetch_ok_at > STALE_AFTER
