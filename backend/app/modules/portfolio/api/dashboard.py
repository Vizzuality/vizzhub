"""Portfolio dashboard sub-router (read-only, gated portfolio:view)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.core.api.deps import DBSession, limiter
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.core.services.portfolio_dashboard import build_portfolio_summary
from app.modules.portfolio.schemas.dashboard import PortfolioDashboardSummary

PortfolioViewer = Annotated[TokenData, Depends(require_permission(Action.PORTFOLIO_VIEW))]

router = APIRouter()


@router.get("/summary")
@limiter.limit("60/minute")
async def dashboard_summary(
    request: Request,
    current_user: PortfolioViewer,
    db: DBSession,
    year: int | None = Query(None, ge=2000, le=2100),
) -> PortfolioDashboardSummary:
    return await build_portfolio_summary(db, year=year)
