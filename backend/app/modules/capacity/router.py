from fastapi import APIRouter

from app.modules.capacity.api import fa_detail as fa_detail_router
from app.modules.capacity.api import insights as insights_router

router = APIRouter()
router.include_router(
    insights_router.router, prefix="/insights", tags=["capacity:insights"]
)
router.include_router(
    fa_detail_router.router, prefix="/insights/detail", tags=["capacity:fa-detail"]
)
