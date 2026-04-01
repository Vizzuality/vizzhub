"""Registry attachment service — S3 upload/delete for registry evidence files."""

from __future__ import annotations

import uuid
from functools import lru_cache

import boto3

from app.config import get_settings

S3_PREFIX = "iso-registries/"

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

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


def _region_from_url(url: str) -> str:
    for part in url.split("."):
        if part.startswith("s3-") or part.startswith("s3."):
            region = part.replace("s3-", "").replace("s3.", "")
            if region:
                return region
    return "eu-west-3"


@lru_cache
def _get_s3_client():  # type: ignore[no-untyped-def]
    settings = get_settings()
    region = _region_from_url(settings.assets_bucket_url)
    return boto3.Session(region_name=region).client("s3")


def _sanitize_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in ".-_" else "-" for c in name).strip("-")


def upload_attachment(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload a file to S3 under iso-registries/ prefix. Returns s3_key."""
    settings = get_settings()
    sanitized = _sanitize_filename(filename)
    unique = uuid.uuid4().hex[:8]
    key = f"{S3_PREFIX}{unique}-{sanitized}"

    _get_s3_client().put_object(
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
    _get_s3_client().delete_object(
        Bucket=settings.assets_bucket_name,
        Key=s3_key,
    )
