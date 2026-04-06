"""Playbook asset upload endpoints."""

from fastapi import Depends

from app.core.api.asset_routes import create_asset_router
from app.modules.playbook.api.deps import PlaybookEditor
from app.modules.playbook.services.asset_service import (
    is_upload_available,
    upload_image,
)


def _require_editor(user: PlaybookEditor) -> None:
    pass


router = create_asset_router(
    is_upload_available=is_upload_available,
    upload_image=upload_image,
    log_event="playbook_image_uploaded",
)
router.dependencies.append(Depends(_require_editor))
