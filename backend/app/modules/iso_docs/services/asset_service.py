"""ISO Docs asset upload service (S3) — images for page content."""

from __future__ import annotations

import re
import uuid

from app.config import get_settings
from app.core.services.s3 import get_s3_client

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

S3_PREFIX = "iso-docs/images/"


def is_upload_available() -> bool:
    settings = get_settings()
    return bool(settings.assets_bucket_name)


def _sanitize_filename(original: str) -> str:
    name = original.lower().strip()
    name = re.sub(r"[^\w.\-]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    if not name:
        name = "image"
    return name


def upload_image(file_bytes: bytes, filename: str, content_type: str) -> str:
    settings = get_settings()

    sanitized = _sanitize_filename(filename)
    stem, _, ext = sanitized.rpartition(".")
    if not stem:
        stem = sanitized
        ext = content_type.split("/")[-1].replace("svg+xml", "svg")
    unique = uuid.uuid4().hex[:8]
    key = f"{S3_PREFIX}{stem}-{unique}.{ext}"

    get_s3_client().put_object(
        Bucket=settings.assets_bucket_name,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )

    if settings.playbook_public_url:
        return f"{settings.playbook_public_url}/{key}"
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.assets_bucket_name, "Key": key},
        ExpiresIn=7 * 24 * 3600,
    )
