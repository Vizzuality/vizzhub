"""
Shared utilities for GitHub collectors.

This module contains common functions and constants used across multiple
GitHub collector modules to avoid duplication.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import structlog

from app.modules.scorecard.services.collectors.utils import parse_iso_datetime

logger = structlog.get_logger()

if TYPE_CHECKING:
    from app.modules.scorecard.services.collectors.github.client import GitHubClient

# Re-export for backwards compatibility
parse_github_datetime = parse_iso_datetime

TARGET_BRANCHES = frozenset({"dev", "develop", "main", "master", "development"})
MAX_CONCURRENT_REQUESTS = 20

# Default datetime for releases without a date (used for sorting)
_MIN_RELEASE_DATE = datetime.min.replace(tzinfo=UTC)


def _is_within_period(
    item_date: datetime | None,
    period_start: date | None,
    period_end: date | None,
) -> bool:
    """Check if a datetime falls within the specified period."""
    if not item_date:
        return True
    if period_start and item_date.date() < period_start:
        return False
    if period_end and item_date.date() > period_end:
        return False
    return True


def _extract_merged_date(pr: dict) -> datetime | None:
    """Extract and parse merged_at date from PR."""
    merged_at = pr.get("merged_at")
    if not merged_at:
        return None
    return parse_iso_datetime(merged_at)


def _extract_release_date(release: dict) -> datetime | None:
    """Extract and parse published/created date from release.

    Args:
        release: Release dict from GitHub API

    Returns:
        datetime object (timezone-aware) or None if no date found
    """
    date_str = release.get("published_at") or release.get("created_at")
    if not date_str:
        return None
    return parse_iso_datetime(date_str)


def _filter_merged_pr(
    pr: dict,
    period_start: date | None,
    period_end: date | None,
) -> dict | None:
    """Filter a single PR by merge date and period.

    Returns the PR if it passes filters, None otherwise.
    """
    merged_date = _extract_merged_date(pr)
    if not merged_date:
        return None
    if not _is_within_period(merged_date, period_start, period_end):
        return None
    return pr


async def _fetch_prs_page(
    http_client,
    owner: str,
    repo: str,
    page: int,
    per_page: int,
) -> list[dict] | None:
    """Fetch a single page of PRs.

    Returns None if the request fails.
    """
    try:
        response = await http_client.get(
            f"/repos/{owner}/{repo}/pulls",
            params={
                "state": "closed",
                "per_page": per_page,
                "page": page,
                "sort": "updated",
                "direction": "desc",
            },
        )
        if response.status_code != 200:
            return None
        return response.json()
    except Exception as e:
        logger.warning("prs_fetch_failed", owner=owner, repo=repo, page=page, error=str(e))
        return None


async def get_merged_prs(
    client: "GitHubClient",
    owner: str,
    repo: str,
    max_results: int = 100,
    period_start: date | None = None,
    period_end: date | None = None,
) -> list[dict]:
    """
    Get merged PRs from repository.

    Args:
        client: Authenticated GitHubClient instance
        owner: Repository owner
        repo: Repository name
        max_results: Maximum number of PRs to fetch
        period_start: Optional start date for punctual filtering (inclusive)
        period_end: Optional end date to filter PRs merged by this date

    Returns:
        List of merged PR dicts
    """
    http_client = await client.get_client()
    merged_prs: list[dict] = []
    page = 1
    per_page = 100

    while len(merged_prs) < max_results:
        prs = await _fetch_prs_page(http_client, owner, repo, page, per_page)
        if not prs:
            break

        for pr in prs:
            filtered = _filter_merged_pr(pr, period_start, period_end)
            if filtered:
                merged_prs.append(filtered)
                if len(merged_prs) >= max_results:
                    break

        if len(prs) < per_page:
            break

        page += 1

    return merged_prs


def filter_target_branch_prs(prs: list[dict]) -> list[dict]:
    """
    Filter PRs to only those merged to target branches.

    Args:
        prs: List of PR dicts

    Returns:
        Filtered list of PRs targeting main/dev branches
    """
    return [pr for pr in prs if (pr.get("base", {}).get("ref") or "").lower() in TARGET_BRANCHES]


def _filter_release(
    release: dict,
    include_prereleases: bool,
    include_drafts: bool,
    period_start: date | None,
    period_end: date | None,
) -> dict | None:
    """Filter a single release by draft/prerelease status and period.

    Returns the release if it passes filters, None otherwise.
    """
    if not include_drafts and release.get("draft"):
        return None
    if not include_prereleases and release.get("prerelease"):
        return None
    release_date = _extract_release_date(release)
    if not _is_within_period(release_date, period_start, period_end):
        return None
    return release


async def _fetch_releases_page(
    http_client,
    owner: str,
    repo: str,
    page: int,
    per_page: int,
) -> list[dict] | None:
    """Fetch a single page of releases.

    Returns None if the request fails.
    """
    try:
        response = await http_client.get(
            f"/repos/{owner}/{repo}/releases",
            params={
                "per_page": per_page,
                "page": page,
            },
        )
        if response.status_code != 200:
            return None
        return response.json()
    except Exception as e:
        logger.warning("releases_fetch_failed", owner=owner, repo=repo, page=page, error=str(e))
        return None


async def get_releases(
    client: "GitHubClient",
    owner: str,
    repo: str,
    include_prereleases: bool = True,
    include_drafts: bool = False,
    max_results: int = 200,
    period_start: date | None = None,
    period_end: date | None = None,
) -> list[dict]:
    """
    Get releases from repository with filtering options.

    Args:
        client: Authenticated GitHubClient instance
        owner: Repository owner
        repo: Repository name
        include_prereleases: Whether to include prerelease versions
        include_drafts: Whether to include draft releases
        max_results: Maximum number of releases to fetch
        period_start: Optional start date for punctual filtering (inclusive)
        period_end: Optional end date to filter releases published by this date

    Returns:
        List of release dicts
    """
    http_client = await client.get_client()
    releases: list[dict] = []
    page = 1
    per_page = 100

    while len(releases) < max_results:
        page_releases = await _fetch_releases_page(http_client, owner, repo, page, per_page)
        if not page_releases:
            break

        for release in page_releases:
            filtered = _filter_release(
                release, include_prereleases, include_drafts, period_start, period_end
            )
            if filtered:
                releases.append(filtered)
                if len(releases) >= max_results:
                    break

        if len(page_releases) < per_page:
            break

        page += 1

    return releases


def parse_release_date(release: dict) -> datetime:
    """
    Parse the release published date for sorting purposes.

    Falls back to created_at if published_at is not available.
    Returns a minimum datetime if no date found (for consistent sorting).

    Args:
        release: Release dict from GitHub API

    Returns:
        datetime object (timezone-aware), never None
    """
    return _extract_release_date(release) or _MIN_RELEASE_DATE
