"""Shared S3 client — single cached boto3 client for the assets bucket."""

from __future__ import annotations

from functools import lru_cache

import boto3
import structlog

from app.config import get_settings

logger = structlog.get_logger()

_DEFAULT_REGION = "eu-west-3"


def _region_from_url(url: str) -> str:
    for part in url.split("."):
        if part.startswith("s3-") or part.startswith("s3."):
            region = part.replace("s3-", "").replace("s3.", "")
            if region:
                return region
    logger.warning(
        "s3_region_fallback",
        url=url,
        default_region=_DEFAULT_REGION,
        hint="Set assets_bucket_url to an S3-style URL or set AWS_REGION explicitly.",
    )
    return _DEFAULT_REGION


@lru_cache
def get_s3_client():  # type: ignore[no-untyped-def]
    settings = get_settings()
    region = _region_from_url(settings.assets_bucket_url)
    return boto3.Session(region_name=region).client("s3")
