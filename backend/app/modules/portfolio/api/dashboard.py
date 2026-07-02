"""Portfolio dashboard sub-router (read-only, gated portfolio:view).

NOTE: /summary endpoint migrated to leaderboard endpoints in Task 3.
This file is a placeholder stub; the old build_portfolio_summary has been
replaced by build_project_leaderboard / build_client_leaderboard.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.core.api.deps import DBSession, limiter
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.core.services.portfolio_dashboard import (
    build_client_leaderboard,
    build_project_leaderboard,
)
from app.modules.portfolio.schemas.dashboard import ClientLeaderboard, ProjectLeaderboard

PortfolioViewer = Annotated[TokenData, Depends(require_permission(Action.PORTFOLIO_VIEW))]

router = APIRouter()


@router.get("/projects")
@limiter.limit("60/minute")
async def project_leaderboard(
    request: Request,
    current_user: PortfolioViewer,
    db: DBSession,
    year: int | None = Query(None, ge=2000, le=2100),
) -> ProjectLeaderboard:
    return await build_project_leaderboard(db, year=year)


@router.get("/clients")
@limiter.limit("60/minute")
async def client_leaderboard(
    request: Request,
    current_user: PortfolioViewer,
    db: DBSession,
    year: int | None = Query(None, ge=2000, le=2100),
) -> ClientLeaderboard:
    return await build_client_leaderboard(db, year=year)
