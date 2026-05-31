"""Accrual module router — aggregates sub-routers."""

from fastapi import APIRouter

from app.modules.accrual.api import cells as cells_router
from app.modules.accrual.api import dashboard as dashboard_router
from app.modules.accrual.api import lines as lines_router
from app.modules.accrual.api import periods as periods_router

# Import models to register with Base.metadata
from app.modules.accrual.models import (  # noqa: F401
    AccrualCellDB,
    AccrualExcelRowDB,
    AccrualImportRunDB,
    AccrualPeriodDB,
)

router = APIRouter()

router.include_router(
    periods_router.router,
    prefix="/periods",
    tags=["accrual:periods"],
)
router.include_router(
    cells_router.router,
    tags=["accrual:cells"],
)
router.include_router(
    lines_router.router,
    tags=["accrual:lines"],
)
router.include_router(
    dashboard_router.router,
    prefix="/dashboard",
    tags=["accrual:dashboard"],
)
