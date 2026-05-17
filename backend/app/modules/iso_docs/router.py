"""ISO Docs module router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.modules.iso_docs.api.assets import router as assets_router
from app.modules.iso_docs.api.drive_export import router as drive_export_router
from app.modules.iso_docs.api.metadata import router as metadata_router
from app.modules.iso_docs.api.nodes import router as nodes_router
from app.modules.iso_docs.api.notes import router as notes_router
from app.modules.iso_docs.api.pages import router as pages_router
from app.modules.iso_docs.api.registry_attachments import router as registry_attachments_router
from app.modules.iso_docs.api.registry_rows import router as registry_rows_router
from app.modules.iso_docs.api.registry_types import router as registry_types_router
from app.modules.iso_docs.api.widget_export import router as widget_export_router

router = APIRouter()

router.include_router(assets_router, prefix="/assets")
router.include_router(nodes_router)
router.include_router(pages_router, prefix="/pages")
router.include_router(metadata_router)
router.include_router(drive_export_router)
router.include_router(registry_types_router)
router.include_router(registry_rows_router)
router.include_router(registry_attachments_router)
router.include_router(widget_export_router)
router.include_router(notes_router)
