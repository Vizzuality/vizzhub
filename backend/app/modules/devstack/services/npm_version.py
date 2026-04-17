"""Fetch latest npm package version from the npm registry."""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger()

NPM_REGISTRY_BASE = "https://registry.npmjs.org"


async def fetch_npm_latest_version(package: str) -> str | None:
    """Fetch the latest published version of an npm package.

    Returns the version string or None if the package doesn't exist or fetch fails.
    """
    url = f"{NPM_REGISTRY_BASE}/{package}/latest"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            version = resp.json().get("version")
            if version:
                logger.info("npm_version_fetched", package=package, version=version)
            return version
    except httpx.HTTPError as exc:
        logger.warning("npm_version_fetch_failed", package=package, error=str(exc))
        return None
