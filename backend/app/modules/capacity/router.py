from fastapi import APIRouter

from app.modules.capacity.api import allocation as allocation_router
from app.modules.capacity.api import fa_detail as fa_detail_router
from app.modules.capacity.api import insights as insights_router
from app.modules.capacity.api import user_detail as user_detail_router

router = APIRouter()
router.include_router(
    insights_router.router, prefix="/insights", tags=["capacity:insights"]
)
router.include_router(
    fa_detail_router.router, prefix="/insights/detail", tags=["capacity:fa-detail"]
)
router.include_router(
    user_detail_router.router, prefix="/insights/user-detail", tags=["capacity:user-detail"]
)
router.include_router(
    allocation_router.router, prefix="/allocation", tags=["capacity:allocation"]
)
