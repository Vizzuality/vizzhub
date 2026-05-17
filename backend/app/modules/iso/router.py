from fastapi import APIRouter

from app.modules.iso.api import config as config_router
from app.modules.iso.api import exports as exports_router
from app.modules.iso.api import reviews as reviews_router
from app.modules.iso.api import snapshots as snapshots_router

router = APIRouter()
router.include_router(config_router.router, prefix="/config", tags=["iso-config"])
router.include_router(exports_router.router, prefix="/exports/snapshots", tags=["iso-exports"])
router.include_router(reviews_router.router, prefix="/reviews", tags=["iso-reviews"])
router.include_router(snapshots_router.router, prefix="/snapshots", tags=["iso-snapshots"])
