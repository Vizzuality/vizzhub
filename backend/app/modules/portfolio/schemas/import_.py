"""Pydantic schemas for the Portfolio Overview import endpoints (project-first)."""

from uuid import UUID

from pydantic import BaseModel

from app.core.models.portfolio_overview import ProgramAction


class UploadResult(BaseModel):
    batch_id: UUID
    row_count: int
    old_count: int


class ProjectCandidate(BaseModel):
    id: UUID
    name: str
    score: float


class CurrentProgram(BaseModel):
    program_id: UUID | None = None
    name: str | None = None


class SuggestedProject(BaseModel):
    project_id: UUID | None = None
    score: float


class ProgramCandidate(BaseModel):
    id: UUID
    name: str
    score: float


class SuggestedProgram(BaseModel):
    program_id: UUID | None = None
    score: float


class StagingMatch(BaseModel):
    staging_id: UUID
    name: str
    is_old_project: bool
    client_type_raw: str | None = None
    service_raw: str | None = None
    impact_area_raw: str | None = None
    suggested_project: SuggestedProject
    project_candidates: list[ProjectCandidate]
    current_program: CurrentProgram
    program_candidates: list[ProgramCandidate]
    suggested_program: SuggestedProgram


class ImportProject(BaseModel):
    id: UUID
    name: str
    program_id: UUID | None = None


class MatchDecision(BaseModel):
    staging_id: UUID
    project_id: UUID | None = None
    program_action: ProgramAction
    program_id: UUID | None = None
    new_program_name: str | None = None


class ApplyResult(BaseModel):
    applied: int
    programs_created: int
    projects_linked_to_program: int
    programs_annotated: int
    skipped: int
    unmapped_terms: list[str]
    unresolved_clients: list[str]
