from fastapi import APIRouter

from app.modules.scorecard.api import exports as exports_router

router = APIRouter()
router.include_router(exports_router.router, prefix="/exports", tags=["exports"])
