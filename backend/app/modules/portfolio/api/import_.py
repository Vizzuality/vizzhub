"""Portfolio Overview import endpoints. Read=portfolio:view, write=portfolio:manage."""

from typing import Annotated
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, Request, UploadFile

from app.core.api.deps import DBSession, limiter
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.core.services.overview_import import (
    DecisionInput,
    apply_decisions,
    build_matches,
    parse_overview_xlsx,
    replace_staging,
)
from app.modules.portfolio.schemas.import_ import (
    ApplyResult,
    CurrentProgram,
    MatchDecision,
    ProjectCandidate,
    StagingMatch,
    SuggestedProject,
    UploadResult,
)

PortfolioViewer = Annotated[TokenData, Depends(require_permission(Action.PORTFOLIO_VIEW))]
PortfolioManager = Annotated[TokenData, Depends(require_permission(Action.PORTFOLIO_MANAGE))]

router = APIRouter()
logger = structlog.get_logger()


@router.post("/upload", responses={403: {"description": "Missing portfolio:manage"}})
@limiter.limit("10/minute")
async def upload_overview(
    request: Request, current_user: PortfolioManager, db: DBSession, file: UploadFile
) -> UploadResult:
    content = await file.read()
    rows = parse_overview_xlsx(content)
    batch_id = uuid4()
    count, old = await replace_staging(db, batch_id, rows)
    return UploadResult(batch_id=batch_id, row_count=count, old_count=old)


@router.get("/{batch_id}/matches", responses={403: {"description": "Missing portfolio:view"}})
@limiter.limit("60/minute")
async def get_matches(
    request: Request, current_user: PortfolioViewer, db: DBSession, batch_id: UUID
) -> list[StagingMatch]:
    data = await build_matches(db, batch_id)
    return [
        StagingMatch(
            staging_id=m.staging_id,
            name=m.name,
            is_old_project=m.is_old_project,
            client_type_raw=m.client_type_raw,
            service_raw=m.service_raw,
            impact_area_raw=m.impact_area_raw,
            suggested_project=SuggestedProject(
                project_id=m.suggested_project.project_id, score=m.suggested_project.score
            ),
            project_candidates=[
                ProjectCandidate(id=c.id, name=c.name, score=c.score) for c in m.project_candidates
            ],
            current_program=CurrentProgram(
                program_id=m.current_program.program_id, name=m.current_program.name
            ),
        )
        for m in data
    ]


@router.post("/{batch_id}/apply", responses={403: {"description": "Missing portfolio:manage"}})
@limiter.limit("20/minute")
async def apply_matches(
    request: Request,
    current_user: PortfolioManager,
    db: DBSession,
    batch_id: UUID,
    payload: list[MatchDecision],
) -> ApplyResult:
    decisions = [
        DecisionInput(
            staging_id=d.staging_id,
            project_id=d.project_id,
            program_action=d.program_action,
            program_id=d.program_id,
            new_program_name=d.new_program_name,
        )
        for d in payload
    ]
    result = await apply_decisions(db, batch_id, decisions, user_id=current_user.user_id)
    return ApplyResult(**result.__dict__)
