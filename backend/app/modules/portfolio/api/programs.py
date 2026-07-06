"""Program catalogue endpoints (F2). Read=portfolio:view, write=portfolio:manage."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, Request

from app.core.api.deps import DBSession, limiter
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.core.services.program_catalog import build_program_index
from app.modules.portfolio.schemas.programs import ProgramIndexResponse

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
) -> ProgramIndexResponse:
    return await build_program_index(db, search=search, term_ids=term_ids, client_id=client_id)
