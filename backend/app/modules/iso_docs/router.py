"""ISO Docs module router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.modules.iso_docs.api.nodes import router as nodes_router
from app.modules.iso_docs.api.pages import router as pages_router
from app.modules.iso_docs.api.metadata import router as metadata_router

router = APIRouter()

router.include_router(nodes_router)
router.include_router(pages_router, prefix="/pages")
router.include_router(metadata_router)
