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

    return f"{settings.assets_bucket_url}/{key}"
