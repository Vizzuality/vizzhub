"""Accrual module router — aggregates sub-routers."""

from fastapi import APIRouter

from app.modules.accrual.api import aliases as aliases_router
from app.modules.accrual.api import cells as cells_router
from app.modules.accrual.api import drift as drift_router
from app.modules.accrual.api import excel_rows as excel_rows_router
from app.modules.accrual.api import lines as lines_router
from app.modules.accrual.api import periods as periods_router

# Import models to register with Base.metadata
from app.modules.accrual.models import (  # noqa: F401
    AccrualAliasDB,
    AccrualDriftFindingDB,
    AccrualExcelRowDB,
    AccrualImportRunDB,
    AccrualPeriodDB,
    ProjectAccrualCellDB,
)

router = APIRouter()

router.include_router(
    periods_router.router,
    prefix="/periods",
    tags=["accrual:periods"],
)
router.include_router(
    drift_router.router,
    prefix="/drift",
    tags=["accrual:drift"],
)
router.include_router(
    aliases_router.router,
    prefix="/aliases",
    tags=["accrual:aliases"],
)
router.include_router(
    excel_rows_router.router,
    prefix="/excel-rows",
    tags=["accrual:excel-rows"],
)
router.include_router(
    cells_router.router,
    tags=["accrual:cells"],
)
router.include_router(
    lines_router.router,
    tags=["accrual:lines"],
)
