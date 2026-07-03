"""Portfolio module router — aggregates portfolio sub-routers (F1/F2)."""

from fastapi import APIRouter

from app.modules.portfolio.api import dashboard, import_

router = APIRouter()
router.include_router(dashboard.router, prefix="/dashboard", tags=["portfolio"])
router.include_router(import_.router, prefix="/import", tags=["portfolio"])
