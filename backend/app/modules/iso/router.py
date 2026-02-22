from fastapi import APIRouter

from app.modules.iso.api import config as config_router

router = APIRouter()
router.include_router(config_router.router, prefix="/config", tags=["iso-config"])
