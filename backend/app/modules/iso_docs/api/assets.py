"""ISO Docs asset upload endpoint — images for page content."""

from fastapi import Depends

from app.core.api.asset_routes import create_asset_router
from app.modules.iso_docs.api.deps import IsoDocsEditor
from app.modules.iso_docs.services.asset_service import (
    is_upload_available,
    upload_image,
)


def _require_editor(user: IsoDocsEditor) -> None:
    """FastAPI resolves IsoDocsEditor via its type annotation."""


router = create_asset_router(
    is_upload_available=is_upload_available,
    upload_image=upload_image,
    log_event="iso_docs_image_uploaded",
    dependencies=[Depends(_require_editor)],
)
