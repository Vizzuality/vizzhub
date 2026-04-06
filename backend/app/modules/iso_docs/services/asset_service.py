"""ISO Docs asset upload service (S3) — images for page content."""

from __future__ import annotations

from app.config import get_settings
from app.core.services.doc_asset_service import (  # noqa: F401
    ALLOWED_CONTENT_TYPES,
    MAX_FILE_SIZE,
    is_upload_available,
    upload_image as _upload_image,
)
from app.core.services.s3 import get_s3_client

S3_PREFIX = "iso-docs/images/"


def _build_url(key: str) -> str:
    settings = get_settings()
    if settings.playbook_public_url:
        return f"{settings.playbook_public_url}/{key}"
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.assets_bucket_name, "Key": key},
        ExpiresIn=7 * 24 * 3600,
    )


def upload_image(file_bytes: bytes, filename: str, content_type: str) -> str:
    return _upload_image(file_bytes, filename, content_type, S3_PREFIX, _build_url)
