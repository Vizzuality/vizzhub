"""Fetch npm package vulnerabilities from the GitHub Advisory Database."""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger()

_ADVISORY_URL = "https://api.github.com/advisories"
_SEVERITY_KEYS = ("critical", "high", "moderate", "low")


async def fetch_npm_advisories(package: str, version: str, token: str | None) -> dict | None:
    """Fetch advisories for package@version from the GitHub Advisory DB.

    Returns a dict with per-severity counts and a list of {id, severity, title, url},
    or None on HTTP error.
    """
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    params = {
        "ecosystem": "npm",
        "affects": f"{package}@{version}",
        "per_page": "100",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_ADVISORY_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning(
            "npm_advisories_fetch_failed",
            package=package,
            version=version,
            error=str(exc),
        )
        return None

    summary: dict = dict.fromkeys(_SEVERITY_KEYS, 0)
    advisories: list[dict] = []

    for item in data:
        severity = item.get("severity", "")
        if severity in _SEVERITY_KEYS:
            summary[severity] += 1
        advisories.append(
            {
                "id": item.get("ghsa_id"),
                "severity": severity,
                "title": item.get("summary"),
                "url": item.get("html_url"),
            }
        )

    summary["advisories"] = advisories
    logger.info(
        "npm_advisories_fetched",
        package=package,
        version=version,
        total=len(advisories),
        critical=summary["critical"],
        high=summary["high"],
    )
    return summary
