from fastapi import APIRouter

from app.modules.capacity.api import insights as insights_router

router = APIRouter()
router.include_router(
    insights_router.router, prefix="/insights", tags=["capacity:insights"]
)
