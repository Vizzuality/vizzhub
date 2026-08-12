"""GitHub SHA resolution for devstack catalog entries."""

from __future__ import annotations

import asyncio
import base64
import re

import httpx
import structlog

logger = structlog.get_logger()

# Emit a warning when the GitHub API leaves fewer than this many calls in
# the rate-limit budget. 60/hour unauthenticated, 5000/hour authenticated.
_RATE_LIMIT_WARN_BELOW = 10

# Max time we'll sleep on a 429 before giving up and returning None. The
# refresher iterates many entries; blocking a worker for too long on one
# broken entry is worse than skipping it for this round.
_MAX_RATE_LIMIT_SLEEP_SECONDS = 30.0


def _log_rate_limit(resp: httpx.Response, url: str) -> None:
    """Warn when the GitHub rate-limit budget is running low."""
    remaining_header = resp.headers.get("X-RateLimit-Remaining")
    if remaining_header is None:
        return
    try:
        remaining = int(remaining_header)
    except ValueError:
        return
    if remaining < _RATE_LIMIT_WARN_BELOW:
        logger.warning(
            "github_rate_limit_low",
            url=url,
            remaining=remaining,
            reset=resp.headers.get("X-RateLimit-Reset"),
            authenticated=bool(resp.headers.get("X-OAuth-Scopes")),
        )


def _parse_retry_after(resp: httpx.Response) -> float | None:
    """Return seconds to wait per the Retry-After header, capped."""
    retry_after = resp.headers.get("Retry-After")
    if retry_after is None:
        return None
    try:
        wait = float(retry_after)
    except ValueError:
        return None
    if wait <= 0:
        return None
    return min(wait, _MAX_RATE_LIMIT_SLEEP_SECONDS)


# Standard GitHub blob URL: github.com/{owner}/{repo}/blob/{ref}/{path}
# Note: refs with '/' (e.g. feature/test) are not supported — first segment is taken as ref.
_BLOB_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)")
# Raw URL with refs/heads or refs/tags prefix (GitHub's "Copy raw file" button):
# raw.githubusercontent.com/{owner}/{repo}/refs/heads/{ref}/{path}
_RAW_REFS_RE = re.compile(
    r"https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/refs/(?:heads|tags)/([^/]+)/(.+)"
)
# Raw content URL (plain): raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}
_RAW_RE = re.compile(r"https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)")

GITHUB_API_BASE = "https://api.github.com"


def parse_github_url(url: str) -> tuple[str, str, str, str] | None:
    """Extract (owner, repo, ref, path) from a GitHub file URL.

    Supports:
    - github.com/{owner}/{repo}/blob/{ref}/{path}
    - raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}
    - raw.githubusercontent.com/{owner}/{repo}/refs/heads/{ref}/{path}
    - raw.githubusercontent.com/{owner}/{repo}/refs/tags/{ref}/{path}

    Returns None if the URL format is not recognized.
    """
    for pattern in (_BLOB_RE, _RAW_REFS_RE, _RAW_RE):
        match = pattern.match(url)
        if match:
            return match.group(1), match.group(2), match.group(3), match.group(4)
    return None


async def _get_with_rate_limit_retry(
    client: httpx.AsyncClient,
    api_url: str,
    headers: dict[str, str],
    params: dict[str, str],
    *,
    url_for_log: str,
) -> httpx.Response:
    """GET the URL, warn on low rate-limit budget, retry once on 429.

    Returns the eventual response (which still needs `raise_for_status()`
    by the caller). We retry exactly once: a persistently rate-limited
    refresher would block the worker for the whole hourly window.
    """
    resp = await client.get(api_url, headers=headers, params=params)
    if resp.status_code == 429:
        wait = _parse_retry_after(resp)
        if wait is not None:
            logger.warning(
                "github_rate_limited_retrying",
                url=url_for_log,
                retry_after_s=wait,
            )
            await asyncio.sleep(wait)
            resp = await client.get(api_url, headers=headers, params=params)
    _log_rate_limit(resp, url_for_log)
    return resp


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
            resp = await _get_with_rate_limit_retry(
                client,
                api_url,
                headers,
                {"ref": ref},
                url_for_log=url,
            )
            resp.raise_for_status()
            sha = resp.json().get("sha")
            if sha:
                logger.info("devstack_sha_fetched", url=url, sha=sha[:8])
            return sha
    except (httpx.HTTPError, ValueError) as exc:
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
            resp = await _get_with_rate_limit_retry(
                client,
                api_url,
                headers,
                {"ref": ref},
                url_for_log=url,
            )
            resp.raise_for_status()
            data = resp.json()
            encoded = data.get("content")
            if not encoded:
                return None
            return base64.b64decode(encoded).decode("utf-8")
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("devstack_content_fetch_failed", url=url, error=str(exc))
        return None
