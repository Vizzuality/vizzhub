"""Playbook asset upload service (S3)."""

from __future__ import annotations

from app.config import get_settings
from app.core.services.doc_asset_service import (  # noqa: F401
    ALLOWED_CONTENT_TYPES,
    MAX_FILE_SIZE,
    is_upload_available,
    upload_image as _upload_image,
)

S3_PREFIX = "playbook/images/"
S3_ROOT = S3_PREFIX.split("/", 1)[0] + "/"  # "playbook/"


def _build_url(key: str) -> str:
    settings = get_settings()
    if settings.playbook_public_url:
        return f"{settings.playbook_public_url}/{key.removeprefix(S3_ROOT)}"
    return f"{settings.assets_bucket_url}/{key}"


def upload_image(file_bytes: bytes, filename: str, content_type: str) -> str:
    return _upload_image(file_bytes, filename, content_type, S3_PREFIX, _build_url)


def rewrite_image_urls(content: str) -> str:
    """Replace legacy S3 image URLs with CloudFront URLs in markdown content."""
    settings = get_settings()
    if not settings.playbook_public_url or not settings.assets_bucket_url:
        return content
    s3_prefix = f"{settings.assets_bucket_url}/{S3_PREFIX}"
    cf_prefix = f"{settings.playbook_public_url}/images/"
    return content.replace(s3_prefix, cf_prefix)
