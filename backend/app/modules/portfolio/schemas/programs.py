"""Program catalogue response/request schemas (F2)."""

from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TermChip(BaseModel):
    term_id: UUID
    taxonomy_id: UUID
    taxonomy_slug: str
    name: str
    is_primary: bool


class ClientRef(BaseModel):
    id: UUID
    name: str


class ProjectIteration(BaseModel):
    id: UUID
    name: str
    status: str
    start_year: int | None
    end_year: int | None
    has_scorecard: bool
    is_billable: bool
    is_absence: bool
    client_id: UUID | None
    client_name: str | None


class ProfileFields(BaseModel):
    objective: str | None = None
    short_description: str | None = None
    web_copy: str | None = None
    website_url: str | None = None
    impact_story: str | None = None
    main_partner: str | None = None
    stage: str | None = None
    on_website: bool = False
    model_config = {"from_attributes": True}


class ProgramSummary(BaseModel):
    id: UUID
    name: str
    profile: ProfileFields | None
    terms: list[TermChip] = Field(default_factory=list)
    clients: list[ClientRef] = Field(default_factory=list)
    projects: list[ProjectIteration] = Field(default_factory=list)


class ProgramIndexResponse(BaseModel):
    programs: list[ProgramSummary]
    total: int
    pages: int


class ProgramProfileUpdate(BaseModel):
    """PATCH body — model_fields_set distinguishes absent from explicit null."""

    objective: str | None = None
    short_description: str | None = None
    web_copy: str | None = None
    website_url: str | None = None
    impact_story: str | None = None
    main_partner: str | None = None
    stage: str | None = None
    on_website: bool | None = None

    @field_validator("website_url")
    @classmethod
    def _http_scheme_only(cls, v: str | None) -> str | None:
        if v is not None and urlsplit(v).scheme not in ("http", "https"):
            raise ValueError("website_url must start with http:// or https://")
        return v


class ProgramTermsUpdate(BaseModel):
    """PUT body — replace the program's terms for ONE taxonomy."""

    taxonomy_id: UUID
    term_ids: list[UUID] = Field(default_factory=list)
    primary_term_id: UUID | None = None
