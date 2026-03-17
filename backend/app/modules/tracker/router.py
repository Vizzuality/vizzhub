"""Tracker module router — aggregates all tracker sub-routers."""

from fastapi import APIRouter

from app.modules.tracker.api import non_staff_costs as non_staff_costs_router
from app.modules.tracker.api import report_parts as report_parts_router
from app.modules.tracker.api import reports as reports_router
from app.modules.tracker.api import reporting_periods as reporting_periods_router

router = APIRouter()

router.include_router(
    reporting_periods_router.router,
    prefix="/reporting-periods",
    tags=["tracker:reporting-periods"],
)
router.include_router(
    reports_router.router,
    prefix="/reports",
    tags=["tracker:reports"],
)
router.include_router(
    report_parts_router.router,
    prefix="/report-parts",
    tags=["tracker:report-parts"],
)
router.include_router(
    non_staff_costs_router.router,
    prefix="/non-staff-costs",
    tags=["tracker:non-staff-costs"],
)
