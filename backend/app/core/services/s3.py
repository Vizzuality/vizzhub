"""Shared S3 client — single cached boto3 client for the assets bucket."""

from __future__ import annotations

from functools import lru_cache

import boto3

from app.config import get_settings


def _region_from_url(url: str) -> str:
    for part in url.split("."):
        if part.startswith("s3-") or part.startswith("s3."):
            region = part.replace("s3-", "").replace("s3.", "")
            if region:
                return region
    return "eu-west-3"


@lru_cache
def get_s3_client():  # type: ignore[no-untyped-def]
    settings = get_settings()
    region = _region_from_url(settings.assets_bucket_url)
    return boto3.Session(region_name=region).client("s3")
