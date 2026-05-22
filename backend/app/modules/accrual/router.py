"""Accrual module router — aggregates sub-routers."""

from fastapi import APIRouter

from app.modules.accrual.api import cells as cells_router
from app.modules.accrual.api import periods as periods_router

# Import models to register with Base.metadata
from app.modules.accrual.models import AccrualPeriodDB, ProjectAccrualCellDB  # noqa: F401

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
