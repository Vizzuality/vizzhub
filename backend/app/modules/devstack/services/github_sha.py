"""GitHub SHA resolution for devstack catalog entries."""

from __future__ import annotations

import base64
import re

import httpx
import structlog

logger = structlog.get_logger()

# Standard GitHub blob URL: github.com/{owner}/{repo}/blob/{ref}/{path}
# Note: refs with '/' (e.g. feature/test) are not supported — first segment is taken as ref.
_BLOB_RE = re.compile(
    r"https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)"
)
# Raw content URL: raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}
_RAW_RE = re.compile(
    r"https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)"
)

GITHUB_API_BASE = "https://api.github.com"


def parse_github_url(url: str) -> tuple[str, str, str, str] | None:
    """Extract (owner, repo, ref, path) from a GitHub file URL.

    Supports:
    - github.com/{owner}/{repo}/blob/{ref}/{path}
    - raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}

    Returns None if the URL format is not recognized.
    """
    for pattern in (_BLOB_RE, _RAW_RE):
        match = pattern.match(url)
        if match:
            return match.group(1), match.group(2), match.group(3), match.group(4)
    return None


async def fetch_github_sha(url: str, token: str | None = None) -> str | None:
    """Fetch the blob SHA of a file from the GitHub Contents API.

    Returns the 40-char hex SHA string, or None on any failure.
    """
    parsed = parse_github_url(url)
    if parsed is None:
        logger.warning("devstack_sha_url_unparseable", url=url)
        return None

    owner, repo, ref, path = parsed
    api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(api_url, headers=headers, params={"ref": ref})
            resp.raise_for_status()
            sha = resp.json().get("sha")
            if sha:
                logger.info("devstack_sha_fetched", url=url, sha=sha[:8])
            return sha
    except httpx.HTTPError as exc:
        logger.warning("devstack_sha_fetch_failed", url=url, error=str(exc))
        return None


async def fetch_github_content(url: str, token: str | None = None) -> str | None:
    """Fetch the decoded content of a file from the GitHub Contents API.

    Returns the text content, or None on any failure. Supports private repos
    when a token is provided.
    """
    parsed = parse_github_url(url)
    if parsed is None:
        logger.warning("devstack_content_url_unparseable", url=url)
        return None

    owner, repo, ref, path = parsed
    api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(api_url, headers=headers, params={"ref": ref})
            resp.raise_for_status()
            data = resp.json()
            encoded = data.get("content")
            if not encoded:
                return None
            return base64.b64decode(encoded).decode("utf-8")
    except (httpx.HTTPError, ValueError, UnicodeDecodeError) as exc:
        logger.warning("devstack_content_fetch_failed", url=url, error=str(exc))
        return None
