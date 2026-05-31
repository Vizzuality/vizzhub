"""Accrual dashboard endpoints (/api/accrual/dashboard)."""

from datetime import date
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission
from app.modules.accrual.schemas.accrual_dashboard import DashboardSummary
from app.modules.accrual.services import dashboard_service

logger = structlog.get_logger()

router = APIRouter()

AccrualViewer = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_VIEW))]


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(year: int, db: DBSession, _: AccrualViewer) -> DashboardSummary:
    """Aggregated recognition figures for the dashboard, scoped to ``year``."""
    summary = await dashboard_service.build_summary(db, year=year, today=date.today())
    logger.info("accrual_dashboard_viewed", year=year)
    return summary
