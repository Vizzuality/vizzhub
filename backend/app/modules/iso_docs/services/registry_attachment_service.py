"""Registry attachment service — S3 upload/delete for registry evidence files."""

from __future__ import annotations

import uuid

from app.config import get_settings
from app.core.services.s3 import get_s3_client

S3_PREFIX = "iso-registries/"

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/msword",
    "text/csv",
}


def _sanitize_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in ".-_" else "-" for c in name).strip("-")


def upload_attachment(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload a file to S3 under iso-registries/ prefix. Returns s3_key."""
    settings = get_settings()
    sanitized = _sanitize_filename(filename)
    unique = uuid.uuid4().hex[:8]
    key = f"{S3_PREFIX}{unique}-{sanitized}"

    get_s3_client().put_object(
        Bucket=settings.assets_bucket_name,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return key


def get_attachment_url(s3_key: str) -> str:
    """Construct a URL for an S3 object."""
    settings = get_settings()
    return f"{settings.assets_bucket_url}/{s3_key}"


def delete_attachment(s3_key: str) -> None:
    """Delete a file from S3."""
    settings = get_settings()
    get_s3_client().delete_object(
        Bucket=settings.assets_bucket_name,
        Key=s3_key,
    )
