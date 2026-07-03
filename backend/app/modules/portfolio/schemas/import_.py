"""Pydantic schemas for the Portfolio Overview import endpoints."""

from uuid import UUID

from pydantic import BaseModel

from app.core.models.portfolio_overview import MatchAction


class UploadResult(BaseModel):
    batch_id: UUID
    row_count: int
    old_count: int


class MatchCandidate(BaseModel):
    kind: str
    id: UUID
    name: str
    score: float


class SuggestedMatch(BaseModel):
    action: MatchAction
    program_id: UUID | None = None
    project_id: UUID | None = None
    score: float


class StagingMatch(BaseModel):
    staging_id: UUID
    name: str
    is_old_project: bool
    client_type_raw: str | None = None
    service_raw: str | None = None
    impact_area_raw: str | None = None
    suggested: SuggestedMatch
    candidates: list[MatchCandidate]


class MatchDecision(BaseModel):
    staging_id: UUID
    action: MatchAction
    program_id: UUID | None = None
    project_id: UUID | None = None


class ApplyResult(BaseModel):
    applied: int
    created_programs: int
    linked: int
    skipped: int
    unmapped_terms: list[str]
    unresolved_clients: list[str]
