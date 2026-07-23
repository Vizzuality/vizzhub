"""Program catalogue endpoints (F2). Read=portfolio:view, write=portfolio:manage."""

from typing import Annotated, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.api.deps import DBSession, limiter
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.core.services.program_catalog import (
    build_program_detail,
    build_program_index,
    list_program_stages,
    list_unassigned_projects,
    replace_program_terms,
    upsert_program_profile,
)
from app.modules.portfolio.schemas.programs import (
    ProfileFields,
    ProgramIndexResponse,
    ProgramProfileUpdate,
    ProgramSummary,
    ProgramTermsUpdate,
    ProjectIteration,
    TermChip,
)

PortfolioViewer = Annotated[TokenData, Depends(require_permission(Action.PORTFOLIO_VIEW))]
PortfolioManager = Annotated[TokenData, Depends(require_permission(Action.PORTFOLIO_MANAGE))]

router = APIRouter()
logger = structlog.get_logger()


@router.get("", responses={403: {"description": "Missing portfolio:view permission"}})
@limiter.limit("60/minute")
async def program_index(
    request: Request,
    current_user: PortfolioViewer,
    db: DBSession,
    search: str = "",
    term_ids: Annotated[list[UUID] | None, Query()] = None,
    client_id: Annotated[UUID | None, Query()] = None,
    stage: Annotated[str | None, Query()] = None,
    on_website: Annotated[bool | None, Query()] = None,
    sort: Annotated[Literal["recent", "alpha"], Query()] = "recent",
    page: Annotated[int, Query(ge=1)] = 1,
    n: Annotated[int, Query(ge=1, le=100)] = 24,
) -> ProgramIndexResponse:
    return await build_program_index(
        db,
        search=search,
        term_ids=term_ids,
        client_id=client_id,
        stage=stage,
        on_website=on_website,
        sort=sort,
        page=page,
        n=n,
    )


@router.get("/unassigned", responses={403: {"description": "Missing portfolio:view permission"}})
@limiter.limit("60/minute")
async def unassigned_projects(
    request: Request,
    current_user: PortfolioViewer,
    db: DBSession,
) -> list[ProjectIteration]:
    return await list_unassigned_projects(db)


@router.get("/stages", responses={403: {"description": "Missing portfolio:view permission"}})
@limiter.limit("60/minute")
async def program_stages(
    request: Request,
    current_user: PortfolioViewer,
    db: DBSession,
) -> list[str]:
    return await list_program_stages(db)


@router.get(
    "/{program_id}",
    responses={
        403: {"description": "Missing portfolio:view permission"},
        404: {"description": "Program not found"},
    },
)
@limiter.limit("60/minute")
async def program_detail(
    request: Request,
    current_user: PortfolioViewer,
    db: DBSession,
    program_id: UUID,
) -> ProgramSummary:
    detail = await build_program_detail(db, program_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return detail


@router.patch(
    "/{program_id}/profile",
    responses={
        403: {"description": "Missing portfolio:manage permission"},
        404: {"description": "Program not found"},
    },
)
@limiter.limit("30/minute")
async def update_program_profile(
    request: Request,
    current_user: PortfolioManager,
    db: DBSession,
    program_id: UUID,
    payload: ProgramProfileUpdate,
) -> ProfileFields:
    try:
        result = await upsert_program_profile(db, program_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    logger.info(
        "portfolio_profile_updated",
        program_id=str(program_id),
        fields=sorted(payload.model_fields_set),
        user_id=current_user.user_id,
    )
    return result


@router.put(
    "/{program_id}/terms",
    responses={
        400: {"description": "Cardinality/primary/term validation failed"},
        403: {"description": "Missing portfolio:manage permission"},
        404: {"description": "Program or taxonomy not found"},
    },
)
@limiter.limit("30/minute")
async def replace_terms(
    request: Request,
    current_user: PortfolioManager,
    db: DBSession,
    program_id: UUID,
    payload: ProgramTermsUpdate,
) -> list[TermChip]:
    assigned_by = UUID(current_user.user_id)
    try:
        chips = await replace_program_terms(db, program_id, payload, assigned_by=assigned_by)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info(
        "portfolio_terms_updated",
        program_id=str(program_id),
        taxonomy_id=str(payload.taxonomy_id),
        count=len(chips),
        user_id=current_user.user_id,
    )
    return chips
