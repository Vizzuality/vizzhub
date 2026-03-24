"""Playbook asset upload service (S3)."""

from __future__ import annotations

from app.config import get_settings


def is_upload_available() -> bool:
    """Check if S3 bucket is configured for uploads."""
    settings = get_settings()
    return bool(getattr(settings, "playbook_s3_bucket", None))
