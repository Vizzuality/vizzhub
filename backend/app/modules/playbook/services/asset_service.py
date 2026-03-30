"""Playbook asset upload service (S3)."""

from __future__ import annotations

import re
import uuid
from functools import lru_cache
from urllib.parse import urlparse

import boto3

from app.config import get_settings

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

S3_PREFIX = "playbook/images/"
S3_ROOT = S3_PREFIX.split("/", 1)[0] + "/"  # "playbook/"


def is_upload_available() -> bool:
    settings = get_settings()
    return bool(settings.assets_bucket_name)


def _region_from_url(url: str) -> str:
    host = urlparse(url).hostname or ""
    parts = host.split(".")
    if len(parts) >= 4 and parts[1] == "s3":
        return parts[2]
    return "eu-west-3"


@lru_cache
def _get_s3_client():  # type: ignore[no-untyped-def]
    settings = get_settings()
    region = _region_from_url(settings.assets_bucket_url)
    return boto3.Session(region_name=region).client("s3")


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

    _get_s3_client().put_object(
        Bucket=settings.assets_bucket_name,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )

    if settings.playbook_public_url:
        return f"{settings.playbook_public_url}/{key.removeprefix(S3_ROOT)}"
    return f"{settings.assets_bucket_url}/{key}"


def rewrite_image_urls(content: str) -> str:
    """Replace legacy S3 image URLs with CloudFront URLs in markdown content."""
    settings = get_settings()
    if not settings.playbook_public_url or not settings.assets_bucket_url:
        return content
    s3_prefix = f"{settings.assets_bucket_url}/{S3_PREFIX}"
    cf_prefix = f"{settings.playbook_public_url}/images/"
    return content.replace(s3_prefix, cf_prefix)
