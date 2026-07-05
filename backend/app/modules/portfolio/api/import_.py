"""Portfolio Overview import endpoints. Read=portfolio:view, write=portfolio:manage."""

from typing import Annotated
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy import select

from app.core.api.deps import DBSession, limiter
from app.core.auth import TokenData
from app.core.models.project import ProjectDB
from app.core.permissions import Action, require_permission
from app.core.services.overview_import import (
    apply_persisted,
    build_matches,
    get_current_batch,
    parse_overview_xlsx,
    replace_staging,
    save_decision,
    seed_default_decisions,
)
from app.modules.portfolio.schemas.import_ import (
    ApplyResult,
    CurrentBatch,
    CurrentProgram,
    DecisionPatch,
    ImportProject,
    ProgramCandidate,
    ProjectCandidate,
    SavedDecision,
    StagingMatch,
    SuggestedProgram,
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
    await seed_default_decisions(db, batch_id)
    return UploadResult(batch_id=batch_id, row_count=count, old_count=old)


@router.get("/current", responses={403: {"description": "Missing portfolio:view"}})
@limiter.limit("60/minute")
async def current_batch(
    request: Request, current_user: PortfolioViewer, db: DBSession
) -> CurrentBatch | None:
    cur = await get_current_batch(db)
    return CurrentBatch(batch_id=cur.batch_id, row_count=cur.row_count) if cur else None


@router.get("/projects", responses={403: {"description": "Missing portfolio:view"}})
@limiter.limit("60/minute")
async def list_import_projects(
    request: Request, current_user: PortfolioViewer, db: DBSession
) -> list[ImportProject]:
    """All non-absence projects (any status, billable or not) for the import project picker.

    Mirrors the build_matches candidate universe so finished and non-billable projects are
    pickable too, and carries program_id so the UI can derive program context for any chosen
    project.
    """
    rows = (
        await db.execute(
            select(ProjectDB.id, ProjectDB.name, ProjectDB.program_id)
            .where(ProjectDB.is_absence.is_(False))
            .order_by(ProjectDB.name)
        )
    ).all()
    return [ImportProject(id=r.id, name=r.name, program_id=r.program_id) for r in rows]


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
            program_candidates=[
                ProgramCandidate(id=c.id, name=c.name, score=c.score) for c in m.program_candidates
            ],
            suggested_program=SuggestedProgram(
                program_id=m.suggested_program.program_id, score=m.suggested_program.score
            ),
            saved_decision=(
                SavedDecision(
                    project_id=m.saved_decision.project_id,
                    program_action=m.saved_decision.program_action,
                    program_id=m.saved_decision.program_id,
                    new_program_name=m.saved_decision.new_program_name,
                )
                if m.saved_decision is not None
                else None
            ),
        )
        for m in data
    ]


@router.patch(
    "/{batch_id}/decisions/{staging_id}",
    responses={
        403: {"description": "Missing portfolio:manage"},
        404: {"description": "Staging row not found in batch"},
    },
)
@limiter.limit("120/minute")
async def patch_decision(
    request: Request,
    current_user: PortfolioManager,
    db: DBSession,
    batch_id: UUID,
    staging_id: UUID,
    payload: DecisionPatch,
) -> dict[str, bool]:
    ok = await save_decision(
        db,
        batch_id,
        staging_id,
        project_id=payload.project_id,
        program_action=payload.program_action,
        program_id=payload.program_id,
        new_program_name=payload.new_program_name,
        user_id=current_user.user_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Staging row not found")
    return {"saved": True}


@router.post("/{batch_id}/apply", responses={403: {"description": "Missing portfolio:manage"}})
@limiter.limit("20/minute")
async def apply_matches(
    request: Request, current_user: PortfolioManager, db: DBSession, batch_id: UUID
) -> ApplyResult:
    result = await apply_persisted(db, batch_id, user_id=current_user.user_id)
    return ApplyResult(**result.__dict__)
