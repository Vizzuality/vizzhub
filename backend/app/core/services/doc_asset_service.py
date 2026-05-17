"""Shared asset upload service for wiki-style doc modules (Playbook, ISO Docs)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable

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


def is_upload_available() -> bool:
    settings = get_settings()
    return bool(settings.assets_bucket_name)


def sanitize_filename(original: str) -> str:
    name = original.lower().strip()
    name = re.sub(r"[^\w.\-]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    if not name:
        name = "image"
    return name


def upload_image(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    s3_prefix: str,
    build_url: Callable[[str], str],
) -> str:
    """Upload an image to S3 and return the public URL.

    Args:
        file_bytes: Raw file content.
        filename: Original filename for sanitization.
        content_type: MIME type.
        s3_prefix: S3 key prefix (e.g. "playbook/images/").
        build_url: Callable that receives the S3 key and returns a URL.
    """
    settings = get_settings()

    sanitized = sanitize_filename(filename)
    stem, _, ext = sanitized.rpartition(".")
    if not stem:
        stem = sanitized
        ext = content_type.split("/")[-1].replace("svg+xml", "svg")
    unique = uuid.uuid4().hex[:8]
    key = f"{s3_prefix}{stem}-{unique}.{ext}"

    get_s3_client().put_object(
        Bucket=settings.assets_bucket_name,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )

    return build_url(key)
